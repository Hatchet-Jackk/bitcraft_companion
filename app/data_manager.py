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

    # In data_manager.py

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

            # --- FIX: Re-added the necessary client configuration calls ---
            # 2. Configure and establish WebSocket connection
            self.client.set_region(region)
            self.client.set_endpoint("subscribe")
            self.client.set_websocket_uri()
            self.client.connect_websocket()  # This will now succeed

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
            if not claim_id:
                logging.error("[DataService] Could not retrieve claim ID.")
                self.data_queue.put({"type": "error", "data": "Could not retrieve claim ID."})
                return
            logging.info(f"[DataService] Acquired Claim ID: {claim_id}")

            # 7. Initialize Services
            self.inventory_service = self.InventoryServiceClass(bitcraft_client=self.client, claim_instance=self.claim)
            self.passive_crafting_service = self.PassiveCraftingServiceClass(
                bitcraft_client=self.client, claim_instance=self.claim, reference_data=reference_data
            )

            # 8. PERFORM INITIAL DATA FETCHES BEFORE SUBSCRIBING
            self.inventory_service.initialize_full_inventory()
            initial_inventory = self.claim.get_inventory()
            self.data_queue.put({"type": "inventory_update", "data": initial_inventory})
            logging.info("Initial inventory data has been sent to the UI.")

            # 9. BUILD AND START SUBSCRIPTIONS FOR LIVE UPDATES
            buildings_query = f"SELECT entity_id FROM building_state WHERE claim_entity_id = '{claim_id}';"
            building_results = self.client.query(buildings_query)
            building_ids = [b["entity_id"] for b in building_results if "entity_id" in b] if building_results else []

            if building_ids:
                inventory_queries = self.inventory_service.get_subscription_queries(building_ids)
                passive_crafting_queries = self.passive_crafting_service.get_subscription_queries(building_ids)
                all_subscriptions = inventory_queries + passive_crafting_queries

                if all_subscriptions:
                    self.client.start_subscription_listener(all_subscriptions, self._handle_message)
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
        """Callback to process messages from the client's listener thread."""
        # The listener will now pass both the initial confirmation and subsequent updates here.
        if "InitialSubscription" in message or "SubscriptionUpdate" in message:
            logging.info("Processing data from subscription...")
            # Upon any relevant update, we re-run the full inventory consolidation.
            # This is a simple but effective strategy.
            self.inventory_service.initialize_full_inventory()
            fresh_inventory = self.claim.get_inventory()
            self.data_queue.put({"type": "inventory_update", "data": fresh_inventory})

        # Add similar logic for passive_crafting if needed
        # if self.passive_crafting_service.parse_crafting_message(db_update):
        #     ...
