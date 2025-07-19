import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

from client import BitCraft
from claim import Claim
import re


class PassiveCraftingService:
    """Service class to handle passive crafting status operations and caching.

    Provides passive crafting data fetching, grouping, and cache management for BitCraft claims.
    Handles asynchronous data loading, cache validation, and timer overlay data preparation.
    """

    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim):
        """Initialize the PassiveCraftingService with BitCraft client and claim instance.

        Args:
            bitcraft_client: BitCraft client for API/database access
            claim_instance: Claim instance for claim and crafting data
        """
        self.bitcraft_client = bitcraft_client
        self.claim_instance = claim_instance

        # Caching variables
        self.cached_crafting_data: Optional[List[Dict]] = None
        self.last_crafting_fetch_time: Optional[datetime] = None
        self.crafting_cache_duration_minutes = (
            2  # Shorter cache for more real-time data
        )
        self.ready_items_cache = {}  # Cache for items that have reached READY state

        # Use reference data from the claim instance (already loaded)
        self.building_types = self._get_building_types_dict()
        self.crafting_recipes = self._get_crafting_recipes_dict()
        self.item_descriptions = self._get_item_descriptions_dict()

    def _get_building_types_dict(self) -> Dict:
        """Get building type descriptions from claim's reference data.

        Returns:
            Dict: Mapping of building type IDs to descriptions
        """
        if self.claim_instance.building_type_desc_data:
            return {bt["id"]: bt for bt in self.claim_instance.building_type_desc_data}
        return {}

    def _get_crafting_recipes_dict(self) -> Dict:
        """Get crafting recipes from claim's reference data.

        Returns:
            Dict: Mapping of recipe IDs to recipe data
        """
        try:
            # Load crafting recipes using the claim's existing method
            recipes_list = self.claim_instance._load_reference_data(
                "crafting_recipe_desc.json"
            )
            if recipes_list:
                return {recipe["id"]: recipe for recipe in recipes_list}
            return {}
        except Exception as e:
            logging.error(f"Error loading crafting recipes: {e}")
            return {}

    def _get_item_descriptions_dict(self) -> Dict:
        """Get item descriptions from claim's reference data.

        Returns:
            Dict: Mapping of item IDs to item description data
        """
        try:
            # First try to use already loaded data
            if self.claim_instance.item_desc:
                logging.info(
                    f"Using cached item descriptions, count: {len(self.claim_instance.item_desc)}"
                )
                return {item["id"]: item for item in self.claim_instance.item_desc}

            # If not available, try to load it
            logging.warning(
                "item_desc not available in claim instance, trying to load directly"
            )
            items_list = self.claim_instance._load_reference_data("item_desc.json")
            if items_list:
                logging.info(
                    f"Loaded item descriptions directly, count: {len(items_list)}"
                )
                return {item["id"]: item for item in items_list}

            logging.error("Could not load item descriptions from any source")
            return {}
        except Exception as e:
            logging.error(f"Error loading item descriptions: {e}")
            return {}

    def _is_processing_building(
        self, building_description_id: int, building_name: str
    ) -> bool:
        """Check if a building type is one that can do passive crafting.

        Targets: stations, loom, farming field, kiln, smelter, oven.
        Excludes: storage buildings, cargo stockpile.

        Args:
            building_description_id: Building description ID
            building_name: Name of the building
        Returns:
            bool: True if building can do passive crafting, False otherwise
        """
        if not building_name:
            return False

        building_name_lower = building_name.lower()

        # Exclude storage and cargo buildings
        exclude_keywords = ["storage", "cargo stockpile", "stockpile", "bank", "chest"]
        if any(exclude in building_name_lower for exclude in exclude_keywords):
            return False

        # Include stations and specific building types
        target_keywords = [
            "station",  # All types of stations (crafting, farming, etc.)
            "loom",  # Loom
            "farming field",  # Farming field
            "kiln",  # Kiln
            "smelter",  # Smelter
            "oven",  # Oven
            "workbench",  # Workbenches can also do passive crafting
            "tanning tub",  # Tanning tub
        ]

        found_match = any(keyword in building_name_lower for keyword in target_keywords)

        return found_match

    def is_cache_valid(self) -> bool:
        """Check if the cached crafting data is still valid.

        Returns:
            bool: True if cache is valid, False otherwise
        """
        if self.cached_crafting_data is None or self.last_crafting_fetch_time is None:
            logging.info("No cached passive crafting data available")
            return False

        time_since_last_fetch = datetime.now() - self.last_crafting_fetch_time
        cache_duration = timedelta(minutes=self.crafting_cache_duration_minutes)

        is_valid = time_since_last_fetch < cache_duration
        if is_valid:
            remaining_time = cache_duration - time_since_last_fetch
            logging.info(
                f"Using cached passive crafting data (expires in {remaining_time.total_seconds():.0f} seconds)"
            )
        else:
            logging.info(
                f"Cached passive crafting data expired ({time_since_last_fetch.total_seconds():.0f} seconds old)"
            )

        return is_valid

    def clear_cache(self):
        """Clear the passive crafting cache to force a fresh fetch.

        Resets cached crafting data and last fetch timestamp.
        """
        logging.info("Clearing passive crafting cache")
        self.cached_crafting_data = None
        self.last_crafting_fetch_time = None

    def get_cached_data(self) -> Optional[List[Dict]]:
        """Get cached passive crafting data if valid.

        Returns:
            Optional[List[Dict]]: Copy of cached crafting data if valid, else None
        """
        if self.is_cache_valid():
            return (
                self.cached_crafting_data.copy() if self.cached_crafting_data else None
            )
        return None

    def fetch_passive_crafting_async(
        self, callback: Callable[[List[Dict], bool, str, bool], None]
    ):
        """Fetch passive crafting data asynchronously.

        Args:
            callback: Function to call with (display_data, success, message, is_fresh_data)
                - display_data: List of crafting items for display
                - success: True if fetch succeeded, False otherwise
                - message: Status message for UI
                - is_fresh_data: True if data is freshly fetched, False if cached
        """

        def fetch_thread():
            display_data = []
            message = ""
            try:
                claim_id = self.claim_instance.get_claim_id()
                if not claim_id:
                    logging.error(
                        "Claim ID not set for passive crafting fetch. Cannot fetch data."
                    )
                    message = "Claim ID missing for passive crafting."
                    callback(display_data, False, message, False)
                    return

                # First, get all buildings for the claim
                building_states = self.bitcraft_client.fetch_claim_building_state(
                    claim_id
                )
                if not building_states:
                    logging.info("No buildings found for claim")
                    message = "No buildings found for claim."
                    callback(display_data, True, message, True)
                    return

                # Get claim members for user name lookup
                claim_members = self.bitcraft_client.fetch_claim_member_state(claim_id)
                user_lookup = {}
                if claim_members:
                    user_lookup = {
                        member.get("player_entity_id"): member.get("user_name")
                        for member in claim_members
                        if member.get("player_entity_id") and member.get("user_name")
                    }
                    logging.info(
                        f"Loaded {len(user_lookup)} claim members for user name lookup"
                    )
                else:
                    logging.warning("No claim members found for user name lookup")

                # Filter buildings to only processing-capable ones
                processing_buildings = []
                building_nicknames = (
                    self.bitcraft_client.fetch_building_nickname_state()
                )
                nickname_lookup = {}
                if building_nicknames:
                    nickname_lookup = {
                        entry.get("entity_id"): entry.get("nickname")
                        for entry in building_nicknames
                        if entry.get("entity_id") is not None
                    }

                for building in building_states:
                    building_description_id = building.get("building_description_id")
                    entity_id = building.get("entity_id")

                    if building_description_id and entity_id:
                        # Use the claim's method to get the proper building name
                        building_name = self.claim_instance._get_building_name_from_id(
                            building_description_id
                        )
                        if not building_name:
                            building_name = (
                                f"Unknown Building Desc {building_description_id}"
                            )

                        if self._is_processing_building(
                            building_description_id, building_name
                        ):
                            # Add building info to processing buildings list
                            building_info = {
                                "entity_id": entity_id,
                                "building_description_id": building_description_id,
                                "building_name": building_name,
                                "nickname": nickname_lookup.get(entity_id),
                                "building_data": building,
                            }
                            processing_buildings.append(building_info)

                logging.info(
                    f"Found {len(processing_buildings)} processing buildings out of {len(building_states)} total buildings"
                )

                if not processing_buildings:
                    message = (
                        "No processing buildings found (stations, looms, kilns, etc.)."
                    )
                    callback(display_data, True, message, True)
                    return

                # Get passive craft states for all processing buildings
                entity_ids = [
                    building["entity_id"] for building in processing_buildings
                ]
                logging.info(
                    f"Querying passive craft state for entity IDs: {entity_ids[:5]}{'...' if len(entity_ids) > 5 else ''}"
                )
                passive_craft_states = self.bitcraft_client.fetch_passive_craft_state(
                    entity_ids
                )

                if not passive_craft_states:
                    message = f"No active passive crafting found in {len(processing_buildings)} processing buildings."
                    callback(display_data, True, message, True)
                    return

                # Process passive craft data into display format
                # Group by item to sum quantities
                item_groups = {}

                for craft_state in passive_craft_states:
                    craft_entity_id = craft_state.get(
                        "entity_id"
                    )  # This is the craft operation ID
                    building_entity_id = craft_state.get(
                        "building_entity_id"
                    )  # This is the building ID
                    recipe_id = craft_state.get("recipe_id")
                    owner_entity_id = craft_state.get(
                        "owner_entity_id"
                    )  # The user who started the craft

                    # Skip crafting operations by non-claim members
                    if owner_entity_id not in user_lookup:
                        logging.debug(
                            f"Skipping passive craft operation by non-claim member: {owner_entity_id}"
                        )
                        continue

                    # Find the building info using building_entity_id
                    building_info = next(
                        (
                            b
                            for b in processing_buildings
                            if b["entity_id"] == building_entity_id
                        ),
                        None,
                    )
                    if not building_info:
                        logging.debug(
                            f"Could not find building info for building_entity_id: {building_entity_id}"
                        )
                        continue

                    # Get user name from owner_entity_id (we know they're a claim member now)
                    crafter_name = user_lookup.get(
                        owner_entity_id, f"User {owner_entity_id}"
                    )

                    # Get recipe information
                    recipe_info = self.crafting_recipes.get(recipe_id, {})
                    recipe_name = recipe_info.get("name", f"Unknown Recipe {recipe_id}")
                    # Remove any {int} pattern from the recipe name
                    recipe_name = re.sub(r"\{\d+\}", "", recipe_name)

                    # Try to determine what item is being crafted
                    crafted_item_name = "Unknown Item"
                    crafted_item_tier = 0
                    recipe_quantity = 1  # Default quantity per recipe

                    # Look for produced items in recipe
                    produced_items = recipe_info.get("crafted_item_stacks", [])

                    if produced_items and len(produced_items) > 0:
                        # Take the first produced item
                        first_item = produced_items[0]

                        if len(first_item) >= 2:
                            item_id = first_item[0]
                            recipe_quantity = first_item[
                                1
                            ]  # How many this recipe produces

                            item_info = self.item_descriptions.get(item_id, {})
                            crafted_item_name = item_info.get("name", f"Item {item_id}")
                            crafted_item_tier = item_info.get("tier", 0)

                    # Create unique key for grouping (item name + tier)
                    group_key = f"{crafted_item_name}|{crafted_item_tier}"

                    if group_key not in item_groups:
                        # Build display name for the refinery
                        refinery_name = building_info["building_name"]
                        if building_info["nickname"]:
                            refinery_name = f"{building_info['nickname']} ({building_info['building_name']})"

                        item_groups[group_key] = {
                            "Tier": crafted_item_tier,
                            "Name": crafted_item_name,
                            "Quantity": 0,  # Will be summed
                            "Refinery": refinery_name,  # First refinery found
                            "Tag": f"Recipe: {recipe_name}",  # First recipe found
                            "refineries": set([refinery_name]),  # Track all refineries
                            "recipes": set([recipe_name]),  # Track all recipes
                            "crafters": set([crafter_name]),  # Track all crafters
                            "refinery_quantities": {
                                refinery_name: 0
                            },  # Track quantities per refinery
                        }
                    else:
                        # Add this refinery to the set
                        refinery_name = building_info["building_name"]
                        if building_info["nickname"]:
                            refinery_name = f"{building_info['nickname']} ({building_info['building_name']})"
                        item_groups[group_key]["refineries"].add(refinery_name)
                        item_groups[group_key]["recipes"].add(recipe_name)
                        item_groups[group_key]["crafters"].add(crafter_name)
                        # Initialize refinery quantity if not exists
                        if (
                            refinery_name
                            not in item_groups[group_key]["refinery_quantities"]
                        ):
                            item_groups[group_key]["refinery_quantities"][
                                refinery_name
                            ] = 0

                    # Add the quantity for this craft operation to both total and refinery-specific
                    item_groups[group_key]["Quantity"] += recipe_quantity
                    item_groups[group_key]["refinery_quantities"][
                        refinery_name
                    ] += recipe_quantity

                # Convert grouped data to display format
                for group_key, group_data in item_groups.items():
                    # Update refinery field to show count if multiple
                    refineries = list(group_data["refineries"])
                    if len(refineries) == 1:
                        refinery_display = refineries[0]
                    else:
                        refinery_display = (
                            f"{len(refineries)} refineries ({refineries[0]}...)"
                        )

                    # Update recipe field to show count if multiple
                    recipes = list(group_data["recipes"])
                    if len(recipes) == 1:
                        recipe_display = f"Recipe: {recipes[0]}"
                    else:
                        recipe_display = f"{len(recipes)} recipes ({recipes[0]}...)"

                    # Format crafter information
                    crafters = list(group_data["crafters"])
                    crafter_count = len(crafters)

                    display_row = {
                        "Tier": group_data["Tier"],
                        "Name": group_data["Name"],
                        "Quantity": group_data["Quantity"],
                        "Refinery": refinery_display,
                        "Tag": recipe_display,
                        "Crafters": crafter_count,
                        "CrafterDetails": crafters,  # For tooltip/context menu
                        "refineries": refineries,  # Include refineries list for expandable logic
                        "refinery_quantities": group_data[
                            "refinery_quantities"
                        ],  # Include per-refinery quantities
                    }

                    display_data.append(display_row)

                # Cache the results
                self.cached_crafting_data = display_data.copy()
                self.last_crafting_fetch_time = datetime.now()

                logging.info(
                    f"Successfully processed {len(display_data)} active passive crafting operations"
                )
                message = f"Found {len(display_data)} active crafting operations."
                callback(display_data, True, message, True)

            except Exception as e:
                logging.error(f"Error fetching passive crafting data: {e}")
                message = f"Error fetching passive crafting data: {str(e)}"
                callback(display_data, False, message, False)

        # Run in background thread
        thread = threading.Thread(target=fetch_thread, daemon=True)
        thread.start()

    def get_timer_data(self, callback):
        """Fetch current passive crafting data specifically for timer overlay.

        Only returns crafting operations for the current user.
        Args:
            callback: Function to call with (user_crafting, success, message, is_fresh_data)
        """

        def fetch_thread():
            try:
                # Clean up old READY cache entries
                self._cleanup_ready_cache()

                # Get current user's username
                current_username = self.bitcraft_client.player_name
                if not current_username:
                    callback([], False, "No username available", False)
                    return

                claim_id = self.claim_instance.get_claim_id()
                if not claim_id:
                    callback([], False, "Claim ID not available", False)
                    return

                # Get all buildings for the claim
                building_states = self.bitcraft_client.fetch_claim_building_state(
                    claim_id
                )
                if not building_states:
                    callback([], False, "No buildings found for claim", False)
                    return

                # Get claim members for user lookup
                claim_members = self.bitcraft_client.fetch_claim_member_state(claim_id)
                user_lookup = {}
                current_user_entity_id = None

                if claim_members:
                    user_lookup = {
                        member.get("player_entity_id"): member.get("user_name")
                        for member in claim_members
                        if member.get("player_entity_id") and member.get("user_name")
                    }

                    # Find current user's entity ID
                    for member in claim_members:
                        if member.get("user_name") == current_username:
                            current_user_entity_id = member.get("player_entity_id")
                            break

                if not current_user_entity_id:
                    callback(
                        [],
                        False,
                        f"Current user '{current_username}' not found in claim members",
                        False,
                    )
                    return

                # Filter processing buildings
                processing_buildings = []
                building_nicknames = (
                    self.bitcraft_client.fetch_building_nickname_state()
                )
                nickname_lookup = {}
                if building_nicknames:
                    nickname_lookup = {
                        entry.get("entity_id"): entry.get("nickname")
                        for entry in building_nicknames
                        if entry.get("entity_id") is not None
                    }

                for building in building_states:
                    building_description_id = building.get("building_description_id")
                    entity_id = building.get("entity_id")

                    if building_description_id and entity_id:
                        building_name = self.claim_instance._get_building_name_from_id(
                            building_description_id
                        )
                        if not building_name:
                            building_name = (
                                f"Unknown Building Desc {building_description_id}"
                            )

                        if self._is_processing_building(
                            building_description_id, building_name
                        ):
                            building_info = {
                                "entity_id": entity_id,
                                "building_description_id": building_description_id,
                                "building_name": building_name,
                                "nickname": nickname_lookup.get(entity_id),
                                "building_data": building,
                            }
                            processing_buildings.append(building_info)

                if not processing_buildings:
                    callback([], False, "No processing buildings found", False)
                    return

                # Get passive craft states
                entity_ids = [
                    building["entity_id"] for building in processing_buildings
                ]
                passive_craft_states = self.bitcraft_client.fetch_passive_craft_state(
                    entity_ids
                )

                if not passive_craft_states:
                    callback([], False, "No active passive crafting found", False)
                    return

                # Filter for current user and group by item type
                item_groups = {}
                for craft_state in passive_craft_states:
                    owner_entity_id = craft_state.get("owner_entity_id")

                    # Only include crafting operations by the current user
                    if owner_entity_id != current_user_entity_id:
                        continue

                    building_entity_id = craft_state.get("building_entity_id")
                    recipe_id = craft_state.get("recipe_id")

                    # Find building info
                    building_info = next(
                        (
                            b
                            for b in processing_buildings
                            if b["entity_id"] == building_entity_id
                        ),
                        None,
                    )
                    if not building_info:
                        continue

                    # Get recipe information
                    recipe_info = self.crafting_recipes.get(recipe_id, {})
                    recipe_name = recipe_info.get("name", f"Unknown Recipe {recipe_id}")
                    recipe_name = re.sub(
                        r"\{\d+\}", "", recipe_name
                    )  # Remove {int} patterns

                    # Get crafted item details
                    crafted_item_name = "Unknown Item"
                    crafted_item_tier = 0
                    recipe_quantity = 1

                    produced_items = recipe_info.get("crafted_item_stacks", [])
                    if produced_items and len(produced_items) > 0:
                        first_item = produced_items[0]
                        if len(first_item) >= 2:
                            item_id = first_item[0]
                            recipe_quantity = first_item[1]

                            item_info = self.item_descriptions.get(item_id, {})
                            crafted_item_name = item_info.get("name", f"Item {item_id}")
                            crafted_item_tier = item_info.get("tier", 0)

                    # Build refinery name
                    refinery_name = building_info["building_name"]
                    if building_info["nickname"]:
                        refinery_name = f"{building_info['nickname']} ({building_info['building_name']})"

                    # Calculate remaining time
                    remaining_time = self.calculate_remaining_time(craft_state)
                    is_completed = remaining_time == "READY"

                    # Create group key for same item type
                    group_key = f"{crafted_item_name}|{crafted_item_tier}"

                    if group_key not in item_groups:
                        item_groups[group_key] = {
                            "name": crafted_item_name,
                            "tier": crafted_item_tier,
                            "total_quantity": 0,
                            "refineries": set(),
                            "recipes": set(),
                            "children": [],
                            "completed_count": 0,
                            "total_count": 0,
                            "max_remaining_time": 0,
                            "max_remaining_time_str": "0s",
                        }

                    group = item_groups[group_key]
                    group["total_quantity"] += recipe_quantity
                    group["refineries"].add(refinery_name)
                    group["recipes"].add(recipe_name)
                    group["total_count"] += 1

                    if is_completed:
                        group["completed_count"] += 1

                    # Track the highest remaining time for the parent
                    if (
                        remaining_time != "READY"
                        and remaining_time != "Error"
                        and remaining_time != "Unknown"
                    ):
                        remaining_seconds = self.parse_time_to_seconds(remaining_time)
                        if remaining_seconds > group["max_remaining_time"]:
                            group["max_remaining_time"] = remaining_seconds
                            group["max_remaining_time_str"] = remaining_time

                    # Add child entry
                    group["children"].append(
                        {
                            "name": crafted_item_name,
                            "tier": crafted_item_tier,
                            "quantity": recipe_quantity,
                            "refinery": refinery_name,
                            "tag": f"Recipe: {recipe_name}",
                            "remaining_time": remaining_time,
                            "completed": "✓" if is_completed else "",
                            "is_child": True,
                        }
                    )

                # Convert groups to hierarchical structure
                user_crafting = []
                for group_key, group in item_groups.items():
                    # Build parent row
                    refineries = list(group["refineries"])
                    recipes = list(group["recipes"])

                    refinery_display = (
                        refineries[0]
                        if len(refineries) == 1
                        else f"{len(refineries)} refineries"
                    )
                    recipe_display = (
                        f"Recipe: {recipes[0]}"
                        if len(recipes) == 1
                        else f"{len(recipes)} recipes"
                    )

                    parent_row = {
                        "name": group["name"],
                        "tier": group["tier"],
                        "quantity": group["total_quantity"],
                        "refinery": refinery_display,
                        "tag": recipe_display,
                        "remaining_time": (
                            group["max_remaining_time_str"]
                            if group["max_remaining_time"] > 0
                            else "READY"
                        ),
                        "completed": f"{group['completed_count']}/{group['total_count']}",
                        "is_parent": True,
                        "children": group["children"],
                    }

                    user_crafting.append(parent_row)

                callback(
                    user_crafting,
                    True,
                    f"Found {len(user_crafting)} item groups with {sum(g['total_count'] for g in item_groups.values())} total operations.",
                    True,
                )

            except Exception as e:
                logging.error(f"Error fetching timer data: {e}")
                callback([], False, f"Error fetching timer data: {str(e)}", False)

        # Run in background thread
        thread = threading.Thread(target=fetch_thread, daemon=True)
        thread.start()

    def _cleanup_ready_cache(self):
        """Clean up old entries from the ready items cache."""
        current_time = time.time()
        # Remove entries older than 10 minutes
        cutoff_time = current_time - 600  # 10 minutes in seconds

        keys_to_remove = []
        for key, cached_time in self.ready_items_cache.items():
            if cached_time < cutoff_time:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.ready_items_cache[key]

    def calculate_remaining_time(self, crafting_entry):
        """Calculate remaining time for a crafting operation.

        Args:
            crafting_entry: Crafting operation entry dict
        Returns:
            str: Formatted time string or "READY" if completed
        """
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
                timestamp_micros = timestamp_data.get(
                    "__timestamp_micros_since_unix_epoch__"
                )
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
            timestamp_micros = timestamp_data.get(
                "__timestamp_micros_since_unix_epoch__"
            )
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

    def format_time(self, seconds):
        """Format seconds into a human-readable time string.

        Args:
            seconds: Number of seconds to format
        Returns:
            str: Formatted time string (e.g., '1h 30m 45s')
        """
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

    def parse_time_to_seconds(self, time_str: str) -> int:
        """Parse time string (e.g., '1h 30m 45s') to seconds for comparison.

        Args:
            time_str: Time string to parse
        Returns:
            int: Number of seconds represented by the time string
        """
        if (
            not time_str
            or time_str == "READY"
            or time_str == "Error"
            or time_str == "Unknown"
        ):
            return 0

        try:
            total_seconds = 0
            parts = time_str.split()

            for part in parts:
                if part.startswith("~"):
                    part = part[1:]  # Remove ~ prefix
                if part.endswith("h"):
                    total_seconds += int(part[:-1]) * 3600
                elif part.endswith("m"):
                    total_seconds += int(part[:-1]) * 60
                elif part.endswith("s"):
                    total_seconds += int(part[:-1])

            return total_seconds
        except Exception:
            return 0
