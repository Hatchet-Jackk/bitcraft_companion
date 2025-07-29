import threading
import queue
import time
import logging


class DataService:
    """
    Manages the connection to the game client, handles data subscriptions,
    and passes data to the GUI via a thread-safe queue.
    """

    def __init__(self):
        # Import here to prevent circular dependencies
        from client import BitCraft
        from player import Player
        from claim import Claim
        from inventory_service import InventoryService
        from passive_crafting_service import PassiveCraftingService

        # Store the classes themselves
        self.BitCraftClass = BitCraft
        self.PlayerClass = Player
        self.ClaimClass = Claim
        self.InventoryServiceClass = InventoryService
        self.PassiveCraftingServiceClass = PassiveCraftingService

        # Instantiate the client immediately to load saved user data
        self.client = self.BitCraftClass()

        # These will be instantiated in the _run method after login
        self.player = None
        self.claim = None
        self.inventory_service = None
        self.passive_crafting_service = None

        self.data_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.service_thread = None

    def start(self, username, password, region, player_name):
        """Starts the data fetching thread with user credentials."""
        if self.service_thread and self.service_thread.is_alive():
            logging.warning("DataService is already running.")
            return

        self._stop_event.clear()
        self.service_thread = threading.Thread(target=self._run, args=(username, password, region, player_name), daemon=True)
        self.service_thread.start()

    def stop(self):
        """Signals the data fetching thread to stop."""
        logging.info("Stopping DataService...")
        self._stop_event.set()
        if self.client:
            self.client.close_websocket()
        if self.service_thread and self.service_thread.is_alive():
            self.service_thread.join()  # Wait for the thread to finish
        logging.info("DataService stopped.")

    def _run(self, username, password, region, player_name):
        """The main loop for the data service thread."""
        logging.info("[DataService] Thread started.")

        try:
            # 1. Authenticate
            if not self.client.authenticate(email=username, access_code=password):
                logging.error("[DataService] Authentication failed.")
                self.data_queue.put(
                    {"type": "connection_status", "data": {"status": "failed", "reason": "Authentication Failed"}}
                )
                return

            # 2. Configure and establish WebSocket connection
            self.client.set_region(region)
            self.client.set_endpoint("subscribe")
            self.client.set_websocket_uri()
            self.client.connect_websocket()

            self.data_queue.put({"type": "connection_status", "data": {"status": "connected"}})

            # 3. Load all required reference data before initializing dependent classes
            logging.info("Loading reference data...")
            reference_tables = [
                "resource_desc",
                "item_desc",
                "cargo_desc",
                "building_desc",
                "type_desc_ids",
                "building_types",
                "crafting_recipe_desc",
            ]
            reference_data = {table: self.client._load_reference_data(table) for table in reference_tables}

            # 4. Instantiate classes with correct dependencies
            self.player = self.PlayerClass(username=player_name)
            self.claim = self.ClaimClass(client=self.client, reference_data=reference_data)

            # 5. Fetch the Player's User ID
            user_id = self.client.fetch_user_id_by_username(player_name)
            if not user_id:
                logging.error(f"[DataService] Could not retrieve user ID for {player_name}.")
                self.data_queue.put({"type": "error", "data": f"Could not find player: {player_name}"})
                return
            self.player.user_id = user_id

            # 6. Use the user_id to get the Claim ID
            claim_id = self.claim.fetch_and_set_claim_id_by_user(user_id)
            if claim_id:
                # Fetch initial claim info
                claim_info = self.fetch_claim_info(claim_id)
                self.data_queue.put({"type": "claim_info_update", "data": claim_info})
                logging.info(f"Initial claim info sent to UI: {claim_info}")

            # 7. Initialize Services
            self.inventory_service = self.InventoryServiceClass(bitcraft_client=self.client, claim_instance=self.claim)
            self.passive_crafting_service = self.PassiveCraftingServiceClass(
                bitcraft_client=self.client, claim_instance=self.claim, reference_data=reference_data
            )

            # 8. PERFORM INITIAL DATA FETCHES BEFORE SUBSCRIBING
            # Initialize inventory data
            self.inventory_service.initialize_full_inventory()
            initial_inventory = self.claim.get_inventory()
            self.data_queue.put({"type": "inventory_update", "data": initial_inventory})
            logging.info("Initial inventory data has been sent to the UI.")

            # Initialize crafting data
            initial_crafting_data = self.passive_crafting_service.get_all_crafting_data()
            self.data_queue.put({"type": "crafting_update", "data": initial_crafting_data})
            logging.info("Initial crafting data has been sent to the UI.")

            # 9. BUILD AND START SUBSCRIPTIONS FOR LIVE UPDATES
            buildings_query = f"SELECT * FROM building_state WHERE claim_entity_id = '{claim_id}';"
            building_results = self.client.query(buildings_query)
            building_ids = [b["entity_id"] for b in building_results if "entity_id" in b] if building_results else []

            if building_ids:
                # Get subscription queries for both services
                inventory_queries = self.inventory_service.get_subscription_queries(building_ids)
                passive_crafting_queries = self.passive_crafting_service.get_subscription_queries(building_ids)

                # Combine all subscription queries
                all_subscriptions = inventory_queries + passive_crafting_queries

                # Add claim-level subscriptions
                if claim_id:
                    claim_subscription_queries = [
                        f"SELECT * FROM claim_local_state WHERE entity_id = '{claim_id}';",
                        f"SELECT * FROM claim_state WHERE entity_id = '{claim_id}';",
                    ]
                    all_subscriptions.extend(claim_subscription_queries)

                if all_subscriptions:
                    self.client.start_subscription_listener(all_subscriptions, self._handle_message)
                    logging.info(f"Started subscriptions for {len(all_subscriptions)} queries")
            else:
                logging.warning("No buildings found; skipping subscriptions.")

            # Keep the thread alive to listen for subscription updates
            while not self._stop_event.is_set():
                time.sleep(1)

        except Exception as e:
            logging.error(f"[DataService] An error occurred in the data thread: {e}", exc_info=True)
            self.data_queue.put({"type": "error", "data": f"A connection error occurred: {e}"})
        finally:
            if self.client:
                self.client.close_websocket()
            logging.info("[DataService] Thread stopped and connection closed.")

    def _handle_message(self, message):
        """Enhanced callback to process inventory, crafting, and claim info messages."""
        try:
            message_str = str(message)

            # Handle claim info updates
            if "claim_local_state" in message_str or "claim_state" in message_str:
                if self.claim and self.claim.claim_id:
                    updated_claim_info = self.fetch_claim_info(self.claim.claim_id)
                    self.data_queue.put({"type": "claim_info_update", "data": updated_claim_info})
                    logging.debug("Claim info updated via subscription")

            # Handle inventory updates
            if "inventory_state" in message_str or "building_state" in message_str:
                logging.debug("Processing inventory update from subscription...")
                self.inventory_service.initialize_full_inventory()
                fresh_inventory = self.claim.get_inventory()
                self.data_queue.put({"type": "inventory_update", "data": fresh_inventory})

            # Handle passive crafting updates
            if "passive_craft_state" in message_str:
                logging.debug("Processing crafting update from subscription...")
                if self.passive_crafting_service.parse_crafting_update(message):
                    fresh_crafting_data = self.passive_crafting_service.get_current_crafting_data_for_gui()
                    self.data_queue.put({"type": "crafting_update", "data": fresh_crafting_data})

        except Exception as e:
            logging.error(f"Error handling WebSocket message: {e}")

    def fetch_claim_info(self, claim_id):
        """
        Fetches comprehensive claim information including name, treasury, supplies, etc.

        Args:
            claim_id (str): The claim entity ID

        Returns:
            dict: Claim information ready for the UI
        """
        try:
            claim_info = {
                "name": "Unknown Claim",
                "treasury": 0,
                "supplies": 0,
                "supplies_per_hour": 0,
            }

            # Fetch claim local state (treasury, supplies, etc.)
            local_state_query = f"SELECT * FROM claim_local_state WHERE entity_id = '{claim_id}';"
            local_results = self.client.query(local_state_query)

            if local_results and len(local_results) > 0:
                local_data = local_results[0]
                claim_info["treasury"] = local_data.get("treasury", 0)
                claim_info["supplies"] = local_data.get("supplies", 0)

                # Extract building maintenance rate for supplies calculation
                building_maintenance = local_data.get("building_maintenance", 0.0)
                # Convert per-second rate to per-hour (approximate)
                claim_info["supplies_per_hour"] = building_maintenance * 3600 if building_maintenance > 0 else 0

                logging.debug(f"Claim local state: Treasury={claim_info['treasury']}, Supplies={claim_info['supplies']}")

            # Fetch claim state (name, owner, etc.)
            claim_state_query = f"SELECT * FROM claim_state WHERE entity_id = '{claim_id}';"
            state_results = self.client.query(claim_state_query)

            if state_results and len(state_results) > 0:
                state_data = state_results[0]
                claim_info["name"] = state_data.get("name", "Unknown Claim")
                logging.debug(f"Claim name: {claim_info['name']}")

            return claim_info

        except Exception as e:
            logging.error(f"Error fetching claim info: {e}")
            return {"name": "Error Loading", "treasury": 0, "supplies": 0, "supplies_per_hour": 0}
