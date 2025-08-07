"""
Tasks processor for handling traveler_task_state table updates.
"""

import ast
import time
import logging
from .base_processor import BaseProcessor


class TasksProcessor(BaseProcessor):
    """
    Processes traveler_task_state table updates from SpacetimeDB.

    Handles both real-time transactions and batch subscription updates
    for traveler task changes.
    """

    def __init__(self, data_queue, services, reference_data):
        """Initialize TasksProcessor with proper cache setup."""
        super().__init__(data_queue, services, reference_data)

        # Initialize task caches to ensure they exist for transactions
        self._task_states = {}
        self._task_descriptions = {}
        self._player_state = {}

    def get_table_names(self):
        """Return list of table names this processor handles."""
        return ["traveler_task_state", "traveler_task_desc", "player_state"]

    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Handle traveler_task_state transactions.

        Process incremental changes and update cached data without wiping UI.
        """
        try:
            table_name = table_update.get("table_name", "")
            updates = table_update.get("updates", [])

            # Track if we need to refresh UI
            data_changed = False
            completed_tasks = []

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                if inserts or deletes:
                    logging.info(f"TASK TRANSACTION: {len(inserts)} inserts, {len(deletes)} deletes - {reducer_name}")
                    data_changed = True

                    # Process inserts to update cached data and detect completions
                    for insert_str in inserts:
                        try:
                            import json

                            # Parse the transaction data
                            if isinstance(insert_str, str):
                                task_data = json.loads(insert_str)
                            else:
                                task_data = list(insert_str)

                            # Update cached data based on table type
                            if table_name == "traveler_task_state" and isinstance(task_data, list) and len(task_data) >= 4:
                                # Extract task state data: [entity_id, player_entity_id, task_id, completed, traveler_id]
                                entity_id = task_data[0] if len(task_data) > 0 else None
                                player_entity_id = task_data[1] if len(task_data) > 1 else None
                                task_id = task_data[2] if len(task_data) > 2 else None
                                completed = task_data[3] if len(task_data) > 3 else False
                                traveler_id = task_data[4] if len(task_data) > 4 else None

                                # Update cached task state
                                if task_id and hasattr(self, "_task_states"):
                                    old_completed = self._task_states.get(task_id, {}).get("completed", False)

                                    self._task_states[task_id] = {
                                        "entity_id": entity_id,
                                        "player_entity_id": player_entity_id,
                                        "traveler_id": traveler_id,
                                        "completed": completed,
                                    }

                                    # Detect newly completed tasks
                                    if not old_completed and completed:
                                        completed_tasks.append(
                                            {"task_id": task_id, "traveler_id": traveler_id, "reducer_name": reducer_name}
                                        )

                        except Exception as e:
                            logging.warning(f"Error parsing task transaction insert: {e}")

                    # Process deletes (remove from cache if needed)
                    for delete_str in deletes:
                        try:
                            import json

                            if isinstance(delete_str, str):
                                delete_data = json.loads(delete_str)
                            else:
                                delete_data = list(delete_str)

                            # Remove from cached data if needed
                            if table_name == "traveler_task_state" and isinstance(delete_data, list) and len(delete_data) >= 3:
                                task_id = delete_data[2] if len(delete_data) > 2 else None
                                if task_id and hasattr(self, "_task_states") and task_id in self._task_states:
                                    del self._task_states[task_id]

                        except Exception as e:
                            logging.warning(f"Error parsing task transaction delete: {e}")

            # Log task completions
            for completed_task in completed_tasks:
                logging.info(f"Task {completed_task['task_id']} completed! {completed_task['reducer_name']}")

            # Only refresh UI if data actually changed and we have cached data to send
            if data_changed:
                self._refresh_tasks()

        except Exception as e:
            logging.error(f"Error handling tasks transaction: {e}")

    def process_subscription(self, table_update):
        """
        Handle traveler_task_state, traveler_task_desc, and player_state subscription updates.
        Cache all data types and combine them for UI.
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
            if table_name == "traveler_task_state":
                self._process_task_state_data(table_rows)
            elif table_name == "traveler_task_desc":
                self._process_task_desc_data(table_rows)
            elif table_name == "player_state":
                self._process_player_state_data(table_rows)

            # Try to send formatted tasks if we have both data types
            self._send_tasks_update()

        except Exception as e:
            logging.error(f"Error handling tasks subscription: {e}")

    def _refresh_tasks(self):
        """
        Send current cached tasks data to UI instead of wiping it.
        Called during transactions to update UI without losing data.
        """
        try:
            # Send current cached task data if available
            if (
                hasattr(self, "_task_states")
                and self._task_states
                and hasattr(self, "_task_descriptions")
                and self._task_descriptions
            ):
                # Use cached data to maintain current task state
                formatted_tasks = self._format_combined_task_data()
                self._queue_update("tasks_update", formatted_tasks, {"transaction_update": True})
                logging.debug("Refreshed tasks UI with cached data")
            else:
                # Only send empty data if we truly have no cached data
                logging.debug("No cached task data available for refresh - preserving current UI state")
                # Don't send empty data - let UI keep current state

        except Exception as e:
            logging.error(f"Error refreshing tasks: {e}")

    def _process_task_state_data(self, task_state_rows):
        """
        Process traveler_task_state data to store task assignments with traveler info.
        """
        try:
            # Ensure task state cache exists (should be initialized in __init__)
            if not hasattr(self, "_task_states") or self._task_states is None:
                self._task_states = {}

            for row in task_state_rows:
                task_id = row.get("task_id")
                if task_id:
                    self._task_states[task_id] = {
                        "entity_id": row.get("entity_id"),
                        "player_entity_id": row.get("player_entity_id"),
                        "traveler_id": row.get("traveler_id"),
                        "completed": row.get("completed", False),
                    }

        except Exception as e:
            logging.error(f"Error processing task state data: {e}")

    def _process_task_desc_data(self, task_desc_rows):
        """
        Process traveler_task_desc data to store task descriptions.
        """
        try:
            # Ensure task description cache exists (should be initialized in __init__)
            if not hasattr(self, "_task_descriptions") or self._task_descriptions is None:
                self._task_descriptions = {}

            for row in task_desc_rows:
                task_id = row.get("id")
                if task_id:
                    self._task_descriptions[task_id] = {
                        "description": row.get("description", f"Task {task_id}"),
                        "level_requirement": row.get("level_requirement", {}),
                        "required_items": row.get("required_items", []),
                        "rewarded_items": row.get("rewarded_items", []),
                        "rewarded_experience": row.get("rewarded_experience", {}),
                    }

        except Exception as e:
            logging.error(f"Error processing task description data: {e}")

    def _process_player_state_data(self, player_state_rows):
        """
        Process player_state data to extract traveler_tasks_expiration.
        """
        try:
            # Ensure player state cache exists (should be initialized in __init__)
            if not hasattr(self, "_player_state") or self._player_state is None:
                self._player_state = {}

            for row in player_state_rows:
                entity_id = row.get("entity_id")
                if entity_id:
                    self._player_state[entity_id] = {
                        "traveler_tasks_expiration": row.get("traveler_tasks_expiration", 0),
                    }

                    # Send the expiration time to the claim info header
                    expiration_time = row.get("traveler_tasks_expiration", 0)
                    if expiration_time > 0:
                        # Debug the timestamp we're receiving (expiration_time is in SECONDS)
                        self._queue_update("player_state_update", {"traveler_tasks_expiration": expiration_time})

        except Exception as e:
            logging.error(f"Error processing player state data: {e}")

    def _send_tasks_update(self):
        """
        Send tasks update by combining state and description data.
        """
        try:
            if not (hasattr(self, "_task_states") and self._task_states):
                return

            if not (hasattr(self, "_task_descriptions") and self._task_descriptions):
                return

            # Format task data using cached data
            formatted_tasks = self._format_combined_task_data()

            # Send to UI
            self._queue_update("tasks_update", formatted_tasks)

        except Exception as e:
            logging.error(f"Error sending tasks update: {e}")

    def _format_combined_task_data(self):
        """
        Format task data by combining task states and descriptions with traveler names.

        Returns:
            Formatted task data grouped by traveler for UI
        """
        try:
            # Get traveler reference data
            traveler_names = self._get_traveler_names()

            # Group tasks by traveler
            travelers = {}

            # Combine task state and description data
            for task_id, task_state in self._task_states.items():
                task_desc = self._task_descriptions.get(task_id, {})
                traveler_id = task_state.get("traveler_id", 0)

                if traveler_id not in travelers:
                    traveler_name = traveler_names.get(traveler_id, f"Traveler {traveler_id}")
                    travelers[traveler_id] = {
                        "traveler_id": traveler_id,
                        "traveler": traveler_name,  # Tab expects 'traveler' not 'traveler_name'
                        "operations": [],  # Tab expects 'operations' not 'tasks'
                    }

                # Parse required items with item details from reference data
                required_items_formatted = self._format_required_items(task_desc.get("required_items", []))

                # Combine state and description data in the format the tab expects
                task_info = {
                    "task_id": task_id,
                    "entity_id": task_state.get("entity_id"),
                    "task_description": task_desc.get("description", f"Task {task_id}"),
                    "completion_status": "✅" if task_state.get("completed", False) else "❌",
                    "level_requirement": task_desc.get("level_requirement", {}),
                    "required_items_detailed": required_items_formatted,  # Tab expects this key
                    "rewarded_items": task_desc.get("rewarded_items", []),
                    "rewarded_experience": task_desc.get("rewarded_experience", {}),
                }
                travelers[traveler_id]["operations"].append(task_info)

            # Add completion counts and status for each traveler
            for traveler_data in travelers.values():
                operations = traveler_data["operations"]
                completed_count = sum(1 for op in operations if op.get("completion_status") == "✅")
                total_count = len(operations)

                traveler_data["completed_count"] = completed_count
                traveler_data["total_count"] = total_count
                traveler_data["complete"] = "✅" if completed_count == total_count else "❌"

            # Convert to list format expected by UI
            formatted_travelers = list(travelers.values())

            # The traveler tasks tab expects a flat list, not a nested structure
            return formatted_travelers

        except Exception as e:
            logging.error(f"Error formatting combined task data: {e}")
            return {"active_tasks": [], "pending_tasks": [], "completed_tasks": []}

    def _get_traveler_names(self):
        """
        Get traveler names from reference data.

        Returns:
            Dictionary mapping traveler_id to traveler_name
        """
        try:
            traveler_names = {}

            # Get traveler data from reference data (passed to processor)
            traveler_data = self.reference_data.get("traveler_desc", [])
            if traveler_data:
                for traveler in traveler_data:
                    npc_type = traveler.get("npc_type")
                    name = traveler.get("name")
                    if npc_type and name:
                        traveler_names[npc_type] = name
            else:
                logging.warning("No traveler reference data found")

            return traveler_names

        except Exception as e:
            logging.error(f"Error getting traveler names: {e}")
            return {}

    def _format_required_items(self, required_items_raw):
        """
        Format required items list with item details from reference data.

        Args:
            required_items_raw: Raw required items list like [[1170001, 10, [0, []], [0, 0]]]

        Returns:
            List of formatted required items with names, tiers, tags
        """
        try:
            if not required_items_raw:
                return []

            # Get item lookups from reference data
            item_lookups = self._get_item_lookups()
            formatted_items = []

            for item_raw in required_items_raw:
                if isinstance(item_raw, list) and len(item_raw) >= 2:
                    item_id = item_raw[0]
                    quantity = item_raw[1]

                    # Look up item details using smart lookup
                    item_info = self._lookup_item_by_id(item_lookups, item_id)
                    item_name = item_info.get("name", f"Unknown Item {item_id}") if item_info else f"Unknown Item {item_id}"
                    item_tier = item_info.get("tier", 0) if item_info else 0
                    item_tag = item_info.get("tag", "") if item_info else ""

                    formatted_item = {
                        "item_id": item_id,
                        "item_name": item_name,  # Tab expects 'item_name' not 'name'
                        "quantity": quantity,
                        "tier": item_tier,
                        "tag": item_tag,
                    }
                    formatted_items.append(formatted_item)

            return formatted_items

        except Exception as e:
            logging.error(f"Error formatting required items: {e}")
            return []

    def _get_item_lookups(self):
        """
        Create combined item lookup dictionary from all reference data sources.

        Uses compound keys to prevent ID conflicts between tables.
        Example: item_id 1050001 exists in both item_desc and cargo_desc as different items.

        Returns:
            Dictionary mapping both (item_id, table_source) and item_id to item details
        """
        try:
            item_lookups = {}

            # Combine all item reference data with compound keys to prevent overwrites
            for data_source in ["resource_desc", "item_desc", "cargo_desc"]:
                items = self.reference_data.get(data_source, [])
                for item in items:
                    item_id = item.get("id")
                    if item_id is not None:
                        # Use compound key (item_id, table_source) to prevent overwrites
                        compound_key = (item_id, data_source)
                        item_lookups[compound_key] = item

                        # Also maintain simple item_id lookup for backwards compatibility
                        # Priority: item_desc > cargo_desc > resource_desc
                        if item_id not in item_lookups or data_source == "item_desc":
                            item_lookups[item_id] = item

            return item_lookups

        except Exception as e:
            logging.error(f"Error creating item lookups: {e}")
            return {}

    def _lookup_item_by_id(self, item_lookups, item_id, preferred_source=None):
        """
        Smart item lookup that handles both compound keys and simple keys.

        Args:
            item_lookups: The lookup dictionary from _get_item_lookups()
            item_id: The item ID to look up
            preferred_source: Preferred table source ("item_desc", "cargo_desc", "resource_desc")

        Returns:
            Item details dictionary or None if not found
        """
        try:
            # Try preferred source first if specified
            if preferred_source:
                compound_key = (item_id, preferred_source)
                if compound_key in item_lookups:
                    return item_lookups[compound_key]

            # Try simple item_id lookup (uses priority system)
            if item_id in item_lookups:
                return item_lookups[item_id]

            # Try all compound keys if simple lookup failed
            for source in ["item_desc", "cargo_desc", "resource_desc"]:
                compound_key = (item_id, source)
                if compound_key in item_lookups:
                    return item_lookups[compound_key]

            return None

        except Exception as e:
            logging.error(f"Error looking up item {item_id}: {e}")
            return None

    def clear_cache(self):
        """Clear cached tasks data when switching claims."""
        super().clear_cache()

        # Clear claim-specific cached data
        if hasattr(self, "_task_states"):
            self._task_states.clear()

        if hasattr(self, "_task_descriptions"):
            self._task_descriptions.clear()

        if hasattr(self, "_player_state"):
            self._player_state.clear()
