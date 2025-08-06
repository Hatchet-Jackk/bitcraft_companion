import logging
import time
from typing import List, Dict, Optional


class ClaimService:
    """
    Manages multiple claims for a player, handles claim switching,
    and provides claim data caching and persistence.
    """

    def __init__(self, client, query_service):
        """
        Initialize the ClaimService with a BitCraft client for data operations.

        Args:
            client: BitCraft client instance for making queries
        """
        self.client = client
        self.query_service = query_service
        self.available_claims: List[Dict] = []
        self.current_claim_id: Optional[str] = None
        self.current_claim_index: int = 0
        self.claims_list = []

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
            claim_memberships = self.query_service.get_user_claims(user_id)
            if not claim_memberships:
                logging.warning(f"No claim memberships found for user {user_id}")
                return []

            # Get detailed info for each claim
            claims_list = []
            for membership in claim_memberships:
                claim_entity_id = membership.get("claim_entity_id")
                if not claim_entity_id:
                    continue

                # Get claim name and details
                claim_details = self._fetch_claim_details(claim_entity_id)
                if claim_details:
                    claims_list.append(claim_details)

            logging.info(f"Found {len(claims_list)} claims for user {user_id}")
            return claims_list

        except Exception as e:
            logging.error(f"Error fetching user claims: {e}")
            return []

    def refresh_user_claims(self, user_id: str) -> List[Dict]:
        """
        Refreshes the list of claims for a user and updates the available claims.

        Args:
            user_id: The player's entity ID

        Returns:
            Updated list of claim dictionaries
        """
        try:
            updated_claims = self.fetch_all_user_claims(user_id)
            if updated_claims:
                self.set_available_claims(updated_claims)
                logging.info(f"Refreshed claims list: {len(updated_claims)} claims found")
            return updated_claims
        except Exception as e:
            logging.error(f"Error refreshing user claims: {e}")
            return self.available_claims  # Return current claims on error

    def _fetch_claim_details(self, claim_id: str) -> Optional[Dict]:
        """
        Fetches detailed information for a specific claim.

        Args:
            claim_id: The claim entity ID

        Returns:
            Dictionary with claim details or None if not found
        """
        claim_data = {}
        try:
            claim_local_state = self.query_service.get_claim_local_state(claim_id)
            claim_data.update(claim_local_state)

            claim_state = self.query_service.get_claim_state(claim_id)
            claim_data.update(claim_state)

            return claim_data
        except Exception as e:
            logging.error(f"Error fetching details for claim {claim_id}: {e}")
            return {}

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
                    if claim["entity_id"] == last_selected:
                        self.current_claim_id = last_selected
                        self.current_claim_index = i
                        logging.info(f"Restored last selected claim: {claim['name']}")
                        return

        # Default to first claim if no cached selection
        if self.available_claims:
            self.current_claim_id = self.available_claims[0]["entity_id"]
            self.current_claim_index = 0
            logging.info(f"Defaulted to first claim: {self.available_claims[0]['name']}")

    def get_all_claims(self) -> List[Dict]:
        """Returns the full list of available claims."""
        return self.available_claims

    def get_current_claim(self) -> Optional[Dict]:
        """Returns the currently selected claim info."""
        if self.current_claim_id and self.available_claims:
            for claim in self.available_claims:
                if claim["entity_id"] == self.current_claim_id:
                    return claim
        return None

    def get_current_claim_id(self) -> Optional[str]:
        """Returns the currently selected claim ID."""
        return self.current_claim_id

    def set_current_claim(self, claim_id: str) -> bool:
        """
        Sets the current claim (alias for switch_to_claim for API compatibility).
        
        Args:
            claim_id: The claim ID to set as current
            
        Returns:
            True if switch was successful, False otherwise
        """
        return self.switch_to_claim(claim_id)

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
            if claim["entity_id"] == claim_id:
                self.current_claim_id = claim_id
                self.current_claim_index = i

                # Update last accessed time
                claim["last_accessed"] = time.time()

                # Save to cache
                self._save_claims_cache()

                logging.info(f"Switched to claim: {claim['name']}")
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
            if claim["entity_id"] == claim_id:
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
            if claim["entity_id"] == claim_id:
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
        self.available_claims = [c for c in self.available_claims if c["entity_id"] != claim_id]

        # If we removed the current claim, switch to the first available
        if self.current_claim_id == claim_id and self.available_claims:
            self.switch_to_claim(self.available_claims[0]["entity_id"])
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
