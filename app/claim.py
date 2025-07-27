import logging

# We no longer need sqlite3, os, or json imports here, as this class
# should not be directly accessing the filesystem or database.


class Claim:
    """
    Represents and processes data for a specific BitCraft claim.

    This class holds information about a claim's properties, buildings, and
    inventory. It relies on a client instance for data fetching and pre-loaded
    reference data for describing items and buildings.
    """

    def __init__(self, client, reference_data: dict):
        """
        Initializes the Claim instance with its dependencies.

        Args:
            client: An instance of the BitCraft client for making API calls.
            reference_data (dict): A dictionary containing all static game data
                                 (e.g., item_desc, building_desc).
        """
        # --- Dependencies ---
        self.client = client

        # --- Claim State Attributes ---
        self.claim_name = None
        self.claim_id = None
        self.owner_id = None
        self.owner_building_id = None
        self.supplies = 0
        self.size = 0
        self.treasury = 0
        self.buildings = {}

        # --- Injected Reference Data ---
        # Unpack the provided reference data into instance attributes
        self.resource_desc = reference_data.get("resource_desc", [])
        self.item_desc = reference_data.get("item_desc", [])
        self.cargo_desc = reference_data.get("cargo_desc", [])
        self.building_desc_data = reference_data.get("building_desc", [])
        self.building_function_type_mapping_desc_data = reference_data.get("type_desc_ids", [])
        self.building_type_desc_data = reference_data.get("building_types", [])

    def fetch_and_set_claim_id_by_user(self, user_id: str) -> str | None:
        """
        Fetches the claim ID for a given user ID using the client and sets it on the instance.

        Args:
            user_id (str): The user's ID.

        Returns:
            The claim ID if found, otherwise None.
        """
        if not user_id:
            logging.error("User ID is missing for claim ID fetch.")
            return None

        sanitized_user_id = str(user_id).replace("'", "''")
        query_string = f"SELECT * FROM claim_member_state WHERE player_entity_id = '{sanitized_user_id}';"

        try:
            results = self.client.query(query_string)
            if results and isinstance(results, list) and len(results) > 0:
                claim_id = results[0].get("claim_entity_id")
                if claim_id:
                    self.claim_id = claim_id
                    logging.info(f"Claim ID for user {user_id} found and set: {claim_id}")
                    return claim_id

            logging.warning(f"No claim ID found for user {user_id}.")
            return None
        except RuntimeError as e:
            logging.error(f"Failed to retrieve claim ID due to a client runtime error: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred while fetching claim ID: {e}")
            return None

    def set_buildings(self, buildings: list[dict]):
        """
        Processes and categorizes building data for the claim.
        """
        logging.debug("Processing and categorizing buildings for the claim.")
        self.buildings = {}

        # Create dictionaries for faster lookups
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
                continue

            building_name = building_desc_lookup.get(building_description_id, "Unknown Building")
            building["name"] = building_name

            building_type_id = type_mapping_lookup.get(building_description_id)
            building_type_description = "Unknown Type"
            if building_type_id:
                building_type_description = building_type_desc_lookup.get(building_type_id, "Unknown Type")

            if building_type_description not in self.buildings:
                self.buildings[building_type_description] = []
            self.buildings[building_type_description].append(building)

    def get_inventory(self) -> dict:
        """
        Consolidates and returns the inventory from all storage buildings.
        """
        if not self.buildings:
            logging.warning("Cannot get inventory, no buildings have been set.")
            return {}

        logging.info("Consolidating resources from claim inventory.")

        # Create a combined lookup for all item types
        combined_item_lookup = {}
        for data_list in [self.resource_desc, self.item_desc, self.cargo_desc]:
            if data_list:
                for item in data_list:
                    if "id" in item:
                        combined_item_lookup[item["id"]] = item

        collection = {}
        storage_buildings = self.buildings.get("Storage", []) + self.buildings.get("Cargo Stockpile", [])

        for building in storage_buildings:
            # --- FIX: Add a safety check for the inventory key ---
            inventory = building.get("inventory")
            if not inventory:
                continue  # Skip this building if it has no inventory data

            container_name = building.get("nickname") or building.get("name", "Unknown Storage")

            # Now it's safe to access "pockets"
            for slot in inventory.get("pockets", []):
                try:
                    # Assuming the format is [slot_index, [item_id, quantity]]
                    item_id = slot[1][0]
                    quantity = int(slot[1][1])

                    if item_id in combined_item_lookup:
                        item_data = combined_item_lookup[item_id]
                        item_name = item_data.get("name", "Unknown Item")

                        if item_name not in collection:
                            collection[item_name] = {
                                "quantity": 0,
                                "name": item_name,
                                "tier": item_data.get("tier", 0),
                                "tag": item_data.get("tag", ""),
                                "containers": {},
                            }

                        collection[item_name]["quantity"] += quantity

                        # Track quantity per container
                        if container_name not in collection[item_name]["containers"]:
                            collection[item_name]["containers"][container_name] = 0
                        collection[item_name]["containers"][container_name] += quantity

                except (IndexError, TypeError, ValueError) as e:
                    logging.debug(f"Skipping malformed inventory slot: {slot}. Reason: {e}")
                    continue

        return collection
