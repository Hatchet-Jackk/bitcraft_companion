"""
Crafting processor for handling passive_craft_state table updates.
"""

import re
import ast
import time
import threading
import logging
from .base_processor import BaseProcessor


class CraftingProcessor(BaseProcessor):
    """
    Processes passive_craft_state table updates from SpacetimeDB.

    Handles both real-time transactions and batch subscription updates
    for passive crafting changes with built-in timer functionality.
    """

    def __init__(self, data_queue, services, reference_data):
        """Initialize the processor with timer functionality."""
        super().__init__(data_queue, services, reference_data)

        # Real-time timer management
        self.timer_thread = None
        self.timer_stop_event = threading.Event()
        self.ui_update_callback = None
        self.last_timer_update = 0

        # Store raw crafting operations for timer calculations
        self.raw_crafting_operations = []

    def get_table_names(self):
        """Return list of table names this processor handles."""
        return ["passive_craft_state", "building_state", "building_nickname_state", "claim_member_state"]

    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Handle passive_craft_state transactions - LIVE incremental updates.

        Process real-time passive crafting changes without full refresh.
        """
        try:
            table_name = table_update.get("table_name", "")
            updates = table_update.get("updates", [])

            # Track if we need to send updates
            has_crafting_changes = False

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                # Process passive_craft_state updates (craft starts, completions, collections)
                if table_name == "passive_craft_state":
                    # Collect all operations first to handle delete+insert as updates
                    delete_operations = {}
                    insert_operations = {}

                    # Parse all deletes
                    for delete_str in deletes:
                        parsed_data = self._parse_crafting_data(delete_str)
                        if parsed_data:
                            # Only process updates for current claim members
                            owner_id = parsed_data.get("owner_entity_id")
                            if self._is_current_claim_member(owner_id):
                                entity_id = parsed_data.get("entity_id")
                                delete_operations[entity_id] = parsed_data

                    # Parse all inserts
                    for insert_str in inserts:
                        parsed_data = self._parse_crafting_data(insert_str)
                        if parsed_data:
                            # Only process updates for current claim members
                            owner_id = parsed_data.get("owner_entity_id")
                            if self._is_current_claim_member(owner_id):
                                entity_id = parsed_data.get("entity_id")
                                insert_operations[entity_id] = parsed_data

                    # Process operations: handle delete+insert as updates, standalone deletes as collections
                    if not hasattr(self, "_passive_craft_data"):
                        self._passive_craft_data = {}

                    # Handle updates (delete+insert for same entity) and new inserts
                    for entity_id in insert_operations:
                        insert_data = insert_operations[entity_id]
                        self._passive_craft_data[entity_id] = insert_data

                        if entity_id in delete_operations:
                            # This is an update (delete+insert)
                            self._log_crafting_action("UPDATED", insert_data, reducer_name)
                        else:
                            # This is a new insert
                            self._log_crafting_action("STARTED", insert_data, reducer_name)

                        has_crafting_changes = True

                    # Handle standalone deletes (collections/completions)
                    for entity_id in delete_operations:
                        if entity_id not in insert_operations:
                            # This is a standalone delete (collection/completion)
                            if entity_id in self._passive_craft_data:
                                del self._passive_craft_data[entity_id]

                            delete_data = delete_operations[entity_id]
                            self._log_crafting_action("COLLECTED", delete_data, reducer_name)
                            has_crafting_changes = True

                # For other table types, do full refresh if we have changes
                elif inserts or deletes:
                    self._log_transaction_debug("passive_crafting", len(inserts), len(deletes), reducer_name)
                    has_crafting_changes = True

            # Send incremental update for passive_craft_state, full refresh for others
            if has_crafting_changes:
                if table_name == "passive_craft_state":
                    self._send_incremental_crafting_update(reducer_name, timestamp)
                else:
                    self._refresh_crafting()

        except Exception as e:
            logging.error(f"Error handling passive crafting transaction: {e}")

    def process_subscription(self, table_update):
        """
        Handle passive_craft_state, building_state, building_nickname_state, and claim_member_state subscription updates.
        Cache all data and combine them for consolidated crafting.
        """
        try:
            table_name = table_update.get("table_name", "")
            table_rows = []

            # Extract rows from table update
            for update in table_update.get("updates", []):
                for insert_str in update.get("inserts", []):
                    try:
                        import json

                        row_data = json.loads(insert_str)
                        table_rows.append(row_data)
                    except json.JSONDecodeError:
                        logging.warning(f"Failed to parse {table_name} insert: {insert_str[:100]}...")

            if not table_rows:
                return

            # Handle different table types
            if table_name == "passive_craft_state":
                self._process_passive_craft_data(table_rows)
            elif table_name == "building_state":
                self._process_building_data(table_rows)
            elif table_name == "building_nickname_state":
                self._process_building_nickname_data(table_rows)
            elif table_name == "claim_member_state":
                self._process_claim_member_data(table_rows)

            # Try to send consolidated crafting if we have all necessary data
            self._send_crafting_update()

        except Exception as e:
            logging.error(f"Error handling crafting subscription: {e}")

    def _parse_crafting_data(self, data_str):
        """
        Parse crafting data from the SpacetimeDB format.
        Format: [entity_id, owner_id, recipe_id, building_id, [timestamp], [status], [slot]]

        Extracted from DataService._parse_crafting_data()
        """
        try:
            data = ast.literal_eval(data_str)
            if not isinstance(data, list) or len(data) < 7:
                return None

            # Extract timestamp - can be direct value or in array format
            timestamp_micros = None
            if data[4]:
                if isinstance(data[4], list) and len(data[4]) > 0:
                    timestamp_micros = data[4][0]
                else:
                    timestamp_micros = data[4]

            return {
                "entity_id": data[0],
                "owner_entity_id": data[1],
                "recipe_id": data[2],
                "building_entity_id": data[3],
                "timestamp_micros": timestamp_micros,
                "status": data[5] if len(data[5]) > 0 else [0, {}],
                "slot": data[6],
            }
        except Exception as e:
            logging.warning(f"Error parsing crafting data: {e}")
            return None

    def _log_crafting_action(self, action, crafting_data, reducer_name):
        """
        Log crafting actions with meaningful information and trigger notifications for completions.

        Extracted from DataService._log_crafting_action()
        """
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
            claim = getattr(self.inventory_service, "claim", None) if self.inventory_service else None
            if claim and claim.buildings:
                for category, buildings in claim.buildings.items():
                    for building in buildings:
                        if building.get("entity_id") == building_id:
                            building_name = building.get("nickname") or building.get("name", building_name)
                            break

            status_code = status[0] if status and len(status) > 0 else 0
            status_text = "READY" if status_code == 2 else "IN_PROGRESS" if status_code == 1 else "UNKNOWN"

            # Trigger notification for passive craft completions
            if action == "COLLECTED":
                self._trigger_passive_craft_notification(recipe_name)

            logging.info(f"Passive craft {action}: {recipe_name} at {building_name} ({status_text})")

        except Exception as e:
            logging.warning(f"Error logging crafting action: {e}")
    
    def _trigger_passive_craft_notification(self, item_name: str):
        """
        Trigger a passive craft completion notification.
        
        Args:
            item_name: Name of the completed item
        """
        try:
            # Access notification service through data service
            if hasattr(self, 'services') and self.services:
                data_service = self.services.get('data_service')
                if data_service and hasattr(data_service, 'notification_service'):
                    data_service.notification_service.show_passive_craft_notification(item_name)
                    
        except Exception as e:
            logging.error(f"Error triggering passive craft notification: {e}")

    def _refresh_crafting(self):
        """
        Refresh and send crafting data to UI.

        Uses PassiveCraftingService.get_all_crafting_data_enhanced() which handles:
        - Recipe name resolution
        - Building name resolution
        - Proper grouping and summarization
        - Timer calculations

        Extracted from DataService._refresh_crafting()
        """
        try:
            if not self.passive_crafting_service:
                logging.warning("PassiveCraftingService not available")
                return

            # Use the service's enhanced method which handles all the complex logic
            fresh_crafting_data = self.passive_crafting_service.get_all_crafting_data_enhanced()

            self._queue_update("crafting_update", fresh_crafting_data, changes={"source": "live_update"}, timestamp=time.time())

        except Exception as e:
            logging.error(f"Error refreshing crafting: {e}")

    def _send_incremental_crafting_update(self, reducer_name, timestamp):
        """
        Send incremental passive crafting update using processor's own consolidation logic.
        Updates the processor's raw_crafting_operations for timer thread.
        """
        try:
            # Convert processor data to format expected by timer thread
            processor_crafting_operations = []

            for entity_id, craft_data in self._passive_craft_data.items():
                # Create operation in format expected by timer thread
                operation = {
                    "entity_id": entity_id,
                    "recipe_id": craft_data.get("recipe_id"),
                    "building_entity_id": craft_data.get("building_entity_id"),
                    "owner_entity_id": craft_data.get("owner_entity_id"),
                    "timestamp_micros": craft_data.get("timestamp_micros"),
                    "status": craft_data.get("status", [0, {}]),
                    "slot": craft_data.get("slot", 0),
                    "raw_craft_state": craft_data,  # Include raw data for timer calculations
                }
                processor_crafting_operations.append(operation)

            # Update the processor's raw operations for timer thread
            self.raw_crafting_operations = processor_crafting_operations

            # Use the full consolidation method that formats hierarchy for UI
            consolidated_data = self._consolidate_crafting()
            fresh_crafting_data = self._format_crafting_for_ui(consolidated_data)

            self._queue_update(
                "crafting_update",
                fresh_crafting_data,
                changes={"type": "incremental", "source": "live_transaction", "reducer": reducer_name},
                timestamp=timestamp,
            )
        except Exception as e:
            logging.error(f"Error sending incremental passive crafting update: {e}")

    def _process_passive_craft_data(self, craft_rows):
        "Process passive_craft_state data to store crafting operations."
        try:
            # Store crafting data keyed by entity_id
            if not hasattr(self, "_passive_craft_data"):
                self._passive_craft_data = {}

            for row in craft_rows:
                entity_id = row.get("entity_id")
                if row.get("status", [0, {}]) == [1, {}]:
                    pass
                if entity_id:
                    # Extract timestamp from subscription format
                    timestamp_micros = None
                    if "timestamp" in row:
                        timestamp_obj = row["timestamp"]
                        if isinstance(timestamp_obj, dict) and "__timestamp_micros_since_unix_epoch__" in timestamp_obj:
                            timestamp_micros = timestamp_obj["__timestamp_micros_since_unix_epoch__"]

                    # Fallback for direct timestamp_micros field (transaction format)
                    if timestamp_micros is None:
                        timestamp_micros = row.get("timestamp_micros")

                    self._passive_craft_data[entity_id] = {
                        "entity_id": entity_id,
                        "owner_entity_id": row.get("owner_entity_id"),
                        "recipe_id": row.get("recipe_id"),
                        "building_entity_id": row.get("building_entity_id"),
                        "timestamp_micros": timestamp_micros,
                        "status": row.get("status", [0, {}]),
                        "slot": row.get("slot", 0),
                        "consumed_item_stacks": row.get("consumed_item_stacks", []),
                        "crafted_item_stacks": row.get("crafted_item_stacks", []),
                    }

            for craft_id, craft_data in self._passive_craft_data.items():
                recipe_id = craft_data.get("recipe_id")
                building_id = craft_data.get("building_entity_id")
                status = craft_data.get("status", [0, {}])
                status_code = status[0] if status and len(status) > 0 else 0
                status_text = "READY" if status_code == 2 else "IN_PROGRESS" if status_code == 1 else "UNKNOWN"

        except Exception as e:
            logging.error(f"Error processing passive craft data: {e}")

    def _process_building_data(self, building_rows):
        "Process building_state data to store building info."
        try:
            # Store building data keyed by entity_id
            if not hasattr(self, "_building_data"):
                self._building_data = {}

            for row in building_rows:
                entity_id = row.get("entity_id")
                if entity_id:
                    self._building_data[entity_id] = {
                        "building_description_id": row.get("building_description_id"),
                        "claim_entity_id": row.get("claim_entity_id"),
                        "entity_id": entity_id,
                    }

        except Exception as e:
            logging.error(f"Error processing building data: {e}")

    def _process_building_nickname_data(self, nickname_rows):
        """
        Process building_nickname_state data to store custom building names.
        """
        try:
            # Store nickname data keyed by entity_id
            if not hasattr(self, "_building_nicknames"):
                self._building_nicknames = {}

            for row in nickname_rows:
                entity_id = row.get("entity_id")
                nickname = row.get("nickname")
                if entity_id and nickname:
                    self._building_nicknames[entity_id] = nickname

        except Exception as e:
            logging.error(f"Error processing building nickname data: {e}")

    def _process_claim_member_data(self, member_rows):
        """
        Process claim_member_state data to store player names for current claim members.

        Note: We filter to only store data for the current claim to avoid confusion
        with the user's own claims from other claim_member_state queries.
        """
        try:
            # Store member data keyed by player_entity_id
            if not hasattr(self, "_claim_members"):
                self._claim_members = {}

            for row in member_rows:
                claim_entity_id = row.get("claim_entity_id")
                player_entity_id = row.get("player_entity_id")
                user_name = row.get("user_name")

                # Store all claim member data since the query service already filters by current claim
                if player_entity_id and user_name:
                    self._claim_members[str(player_entity_id)] = user_name

        except Exception as e:
            logging.error(f"Error processing claim member data: {e}")

    def start_real_time_timer(self, ui_update_callback):
        """
        Start the real-time countdown timer that updates the UI every second.

        Args:
            ui_update_callback: Function to call when timers need UI update
        """
        if self.timer_thread and self.timer_thread.is_alive():
            logging.warning("Timer thread already running")
            return

        self.ui_update_callback = ui_update_callback
        self.timer_stop_event.clear()

        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        logging.info("Started real-time crafting countdown timer in processor")

    def stop_real_time_timer(self):
        """Stop the real-time countdown timer with improved cleanup."""
        logging.info("Stopping real-time crafting countdown timer in processor...")

        try:
            if self.timer_thread:
                # Set stop event
                self.timer_stop_event.set()

                # Wait for thread with timeout
                if self.timer_thread.is_alive():
                    self.timer_thread.join(timeout=1.0)  # 1 second timeout

                    if self.timer_thread.is_alive():
                        logging.warning("Timer thread did not finish within timeout")
                    else:
                        logging.info("Timer thread finished cleanly")

                self.timer_thread = None

        except Exception as e:
            logging.error(f"Error stopping timer thread: {e}")
        finally:
            logging.info("Real-time timer shutdown complete")

    def _timer_loop(self):
        """Background thread that updates timers every second."""
        timer_count = 0
        while not self.timer_stop_event.is_set():
            try:
                current_time = time.time()

                # Only update every second to avoid excessive UI updates
                if current_time - self.last_timer_update >= 1.0:
                    timer_count += 1
                    self._update_all_timers()
                    self.last_timer_update = current_time

                # Sleep for a short time to avoid busy waiting
                time.sleep(0.1)

            except Exception as e:
                logging.error(f"Error in timer loop: {e}")
                time.sleep(1.0)  # Longer sleep on error

    def _update_all_timers(self):
        """Update all crafting timers and send FULL data refresh to UI."""
        try:
            has_timer_changes = False
            updated_operations = []

            if len(self.raw_crafting_operations) == 0:

                return

            for operation in self.raw_crafting_operations:
                # Calculate current time remaining
                new_time_remaining = self._calculate_current_time_remaining(operation)
                old_time_remaining = operation.get("time_remaining", "")

                entity_id = operation.get("entity_id", "unknown")

                # Check if status changed (e.g., from "5m 30s" to "READY")
                if new_time_remaining != old_time_remaining:
                    operation["time_remaining"] = new_time_remaining
                    has_timer_changes = True

                updated_operations.append(operation)

            # Update the stored operations
            self.raw_crafting_operations = updated_operations

            # If any timers changed, send a FULL data refresh to avoid entity mapping issues
            if has_timer_changes and self.ui_update_callback:

                # Generate fresh consolidated data with updated timers
                consolidated_data = self._consolidate_crafting()
                fresh_crafting_data = self._format_crafting_for_ui(consolidated_data)

                # Send as regular crafting_update so UI rebuilds completely
                self.ui_update_callback(
                    {
                        "type": "crafting_update",
                        "data": fresh_crafting_data,
                        "timestamp": time.time(),
                        "changes": {"source": "timer_update"},
                    }
                )

        except Exception as e:
            logging.error(f"Error updating timers: {e}")

    def _calculate_current_time_remaining(self, operation):
        """
        Calculate the current time remaining for a crafting operation.
        This is called by the timer thread every second.
        """
        try:
            # First check database status - this is still the source of truth
            raw_craft_state = operation.get("raw_craft_state", {})
            status = raw_craft_state.get("status")
            entity_id = operation.get("entity_id")
            recipe_id = raw_craft_state.get("recipe_id")

            if status and isinstance(status, list) and len(status) > 0:
                if status[0] == 2:  # Completed
                    return "READY"
                elif status[0] != 1:  # Not in progress
                    return "Unknown"

            # For in-progress items, calculate real-time countdown
            if not recipe_id:
                return "In Progress"

            # Get recipe duration from reference data
            crafting_recipes = self.reference_data.get("crafting_recipe_desc", [])
            recipe_lookup = {r["id"]: r for r in crafting_recipes}

            if recipe_id not in recipe_lookup:
                return "In Progress"

            recipe = recipe_lookup[recipe_id]
            duration_seconds = recipe.get("time_requirement", 0)

            # Get timestamp - handle multiple formats
            timestamp_micros = operation.get("timestamp_micros")
            if not timestamp_micros:
                return "In Progress"

            # Calculate remaining time with current timestamp
            start_time = timestamp_micros / 1_000_000
            current_time = time.time()
            elapsed_time = current_time - start_time
            remaining_time = duration_seconds - elapsed_time

            if remaining_time <= 0:
                return "READY"

            formatted_time = self._format_duration_for_display(remaining_time)
            return formatted_time

        except Exception as e:
            logging.error(f"Error calculating timer for entity {operation.get('entity_id')}: {e}")
            return "Error"

    def _format_duration_for_display(self, seconds: float) -> str:
        """
        Format seconds into a human-readable duration string for display.

        Args:
            seconds: Duration in seconds

        Returns:
            str: Formatted duration (e.g., "2h 30m 15s", "45m 30s", "30s")
        """
        if seconds <= 0:
            return "0s"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining_seconds = int(seconds % 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if remaining_seconds > 0:
            parts.append(f"{remaining_seconds}s")

        return " ".join(parts) if parts else "0s"

    def _get_player_name(self, player_entity_id):
        """
        Get player name from entity ID using cached claim member data.

        Args:
            player_entity_id: The player's entity ID

        Returns:
            str: Player name or fallback
        """
        try:
            # Convert to string for consistent lookup
            player_id_str = str(player_entity_id)

            # Try cached claim member data
            if hasattr(self, "_claim_members") and player_id_str in self._claim_members:
                player_name = self._claim_members[player_id_str]
                return player_name

            # Fallback to entity ID format
            return f"Player {player_entity_id}"

        except Exception as e:
            logging.warning(f"Error getting player name for {player_entity_id}: {e}")
            return f"Player {player_entity_id}"

    def _send_crafting_update(self):
        """
        Send consolidated crafting update by combining all cached data.
        """
        try:
            if not (hasattr(self, "_passive_craft_data") and self._passive_craft_data):
                return

            if not (hasattr(self, "_building_data") and self._building_data):
                return

            # Building nicknames are optional
            if not hasattr(self, "_building_nicknames"):
                self._building_nicknames = {}

            # Update raw_crafting_operations for timer thread (same as in incremental update)
            processor_crafting_operations = []
            for entity_id, craft_data in self._passive_craft_data.items():
                operation = {
                    "entity_id": entity_id,
                    "recipe_id": craft_data.get("recipe_id"),
                    "building_entity_id": craft_data.get("building_entity_id"),
                    "owner_entity_id": craft_data.get("owner_entity_id"),
                    "timestamp_micros": craft_data.get("timestamp_micros"),
                    "status": craft_data.get("status", [0, {}]),
                    "slot": craft_data.get("slot", 0),
                    "raw_craft_state": craft_data,
                }
                processor_crafting_operations.append(operation)

            self.raw_crafting_operations = processor_crafting_operations

            # Consolidate crafting by item
            consolidated_crafting = self._consolidate_crafting()

            # Convert dictionary to list format for UI
            crafting_list = self._format_crafting_for_ui(consolidated_crafting)

            # Send to UI
            self._queue_update("crafting_update", crafting_list)

        except Exception as e:
            logging.error(f"Error sending crafting update: {e}")

    def _consolidate_crafting(self):
        """
        Consolidate crafting data into 3-level hierarchy: Item -> Crafter -> Building/Time.

        Returns:
            Dictionary with items consolidated in hierarchical structure
        """
        try:
            # First collect all raw operations
            raw_operations = []

            # Get reference data for lookups
            item_lookups = self._get_item_lookups()
            recipe_lookup = {r["id"]: r for r in self.reference_data.get("crafting_recipe_desc", [])}
            building_desc_lookup = {b["id"]: b["name"] for b in self.reference_data.get("building_desc", [])}

            #     f"[CRAFTING DEBUG] Starting consolidation with {len(item_lookups)} item references, {len(recipe_lookup)} recipes, and {len(building_desc_lookup)} building types"
            # )

            # Process each crafting operation to extract individual items
            for craft_id, craft_data in self._passive_craft_data.items():
                building_id = craft_data.get("building_entity_id")
                recipe_id = craft_data.get("recipe_id")
                owner_id = craft_data.get("owner_entity_id")
                status = craft_data.get("status", [0, {}])
                timestamp_micros = craft_data.get("timestamp_micros")

                # Skip crafting operations from players who are not current claim members
                owner_id_str = str(owner_id)
                if hasattr(self, "_claim_members") and self._claim_members:
                    if owner_id_str not in self._claim_members:
                        continue

                # Get building info
                building_info = self._building_data.get(building_id, {})
                building_description_id = building_info.get("building_description_id")

                # Get container name (nickname or building type name)
                container_name = self._building_nicknames.get(building_id)
                if not container_name and building_description_id:
                    container_name = building_desc_lookup.get(building_description_id, f"Building {building_id}")
                if not container_name:
                    container_name = f"Unknown Building {building_id}"

                # Get recipe info
                recipe_info = recipe_lookup.get(recipe_id, {})
                recipe_name = recipe_info.get("name", f"Recipe {recipe_id}")
                recipe_name = re.sub(r"\{\d+\}", "", recipe_name).strip()

                # Calculate time remaining
                status_code = status[0] if status and len(status) > 0 else 0
                time_remaining_display = "READY"
                if status_code == 1 and timestamp_micros:  # IN_PROGRESS
                    current_time_micros = int(time.time() * 1_000_000)
                    elapsed_micros = current_time_micros - timestamp_micros
                    # Try different duration field names
                    recipe_duration = recipe_info.get("duration_micros", 0)
                    if recipe_duration == 0:
                        # Check for time_requirement field (from user's data structure)
                        time_requirement_seconds = recipe_info.get("time_requirement", 0)
                        if time_requirement_seconds > 0:
                            recipe_duration = int(time_requirement_seconds * 1_000_000)  # Convert to microseconds

                    if recipe_duration > 0:
                        remaining_micros = max(0, recipe_duration - elapsed_micros)
                        remaining_seconds = remaining_micros / 1_000_000
                        time_remaining_display = self._format_time_remaining(remaining_seconds)
                    else:
                        logging.warning(
                            f"[PASSIVE CRAFTING] Recipe {recipe_id}: No duration_micros found in recipe_info: {recipe_info.keys()}"
                        )
                elif status_code == 0:
                    time_remaining_display = "Unknown"

                # Get crafter name
                crafter_name = self._get_player_name(owner_id)

                # Process crafted items from this operation
                crafted_items = recipe_info.get("crafted_item_stacks", [])
                for item_stack in crafted_items:
                    if isinstance(item_stack, list) and len(item_stack) >= 2:
                        item_id = item_stack[0]
                        quantity = item_stack[1]

                        # Look up item details
                        item_info = item_lookups.get(item_id, {})
                        item_name = item_info.get("name", f"Unknown Item {item_id}")
                        item_tier = item_info.get("tier", 0)
                        item_tag = item_info.get("tag", "")

                        # Create raw operation
                        raw_operation = {
                            "item_name": item_name,
                            "tier": item_tier,
                            "quantity": quantity,
                            "tag": item_tag,
                            "crafter": crafter_name,
                            "building_name": container_name,
                            "time_remaining": time_remaining_display,
                            "entity_id": craft_id,  # This is the entity_id for timer updates
                            "craft_id": craft_id,  # Keep for backwards compatibility
                            "recipe_name": recipe_name,
                        }
                        raw_operations.append(raw_operation)
                        #     f"[CRAFTING DEBUG] Raw operation: {item_name} x{quantity} by '{crafter_name}' in '{container_name}' - {time_remaining_display}"
                        # )

            # Now build the 3-level hierarchy
            return self._build_hierarchy(raw_operations)

        except Exception as e:
            logging.error(f"Error consolidating crafting: {e}")
            return {}

    def _build_hierarchy(self, raw_operations):
        """
        Build hierarchy from raw operations: Item+Crafter -> Building -> Individual Jobs.

        Args:
            raw_operations: List of individual crafting operations

        Returns:
            Dictionary with hierarchical structure for UI
        """
        try:
            hierarchy = {}

            # Group by item name + crafter first (Level 1)
            for op in raw_operations:
                item_name = op["item_name"]
                crafter = op["crafter"]
                item_crafter_key = f"{item_name}|{crafter}"

                if item_crafter_key not in hierarchy:
                    hierarchy[item_crafter_key] = {
                        "item_name": item_name,
                        "crafter": crafter,
                        "tier": op["tier"],
                        "tag": op["tag"],
                        "total_quantity": 0,
                        "buildings": {},  # Level 2: building data
                        "unique_buildings": set(),
                        "unique_building_types": set(),
                        "operations": [],  # All operations for this item+crafter
                    }

                # Add to item+crafter totals
                hierarchy[item_crafter_key]["total_quantity"] += op["quantity"]
                hierarchy[item_crafter_key]["unique_buildings"].add(op["building_name"])
                hierarchy[item_crafter_key]["operations"].append(op)

                # Track building types for smart summary
                # Extract base building type (e.g., "Fine Smelter" from "Fine Smelter A" or just "Fine Smelter")
                building_parts = op["building_name"].split(" ")
                if len(building_parts) >= 2:
                    building_type = (
                        " ".join(building_parts[:-1])
                        if building_parts[-1] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                        else op["building_name"]
                    )
                else:
                    building_type = op["building_name"]
                hierarchy[item_crafter_key]["unique_building_types"].add(building_type)

                # Group by building + time remaining (Level 2)
                building_time_key = f"{op['building_name']}|{op['time_remaining']}"
                if building_time_key not in hierarchy[item_crafter_key]["buildings"]:
                    hierarchy[item_crafter_key]["buildings"][building_time_key] = {
                        "building_name": op["building_name"],
                        "time_remaining": op["time_remaining"],
                        "quantity": 0,
                        "operations": [],
                    }

                # Add to building/time group
                hierarchy[item_crafter_key]["buildings"][building_time_key]["quantity"] += op["quantity"]
                hierarchy[item_crafter_key]["buildings"][building_time_key]["operations"].append(op)

            # Convert to UI format
            return self._format_hierarchy_for_ui(hierarchy)

        except Exception as e:
            logging.error(f"Error building hierarchy: {e}")
            return {}

    def _format_hierarchy_for_ui(self, hierarchy):
        """
        Format hierarchical data for UI consumption with item+crafter grouping.

        Args:
            hierarchy: The item+crafter hierarchy structure

        Returns:
            Dictionary formatted for UI display
        """
        try:
            formatted = {}

            for item_crafter_key, group_data in hierarchy.items():
                item_name = group_data["item_name"]
                crafter = group_data["crafter"]

                # Calculate job completion status
                total_jobs = len(group_data["buildings"])
                completed_jobs = sum(
                    1 for building_data in group_data["buildings"].values() if building_data["time_remaining"] == "READY"
                )

                # Get all time values for this crafter's jobs
                all_times = [building_data["time_remaining"] for building_data in group_data["buildings"].values()]

                # Get longest active time (not READY)
                active_times = [t for t in all_times if t != "READY"]
                if active_times:
                    parent_time = self._get_longest_time(active_times)
                    if len(active_times) > 1:
                        parent_time = f"~{parent_time}"  # Add ~ for multiple active jobs
                else:
                    parent_time = "READY"  # All jobs complete

                # Build smart building summary
                num_buildings = len(group_data["unique_buildings"])
                num_building_types = len(group_data["unique_building_types"])

                if num_buildings == 1:
                    # Single building - no suffix needed
                    building_summary = list(group_data["unique_buildings"])[0]
                elif num_building_types > 1:
                    # Multiple building types
                    building_summary = f"{num_buildings} Buildings"
                else:
                    # Multiple buildings of same type
                    building_type = list(group_data["unique_building_types"])[0]
                    building_summary = building_type  # Use the base building type name

                # Create child operations for expansion - consolidate by building + time
                child_operations = []
                for building_time_key, building_data in group_data["buildings"].items():
                    # Consolidate all operations in this building + time group
                    original_operations = building_data.get("operations", [])

                    # Sum quantities and collect entity IDs for this group
                    total_quantity = building_data["quantity"]  # Already summed in building logic
                    entity_ids = [op.get("entity_id") for op in original_operations if op.get("entity_id")]

                    # Create single consolidated child row for this building + time combination
                    child_operations.append(
                        {
                            "item": item_name,
                            "tier": group_data["tier"],
                            "quantity": total_quantity,  # Consolidated quantity
                            "tag": group_data["tag"],
                            "time_remaining": building_data["time_remaining"],
                            "crafter": crafter,
                            "building_name": self._add_building_suffix(
                                building_data["building_name"], group_data["unique_buildings"]
                            ),
                            "entity_ids": entity_ids,  # Multiple entity IDs for timer updates
                            "entity_id": entity_ids[0] if entity_ids else None,  # Primary entity ID for compatibility
                            "is_expandable": False,
                            "expansion_level": 1,
                        }
                    )

                # Determine if parent should be expandable
                parent_is_expandable = len(group_data["buildings"]) > 1

                # Create unique key for this crafter's items
                display_key = (
                    f"{item_name}|{crafter}"
                    if len([k for k in hierarchy.keys() if k.startswith(f"{item_name}|")]) > 1
                    else item_name
                )

                formatted[display_key] = {
                    "item": item_name,
                    "tier": group_data["tier"],
                    "total_quantity": group_data["total_quantity"],
                    "tag": group_data["tag"],
                    "time_remaining": parent_time,
                    "crafter": crafter,
                    "building_name": building_summary,
                    "completed_jobs": completed_jobs,
                    "total_jobs": total_jobs,
                    "operations": child_operations,
                    "is_expandable": parent_is_expandable,
                    "expansion_level": 0,
                }

            return formatted

        except Exception as e:
            logging.error(f"Error formatting hierarchy for UI: {e}")
            return {}

    def _get_latest_time(self, time_list):
        """
        Get the latest (shortest/most urgent) time from a list of time strings.

        Args:
            time_list: List of time remaining strings

        Returns:
            str: The shortest/most urgent time remaining
        """
        try:
            if not time_list:
                return "Unknown"

            # Filter out empty/unknown times
            valid_times = [t for t in time_list if t and t not in ["", "Unknown", "Error"]]
            if not valid_times:
                return "Unknown"

            # If any are READY, that's the most urgent
            if "READY" in valid_times:
                return "READY"

            # Convert times to seconds for comparison
            times_in_seconds = []
            for time_str in valid_times:
                seconds = self._time_string_to_seconds(time_str)
                if seconds is not None:
                    times_in_seconds.append((seconds, time_str))

            if not times_in_seconds:
                return valid_times[0]  # Fallback to first valid time

            # Return the shortest time (most urgent)
            shortest = min(times_in_seconds, key=lambda x: x[0])
            return shortest[1]

        except Exception as e:
            return "Unknown"

    def _get_longest_time(self, time_list):
        """
        Get the longest time from a list of time strings (for parent row display).

        Args:
            time_list: List of time remaining strings

        Returns:
            str: The longest time remaining
        """
        try:
            if not time_list:
                return "Unknown"

            # Filter out empty/unknown times
            valid_times = [t for t in time_list if t and t not in ["", "Unknown", "Error", "READY"]]
            if not valid_times:
                return "READY" if "READY" in time_list else "Unknown"

            # Convert times to seconds for comparison
            times_in_seconds = []
            for time_str in valid_times:
                seconds = self._time_string_to_seconds(time_str)
                if seconds is not None:
                    times_in_seconds.append((seconds, time_str))

            if not times_in_seconds:
                return valid_times[0]  # Fallback to first valid time

            # Return the longest time
            longest = max(times_in_seconds, key=lambda x: x[0])
            return longest[1]

        except Exception as e:
            logging.warning(f"Error getting longest time from {time_list}: {e}")
            return "Unknown"

    def _add_building_suffix(self, building_name, all_buildings):
        """
        Add A/B/C suffix to building name if multiple buildings exist.

        Args:
            building_name: The building name to potentially suffix
            all_buildings: Set of all building names for this group

        Returns:
            str: Building name with suffix if needed
        """
        try:
            if len(all_buildings) <= 1:
                return building_name

            # Sort buildings for consistent A/B/C assignment
            sorted_buildings = sorted(list(all_buildings))

            # Find index of this building in the sorted list
            try:
                building_index = sorted_buildings.index(building_name)
                suffix = chr(65 + building_index)  # A=65, B=66, etc.

                # Check if building already has a suffix
                if building_name.endswith(f" {suffix}"):
                    return building_name  # Already has correct suffix
                else:
                    # Remove any existing suffix and add the correct one
                    base_name = building_name.rstrip(" ABCDEFGHIJKLMNOPQRSTUVWXYZ").strip()
                    return f"{base_name} {suffix}"

            except ValueError:
                # Building not found in list, return as-is
                return building_name

        except Exception as e:
            logging.warning(f"Error adding building suffix to {building_name}: {e}")
            return building_name

    def _time_string_to_seconds(self, time_str):
        """
        Convert time string like '2h 30m 15s' to total seconds for comparison.

        Args:
            time_str: Time string to convert

        Returns:
            int: Total seconds, or None if cannot parse
        """
        try:
            if not time_str or time_str in ["READY", "Unknown", "Error"]:
                return 0 if time_str == "READY" else None

            total_seconds = 0
            # Parse formats like "2h 30m 15s", "30m 15s", "15s"
            parts = time_str.split()
            for part in parts:
                if "h" in part:
                    total_seconds += int(part.replace("h", "")) * 3600
                elif "m" in part:
                    total_seconds += int(part.replace("m", "")) * 60
                elif "s" in part:
                    total_seconds += int(part.replace("s", ""))

            return total_seconds

        except Exception as e:
            logging.warning(f"Error converting time string '{time_str}' to seconds: {e}")
            return None

    def _get_item_lookups(self):
        """
        Create combined item lookup dictionary from all reference data sources.

        Returns:
            Dictionary mapping item_id to item details
        """
        try:
            item_lookups = {}

            # Combine all item reference data
            for data_source in ["resource_desc", "item_desc", "cargo_desc"]:
                items = self.reference_data.get(data_source, [])
                for item in items:
                    item_id = item.get("id")
                    if item_id is not None:
                        item_lookups[item_id] = item

            return item_lookups

        except Exception as e:
            logging.error(f"Error creating item lookups: {e}")
            return {}

    def _format_crafting_for_ui(self, consolidated_crafting):
        """
        Convert consolidated crafting dictionary to list format expected by UI.

        Args:
            consolidated_crafting: Dictionary with items consolidated by name

        Returns:
            List of item groups with operations for expandable UI
        """
        try:
            formatted_list = []

            for item_name, item_data in consolidated_crafting.items():
                # Keep all the properly formatted data from _format_hierarchy_for_ui
                # Don't recreate the structure - it's already correct!
                formatted_list.append(item_data)

            # Sort by item name for consistent display
            formatted_list.sort(key=lambda x: x.get("item", "").lower())

            # for item in formatted_list:
            #         f"[CRAFTING DEBUG] Item '{item.get('item')}': tier={item.get('tier')}, qty={item.get('total_quantity')}, time='{item.get('time_remaining')}', crafter='{item.get('crafter')}', building='{item.get('building_name')}'"
            #     )

            return formatted_list

        except Exception as e:
            logging.error(f"Error formatting crafting for UI: {e}")
            return []

    def _get_player_name(self, player_entity_id):
        """
        Get player name from entity ID using cached claim member data.

        Args:
            player_entity_id: The player's entity ID

        Returns:
            str: Player name or fallback
        """
        try:
            # Convert to string for consistent lookup
            player_id_str = str(player_entity_id)

            # Try cached claim member data (primary method)
            if hasattr(self, "_claim_members") and player_id_str in self._claim_members:
                player_name = self._claim_members[player_id_str]
                return player_name

            # Try claim members service as fallback
            claim_members_service = self.services.get("claim_members_service")
            if claim_members_service:
                player_name = claim_members_service.get_player_name(player_entity_id)
                if player_name and not player_name.startswith("Player "):
                    return player_name

            logging.warning(f"Could not resolve player name for {player_entity_id}, using fallback")
            # Fallback to entity ID format
            return f"Player {player_entity_id}"

        except Exception as e:
            logging.warning(f"Error getting player name for {player_entity_id}: {e}")
            return f"Player {player_entity_id}"

    def _format_time_remaining(self, seconds):
        """
        Format seconds into a human-readable duration string.

        Args:
            seconds: Duration in seconds

        Returns:
            str: Formatted duration (e.g., "2h 30m", "45m", "30s")
        """
        try:
            if seconds <= 0:
                return "READY"

            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            remaining_seconds = int(seconds % 60)

            parts = []
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if remaining_seconds > 0 and hours == 0:  # Only show seconds if no hours
                parts.append(f"{remaining_seconds}s")

            return " ".join(parts) if parts else "READY"

        except Exception as e:
            logging.warning(f"Error formatting time {seconds}: {e}")
            return "Unknown"

    def _is_current_claim_member(self, owner_entity_id):
        """Check if the owner is a member of the current claim."""
        if not hasattr(self, "_claim_members") or not self._claim_members:
            return True  # If no member data, process everything

        owner_id_str = str(owner_entity_id)
        return owner_id_str in self._claim_members

    def clear_cache(self):
        """Clear cached crafting data when switching claims."""
        super().clear_cache()

        # Clear claim-specific cached data
        if hasattr(self, "_passive_craft_data"):
            self._passive_craft_data.clear()

        if hasattr(self, "_building_data"):
            self._building_data.clear()

        if hasattr(self, "_building_nicknames"):
            self._building_nicknames.clear()

        if hasattr(self, "_claim_members"):
            self._claim_members.clear()
