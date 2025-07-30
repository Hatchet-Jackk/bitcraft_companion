import ast
import json
import threading
import queue
import time
import logging


class DataService:
    """
    Manages the connection to the game client, handles data subscriptions,
    and passes data to the GUI via a thread-safe queue.

    Simplified and focused on proper message parsing.
    """

    def __init__(self):
        # Import here to prevent circular dependencies
        from client import BitCraft
        from player import Player
        from claim import Claim
        from inventory_service import InventoryService
        from passive_crafting_service import PassiveCraftingService
        from traveler_tasks_service import TravelerTasksService

        # Store the classes themselves
        self.BitCraftClass = BitCraft
        self.PlayerClass = Player
        self.ClaimClass = Claim
        self.InventoryServiceClass = InventoryService
        self.PassiveCraftingServiceClass = PassiveCraftingService
        self.TravelerTasksServiceClass = TravelerTasksService

        # Instantiate the client immediately to load saved user data
        self.client = self.BitCraftClass()

        # These will be instantiated in the _run method after login
        self.player = None
        self.claim = None
        self.inventory_service = None
        self.passive_crafting_service = None
        self.traveler_tasks_service = None

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
        """Stop the data service and clean up resources."""
        logging.info("Stopping DataService...")

        try:
            # Set stop event first
            self._stop_event.set()

            # Stop the real-time timer with timeout
            if self.passive_crafting_service:
                logging.info("Stopping real-time timer...")
                self.passive_crafting_service.stop_real_time_timer()

            # Close WebSocket connection with timeout
            if self.client:
                logging.info("Closing WebSocket connection...")
                try:
                    self.client.close_websocket()
                except Exception as e:
                    logging.warning(f"Error closing WebSocket: {e}")

            # Wait for service thread to finish with timeout
            if self.service_thread and self.service_thread.is_alive():
                logging.info("Waiting for service thread to finish...")
                self.service_thread.join(timeout=2.0)  # 2 second timeout

                if self.service_thread.is_alive():
                    logging.warning("Service thread did not finish within timeout")
                else:
                    logging.info("Service thread finished cleanly")

        except Exception as e:
            logging.error(f"Error during DataService shutdown: {e}")
        finally:
            logging.info("DataService stopped.")

    def _run(self, username, password, region, player_name):
        """Main loop for the data service thread."""
        logging.info("[DataService] Thread started with enhanced message processing.")

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

            # 3. Load reference data
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
            # Note: NPC and task descriptions will be fetched live by TravelerTasksService

            # 4. Initialize services
            self.player = self.PlayerClass(username=player_name)
            self.claim = self.ClaimClass(client=self.client, reference_data=reference_data)

            # 5. Get user and claim IDs
            user_id = self.client.fetch_user_id_by_username(player_name)
            if not user_id:
                logging.error(f"[DataService] Could not retrieve user ID for {player_name}.")
                self.data_queue.put({"type": "error", "data": f"Could not find player: {player_name}"})
                return
            self.player.user_id = user_id

            claim_id = self.claim.fetch_and_set_claim_id_by_user(user_id)
            if claim_id:
                claim_info = self.fetch_claim_info(claim_id)
                self.data_queue.put({"type": "claim_info_update", "data": claim_info})

            # 6. Initialize services
            self.inventory_service = self.InventoryServiceClass(bitcraft_client=self.client, claim_instance=self.claim)
            self.passive_crafting_service = self.PassiveCraftingServiceClass(
                bitcraft_client=self.client, claim_instance=self.claim, reference_data=reference_data
            )
            self.traveler_tasks_service = self.TravelerTasksServiceClass(
                bitcraft_client=self.client, player_instance=self.player, reference_data=reference_data
            )

            # 7. Initial data loads
            self.inventory_service.initialize_full_inventory()
            initial_inventory = self.claim.get_inventory()
            self.data_queue.put({"type": "inventory_update", "data": initial_inventory})

            initial_crafting_data = self.passive_crafting_service.get_all_crafting_data_enhanced()
            self.data_queue.put(
                {
                    "type": "crafting_update",
                    "data": initial_crafting_data,
                    "changes": {"initial_load": True},
                    "timestamp": time.time(),
                }
            )

            initial_tasks_data = self.traveler_tasks_service.get_all_tasks_data_grouped()
            self.data_queue.put(
                {
                    "type": "tasks_update",
                    "data": initial_tasks_data,
                    "changes": {"initial_load": True},
                    "timestamp": time.time(),
                }
            )

            # Start real-time timer
            self.passive_crafting_service.start_real_time_timer(self._handle_timer_update)

            # 8. Set up subscriptions
            buildings_query = f"SELECT * FROM building_state WHERE claim_entity_id = '{claim_id}';"
            building_results = self.client.query(buildings_query)
            building_ids = [b["entity_id"] for b in building_results if "entity_id" in b] if building_results else []

            all_subscriptions = []

            if building_ids:
                inventory_queries = self.inventory_service.get_subscription_queries(building_ids)
                passive_crafting_queries = self.passive_crafting_service.get_subscription_queries(building_ids)
                all_subscriptions.extend(inventory_queries)
                all_subscriptions.extend(passive_crafting_queries)

            # Add task subscriptions
            task_queries = self.traveler_tasks_service.get_subscription_queries()
            all_subscriptions.extend(task_queries)

            if claim_id:
                claim_queries = [
                    f"SELECT * FROM claim_local_state WHERE entity_id = '{claim_id}';",
                    f"SELECT * FROM claim_state WHERE entity_id = '{claim_id}';",
                ]
                all_subscriptions.extend(claim_queries)

            if all_subscriptions:
                self.client.start_subscription_listener(all_subscriptions, self._handle_message)
                logging.info(f"Started subscriptions for {len(all_subscriptions)} queries")

            # Keep thread alive
            while not self._stop_event.is_set():
                time.sleep(1)

        except Exception as e:
            logging.error(f"[DataService] Error in data thread: {e}", exc_info=True)
            self.data_queue.put({"type": "error", "data": f"Connection error: {e}"})
        finally:
            if self.passive_crafting_service:
                self.passive_crafting_service.stop_real_time_timer()
            if self.client:
                self.client.close_websocket()
            logging.info("[DataService] Thread stopped and connection closed.")

    def _handle_timer_update(self, timer_data):
        """Handle real-time timer updates from the crafting service"""
        try:
            self.data_queue.put(timer_data)
            logging.debug("Real-time timer update sent to UI")
        except Exception as e:
            logging.error(f"Error handling timer update: {e}")

    def _handle_message(self, message):
        """
        Main message handler - routes all SpacetimeDB message types.
        """
        try:
            if "TransactionUpdate" in message:
                self._process_transaction_update(message["TransactionUpdate"])
            elif "SubscriptionUpdate" in message:
                self._process_subscription_update(message["SubscriptionUpdate"])
            elif "InitialSubscription" in message:
                self._process_initial_subscription(message["InitialSubscription"])
            else:
                logging.debug(f"Unknown message type: {list(message.keys())}")

        except Exception as e:
            logging.error(f"Error in message handler: {e}")

    def _process_transaction_update(self, transaction_data):
        """
        Process TransactionUpdate messages - LIVE real-time updates.
        """
        try:
            status = transaction_data.get("status", {})
            reducer_call = transaction_data.get("reducer_call", {})

            # Check if transaction was successful
            if "Committed" not in status:
                return

            reducer_name = reducer_call.get("reducer_name", "unknown")
            timestamp_micros = transaction_data.get("timestamp", {}).get("__timestamp_micros_since_unix_epoch__", 0)
            timestamp_seconds = timestamp_micros / 1_000_000 if timestamp_micros else 0

            logging.info(f"LIVE TRANSACTION: {reducer_name}")

            # Process table updates
            tables = status.get("Committed", {}).get("tables", [])
            for table_update in tables:
                table_name = table_update.get("table_name", "")

                if table_name == "passive_craft_state":
                    self._handle_crafting_transaction(table_update, reducer_name, timestamp_seconds)
                elif table_name == "inventory_state":
                    self._handle_inventory_transaction(table_update, reducer_name, timestamp_seconds)
                elif table_name in ["claim_local_state", "claim_state"]:
                    self._handle_claim_transaction(table_update, reducer_name, timestamp_seconds)
                elif table_name == "traveler_task_state":  # FIX: ADD TASKS HANDLING
                    self._handle_tasks_transaction(table_update, reducer_name, timestamp_seconds)

        except Exception as e:
            logging.error(f"Error processing transaction update: {e}")

    def _process_subscription_update(self, subscription_data):
        """
        Process SubscriptionUpdate messages - batch updates.
        """
        try:
            database_update = subscription_data.get("database_update", {})
            tables = database_update.get("tables", [])

            logging.info(f"Processing SubscriptionUpdate with {len(tables)} table updates")

            needs_inventory_update = False
            needs_crafting_update = False
            needs_claim_update = False
            needs_tasks_update = False

            for table_update in tables:
                table_name = table_update.get("table_name", "")

                if table_name == "inventory_state":
                    needs_inventory_update = True
                elif table_name == "passive_craft_state":
                    needs_crafting_update = True
                elif table_name in ["claim_local_state", "claim_state"]:
                    needs_claim_update = True
                elif table_name == "traveler_task_state":  # FIX: ADD TASKS HANDLING
                    needs_tasks_update = True

            # Send consolidated updates
            if needs_inventory_update:
                self._refresh_inventory()
            if needs_crafting_update:
                self._refresh_crafting()
            if needs_claim_update:
                self._refresh_claim_info()
            if needs_tasks_update:  # FIX: ADD TASKS REFRESH
                self._refresh_tasks()

        except Exception as e:
            logging.error(f"Error processing subscription update: {e}")

    def _process_initial_subscription(self, initial_data):
        """Process InitialSubscription data."""
        logging.info("Received InitialSubscription - current game state snapshot")

    def _handle_crafting_transaction(self, table_update, reducer_name, timestamp):
        """
        Handle passive_craft_state transactions with proper parsing.
        """
        try:
            updates = table_update.get("updates", [])

            for update in updates:
                deletes = update.get("deletes", [])
                inserts = update.get("inserts", [])

                # Process deletions (usually collections)
                for delete_str in deletes:
                    crafting_data = self._parse_crafting_data(delete_str)
                    if crafting_data:
                        self._log_crafting_action("COLLECTED", crafting_data, reducer_name)

                # Process insertions (new crafting operations)
                for insert_str in inserts:
                    crafting_data = self._parse_crafting_data(insert_str)
                    if crafting_data:
                        self._log_crafting_action("STARTED", crafting_data, reducer_name)

                # Refresh crafting data if any changes
                if deletes or inserts:
                    self._refresh_crafting()

        except Exception as e:
            logging.error(f"Error handling crafting transaction: {e}")

    def _handle_tasks_transaction(self, table_update, reducer_name, timestamp):
        """Handle traveler_task_state transactions."""
        try:
            updates = table_update.get("updates", [])

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                if inserts or deletes:
                    logging.info(f"TASK UPDATE: {len(inserts)} inserts, {len(deletes)} deletes - {reducer_name}")

                    # Check for task completions in inserts
                    for insert_str in inserts:
                        try:
                            task_data = ast.literal_eval(insert_str)
                            if isinstance(task_data, list) and len(task_data) >= 4:
                                completed = task_data[3] if len(task_data) > 3 else False
                                if completed:
                                    logging.info(f"🎉 Task completed! {reducer_name}")
                        except Exception as e:
                            logging.debug(f"Error parsing task insert: {e}")

                    self._refresh_tasks()

        except Exception as e:
            logging.error(f"Error handling tasks transaction: {e}")

    def _parse_crafting_data(self, data_str):
        """
        Parse crafting data from the SpacetimeDB format.
        Format: [entity_id, owner_id, recipe_id, building_id, [timestamp], [status], [slot]]
        """
        try:
            data = ast.literal_eval(data_str)
            if not isinstance(data, list) or len(data) < 7:
                return None

            return {
                "entity_id": data[0],
                "owner_entity_id": data[1],
                "recipe_id": data[2],
                "building_entity_id": data[3],
                "timestamp_micros": data[4][0] if data[4] and len(data[4]) > 0 else None,
                "status": data[5] if len(data[5]) > 0 else [0, {}],
                "slot": data[6],
            }
        except Exception as e:
            logging.debug(f"Error parsing crafting data: {e}")
            return None

    def _log_crafting_action(self, action, crafting_data, reducer_name):
        """Log crafting actions with meaningful information."""
        try:
            recipe_id = crafting_data["recipe_id"]
            building_id = crafting_data["building_entity_id"]
            status = crafting_data["status"]

            # Get recipe name if available
            recipe_name = f"Recipe {recipe_id}"
            if self.passive_crafting_service and hasattr(self.passive_crafting_service, "crafting_recipes"):
                recipe_info = self.passive_crafting_service.crafting_recipes.get(recipe_id, {})
                recipe_name = recipe_info.get("name", recipe_name)
                recipe_name = recipe_name.replace("{0}", "").strip()

            # Get building name if available
            building_name = f"Building {building_id}"
            if self.claim and self.claim.buildings:
                for category, buildings in self.claim.buildings.items():
                    for building in buildings:
                        if building.get("entity_id") == building_id:
                            building_name = building.get("nickname") or building.get("name", building_name)
                            break

            status_code = status[0] if status and len(status) > 0 else 0
            status_text = "READY" if status_code == 2 else "IN_PROGRESS" if status_code == 1 else "UNKNOWN"

            logging.debug(f"{action}: {recipe_name} in {building_name} (Status: {status_text}) - {reducer_name}")

        except Exception as e:
            logging.debug(f"Error logging crafting action: {e}")

    def _handle_inventory_transaction(self, table_update, reducer_name, timestamp):
        """Handle inventory_state transactions."""
        try:
            updates = table_update.get("updates", [])
            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                if inserts or deletes:
                    logging.debug(f"INVENTORY UPDATE: {len(inserts)} inserts, {len(deletes)} deletes - {reducer_name}")
                    self._refresh_inventory()

        except Exception as e:
            logging.error(f"Error handling inventory transaction: {e}")

    def _handle_claim_transaction(self, table_update, reducer_name, timestamp):
        """Handle claim state transactions."""
        try:
            updates = table_update.get("updates", [])
            for update in updates:
                inserts = update.get("inserts", [])
                if inserts:
                    logging.debug(f"CLAIM UPDATE - {reducer_name}")
                    self._refresh_claim_info()

        except Exception as e:
            logging.error(f"Error handling claim transaction: {e}")

    def _refresh_inventory(self):
        """Refresh and send inventory data to UI."""
        try:
            if self.inventory_service:
                self.inventory_service.initialize_full_inventory()
                fresh_inventory = self.claim.get_inventory()
                self.data_queue.put(
                    {"type": "inventory_update", "data": fresh_inventory, "source": "live_update", "timestamp": time.time()}
                )
                logging.info(f"Sent inventory update: {len(fresh_inventory)} item types")
        except Exception as e:
            logging.error(f"Error refreshing inventory: {e}")

    def _refresh_crafting(self):
        """Refresh and send crafting data to UI."""
        try:
            if self.passive_crafting_service:
                fresh_crafting_data = self.passive_crafting_service.get_all_crafting_data_enhanced()
                self.data_queue.put(
                    {"type": "crafting_update", "data": fresh_crafting_data, "source": "live_update", "timestamp": time.time()}
                )
                logging.info(f"Sent crafting update: {len(fresh_crafting_data)} operations")
        except Exception as e:
            logging.error(f"Error refreshing crafting: {e}")

    def _refresh_tasks(self):
        """Refresh and send tasks data to UI."""
        try:
            if self.traveler_tasks_service:
                # Get old data for completion detection
                old_data = self.traveler_tasks_service.get_current_tasks_data_for_gui()

                # Get fresh data
                fresh_tasks_data = self.traveler_tasks_service.get_all_tasks_data_grouped()

                # Detect completions for notifications
                completed_tasks = self.traveler_tasks_service.detect_task_completions(old_data, fresh_tasks_data)

                # Send update to UI
                changes = {"completed_tasks": completed_tasks} if completed_tasks else {}
                self.data_queue.put(
                    {
                        "type": "tasks_update",
                        "data": fresh_tasks_data,
                        "changes": changes,
                        "source": "live_update",
                        "timestamp": time.time(),
                    }
                )
                logging.info(f"Sent tasks update: {len(fresh_tasks_data)} traveler groups")

                # Log completions
                if completed_tasks:
                    for task in completed_tasks:
                        logging.info(f"🎉 Task completed: {task['task_description']} for {task['traveler_name']}")

        except Exception as e:
            logging.error(f"Error refreshing tasks: {e}")

    def _refresh_claim_info(self):
        """Refresh and send claim info to UI."""
        try:
            if self.claim and self.claim.claim_id:
                fresh_claim_info = self.fetch_claim_info(self.claim.claim_id)
                self.data_queue.put(
                    {"type": "claim_info_update", "data": fresh_claim_info, "source": "live_update", "timestamp": time.time()}
                )
                logging.info("Sent claim info update")
        except Exception as e:
            logging.error(f"Error refreshing claim info: {e}")

    def fetch_claim_info(self, claim_id):
        """Fetch comprehensive claim information."""
        try:
            claim_info = {
                "name": "Unknown Claim",
                "treasury": 0,
                "supplies": 0,
                "supplies_per_hour": 0,
            }

            # Fetch claim local state
            local_state_query = f"SELECT * FROM claim_local_state WHERE entity_id = '{claim_id}';"
            local_results = self.client.query(local_state_query)

            if local_results and len(local_results) > 0:
                local_data = local_results[0]
                claim_info["treasury"] = local_data.get("treasury", 0)
                claim_info["supplies"] = local_data.get("supplies", 0)
                building_maintenance = local_data.get("building_maintenance", 0.0)
                claim_info["supplies_per_hour"] = building_maintenance * 3600 if building_maintenance > 0 else 0

            # Fetch claim state
            claim_state_query = f"SELECT * FROM claim_state WHERE entity_id = '{claim_id}';"
            state_results = self.client.query(claim_state_query)

            if state_results and len(state_results) > 0:
                state_data = state_results[0]
                claim_info["name"] = state_data.get("name", "Unknown Claim")

            return claim_info

        except Exception as e:
            logging.error(f"Error fetching claim info: {e}")
            return {"name": "Error Loading", "treasury": 0, "supplies": 0, "supplies_per_hour": 0}
