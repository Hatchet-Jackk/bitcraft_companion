# claim.py
import logging
import os
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class Claim:
    # Class-level attributes to cache reference data
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
            Claim._resource_desc = self._load_reference_data('resource_desc.json')
        self.resource_desc = Claim._resource_desc

        if Claim._item_desc is None:
            Claim._item_desc = self._load_reference_data('item_desc.json')
        self.item_desc = Claim._item_desc

        if Claim._cargo_desc is None:
            Claim._cargo_desc = self._load_reference_data('cargo_desc.json')
        self.cargo_desc = Claim._cargo_desc

        if Claim._building_desc_data is None:
            Claim._building_desc_data = self._load_reference_data('building_desc.json')
        self.building_desc_data = Claim._building_desc_data

        if Claim._building_function_type_mapping_desc_data is None:
            Claim._building_function_type_mapping_desc_data = self._load_reference_data('building_function_type_mapping_desc.json')
        self.building_function_type_mapping_desc_data = Claim._building_function_type_mapping_desc_data

        if Claim._building_type_desc_data is None:
            Claim._building_type_desc_data = self._load_reference_data('building_type_desc.json')
        self.building_type_desc_data = Claim._building_type_desc_data


    def _load_reference_data(self, filename: str) -> dict | list | None:
        """Loads reference data from a JSON file, handles caching."""
        file_path = os.path.join(os.path.dirname(__file__), 'references', filename)
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                logging.debug(f"Loaded reference data from {filename}")
                return data
        except FileNotFoundError:
            logging.error(f"Reference file not found: {filename}")
            return None
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from: {filename}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred loading {filename}: {e}")
            return None

    def _get_building_name_from_id(self, building_description_id: int) -> str | None:
        """
        Looks up the building name using its description ID from the loaded reference data.
        """
        if self.building_desc_data:
            for b_desc in self.building_desc_data:
                if b_desc.get('id') == building_description_id:
                    return b_desc.get('name')
        return None

    def _get_building_type_id_from_desc_id(self, building_description_id: int) -> int | None:
        """
        Looks up the building type ID using its description ID from the loaded reference data.
        """
        if self.building_function_type_mapping_desc_data:
            for mapping in self.building_function_type_mapping_desc_data:
                if building_description_id in mapping.get('desc_ids', []):
                    return mapping.get('type_id')
        return None

    def _get_building_type_description_from_type_id(self, type_id: int) -> str | None:
        """
        Looks up the building type description (e.g., "Storage", "Housing")
        using its type ID from the loaded reference data.
        """
        if self.building_type_desc_data:
            for type_desc in self.building_type_desc_data:
                if type_desc.get('id') == type_id:
                    return type_desc.get('name') # Assuming 'name' is the descriptive string
        return None

    def set_value(self, key, value):
        """Generic setter for claim attributes."""
        if hasattr(self, key):
            setattr(self, key, value)
            logging.info(f"Claim {key} set to: {value}")
        else:
            logging.warning(f"Attempted to set unknown attribute: {key}. Consider adding it to __init__.")

    def set_claim_name(self, claim_name: str):
        self.claim_name = claim_name
        logging.info(f"Claim name set to: {self.claim_name}")

    def get_claim_name(self) -> str | None:
        logging.info(f"Fetching claim name: {self.claim_name}")
        return self.claim_name

    def set_claim_id(self, claim_id: str):
        logging.info(f"Claim ID set to: {claim_id}")
        self.claim_id = claim_id

    def get_claim_id(self) -> str | None:
        logging.info(f"Fetching claim ID: {self.claim_id}")
        return self.claim_id

    def set_owner_id(self, owner_id: str):
        logging.info(f"Owner ID set to: {owner_id}")
        self.owner_id = owner_id

    def get_owner_id(self) -> str | None:
        logging.info(f"Fetching owner ID: {self.owner_id}")
        return self.owner_id

    def set_owner_building_id(self, owner_building_id: str):
        logging.info(f"Owner Building ID set to: {owner_building_id}")
        self.owner_building_id = owner_building_id

    def get_owner_building_id(self) -> str | None:
        logging.info(f"Fetching owner building ID: {self.owner_building_id}")
        return self.owner_building_id

    def set_supplies(self, supplies: int):
        logging.info(f"Supplies set to: {supplies}")
        self.supplies = supplies

    def get_supplies(self) -> int | None:
        logging.info(f"Fetching supplies: {self.supplies}")
        return self.supplies

    def set_buildings(self, buildings: list[dict]):
        """
        Sets building data for the claim, categorizing them by their functional type (e.g., "Storage").
        It looks up the building name and its type description using reference IDs.
        """
        logging.debug(f"Processing buildings for claim")
        self.buildings = {} # Reset to avoid duplicates on re-setting

        # Create dictionaries for faster lookup of building descriptions and types
        building_desc_lookup = {b.get('id'): b.get('name') for b in self.building_desc_data if b.get('id') is not None}
        type_mapping_lookup = {
            desc_id: mapping.get('type_id')
            for mapping in self.building_function_type_mapping_desc_data if mapping.get('desc_ids')
            for desc_id in mapping['desc_ids']
        }
        building_type_desc_lookup = {t.get('id'): t.get('name') for t in self.building_type_desc_data if t.get('id') is not None}

        for building in buildings:
            building_description_id = building.get("building_description_id")
            if building_description_id is None:
                logging.warning(f"Building data missing 'building_description_id': {building}")
                continue

            # Optimized lookup for building name
            building_name = building_desc_lookup.get(building_description_id, f"Unknown Building (ID:{building_description_id})")
            if building_name.startswith("Unknown Building") and building_name == f"Unknown Building (ID:{building_description_id})":
                 logging.warning(f"Could not find name for building_description_id: {building_description_id} in {building}")
            building['name'] = building_name # Add name to the building dict

            # Optimized lookup for building type ID and description
            building_type_id = type_mapping_lookup.get(building_description_id)
            building_type_description = "Unknown Type"
            if building_type_id is not None:
                building_type_description = building_type_desc_lookup.get(building_type_id, "Unknown Type")
                if building_type_description == "Unknown Type":
                    logging.warning(f"Could not find type description for type ID: {building_type_id} (from desc ID: {building_description_id})")
            else:
                logging.warning(f"Could not find type ID for building_description_id: {building_description_id}")

            # Store the type description directly in the building dictionary
            building['_type_description'] = building_type_description

            # Group buildings by their functional type description
            if building_type_description not in self.buildings:
                self.buildings[building_type_description] = []
            self.buildings[building_type_description].append(building)
        logging.debug(f"Finished processing buildings. Stored {len(self.buildings)} types of buildings.")

    def get_buildings(self) -> dict:
        return self.buildings

    def set_size(self, size: int):
        logging.info(f"Size set to: {size}")
        self.size = size

    def get_size(self) -> int | None:
        logging.info(f"Fetching size: {self.size}")
        return self.size

    def set_treasury(self, treasury: int):
        logging.info(f"Treasury set to: {treasury}")
        self.treasury = treasury

    def get_treasury(self) -> int | None:
        logging.info(f"Fetching treasury: {self.treasury}")
        return self.treasury

    def get_inventory(self) -> dict:
        """
        Processes building inventories to return a consolidated collection of items.
        Returns a dictionary where keys are item IDs and values are item details
        including 'quantity', 'name', 'tier', 'tag'.
        """
        if not self.buildings:
            logging.warning("No buildings found in claim when trying to get inventory.")
            return {}

        logging.info("Fetching resources from claim inventory.")

        # Ensure reference data is loaded
        if self.resource_desc is None or self.item_desc is None:
            logging.error("Resource or item description data not loaded. Cannot process inventory.")
            return {}

        # Create combined lookup for resource_map and item_map for O(1) average access
        combined_item_lookup = {}
        if self.resource_desc:
            combined_item_lookup.update({r["id"]: r for r in self.resource_desc if "id" in r})
        if self.item_desc:
            combined_item_lookup.update({i["id"]: i for i in self.item_desc if "id" in i})
        if self.cargo_desc:
            combined_item_lookup.update({c["id"]: c for c in self.cargo_desc if "id" in c})


        collection = {}
        # Define columns to exclude from the item details.
        # This list is moved outside the loop for efficiency.
        EXCLUDE_COLUMNS = {
            "rarity", 'compendium_entry', 'convert_to_on_durability_zero',
            'despawn_time', 'durability', 'enemy_params_id', 'flattenable',
            'footprint', 'ignore_damage', 'item_list_id', 'max_health',
            'model_asset_name', 'not_respawning', 'on_destroy_yield',
            'on_destroy_yield_resource_id', 'scheduled_respawn_time',
            'secondary_knowledge_id', 'spawn_priority', 'id'
        }


        # Iterate only through 'Storage' type buildings
        for building in self.buildings.get("Storage", []) + self.buildings.get("Cargo Stockpile", []):
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

                    found_item_data = combined_item_lookup.get(inv_id)

                    if found_item_data:
                        if inv_id not in collection:
                            # Use dictionary comprehension for faster creation of item_details
                            item_details = {
                                key: value for key, value in found_item_data.items()
                                if key not in EXCLUDE_COLUMNS
                            }

                            item_details["name"] = item_details.get("name", "Unknown Item")
                            item_details["tier"] = item_details.get("tier", 0)

                            # Handle tag consistently
                            tags_from_data = found_item_data.get("tag")
                            item_details["tag"] = tags_from_data if isinstance(tags_from_data, str) else ""

                            item_details["quantity"] = 0
                            collection[inv_id] = item_details
                        collection[inv_id]["quantity"] += inv_num
                    else:
                        logging.debug(f"Inventory item ID {inv_id} not found in reference data.")

                except (IndexError, TypeError) as e:
                    logging.error(f"Invalid item data structure or type error in slot {slot}. Error: {e}")
                    continue
                except Exception as e:
                    logging.error(f"An unexpected error occurred while processing inventory slot {slot}: {e}")
                    continue

        return collection