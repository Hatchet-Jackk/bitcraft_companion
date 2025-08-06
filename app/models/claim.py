import logging


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
        combined_item_lookup = {}
        for data_list in [self.resource_desc, self.item_desc, self.cargo_desc]:
            if data_list:
                for item in data_list:
                    if "id" in item:
                        combined_item_lookup[item["id"]] = item

        collection = {}
        storage_buildings = self.buildings.get("Storage", []) + self.buildings.get("Cargo Stockpile", [])

        for building in storage_buildings:
            container_name = building.get("nickname") or building.get("name", "Unknown Storage")

            # --- FIX: Add a robust safety check for the inventory object ---
            inventory_data = building.get("inventory")
            if not inventory_data:
                # This building has no inventory attached, so we skip it.
                continue

            # Now it's safe to access "pockets"
            for slot in inventory_data.get("pockets", []):
                try:
                    inv_data = slot[1][1]
                    if not isinstance(inv_data, list) or len(inv_data) < 2:
                        continue
                    item_id = inv_data[0]
                    quantity = inv_data[1]

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

                        if container_name not in collection[item_name]["containers"]:
                            collection[item_name]["containers"][container_name] = 0
                        collection[item_name]["containers"][container_name] += quantity

                except (IndexError, TypeError, ValueError) as e:
                    continue

        return collection

    def fetch_all_claim_ids_by_user(self, user_id: str) -> list[dict] | None:
        """
        Fetches all claims that a user is a member of.

        Args:
            user_id (str): The user's ID.

        Returns:
            List of claim dictionaries with claim details, or None if error.
        """
        if not user_id:
            logging.error("User ID is missing for claims fetch.")
            return None

        sanitized_user_id = str(user_id).replace("'", "''")
        query_string = f"SELECT * FROM claim_member_state WHERE player_entity_id = '{sanitized_user_id}';"

        try:
            results = self.client.query(query_string)
            if not results:
                logging.warning(f"No claims found for user {user_id}.")
                return []

            claims_list = []
            for result in results:
                claim_id = result.get("claim_entity_id")
                if claim_id:
                    # Get detailed claim information
                    claim_details = self._get_claim_full_details(claim_id)
                    if claim_details:
                        claims_list.append(claim_details)

            logging.info(f"Found {len(claims_list)} claims for user {user_id}")
            return claims_list

        except RuntimeError as e:
            logging.error(f"Failed to retrieve claims due to a client runtime error: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred while fetching claims: {e}")
            return None

    def _get_claim_full_details(self, claim_id: str) -> dict | None:
        """
        Fetches comprehensive details for a specific claim.

        Args:
            claim_id (str): The claim entity ID.

        Returns:
            Dictionary with claim details or None if not found.
        """
        try:
            claim_details = {"claim_id": claim_id, "claim_name": "Unknown Claim", "treasury": 0, "supplies": 0, "tile_count": 0}

            # Get claim name from claim_state
            state_query = f"SELECT * FROM claim_state WHERE entity_id = '{claim_id}';"
            state_results = self.client.query(state_query)

            if state_results and len(state_results) > 0:
                claim_details["claim_name"] = state_results[0].get("name", "Unknown Claim")

            # Get treasury, supplies, tile count from claim_local_state
            local_query = f"SELECT * FROM claim_local_state WHERE entity_id = '{claim_id}';"
            local_results = self.client.query(local_query)

            if local_results and len(local_results) > 0:
                local_data = local_results[0]
                claim_details["treasury"] = local_data.get("treasury", 0)
                claim_details["supplies"] = local_data.get("supplies", 0)
                claim_details["tile_count"] = local_data.get("num_tiles", 0)

                # Try to calculate tile count from coordinates if not available
                if claim_details["tile_count"] == 0:
                    coord_query = f"SELECT * FROM claim_coordinate_state WHERE claim_entity_id = '{claim_id}';"
                    coord_results = self.client.query(coord_query)
                    if coord_results:
                        claim_details["tile_count"] = len(coord_results)

            return claim_details

        except Exception as e:
            logging.error(f"Error fetching details for claim {claim_id}: {e}")
            return None

    def switch_to_claim(self, new_claim_id: str) -> bool:
        """
        Switches the current claim instance to a different claim.
        Clears existing data and prepares for new claim data.

        Args:
            new_claim_id (str): The new claim ID to switch to.

        Returns:
            bool: True if switch was successful, False otherwise.
        """
        if not new_claim_id:
            logging.error("New claim ID is required for switching.")
            return False

        try:
            # Clear existing claim data
            self.clear_claim_data()

            # Set new claim ID
            self.claim_id = new_claim_id

            # Fetch basic claim info for the new claim
            claim_details = self._get_claim_full_details(new_claim_id)
            if claim_details:
                self.claim_name = claim_details["claim_name"]
                self.treasury = claim_details["treasury"]
                self.supplies = claim_details["supplies"]
                self.size = claim_details["tile_count"]  # Map to existing size attribute

                logging.info(f"Successfully switched to claim: {self.claim_name} ({new_claim_id})")
                return True
            else:
                logging.error(f"Could not fetch details for new claim {new_claim_id}")
                return False

        except Exception as e:
            logging.error(f"Error switching to claim {new_claim_id}: {e}")
            return False

    def clear_claim_data(self):
        """
        Clears all current claim data in preparation for switching claims.
        Resets buildings, inventory, and other claim-specific state.
        """

        # Reset claim state attributes
        self.claim_name = None
        self.owner_id = None
        self.owner_building_id = None
        self.supplies = 0
        self.size = 0
        self.treasury = 0
        self.buildings = {}

        # Note: claim_id is intentionally NOT cleared here as it's set by switch_to_claim()
        # Note: reference_data is preserved as it's game-wide, not claim-specific

    def refresh_claim_info(self) -> dict:
        """
        Refreshes the current claim's basic information (treasury, supplies, tiles).
        Used after claim switching to get updated data.

        Returns:
            dict: Updated claim information
        """
        if not self.claim_id:
            logging.error("Cannot refresh claim info without a claim_id")
            return {}

        try:
            updated_details = self._get_claim_full_details(self.claim_id)
            if updated_details:
                # Update instance attributes
                self.claim_name = updated_details["claim_name"]
                self.treasury = updated_details["treasury"]
                self.supplies = updated_details["supplies"]
                self.size = updated_details["tile_count"]

                return {
                    "name": self.claim_name,
                    "treasury": self.treasury,
                    "supplies": self.supplies,
                    "tile_count": self.size,
                    "supplies_per_hour": 0,  # Will be calculated by UI
                }
            else:
                logging.error(f"Could not refresh details for claim {self.claim_id}")
                return {}

        except Exception as e:
            logging.error(f"Error refreshing claim info: {e}")
            return {}

    def update_from_subscription_data(self, table_name, table_data):
        """
        Update claim attributes from subscription data.
        This method should be called by processors when subscription data arrives.

        Args:
            table_name: Name of the table (e.g., 'claim_state', 'claim_local_state')
            table_data: The subscription data for this table
        """
        try:
            if table_name == "claim_state" and table_data:
                for row in table_data:
                    if row.get("entity_id") == self.claim_id:
                        self.claim_name = row.get("name", self.claim_name)

            elif table_name == "claim_local_state" and table_data:
                for row in table_data:
                    if row.get("entity_id") == self.claim_id:
                        self.treasury = row.get("treasury", self.treasury)
                        self.supplies = row.get("supplies", self.supplies)
                        self.size = row.get("num_tiles", self.size)
                        #     f"Updated claim data from subscription: treasury={self.treasury}, supplies={self.supplies}, tiles={self.size}"
                        # )

        except Exception as e:
            logging.error(f"Error updating claim from subscription data: {e}")
