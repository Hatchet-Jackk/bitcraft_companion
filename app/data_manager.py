import ast
import threading
import queue
import time
import logging
from claim_manager import ClaimManager


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
        from active_crafting_service import ActiveCraftingService

        # Store the classes themselves
        self.BitCraftClass = BitCraft
        self.PlayerClass = Player
        self.ClaimClass = Claim
        self.InventoryServiceClass = InventoryService
        self.PassiveCraftingServiceClass = PassiveCraftingService
        self.TravelerTasksServiceClass = TravelerTasksService
        self.ActiveCraftingServiceClass = ActiveCraftingService

        # Instantiate the client immediately to load saved user data
        self.client = self.BitCraftClass()

        # These will be instantiated in the _run method after login
        self.player = None
        self.claim = None
        self.inventory_service = None
        self.passive_crafting_service = None
        self.traveler_tasks_service = None
        self.active_crafting_service = None
        self.claim_manager = None
        self.current_subscriptions = []

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

            if self.active_crafting_service:
                logging.info("Stopping active crafting progress tracking...")
                self.active_crafting_service.stop_progress_tracking()

            # Save final claim state to cache
            if self.claim_manager:
                logging.info("Saving claims cache...")
                self.claim_manager._save_claims_cache()

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
                "claim_tile_cost",
            ]
            reference_data = {table: self.client._load_reference_data(table) for table in reference_tables}

            # 4. Initialize services
            self.player = self.PlayerClass(username=player_name)
            self.claim = self.ClaimClass(client=self.client, reference_data=reference_data)

            # 5. Get user ID
            user_id = self.client.fetch_user_id_by_username(player_name)
            if not user_id:
                logging.error(f"[DataService] Could not retrieve user ID for {player_name}.")
                self.data_queue.put({"type": "error", "data": f"Could not find player: {player_name}"})
                return
            self.player.user_id = user_id

            # 6. UPDATED: Initialize claim manager and get all claims
            self.claim_manager = ClaimManager(self.client)

            # Fetch all claims for the user
            all_claims = self.claim.fetch_all_claim_ids_by_user(user_id)
            if not all_claims:
                logging.error(f"[DataService] No claims found for user {player_name}.")
                self.data_queue.put({"type": "error", "data": f"No claims found for player: {player_name}"})
                return

            # Set up claim manager with all claims
            self.claim_manager.set_available_claims(all_claims)

            # Send claims list to UI
            self.data_queue.put(
                {
                    "type": "claims_list_update",
                    "data": {"claims": all_claims, "current_claim_id": self.claim_manager.get_current_claim_id()},
                }
            )

            # Switch to the default/last selected claim
            default_claim_id = self.claim_manager.get_current_claim_id()
            if not self.claim.switch_to_claim(default_claim_id):
                logging.error(f"[DataService] Could not switch to default claim {default_claim_id}.")
                self.data_queue.put({"type": "error", "data": f"Could not access default claim"})
                return

            # Get initial claim info
            claim_info = self.claim.refresh_claim_info()
            self.data_queue.put({"type": "claim_info_update", "data": claim_info})

            # 7. Initialize other services AFTER claim is set
            self.inventory_service = self.InventoryServiceClass(bitcraft_client=self.client, claim_instance=self.claim)
            self.passive_crafting_service = self.PassiveCraftingServiceClass(
                bitcraft_client=self.client,
                claim_instance=self.claim,
                reference_data=reference_data,
            )
            self.traveler_tasks_service = self.TravelerTasksServiceClass(
                bitcraft_client=self.client,
                player_instance=self.player,
                reference_data=reference_data,
            )
            self.active_crafting_service = self.ActiveCraftingServiceClass(
                bitcraft_client=self.client,
                claim_instance=self.claim,
                reference_data=reference_data,
            )

            # 8. Initial data loads
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

            initial_active_crafting_data = self.active_crafting_service.get_all_active_crafting_data_enhanced()
            self.data_queue.put({"type": "active_crafting_update", "data": initial_active_crafting_data})

            # Start real-time timer
            self.passive_crafting_service.start_real_time_timer(self._handle_timer_update)
            self.active_crafting_service.start_progress_tracking(self._handle_timer_update)

            # 9. Set up subscriptions for the current claim
            self._setup_subscriptions_for_current_claim()

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
        """Process TransactionUpdate messages - LIVE real-time updates."""
        try:
            status = transaction_data.get("status", {})
            reducer_call = transaction_data.get("reducer_call", {})

            # Check if transaction was successful
            if "Committed" not in status:
                return

            reducer_name = reducer_call.get("reducer_name", "unknown")
            timestamp_micros = transaction_data.get("timestamp", {}).get("__timestamp_micros_since_unix_epoch__", 0)
            timestamp_seconds = timestamp_micros / 1_000_000 if timestamp_micros else 0

            logging.debug(f"LIVE TRANSACTION: {reducer_name}")

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
                elif table_name == "traveler_task_state":
                    self._handle_tasks_transaction(table_update, reducer_name, timestamp_seconds)
                elif table_name == "progressive_action_state":  # NEW: Handle progressive actions
                    self._handle_progressive_action_transaction(table_update, reducer_name, timestamp_seconds)

        except Exception as e:
            logging.error(f"Error processing transaction update: {e}")

    def _process_subscription_update(self, subscription_data):
        """Process SubscriptionUpdate messages - batch updates."""
        try:
            database_update = subscription_data.get("database_update", {})
            tables = database_update.get("tables", [])

            logging.info(f"Processing SubscriptionUpdate with {len(tables)} table updates")

            needs_inventory_update = False
            needs_crafting_update = False
            needs_claim_update = False
            needs_tasks_update = False
            needs_active_crafting_update = False

            for table_update in tables:
                table_name = table_update.get("table_name", "")

                if table_name == "inventory_state":
                    needs_inventory_update = True
                elif table_name == "passive_craft_state":
                    needs_crafting_update = True
                elif table_name in ["claim_local_state", "claim_state"]:
                    needs_claim_update = True
                elif table_name == "traveler_task_state":
                    needs_tasks_update = True
                elif table_name == "progressive_action_state":  # NEW: Handle progressive actions
                    needs_active_crafting_update = True

            # Send consolidated updates
            if needs_inventory_update:
                self._refresh_inventory()
            if needs_crafting_update:
                self._refresh_crafting()
            if needs_claim_update:
                self._refresh_claim_info()
            if needs_tasks_update:
                self._refresh_tasks()
            if needs_active_crafting_update:
                self._refresh_active_crafting()

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
                logging.debug("Sent claim info update")
        except Exception as e:
            logging.error(f"Error refreshing claim info: {e}")

    def fetch_claim_info(self, claim_id):
        """Fetch comprehensive claim information including tile count."""
        try:
            claim_info = {
                "name": "Unknown Claim",
                "treasury": 0,
                "supplies": 0,
                "tile_count": 0,  # NEW: Add tile count
                "supplies_per_hour": 0,
            }

            # Fetch claim local state
            local_state_query = f"SELECT * FROM claim_local_state WHERE entity_id = '{claim_id}';"
            local_results = self.client.query(local_state_query)

            if local_results and len(local_results) > 0:
                local_data = local_results[0]
                claim_info["treasury"] = local_data.get("treasury", 0)
                claim_info["supplies"] = local_data.get("supplies", 0)
                num_tiles = local_data.get("num_tiles", 0)
                claim_info["tile_count"] = num_tiles
                claim_tile_cost = self.client._load_reference_data("claim_tile_cost")
                # supplies_per_hour will be calculated in the UI using claim_tile_cost and tile_count only
                claim_info["supplies_per_hour"] = 0

            # Fetch claim state for name
            claim_state_query = f"SELECT * FROM claim_state WHERE entity_id = '{claim_id}';"
            state_results = self.client.query(claim_state_query)

            if state_results and len(state_results) > 0:
                state_data = state_results[0]
                claim_info["name"] = state_data.get("name", "Unknown Claim")

            # If we didn't get tile count from size, try to calculate from coordinates
            if claim_info["tile_count"] == 0:
                try:
                    # Try to get tile count from claim coordinates
                    coord_query = f"SELECT * FROM claim_coordinate_state WHERE claim_entity_id = '{claim_id}';"
                    coord_results = self.client.query(coord_query)

                    if coord_results:
                        claim_info["tile_count"] = len(coord_results)
                        logging.info(f"Calculated tile count from coordinates: {claim_info['tile_count']} tiles")
                except Exception as e:
                    logging.warning(f"Could not calculate tile count from coordinates: {e}")

            logging.debug(f"Fetched claim info: {claim_info}")
            return claim_info

        except Exception as e:
            logging.error(f"Error fetching claim info: {e}")
            return {"name": "Error Loading", "treasury": 0, "supplies": 0, "tile_count": 0, "supplies_per_hour": 0}

    def switch_claim(self, new_claim_id: str):
        """
        Switches to a different claim. This method is called from the UI.

        Args:
            new_claim_id: The claim ID to switch to
        """
        if not self.claim_manager or not self.client:
            logging.error("Cannot switch claims - claim manager or client not initialized")
            return

        # Find the claim details
        target_claim = self.claim_manager.get_claim_by_id(new_claim_id)
        if not target_claim:
            logging.error(f"Cannot find claim {new_claim_id} in available claims")
            self.data_queue.put({"type": "error", "data": f"Claim not found: {new_claim_id}"})
            return

        # Start the switch process in a background thread
        import threading

        switch_thread = threading.Thread(
            target=self._perform_claim_switch, args=(new_claim_id, target_claim["claim_name"]), daemon=True
        )
        switch_thread.start()

    def _perform_claim_switch(self, new_claim_id: str, claim_name: str):
        """
        Performs the actual claim switching process in a background thread.

        Args:
            new_claim_id: The claim ID to switch to
            claim_name: The claim name for UI feedback
        """
        try:
            logging.info(f"Starting claim switch to: {claim_name} ({new_claim_id})")

            # Notify UI that switching has started
            self.data_queue.put(
                {
                    "type": "claim_switching",
                    "data": {"status": "loading", "claim_name": claim_name, "message": f"Switching to {claim_name}..."},
                }
            )

            # Clear any pending messages to prevent confusion
            self._handle_message_queue_during_switch()

            # Step 1: Stop subscriptions temporarily to avoid threading conflicts during queries
            logging.info("Temporarily stopping subscriptions for claim switch...")
            if self.client and self.client.ws_connection:
                self.client.stop_subscriptions()

            # Step 2: Stop real-time timer
            if self.passive_crafting_service:
                logging.info("Stopping real-time timer for claim switch")
                self.passive_crafting_service.stop_real_time_timer()

            # Step 3: Switch claim in claim manager
            logging.info("Updating claim manager...")
            if not self.claim_manager.switch_to_claim(new_claim_id):
                raise Exception(f"Failed to switch to claim {new_claim_id} in claim manager")

            # Step 4: Switch claim in claim instance
            logging.info("Switching claim instance...")
            if not self.claim.switch_to_claim(new_claim_id):
                raise Exception(f"Failed to switch claim instance to {new_claim_id}")

            # Step 5: Re-initialize services with new claim data
            logging.info("Re-initializing services for new claim...")

            # Update UI with progress
            self.data_queue.put(
                {
                    "type": "claim_switching",
                    "data": {"status": "loading", "claim_name": claim_name, "message": f"Loading {claim_name} data..."},
                }
            )

            # Refresh claim info first
            claim_info = self.claim.refresh_claim_info()
            self.data_queue.put({"type": "claim_info_update", "data": claim_info})

            # Re-initialize inventory
            self.inventory_service.initialize_full_inventory()
            fresh_inventory = self.claim.get_inventory()
            self.data_queue.put({"type": "inventory_update", "data": fresh_inventory, "source": "claim_switch"})

            # Re-initialize crafting data
            fresh_crafting_data = self.passive_crafting_service.get_all_crafting_data_enhanced()
            self.data_queue.put({"type": "crafting_update", "data": fresh_crafting_data, "source": "claim_switch"})

            # Re-initialize active crafting data
            fresh_active_crafting_data = self.active_crafting_service.get_all_active_crafting_data_enhanced()
            self.data_queue.put({"type": "active_crafting_update", "data": fresh_active_crafting_data, "source": "claim_switch"})

            # Re-initialize tasks data
            fresh_tasks_data = self.traveler_tasks_service.get_all_tasks_data_grouped()
            self.data_queue.put({"type": "tasks_update", "data": fresh_tasks_data, "source": "claim_switch"})

            # Step 6: Set up new subscriptions
            logging.info("Setting up new subscriptions...")
            self._setup_subscriptions_for_current_claim()

            # Step 7: Restart real-time timer
            if self.passive_crafting_service:
                logging.info("Restarting real-time timer...")
                self.passive_crafting_service.start_real_time_timer(self._handle_timer_update)

            if self.active_crafting_service:
                logging.info("Restarting active crafting progress tracking...")
                self.active_crafting_service.start_progress_tracking(self._handle_timer_update)

            # Step 8: Update claim manager cache
            self.claim_manager.update_claim_cache(new_claim_id, claim_info)

            # Step 9: Notify UI that switch is complete
            self.data_queue.put(
                {
                    "type": "claim_switched",
                    "data": {"status": "success", "claim_id": new_claim_id, "claim_name": claim_name, "claim_info": claim_info},
                }
            )

            logging.info(f"Successfully switched to claim: {claim_name}")

        except Exception as e:
            logging.error(f"Error during claim switch: {e}")
            self.data_queue.put({"type": "error", "data": f"Failed to switch to {claim_name}: {str(e)}"})

            # Try to recover by restarting services for current claim
            try:
                logging.info("Attempting to recover from claim switch error...")
                self._setup_subscriptions_for_current_claim()
                if self.passive_crafting_service:
                    self.passive_crafting_service.start_real_time_timer(self._handle_timer_update)
                logging.info("Recovery successful")
            except Exception as recovery_error:
                logging.error(f"Failed to recover after claim switch error: {recovery_error}")

    def _setup_subscriptions_for_current_claim(self):
        """Sets up subscriptions for the currently active claim."""
        try:
            if not self.claim.claim_id:
                logging.warning("No claim ID available for subscriptions")
                return

            # Get buildings for the current claim
            buildings_query = f"SELECT * FROM building_state WHERE claim_entity_id = '{self.claim.claim_id}';"
            building_results = self.client.query(buildings_query)
            building_ids = [b["entity_id"] for b in building_results if "entity_id" in b] if building_results else []

            all_subscriptions = []

            # Add inventory and crafting subscriptions if we have buildings
            if building_ids:
                inventory_queries = self.inventory_service.get_subscription_queries(building_ids)
                passive_crafting_queries = self.passive_crafting_service.get_subscription_queries(building_ids)
                active_crafting_queries = self.active_crafting_service.get_subscription_queries(building_ids)
                all_subscriptions.extend(inventory_queries)
                all_subscriptions.extend(passive_crafting_queries)
                all_subscriptions.extend(active_crafting_queries)

            # Add task subscriptions (player-specific, not claim-specific)
            task_queries = self.traveler_tasks_service.get_subscription_queries()
            all_subscriptions.extend(task_queries)

            # Add claim-specific subscriptions
            claim_queries = [
                f"SELECT * FROM claim_local_state WHERE entity_id = '{self.claim.claim_id}';",
                f"SELECT * FROM claim_state WHERE entity_id = '{self.claim.claim_id}';",
            ]
            all_subscriptions.extend(claim_queries)

            # Start subscriptions
            if all_subscriptions:
                self.client.start_subscription_listener(all_subscriptions, self._handle_message)
                self.current_subscriptions = all_subscriptions
                logging.info(f"Started {len(all_subscriptions)} subscriptions for claim {self.claim.claim_id}")

        except Exception as e:
            logging.error(f"Error setting up subscriptions: {e}")

    def get_current_claim_info(self) -> dict:
        """Returns current claim information for UI updates."""
        if self.claim_manager and self.claim:
            current_claim = self.claim_manager.get_current_claim()
            if current_claim:
                return {
                    "claim_id": current_claim["claim_id"],
                    "claim_name": current_claim["claim_name"],
                    "treasury": self.claim.treasury,
                    "supplies": self.claim.supplies,
                    "tile_count": self.claim.size,
                    "available_claims": self.claim_manager.get_all_claims(),
                }
        return {}

    def stop_updated(self):
        """Updated stop method with claim manager cleanup."""
        logging.info("Stopping DataService...")

        try:
            # Set stop event first
            self._stop_event.set()

            # Stop the real-time timer with timeout
            if self.passive_crafting_service:
                logging.info("Stopping real-time timer...")
                self.passive_crafting_service.stop_real_time_timer()

            # Save final claim state to cache
            if self.claim_manager:
                logging.info("Saving claims cache...")
                self.claim_manager._save_claims_cache()

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
                self.service_thread.join(timeout=2.0)

                if self.service_thread.is_alive():
                    logging.warning("Service thread did not finish within timeout")
                else:
                    logging.info("Service thread finished cleanly")

        except Exception as e:
            logging.error(f"Error during DataService shutdown: {e}")
        finally:
            logging.info("DataService stopped.")

    def _handle_message_queue_during_switch(self):
        """Process any pending messages during claim switch to prevent UI freezing."""
        try:
            # Process up to 10 pending messages to keep UI responsive
            for _ in range(10):
                if not self.data_queue.empty():
                    # Don't actually process, just clear old messages
                    try:
                        self.data_queue.get_nowait()
                    except queue.Empty:
                        break
                else:
                    break
        except Exception as e:
            logging.debug(f"Error clearing message queue: {e}")

    def _handle_active_crafting_transaction(self, table_update, reducer_name, timestamp):
        """Handle active_craft_state transactions."""
        try:
            updates = table_update.get("updates", [])

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                if inserts or deletes:
                    logging.debug(f"ACTIVE CRAFTING UPDATE: {len(inserts)} inserts, {len(deletes)} deletes - {reducer_name}")
                    self._refresh_active_crafting()

        except Exception as e:
            logging.error(f"Error handling active crafting transaction: {e}")

    def _refresh_active_crafting(self):
        """Refresh and send active crafting data to UI."""
        try:
            if self.active_crafting_service:
                fresh_active_crafting_data = self.active_crafting_service.get_all_active_crafting_data_enhanced()
                self.data_queue.put(
                    {
                        "type": "active_crafting_update",
                        "data": fresh_active_crafting_data,
                        "source": "live_update",
                        "timestamp": time.time(),
                    }
                )
                logging.debug(f"Sent active crafting update: {len(fresh_active_crafting_data)} operations")
        except Exception as e:
            logging.error(f"Error refreshing active crafting: {e}")

    def _handle_progressive_action_transaction(self, table_update, reducer_name, timestamp):
        """Handle progressive_action_state transactions (active crafting)."""
        try:
            updates = table_update.get("updates", [])

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                if inserts or deletes:
                    logging.debug(f"PROGRESSIVE ACTION UPDATE: {len(inserts)} inserts, {len(deletes)} deletes - {reducer_name}")

                    # Log the progressive action data for debugging
                    for insert in inserts:
                        if isinstance(insert, dict):
                            progress = insert.get("progress", 0)
                            recipe_id = insert.get("recipe_id", 0)
                            craft_count = insert.get("craft_count", 0)
                            function_type = insert.get("function_type", 0)
                            logging.info(
                                f"Progressive Action: Recipe {recipe_id}, Progress {progress}, Count {craft_count}, Type {function_type}"
                            )

                    self._refresh_active_crafting()

        except Exception as e:
            logging.error(f"Error handling progressive action transaction: {e}")
