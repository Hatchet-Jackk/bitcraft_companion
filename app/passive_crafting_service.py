import logging
from typing import List, Dict
import re
import time
import ast
from datetime import datetime, timedelta

# Type hints for clarity
from client import BitCraft
from claim import Claim


class PassiveCraftingService:
    """Service to handle passive crafting status and data processing."""

    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim, reference_data: dict):
        """Initializes the service with its dependencies."""
        self.client = bitcraft_client
        self.claim = claim_instance

        # --- Injected Reference Data ---
        self.crafting_recipes = {r["id"]: r for r in reference_data.get("crafting_recipe_desc", [])}
        self.building_desc = {b["id"]: b for b in reference_data.get("building_desc", [])}

        # Create combined item lookup from all item sources
        self.item_descriptions = {}
        for data_list in [
            reference_data.get("resource_desc", []),
            reference_data.get("item_desc", []),
            reference_data.get("cargo_desc", []),
        ]:
            if data_list:
                for item in data_list:
                    if "id" in item:
                        self.item_descriptions[item["id"]] = item

        # Store current crafting data for GUI
        self.current_crafting_data = []

        # Cache for items that have reached READY state
        self.ready_items_cache = {}

    def get_subscription_queries(self, building_ids: List[str]) -> List[str]:
        """Returns a list of SQL query strings for subscribing to passive crafting updates."""
        if not building_ids:
            return []

        logging.info(f"Generating passive crafting subscription queries for {len(building_ids)} buildings.")
        return [f"SELECT * FROM passive_craft_state WHERE building_entity_id = '{bid}';" for bid in building_ids]

    def get_all_crafting_data(self) -> List[Dict]:
        """
        Fetches complete crafting state for all buildings in the claim.
        Returns data formatted for GUI display - ITEM-FOCUSED with expandable rows.
        Only includes crafting by claim members.
        """
        if not self.claim.claim_id:
            logging.error("Cannot fetch crafting data without a claim_id.")
            return []

        try:
            logging.info("Fetching all passive crafting data for claim")

            # Get claim members FIRST to filter non-claim members
            claim_members_query = f"SELECT * FROM claim_member_state WHERE claim_entity_id = '{self.claim.claim_id}';"
            claim_members = self.client.query(claim_members_query)

            if not claim_members:
                logging.warning("No claim members found")
                return []

            # Build lookup for claim members only
            claim_member_ids = set()
            user_lookup = {}
            for member in claim_members:
                player_id = member.get("player_entity_id")
                user_name = member.get("user_name")
                if player_id:
                    claim_member_ids.add(player_id)
                    if user_name:
                        user_lookup[player_id] = user_name
                    else:
                        user_lookup[player_id] = f"User {player_id}"

            logging.info(f"Found {len(claim_member_ids)} claim members")

            # Get all buildings in the claim
            buildings_query = f"SELECT * FROM building_state WHERE claim_entity_id = '{self.claim.claim_id}';"
            buildings = self.client.query(buildings_query)

            if not buildings:
                logging.warning("No buildings found for crafting data fetch")
                return []

            # Get building nicknames for display
            nicknames_query = "SELECT * FROM building_nickname_state;"
            building_nicknames = self.client.query(nicknames_query)
            nickname_lookup = {n["entity_id"]: n["nickname"] for n in building_nicknames} if building_nicknames else {}

            # Filter to processing-capable buildings
            processing_buildings = []
            for building in buildings:
                building_id = building.get("entity_id")
                building_desc_id = building.get("building_description_id")

                if not building_id or not building_desc_id:
                    continue

                # Get building display name
                building_name = self.building_desc.get(building_desc_id, {}).get("name", "Unknown Building")

                # Check if this building supports crafting
                if self._building_supports_crafting(building_desc_id, building_name):
                    building_nickname = nickname_lookup.get(building_id)
                    display_name = building_nickname if building_nickname else building_name

                    processing_buildings.append(
                        {
                            "entity_id": building_id,
                            "building_description_id": building_desc_id,
                            "building_name": building_name,
                            "display_name": display_name,
                            "nickname": building_nickname,
                        }
                    )

            # Get passive craft states for all processing buildings
            building_ids = [b["entity_id"] for b in processing_buildings]
            if not building_ids:
                logging.info("No processing buildings found")
                return []

            crafting_operations = []

            # Get all passive crafting states
            for building_id in building_ids:
                crafting_query = f"SELECT * FROM passive_craft_state WHERE building_entity_id = '{building_id}';"
                crafting_states = self.client.query(crafting_query)

                if not crafting_states:
                    continue

                # Find building info
                building_info = next((b for b in processing_buildings if b["entity_id"] == building_id), None)
                if not building_info:
                    continue

                # Process each crafting operation
                for craft_state in crafting_states:
                    owner_entity_id = craft_state.get("owner_entity_id")

                    # FILTER OUT NON-CLAIM MEMBERS
                    if owner_entity_id not in claim_member_ids:
                        logging.debug(f"Skipping crafting operation by non-claim member: {owner_entity_id}")
                        continue

                    crafting_entry = self._format_crafting_entry_item_focused(craft_state, building_info, user_lookup)
                    if crafting_entry:
                        crafting_operations.append(crafting_entry)

            # Group by item name for the expandable structure
            grouped_data = self._group_crafting_data_by_item_name(crafting_operations)

            self.current_crafting_data = grouped_data
            logging.info(f"Fetched crafting data for {len(grouped_data)} item groups")
            return grouped_data

        except Exception as e:
            logging.error(f"Error fetching crafting data: {e}")
            return []

    def _format_crafting_entry_item_focused(self, craft_state: Dict, building_info: Dict, user_lookup: Dict) -> Dict:
        """Formats a single crafting state entry for item-focused GUI display."""
        try:
            recipe_id = craft_state.get("recipe_id")
            owner_entity_id = craft_state.get("owner_entity_id")

            # Get recipe information
            recipe_info = self.crafting_recipes.get(recipe_id, {})
            recipe_name = recipe_info.get("name", f"Unknown Recipe {recipe_id}")
            # Clean up recipe name by removing {0} placeholder
            recipe_name = re.sub(r"\{\d+\}", "", recipe_name).strip()

            # Extract the actual item being crafted from recipe data
            crafted_item_name = "Unknown Item"
            crafted_item_tier = 0
            recipe_quantity = 1

            # Parse the crafted_item_stacks to get actual item info
            crafted_item_stacks = recipe_info.get("crafted_item_stacks", [])

            try:
                # Handle both string and list formats
                if isinstance(crafted_item_stacks, str):
                    produced_items = ast.literal_eval(crafted_item_stacks)
                elif isinstance(crafted_item_stacks, list):
                    produced_items = crafted_item_stacks
                else:
                    produced_items = []

                if produced_items and len(produced_items) > 0:
                    first_item = produced_items[0]

                    if isinstance(first_item, (list, tuple)) and len(first_item) >= 2:
                        item_id = first_item[0]
                        recipe_quantity = first_item[1]

                        if item_id in self.item_descriptions:
                            item_info = self.item_descriptions.get(item_id, {})
                            crafted_item_name = item_info.get("name", f"Item {item_id}")
                            crafted_item_tier = item_info.get("tier", 0)

            except Exception as e:
                logging.debug(f"Error processing crafted_item_stacks: {e}")

            # Get crafter name
            crafter_name = user_lookup.get(owner_entity_id, f"User {owner_entity_id}")

            # Calculate time remaining
            time_remaining = self.calculate_remaining_time(craft_state)

            # Create refinery display name (building + crafter info)
            refinery_display = building_info["display_name"]
            if building_info["nickname"]:
                refinery_display = f"{building_info['nickname']}"
            else:
                refinery_display = building_info["building_name"]

            return {
                "item_name": crafted_item_name,
                "tier": crafted_item_tier,
                "quantity": recipe_quantity,
                "recipe": recipe_name,
                "time_remaining": time_remaining,
                "crafter": crafter_name,
                "refinery": refinery_display,
                "refinery_full": building_info["building_name"],  # For filtering
                "is_empty": False,
            }

        except Exception as e:
            logging.error(f"Error formatting crafting entry: {e}")
            return None

    def _group_crafting_data_by_item_name(self, operations: List[Dict]) -> List[Dict]:
        """Groups crafting operations by item name with individual refineries as children."""
        if not operations:
            return []

        # Group by item name + tier
        item_groups = {}

        for operation in operations:
            item_name = operation.get("item_name", "Unknown Item")
            tier = operation.get("tier", 0)

            # Create unique group key
            group_key = f"{item_name}|{tier}"

            if group_key not in item_groups:
                item_groups[group_key] = {
                    "item_name": item_name,
                    "tier": tier,
                    "total_quantity": 0,
                    "operations": [],  # Individual refinery operations
                    "time_remaining": "N/A",
                    "recipes": set(),
                    "crafters": set(),
                    "building_types": set(),  # Track unique building types, not individual buildings
                }

            group = item_groups[group_key]
            group["total_quantity"] += operation.get("quantity", 0)
            group["operations"].append(operation)  # Store individual operations
            group["recipes"].add(operation.get("recipe", "Unknown"))
            group["crafters"].add(operation.get("crafter", "Unknown"))

            # Add the building type (not individual building instances)
            building_type = operation.get("refinery", "Unknown")  # This is the building type name
            group["building_types"].add(building_type)

            # Update time remaining - show shortest time or READY if any are ready
            operation_time = operation.get("time_remaining", "Unknown")
            if operation_time == "READY":
                group["time_remaining"] = "READY"
            elif group["time_remaining"] not in ["READY"] and operation_time not in ["Empty", "Unknown", "Error"]:
                if group["time_remaining"] in ["N/A", "Empty", "Unknown"]:
                    group["time_remaining"] = operation_time
                elif self._compare_times(operation_time, group["time_remaining"]) < 0:
                    group["time_remaining"] = operation_time

        # Convert to GUI format
        grouped_data = []
        for group_key, group_data in item_groups.items():
            operations = group_data["operations"]
            recipes = list(group_data["recipes"])
            crafters = list(group_data["crafters"])
            building_types = list(group_data["building_types"])

            # Determine if this should be expandable
            is_expandable = len(operations) > 1

            # Create summary display text
            recipe_display = recipes[0] if len(recipes) == 1 else f"{len(recipes)} recipes"

            # FIXED: Building display - show building type, not count of operations
            if len(building_types) == 1:
                # Single building type - just show the building name
                building_display = building_types[0]
            else:
                # Multiple building types - show count of types
                building_display = f"{len(building_types)} building types"

            # FIXED: Crafter display - show crafter name if single, otherwise count
            if len(crafters) == 1:
                # Single crafter - just show the crafter name
                crafter_display = crafters[0]
            else:
                # Multiple crafters - show count
                crafter_display = f"{len(crafters)} crafters"

            # Create the grouped entry
            grouped_entry = {
                "item": group_data["item_name"],
                "tier": group_data["tier"],
                "quantity": group_data["total_quantity"],
                "recipe": recipe_display,
                "time_remaining": group_data["time_remaining"],
                "crafter": crafter_display,
                "building": building_display,
                "operations": operations,  # Individual operations for expansion
                "is_expandable": is_expandable,
            }
            grouped_data.append(grouped_entry)

        return grouped_data

    def _building_supports_crafting(self, building_desc_id: int, building_name: str) -> bool:
        """Checks if a building type supports passive crafting."""
        if not building_desc_id or building_desc_id not in self.building_desc:
            return False

        building_name_lower = building_name.lower()

        # Exclude storage and cargo buildings
        exclude_keywords = ["storage", "cargo stockpile", "stockpile", "bank", "chest"]
        if any(exclude in building_name_lower for exclude in exclude_keywords):
            return False

        # Include crafting-capable buildings
        crafting_keywords = [
            "station",
            "loom",
            "farming field",
            "kiln",
            "smelter",
            "oven",
            "workbench",
            "tanning tub",
            "mill",
            "brewery",
            "forge",
        ]

        return any(keyword in building_name_lower for keyword in crafting_keywords)

    def _get_crafting_status(self, craft_state: Dict) -> str:
        """Determines the current status of a crafting operation."""
        try:
            status_data = craft_state.get("status")
            if status_data and isinstance(status_data, list) and len(status_data) > 0:
                status_code = status_data[0]
                if status_code == 2:  # Status 2 means completed/ready
                    return "READY"
                elif status_code == 1:  # Status 1 means crafting
                    return "Crafting"

            return "Crafting"  # Default assumption

        except Exception as e:
            logging.error(f"Error determining crafting status: {e}")
            return "Unknown"

    def _compare_times(self, time1: str, time2: str) -> int:
        """Compare two time strings. Returns -1 if time1 < time2, 0 if equal, 1 if time1 > time2."""

        def time_to_seconds(time_str):
            if time_str in ["READY", "Empty", "Unknown", "Error", "N/A"]:
                return 0 if time_str == "READY" else 999999

            total_seconds = 0
            try:
                parts = time_str.replace("~", "").split()
                for part in parts:
                    if "h" in part:
                        total_seconds += int(part.replace("h", "")) * 3600
                    elif "m" in part:
                        total_seconds += int(part.replace("m", "")) * 60
                    elif "s" in part:
                        total_seconds += int(part.replace("s", ""))
            except:
                return 999999

            return total_seconds

        seconds1 = time_to_seconds(time1)
        seconds2 = time_to_seconds(time2)

        if seconds1 < seconds2:
            return -1
        elif seconds1 > seconds2:
            return 1
        else:
            return 0

    def parse_crafting_update(self, db_update: dict) -> bool:
        """
        Parses a database update message to check if it's relevant to passive crafting.
        Returns True if the data was updated and needs GUI refresh.
        """
        update_str = str(db_update)
        if "passive_craft_state" in update_str:
            logging.info("Received a passive crafting update.")
            # Refresh the crafting data
            self.current_crafting_data = self.get_all_crafting_data()
            return True

        return False

    def get_current_crafting_data_for_gui(self) -> List[Dict]:
        """Returns the current crafting data formatted for GUI display."""
        return self.current_crafting_data

    def calculate_remaining_time(self, crafting_entry: Dict) -> str:
        """Calculate remaining time for a crafting operation."""
        try:
            # Check status field first - status [2, {}] means completed
            status = crafting_entry.get("status")
            if status and isinstance(status, list) and len(status) > 0:
                status_code = status[0]
                if status_code == 2:  # Status 2 means completed/ready
                    return "READY"

            recipe_id = crafting_entry.get("recipe_id")
            if not recipe_id or recipe_id not in self.crafting_recipes:
                return "Unknown"

            # Create a unique key for this crafting entry
            timestamp_data = crafting_entry.get("timestamp")
            if timestamp_data:
                timestamp_micros = timestamp_data.get("__timestamp_micros_since_unix_epoch__")
                entry_key = f"{recipe_id}_{timestamp_micros}"

                # Check if this entry was already marked as READY
                if entry_key in self.ready_items_cache:
                    return "READY"

            recipe = self.crafting_recipes[recipe_id]
            duration_seconds = recipe.get("time_requirement", 0)

            # Get timestamp from the crafting entry
            if not timestamp_data:
                return f"~{self.format_time(duration_seconds)}"

            # Extract timestamp from the nested structure
            timestamp_micros = timestamp_data.get("__timestamp_micros_since_unix_epoch__")
            if not timestamp_micros:
                return f"~{self.format_time(duration_seconds)}"

            # Convert timestamp from microseconds to seconds
            start_time = timestamp_micros / 1_000_000
            current_time = time.time()

            # Calculate elapsed and remaining time
            elapsed_time = current_time - start_time
            remaining_time = duration_seconds - elapsed_time

            # Add a small buffer to prevent timer flickering at completion
            if remaining_time <= 1:  # 1 second buffer
                # Cache this entry as READY to prevent restart
                if entry_key:
                    self.ready_items_cache[entry_key] = current_time
                return "READY"

            return self.format_time(remaining_time)

        except Exception as e:
            logging.error(f"Error calculating remaining time: {e}")
            return "Error"

    def format_time(self, seconds: float) -> str:
        """Format seconds into a human-readable time string."""
        if seconds <= 0:
            return "READY"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
