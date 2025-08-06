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

    def get_table_names(self):
        """Return list of table names this processor handles."""
        return ["traveler_task_state", "traveler_task_desc", "player_state"]

    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Handle traveler_task_state transactions.

        Extracted from DataService._handle_tasks_transaction()
        """
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
                            logging.warning(f"Error parsing task insert: {e}")

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
        Process tasks data from subscription and send to UI.
        """
        try:
            # This method is called for transactions - for now send empty data
            empty_tasks_data = {"active_tasks": [], "pending_tasks": [], "completed_tasks": []}
            self._queue_update("tasks_update", empty_tasks_data, {"transaction_update": True})

        except Exception as e:
            logging.error(f"Error processing tasks from subscription: {e}")

    def _process_task_state_data(self, task_state_rows):
        """
        Process traveler_task_state data to store task assignments with traveler info.
        """
        try:
            # Store task state data
            if not hasattr(self, "_task_states"):
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
            # Store task description data
            if not hasattr(self, "_task_descriptions"):
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
            # Store player state data
            if not hasattr(self, "_player_state"):
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

                    # Look up item details
                    item_info = item_lookups.get(item_id, {})
                    item_name = item_info.get("name", f"Unknown Item {item_id}")
                    item_tier = item_info.get("tier", 0)
                    item_tag = item_info.get("tag", "")

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
