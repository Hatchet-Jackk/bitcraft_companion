import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

from client import BitCraft
from claim import Claim


class InventoryService:
    """Service class to handle all inventory-related operations and caching.

    Provides inventory fetching, enrichment, and caching for BitCraft claims.
    Handles asynchronous data loading, cache validation, and claim data initialization.

    Attributes:
        bitcraft_client: BitCraft client instance for API/database access
        claim_instance: Claim instance for claim and inventory data
        cached_inventory_data: Cached inventory data for the current claim
        last_inventory_fetch_time: Timestamp of last successful inventory fetch
        inventory_cache_duration_minutes: Cache duration in minutes
    """

    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim):
        """Initialize the InventoryService with BitCraft client and claim instance.

        Args:
            bitcraft_client: BitCraft client for API/database access
            claim_instance: Claim instance for claim and inventory data
        """
        self.bitcraft_client = bitcraft_client
        self.claim_instance = claim_instance
        # Caching variables
        self.cached_inventory_data: Optional[List[Dict]] = None
        self.last_inventory_fetch_time: Optional[datetime] = None
        self.inventory_cache_duration_minutes = 5

    def is_cache_valid(self) -> bool:
        """Check if the cached inventory data is still valid.

        Returns:
            bool: True if cache is valid, False otherwise
        """
        if self.cached_inventory_data is None or self.last_inventory_fetch_time is None:
            logging.debug("No cached inventory data available")
            return False
        time_since_last_fetch = datetime.now() - self.last_inventory_fetch_time
        cache_duration = timedelta(minutes=self.inventory_cache_duration_minutes)
        is_valid = time_since_last_fetch < cache_duration
        if is_valid:
            remaining_time = cache_duration - time_since_last_fetch
            logging.debug(
                f"Using cached inventory data (expires in {remaining_time.total_seconds():.0f} seconds)"
            )
        else:
            logging.debug(
                f"Cached inventory data expired ({time_since_last_fetch.total_seconds():.0f} seconds old)"
            )
        return is_valid

    def clear_cache(self):
        """Clear the inventory cache to force a fresh fetch.

        Resets cached inventory data and last fetch timestamp.
        """
        logging.debug("Clearing inventory cache")
        self.cached_inventory_data = None
        self.last_inventory_fetch_time = None

    def get_cached_data(self) -> Optional[List[Dict]]:
        """Get cached inventory data if valid.

        Returns:
            Optional[List[Dict]]: Copy of cached inventory data if valid, else None
        """
        if self.is_cache_valid():
            return (
                self.cached_inventory_data.copy()
                if self.cached_inventory_data
                else None
            )
        return None

    def fetch_inventory_async(
        self, callback: Callable[[List[Dict], bool, str, bool], None]
    ):
        """Fetch inventory data asynchronously.

        Args:
            callback: Function to call with (display_data, success, message, is_fresh_data)
                - display_data: List of inventory items for display
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
                        "Claim ID not set for inventory fetch. Cannot fetch inventory."
                    )
                    message = "Claim ID missing for inventory."
                    callback(display_data, False, message, False)
                    return

                building_states = self.bitcraft_client.fetch_claim_building_state(
                    claim_id
                )
                logging.debug(f"Fetched raw building_states: {building_states}")

                # Fetch building nicknames from database
                building_nicknames = (
                    self.bitcraft_client.fetch_building_nickname_state()
                )
                nickname_lookup = {}
                if building_nicknames:
                    # Create a lookup dictionary for fast nickname association
                    nickname_lookup = {
                        entry.get("entity_id"): entry.get("nickname")
                        for entry in building_nicknames
                        if entry.get("entity_id") is not None
                    }
                    logging.debug(
                        f"Loaded {len(nickname_lookup)} building nicknames for association"
                    )
                else:
                    logging.warning("No building nicknames found in database")

                enriched_building_states = []
                if building_states:
                    logging.debug(
                        f"Found {len(building_states)} buildings for claim {claim_id}. Fetching their inventories..."
                    )
                    for building in building_states:
                        entity_id = building.get("entity_id")
                        if not entity_id:
                            entity_id = building.get("entity")
                            if entity_id:
                                logging.warning(
                                    f"Building ID key is 'entity' not 'entity_id' for building: {building}. Using 'entity'."
                                )
                            else:
                                logging.error(
                                    f"Building data missing both 'entity_id' and 'entity' keys for: {building}. Skipping."
                                )
                                continue

                        if entity_id:
                            # Associate nickname with building
                            nickname = nickname_lookup.get(entity_id)
                            building["nickname"] = nickname

                            # Fetch inventory for this building
                            inventory_data = self.bitcraft_client.fetch_inventory_state(
                                entity_id
                            )
                            logging.debug(
                                f"Fetched inventory for {entity_id}: {inventory_data}"
                            )
                            if inventory_data:
                                building["inventory"] = inventory_data
                                logging.debug(
                                    f"Attached inventory to building {entity_id}"
                                )
                            else:
                                logging.debug(
                                    f"No inventory found for building {entity_id}"
                                )
                        enriched_building_states.append(building)

                    self.claim_instance.set_buildings(enriched_building_states)
                    logging.info(
                        f"Loaded {len(enriched_building_states)} buildings (some enriched with inventory) for claim {claim_id}"
                    )
                    logging.debug(
                        f"Buildings processed by Claim instance: {self.claim_instance.get_buildings()}"
                    )
                else:
                    logging.warning(
                        f"No buildings found for claim {claim_id} or could not fetch building states."
                    )
                    self.claim_instance.set_buildings([])

                inventory = self.claim_instance.get_inventory()
                logging.debug(f"Consolidated inventory from Claim: {inventory}")

                for item_id, details in inventory.items():
                    name = details.get("name", "N/A")
                    quantity = details.get("quantity", 0)
                    tier = details.get("tier", 0)
                    tag = details.get("tag", "")
                    containers = details.get("containers", {})
                    display_data.append(
                        {
                            "id": item_id,
                            "Name": name,
                            "Quantity": quantity,
                            "Tier": tier,
                            "Tag": tag,
                            "containers": containers,
                        }
                    )

                logging.debug(f"Prepared display_data: {display_data}")

                # Cache the data and timestamp
                self.cached_inventory_data = display_data.copy()
                self.last_inventory_fetch_time = datetime.now()
                logging.info(
                    f"Cached {len(display_data)} inventory items for {self.inventory_cache_duration_minutes} minutes"
                )

                message = "Claim inventory loaded."
                callback(display_data, True, message, True)  # True = fresh data

            except Exception as e:
                logging.exception("Error fetching inventory data:")
                message = f"Error loading inventory: {e}"
                callback([], False, message, False)

        # Start the fetch in a background thread
        threading.Thread(target=fetch_thread, daemon=True).start()

    def initialize_claim_data_async(
        self, user_id: str, callback: Optional[Callable[[], None]] = None
    ):
        """Initialize claim data asynchronously.

        Args:
            user_id: User entity ID to initialize claim data for
            callback: Optional function to call when initialization completes
        """

        def run_initialization():
            try:
                # Store user ID in claim instance
                self.claim_instance.set_owner_id(user_id)

                # Get claim data
                claim_id = self.bitcraft_client.fetch_claim_membership_id_by_user_id(
                    user_id
                )
                if claim_id:
                    self.claim_instance.set_claim_id(claim_id)
                    claim_state = self.bitcraft_client.fetch_claim_state(claim_id)
                    if claim_state:
                        self.claim_instance.set_claim_name(
                            claim_state.get("claim_name")
                        )
                        self.claim_instance.set_owner_building_id(
                            claim_state.get("owner_building_id")
                        )

                    claim_local_state = self.bitcraft_client.fetch_claim_local_state(
                        claim_id
                    )
                    if claim_local_state:
                        self.claim_instance.set_supplies(
                            claim_local_state.get("supplies")
                        )
                        self.claim_instance.set_size(claim_local_state.get("num_tiles"))
                        self.claim_instance.set_treasury(
                            claim_local_state.get("treasury")
                        )
                    logging.info("Initial claim data loaded.")
                else:
                    logging.warning(f"No claim ID found for user {user_id}.")

                if callback:
                    callback()

            except Exception as e:
                logging.error(f"Error during claim data initialization: {e}")
                if callback:
                    callback()

        # Run initialization in background thread
        threading.Thread(target=run_initialization, daemon=True).start()
