import logging
import time
from typing import List, Dict, Optional


class ClaimManager:
    """
    Manages multiple claims for a player, handles claim switching,
    and provides claim data caching and persistence.
    """

    def __init__(self, client):
        """
        Initialize the ClaimManager with a BitCraft client for data operations.

        Args:
            client: BitCraft client instance for making queries
        """
        self.client = client
        self.available_claims: List[Dict] = []
        self.current_claim_id: Optional[str] = None
        self.current_claim_index: int = 0

    def fetch_all_user_claims(self, user_id: str) -> List[Dict]:
        """
        Fetches all claims that the user is a member of.

        Args:
            user_id: The player's entity ID

        Returns:
            List of claim dictionaries with id, name, and metadata
        """
        if not user_id:
            logging.error("User ID is required to fetch claims")
            return []

        try:
            # Get all claim memberships for this user
            sanitized_user_id = str(user_id).replace("'", "''")
            claims_query = f"SELECT * FROM claim_member_state WHERE player_entity_id = '{sanitized_user_id}';"

            claim_memberships = self.client.query(claims_query)
            if not claim_memberships:
                logging.warning(f"No claim memberships found for user {user_id}")
                return []

            # Get detailed info for each claim
            claims_list = []
            for membership in claim_memberships:
                claim_id = membership.get("claim_entity_id")
                if not claim_id:
                    continue

                # Get claim name and details
                claim_info = self._fetch_claim_details(claim_id)
                if claim_info:
                    claims_list.append(claim_info)

            logging.info(f"Found {len(claims_list)} claims for user {user_id}")
            return claims_list

        except Exception as e:
            logging.error(f"Error fetching user claims: {e}")
            return []

    def _fetch_claim_details(self, claim_id: str) -> Optional[Dict]:
        """
        Fetches detailed information for a specific claim.

        Args:
            claim_id: The claim entity ID

        Returns:
            Dictionary with claim details or None if not found
        """
        try:
            # Get claim state for name
            state_query = f"SELECT * FROM claim_state WHERE entity_id = '{claim_id}';"
            state_results = self.client.query(state_query)

            # Get claim local state for treasury/supplies
            local_query = f"SELECT * FROM claim_local_state WHERE entity_id = '{claim_id}';"
            local_results = self.client.query(local_query)

            claim_info = {
                "claim_id": claim_id,
                "claim_name": "Unknown Claim",
                "treasury": 0,
                "supplies": 0,
                "tile_count": 0,
                "last_accessed": time.time(),
            }

            # Extract claim name
            if state_results and len(state_results) > 0:
                claim_info["claim_name"] = state_results[0].get("name", "Unknown Claim")

            # Extract treasury, supplies, tile count
            if local_results and len(local_results) > 0:
                local_data = local_results[0]
                claim_info["treasury"] = local_data.get("treasury", 0)
                claim_info["supplies"] = local_data.get("supplies", 0)
                claim_info["tile_count"] = local_data.get("num_tiles", 0)

            return claim_info

        except Exception as e:
            logging.error(f"Error fetching details for claim {claim_id}: {e}")
            return None

    def set_available_claims(self, claims_list: List[Dict]):
        """
        Sets the list of available claims and loads cached data if available.

        Args:
            claims_list: List of claim dictionaries
        """
        self.available_claims = claims_list

        # Try to restore last selected claim from cache
        cached_claims = self.client._load_reference_data("player_data")
        if cached_claims:
            claims_data = cached_claims.get("claims", {})
            last_selected = claims_data.get("last_selected_claim_id")

            if last_selected:
                # Find the claim in our current list
                for i, claim in enumerate(self.available_claims):
                    if claim["claim_id"] == last_selected:
                        self.current_claim_id = last_selected
                        self.current_claim_index = i
                        logging.info(f"Restored last selected claim: {claim['claim_name']}")
                        return

        # Default to first claim if no cached selection
        if self.available_claims:
            self.current_claim_id = self.available_claims[0]["claim_id"]
            self.current_claim_index = 0
            logging.info(f"Defaulted to first claim: {self.available_claims[0]['claim_name']}")

    def get_all_claims(self) -> List[Dict]:
        """Returns the full list of available claims."""
        return self.available_claims

    def get_current_claim(self) -> Optional[Dict]:
        """Returns the currently selected claim info."""
        if self.current_claim_id and self.available_claims:
            for claim in self.available_claims:
                if claim["claim_id"] == self.current_claim_id:
                    return claim
        return None

    def get_current_claim_id(self) -> Optional[str]:
        """Returns the currently selected claim ID."""
        return self.current_claim_id

    def switch_to_claim(self, claim_id: str) -> bool:
        """
        Switches to a different claim.

        Args:
            claim_id: The claim ID to switch to

        Returns:
            True if switch was successful, False otherwise
        """
        # Find the claim in our available list
        for i, claim in enumerate(self.available_claims):
            if claim["claim_id"] == claim_id:
                self.current_claim_id = claim_id
                self.current_claim_index = i

                # Update last accessed time
                claim["last_accessed"] = time.time()

                # Save to cache
                self._save_claims_cache()

                logging.info(f"Switched to claim: {claim['claim_name']}")
                return True

        logging.error(f"Cannot switch to claim {claim_id} - not found in available claims")
        return False

    def get_claim_by_id(self, claim_id: str) -> Optional[Dict]:
        """
        Gets claim info by claim ID.

        Args:
            claim_id: The claim ID to look up

        Returns:
            Claim dictionary or None if not found
        """
        for claim in self.available_claims:
            if claim["claim_id"] == claim_id:
                return claim
        return None

    def update_claim_cache(self, claim_id: str, updated_info: Dict):
        """
        Updates cached information for a specific claim.

        Args:
            claim_id: The claim ID to update
            updated_info: Dictionary with updated claim data
        """
        for claim in self.available_claims:
            if claim["claim_id"] == claim_id:
                claim.update(updated_info)
                claim["last_accessed"] = time.time()
                self._save_claims_cache()
                break

    def remove_claim(self, claim_id: str):
        """
        Removes a claim from the available list (e.g., if user lost access).

        Args:
            claim_id: The claim ID to remove
        """
        self.available_claims = [c for c in self.available_claims if c["claim_id"] != claim_id]

        # If we removed the current claim, switch to the first available
        if self.current_claim_id == claim_id and self.available_claims:
            self.switch_to_claim(self.available_claims[0]["claim_id"])
        elif not self.available_claims:
            self.current_claim_id = None
            self.current_claim_index = 0

        self._save_claims_cache()
        logging.warning(f"Removed claim {claim_id} from available claims")

    def _save_claims_cache(self):
        """Saves current claims data to the player data cache."""
        try:
            claims_cache = {
                "last_selected_claim_id": self.current_claim_id,
                "available_claims": self.available_claims,
                "cache_timestamp": time.time(),
            }

            self.client.update_user_data_file("claims", claims_cache)
            logging.debug("Claims cache saved successfully")

        except Exception as e:
            logging.error(f"Error saving claims cache: {e}")

    def has_multiple_claims(self) -> bool:
        """Returns True if the user has access to multiple claims."""
        return len(self.available_claims) > 1

    def get_claims_summary(self) -> str:
        """Returns a summary string of available claims for logging/debugging."""
        if not self.available_claims:
            return "No claims available"

        current_name = "None"
        if self.current_claim_id:
            current_claim = self.get_current_claim()
            if current_claim:
                current_name = current_claim["claim_name"]

        return f"{len(self.available_claims)} claims available, current: {current_name}"
