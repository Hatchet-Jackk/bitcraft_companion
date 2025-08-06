import time
import threading
import logging
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
from ..client.bitcraft_client import BitCraft
from ..models.claim import Claim
from ..models.claim_member import ClaimMember


class ClaimMembersService:
    """
    Centralized service for managing claim member data with caching.
    Now uses ClaimMember objects for rich member tracking.
    """

    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim, query_service=None):
        """Initialize the claim members service."""
        self.client = bitcraft_client
        self.claim = claim_instance
        self.query_service = query_service

        # Cache data - now using ClaimMember objects
        self._cache_lock = threading.RLock()
        self._cached_members: Dict[str, ClaimMember] = {}  # entity_id -> ClaimMember
        self._cached_member_ids: Set[str] = set()
        self._cached_user_lookup: Dict[str, str] = {}  # entity_id -> username
        self._cache_buildings: List[Dict] = []
        self._cache_timestamp: float = 0
        self._cache_duration: int = 60  # 60 seconds cache duration

        # Background refresh
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_refresh_event = threading.Event()
        self._is_refreshing = False

    def get_claim_members(self, force_refresh: bool = False) -> List[ClaimMember]:
        """
        Get all claim members as ClaimMember objects with caching.

        Args:
            force_refresh: If True, force a cache refresh regardless of age

        Returns:
            List of ClaimMember objects
        """
        with self._cache_lock:
            if force_refresh or self._is_cache_expired():
                self._refresh_cache()
            return list(self._cached_members.values())

    def get_claim_member_by_id(self, entity_id: str) -> Optional[ClaimMember]:
        """Get a specific claim member by entity ID."""
        with self._cache_lock:
            if self._is_cache_expired():
                self._refresh_cache()
            return self._cached_members.get(entity_id)

    def get_claim_member_by_username(self, username: str) -> Optional[ClaimMember]:
        """Get a claim member by username."""
        with self._cache_lock:
            if self._is_cache_expired():
                self._refresh_cache()
            for member in self._cached_members.values():
                if member.username.lower() == username.lower():
                    return member
            return None

    def get_claim_member_ids(self, force_refresh: bool = False) -> Set[str]:
        """
        Get set of claim member player IDs for fast filtering.

        Args:
            force_refresh: If True, force a cache refresh regardless of age

        Returns:
            Set of player entity IDs
        """
        with self._cache_lock:
            if force_refresh or self._is_cache_expired():
                self._refresh_cache()
            return self._cached_member_ids.copy()

    def get_user_lookup(self, force_refresh: bool = False) -> Dict[str, str]:
        """
        Get player ID to username lookup dictionary.

        Args:
            force_refresh: If True, force a cache refresh regardless of age

        Returns:
            Dictionary mapping player_entity_id to user_name
        """
        with self._cache_lock:
            if force_refresh or self._is_cache_expired():
                self._refresh_cache()
            return self._cached_user_lookup.copy()

    def get_player_name(self, entity_id: str) -> str:
        """Get player name by entity ID, with fallback."""
        member = self.get_claim_member_by_id(entity_id)
        if member:
            return member.get_display_name()

        # Fallback to user lookup
        user_lookup = self.get_user_lookup()
        return user_lookup.get(entity_id, "Unknown Player")

    def update_member_activity(self, entity_id: str, activity_type: str, details: Dict = None, location: str = None):
        """Update a member's activity tracking."""
        member = self.get_claim_member_by_id(entity_id)
        if member:
            member.add_activity(activity_type, details or {}, location)

    def update_member_inventory(self, entity_id: str, item_id: str, item_name: str, quantity: int, location: str, **kwargs):
        """Update a member's inventory."""
        member = self.get_claim_member_by_id(entity_id)
        if member:
            member.update_inventory_item(item_id, item_name, quantity, location, **kwargs)

    def update_member_equipment(self, entity_id: str, slot: str, item_data: Dict):
        """Update a member's equipment."""
        member = self.get_claim_member_by_id(entity_id)
        if member:
            member.update_equipment(slot, item_data)

    def add_member_owned_object(self, entity_id: str, object_id: str, object_type: str, object_name: str, **kwargs):
        """Add an owned object to a member."""
        member = self.get_claim_member_by_id(entity_id)
        if member:
            member.add_owned_object(object_id, object_type, object_name, **kwargs)

    def get_claim_member_data(self, force_refresh: bool = False) -> Tuple[Set[str], Dict[str, str]]:
        """
        Get both member IDs and user lookup in one call for efficiency.

        Args:
            force_refresh: If True, force a cache refresh regardless of age

        Returns:
            Tuple of (member_ids_set, user_lookup_dict)
        """
        with self._cache_lock:
            if force_refresh or self._is_cache_expired():
                self._refresh_cache()
            return self._cached_member_ids.copy(), self._cached_user_lookup.copy()

    def is_claim_member(self, player_entity_id: str, force_refresh: bool = False) -> bool:
        """
        Check if a player ID is a member of the current claim.

        Args:
            player_entity_id: The player entity ID to check
            force_refresh: If True, force a cache refresh regardless of age

        Returns:
            True if player is a claim member
        """
        member_ids = self.get_claim_member_ids(force_refresh)
        return player_entity_id in member_ids

    def get_cache_info(self) -> Dict:
        """Get information about the current cache state for debugging."""
        with self._cache_lock:
            return {
                "cache_age_seconds": time.time() - self._cache_timestamp,
                "cache_expired": self._is_cache_expired(),
                "member_count": len(self._cached_members),
                "member_ids_count": len(self._cached_member_ids),
                "user_lookup_count": len(self._cached_user_lookup),
                "is_refreshing": self._is_refreshing,
                "claim_id": self.claim.claim_id,
                "last_refresh": (
                    time.strftime("%H:%M:%S", time.localtime(self._cache_timestamp)) if self._cache_timestamp else "Never"
                ),
            }

    def _is_cache_expired(self) -> bool:
        """Check if the cache has expired."""
        if not self._cache_timestamp:
            return True
        return time.time() - self._cache_timestamp > self._cache_duration

    def _refresh_cache_if_expired(self) -> bool:
        """Refresh cache only if it has expired. Returns True if cache was refreshed."""
        with self._cache_lock:
            if self._is_cache_expired():
                self._refresh_cache()
                return True
            return False

    def _refresh_cache(self):
        """Refresh the claim members cache from the database."""
        if not self.claim.claim_id:
            logging.warning("Cannot refresh claim members cache - no claim ID available")
            return

        self._is_refreshing = True

        try:

            # Query claim members using QueryService if available
            if self.query_service:
                claim_members = self.query_service.get_claim_members(self.claim.claim_id)
            else:
                # Fallback to direct query
                claim_members_query = f"SELECT * FROM claim_member_state WHERE claim_entity_id = '{self.claim.claim_id}';"
                claim_members = self.client.query(claim_members_query)

            if not claim_members:
                logging.warning("No claim members found during cache refresh")
                claim_members = []

            # Build ClaimMember objects and lookup structures
            new_cached_members = {}
            member_ids = set()
            user_lookup = {}

            for member_data in claim_members:
                player_id = member_data.get("player_entity_id")
                user_name = member_data.get("user_name")

                if player_id:
                    member_ids.add(player_id)
                    username = user_name or f"User {player_id}"
                    user_lookup[player_id] = username

                    # Create or update ClaimMember object
                    if player_id in self._cached_members:
                        # Update existing member
                        existing_member = self._cached_members[player_id]
                        existing_member.username = username
                        existing_member.display_name = username
                        existing_member.update_last_seen()
                        new_cached_members[player_id] = existing_member
                    else:
                        # Create new ClaimMember
                        claim_member = ClaimMember(entity_id=player_id, username=username, claim_id=self.claim.claim_id)
                        claim_member.role = member_data.get("role")
                        claim_member.is_online = member_data.get("is_online", False)
                        new_cached_members[player_id] = claim_member

            # Update cache atomically
            self._cached_members = new_cached_members
            self._cached_member_ids = member_ids
            self._cached_user_lookup = user_lookup
            self._cache_timestamp = time.time()

            logging.info(f"Claim members cache refreshed: {len(new_cached_members)} members, {len(member_ids)} unique IDs")

        except Exception as e:
            logging.error(f"Error refreshing claim members cache: {e}")
        finally:
            self._is_refreshing = False

    def invalidate_cache(self):
        """Manually invalidate the cache to force a refresh on next access."""
        with self._cache_lock:
            self._cache_timestamp = 0

    def warm_cache(self):
        """Manually warm the cache by forcing a refresh."""
        self.get_claim_members(force_refresh=True)
