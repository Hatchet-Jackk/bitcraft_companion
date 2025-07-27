import sqlite3
import logging
import os
import json


class Claim:
    """Represents a BitCraft claim with buildings, inventory, and metadata.

    This class manages claim data including buildings categorized by type,
    consolidated inventory from storage buildings, and claim properties
    like size, treasury, and ownership information.

    Attributes:
        claim_name (str): Display name of the claim.
        claim_id (str): Unique identifier for the claim.
        owner_id (str): ID of the claim owner.
        owner_building_id (str): ID of the main/owner building.
        supplies (int): Available supplies in the claim.
        size (int): Size of the claim in tiles.
        treasury (int): Treasury amount for the claim.
        buildings (dict): Buildings grouped by functional type.
    """

    _resource_desc = None
    _item_desc = None
    _cargo_desc = None
    _building_desc_data = None
    _building_function_type_mapping_desc_data = None
    _building_type_desc_data = None

    def __init__(self):
        """Initialize a new Claim instance and load reference data."""

    _resource_desc = None
    _item_desc = None
    _cargo_desc = None
    _building_desc_data = None
    _building_function_type_mapping_desc_data = None
    _building_type_desc_data = None

    def __init__(self):
        self.claim_name = None
        self.claim_id = None
        self.owner_id = None
        self.owner_building_id = None
        self.supplies = None
        self.size = None
        self.treasury = None
        self.buildings = {}

        # Load reference data once for the class
        if Claim._resource_desc is None:
            Claim._resource_desc = self._load_reference_data("resource_desc")
        self.resource_desc = Claim._resource_desc

        if Claim._item_desc is None:
            Claim._item_desc = self._load_reference_data("item_desc")
        self.item_desc = Claim._item_desc

        if Claim._cargo_desc is None:
            Claim._cargo_desc = self._load_reference_data("cargo_desc")
        self.cargo_desc = Claim._cargo_desc

        if Claim._building_desc_data is None:
            Claim._building_desc_data = self._load_reference_data("building_desc")
        self.building_desc_data = Claim._building_desc_data

        if Claim._building_function_type_mapping_desc_data is None:
            Claim._building_function_type_mapping_desc_data = self._load_reference_data("type_desc_ids")
        self.building_function_type_mapping_desc_data = Claim._building_function_type_mapping_desc_data

        if Claim._building_type_desc_data is None:
            Claim._building_type_desc_data = self._load_reference_data("building_types")
        self.building_type_desc_data = Claim._building_type_desc_data

    def _load_reference_data(self, table: str) -> list[dict] | None:
        """Load reference data from the SQLite database by table name. Only player_data.json is file-based."""
        if table == "player_data":
            file_path = os.path.join(self._get_data_directory(), "player_data.json")
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading player_data.json: {e}")
                return None

        db_path = os.path.join(os.path.dirname(__file__), "data", "data.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]

            # Try to decode any string field as JSON (list/dict)
            for row in result:
                for key, value in row.items():
                    if isinstance(value, str):
                        try:
                            decoded = json.loads(value)
                            if isinstance(decoded, (list, dict)):
                                row[key] = decoded
                        except Exception:
                            pass
            conn.close()
            return result
        except Exception as e:
            logging.error(f"Error loading reference data from DB for table {table}: {e}")
            return None

    def _get_building_name_from_id(self, building_description_id: int) -> str | None:
        """Get building name from its description ID.

        Args:
            building_description_id (int): The building description ID to look up.

        Returns:
            str | None: Building name if found, None otherwise.
        """
        if self.building_desc_data:
            for b_desc in self.building_desc_data:
                if b_desc.get("id") == building_description_id:
                    return b_desc.get("name")
        return None

    def _get_building_type_id_from_desc_id(self, building_description_id: int) -> int | None:
        """Get building type ID from its description ID.

        Args:
            building_description_id (int): The building description ID to look up.

        Returns:
            int | None: Building type ID if found, None otherwise.
        """
        if self.building_function_type_mapping_desc_data:
            for mapping in self.building_function_type_mapping_desc_data:
                if building_description_id in mapping.get("desc_ids", []):
                    return mapping.get("type_id")
        return None

    def _get_building_type_description_from_type_id(self, type_id: int) -> str | None:
        """Get building type description from type ID.

        Args:
            type_id (int): The building type ID to look up.

        Returns:
            str | None: Building type description (e.g., "Storage", "Housing") if found, None otherwise.
        """
        if self.building_type_desc_data:
            for type_desc in self.building_type_desc_data:
                if type_desc.get("id") == type_id:
                    return type_desc.get("name")
        return None

    def set_value(self, key, value):
        """Set a claim attribute dynamically.

        Args:
            key (str): The attribute name to set.
            value: The value to assign to the attribute.
        """
        if hasattr(self, key):
            setattr(self, key, value)
            logging.debug(f"Claim {key} set to: {value}")
        else:
            logging.warning(f"Attempted to set unknown attribute: {key}. Consider adding it to __init__.")

    def set_claim_name(self, claim_name: str):
        self.claim_name = claim_name
        logging.debug(f"Claim name set to: {self.claim_name}")

    def get_claim_name(self) -> str | None:
        logging.debug(f"Fetching claim name: {self.claim_name}")
        return self.claim_name

    def set_claim_id(self, claim_id: str):
        logging.debug(f"Claim ID set to: {claim_id}")
        self.claim_id = claim_id

    def get_claim_id(self) -> str | None:
        logging.debug(f"Fetching claim ID: {self.claim_id}")
        return self.claim_id

    def set_owner_id(self, owner_id: str):
        logging.debug(f"Owner ID set to: {owner_id}")
        self.owner_id = owner_id

    def get_owner_id(self) -> str | None:
        logging.debug(f"Fetching owner ID: {self.owner_id}")
        return self.owner_id

    def set_owner_building_id(self, owner_building_id: str):
        logging.debug(f"Owner Building ID set to: {owner_building_id}")
        self.owner_building_id = owner_building_id

    def get_owner_building_id(self) -> str | None:
        logging.debug(f"Fetching owner building ID: {self.owner_building_id}")
        return self.owner_building_id

    def set_supplies(self, supplies: int):
        logging.debug(f"Supplies set to: {supplies}")
        self.supplies = supplies

    def get_supplies(self) -> int | None:
        logging.debug(f"Fetching supplies: {self.supplies}")
        return self.supplies

    def set_buildings(self, buildings: list[dict]):
        """Set building data for the claim, categorizing by functional type.

        Processes building data and groups them by their functional type
        (e.g., "Storage", "Housing"). Looks up building names and type
        descriptions using reference data.

        Args:
            buildings (list[dict]): List of building dictionaries containing
                building data including building_description_id.
        """
        logging.debug(f"Processing buildings for claim")
        self.buildings = {}

        # Create dictionaries for faster lookup of building descriptions and types
        building_desc_lookup = {b.get("id"): b.get("name") for b in self.building_desc_data if b.get("id") is not None}
        type_mapping_lookup = {
            desc_id: mapping.get("type_id")
            for mapping in self.building_function_type_mapping_desc_data
            if mapping.get("desc_ids")
            for desc_id in mapping["desc_ids"]
        }
        building_type_desc_lookup = {t.get("id"): t.get("name") for t in self.building_type_desc_data if t.get("id") is not None}

        for building in buildings:
            building_description_id = building.get("building_description_id")
            if building_description_id is None:
                logging.warning(f"Building data missing 'building_description_id': {building.get('entity_id', 'Unknown Entity')}")
                continue

            # Optimized lookup for building name
            building_name = building_desc_lookup.get(
                building_description_id,
                f"Unknown Building (ID:{building_description_id})",
            )
            if (
                building_name.startswith("Unknown Building")
                and building_name == f"Unknown Building (ID:{building_description_id})"
            ):
                logging.warning(f"Could not find name for building_description_id: {building_description_id}")
            building["name"] = building_name  # Add name to the building dict

            # Optimized lookup for building type ID and description
            building_type_id = type_mapping_lookup.get(building_description_id)
            building_type_description = "Unknown Type"
            if building_type_id is not None:
                building_type_description = building_type_desc_lookup.get(building_type_id, "Unknown Type")
                if building_type_description == "Unknown Type":
                    logging.warning(
                        f"Could not find type description for type ID: {building_type_id} (from desc ID: {building_description_id})"
                    )
            else:
                logging.warning(f"Could not find type ID for building_description_id: {building_description_id}")

            # Store the type description directly in the building dictionary
            building["_type_description"] = building_type_description

            # Group buildings by their functional type description
            if building_type_description not in self.buildings:
                self.buildings[building_type_description] = []
            self.buildings[building_type_description].append(building)
        logging.debug(f"Finished processing buildings. Stored {len(self.buildings)} types of buildings.")

    def get_buildings(self) -> dict:
        return self.buildings

    def set_size(self, size: int):
        logging.debug(f"Size set to: {size}")
        self.size = size

    def get_size(self) -> int | None:
        logging.debug(f"Fetching size: {self.size}")
        return self.size

    def set_treasury(self, treasury: int):
        logging.debug(f"Treasury set to: {treasury}")
        self.treasury = treasury

    def get_treasury(self) -> int | None:
        logging.debug(f"Fetching treasury: {self.treasury}")
        return self.treasury

    def get_inventory(self) -> dict:
        """Process building inventories and return consolidated item collection.

        Consolidates inventories from all storage-type buildings in the claim
        and returns a dictionary of items with their quantities and metadata.

        Returns:
            dict: Dictionary where keys are item IDs and values are item details
                including 'quantity', 'name', 'tier', 'tag', and 'containers'.
                The 'containers' field shows which specific storage buildings
                contain each item and their quantities.
        """
        if not self.buildings:
            logging.warning("No buildings found in claim when trying to get inventory.")
            return {}

        logging.info("Fetching resources from claim inventory.")

        # Ensure reference data is loaded
        if self.resource_desc is None or self.item_desc is None:
            logging.error("Resource or item description data not loaded. Cannot process inventory.")
            return {}

        # Create a dict of lists to avoid overwriting items with the same ID from different sources
        combined_item_lookup = {}
        for data in [self.resource_desc, self.item_desc, self.cargo_desc]:
            if data:
                for entry in data:
                    if "id" in entry:
                        combined_item_lookup.setdefault(entry["id"], []).append(entry)

        collection = {}
        # Define columns to exclude from the item details.
        # This list is moved outside the loop for efficiency.
        EXCLUDE_COLUMNS = {
            "rarity",
            "compendium_entry",
            "convert_to_on_durability_zero",
            "despawn_time",
            "durability",
            "enemy_params_id",
            "flattenable",
            "footprint",
            "ignore_damage",
            "item_list_id",
            "max_health",
            "model_asset_name",
            "not_respawning",
            "on_destroy_yield",
            "on_destroy_yield_resource_id",
            "scheduled_respawn_time",
            "secondary_knowledge_id",
            "spawn_priority",
            "id",
        }

        # Iterate only through 'Storage' type buildings
        for building in self.buildings.get("Storage", []) + self.buildings.get("Cargo Stockpile", []):
            # Get building name and nickname for display
            building_name = building.get("building_name", "Unknown Building")
            building_nickname = building.get("nickname")

            # Create display name for container
            if building_nickname:
                if building_name and building_name != "Unknown Building":
                    container_name = f"{building_nickname} ({building_name})"
                else:
                    container_name = building_nickname
            else:
                if building_name and building_name != "Unknown Building":
                    container_name = building_name
                else:
                    container_name = "Storage Container"

            for slot in building.get("inventory", {}).get("pockets", []):
                try:
                    inv_data = slot[1][1]
                    if not isinstance(inv_data, list) or len(inv_data) < 2:
                        logging.debug(f"Invalid inventory slot data format (expected list of at least 2): {slot}")
                        continue

                    inv_id = inv_data[0]
                    inv_num = inv_data[1]

                    # Optimize quantity conversion
                    if isinstance(inv_num, list) or not isinstance(inv_num, (int, float)):
                        inv_num = 0

                    found_item_datas = combined_item_lookup.get(inv_id, [])

                    if found_item_datas:
                        # If multiple entries exist for the same ID, process each
                        for found_item_data in found_item_datas:
                            # Use a tuple key to distinguish between sources if needed
                            source_key = (inv_id, found_item_data.get("tag", ""), found_item_data.get("name", ""))
                            if source_key not in collection:
                                item_details = {
                                    key: value for key, value in found_item_data.items() if key not in EXCLUDE_COLUMNS
                                }
                                item_details["name"] = item_details.get("name", "Unknown Item")
                                item_details["tier"] = item_details.get("tier", 0)
                                tags_from_data = found_item_data.get("tag")
                                item_details["tag"] = tags_from_data if isinstance(tags_from_data, str) else ""
                                item_details["quantity"] = 0
                                item_details["containers"] = {}
                                collection[source_key] = item_details

                            # Add to overall quantity
                            collection[source_key]["quantity"] += inv_num

                            # Track container-specific quantities
                            if container_name not in collection[source_key]["containers"]:
                                collection[source_key]["containers"][container_name] = 0
                            collection[source_key]["containers"][container_name] += inv_num
                    else:
                        logging.debug(f"Inventory item ID {inv_id} not found in reference data.")

                except (IndexError, TypeError) as e:
                    logging.error(f"Invalid item data structure or type error in slot {slot}. Error: {e}")
                    continue
                except Exception as e:
                    logging.error(f"An unexpected error occurred while processing inventory slot {slot}: {e}")
                    continue

        return collection
