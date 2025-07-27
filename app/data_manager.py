"""
Data Manager for Bitcraft Companion
Handles all websocket communication and data processing in a separate thread.
"""

import threading
import queue
import time
import logging


class DataService:
    """
    Manages the connection to the game client, handles data subscriptions,
    and passes data to the GUI via a thread-safe queue.
    """

    def __init__(self):
        # Import here to prevent circular dependencies
        from client import BitCraft
        from player import Player
        from claim import Claim
        from inventory_service import InventoryService
        from passive_crafting_service import PassiveCraftingService

        # Store the classes themselves
        self.BitCraftClass = BitCraft
        self.PlayerClass = Player
        self.ClaimClass = Claim
        self.InventoryServiceClass = InventoryService
        self.PassiveCraftingServiceClass = PassiveCraftingService

        # Instantiate the client immediately to load saved user data (email, etc.) for the login screen
        self.client = self.BitCraftClass()

        # These will be instantiated in the _run method after login
        self.player = None
        self.claim = None
        self.inventory_service = None
        self.passive_crafting_service = None

        self.data_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.service_thread = None

    def start(self, username, password, region, player_name):
        """Starts the data fetching thread with user credentials."""
        if self.service_thread and self.service_thread.is_alive():
            logging.warning("DataService is already running.")
            return

        self._stop_event.clear()
        self.service_thread = threading.Thread(target=self._run, args=(username, password, region, player_name), daemon=True)
        self.service_thread.start()

    def stop(self):
        """Signals the data fetching thread to stop."""
        logging.info("Stopping DataService...")
        self._stop_event.set()
        if self.client:
            self.client.close_websocket()
        if self.service_thread and self.service_thread.is_alive():
            self.service_thread.join()  # Wait for the thread to finish
        logging.info("DataService stopped.")

    def _run(self, username, password, region, player_name):
        """The main loop for the data service thread."""
        logging.info("[DataService] Thread started.")

        try:
            # --- Instantiate classes with correct dependencies within the thread ---
            self.player = self.PlayerClass(username=player_name)
            # FIX: The Claim class constructor takes no arguments.
            self.claim = self.ClaimClass()

            # 1. Authenticate
            if not self.client.authenticate(email=username, access_code=password):
                logging.error("[DataService] Authentication failed.")
                self.data_queue.put(
                    {"type": "connection_status", "data": {"status": "failed", "reason": "Authentication Failed"}}
                )
                return

            # 2. Configure connection
            self.client.set_region(region)
            self.client.set_endpoint("subscribe")
            self.client.set_websocket_uri()
            self.client.connect_websocket()

            self.data_queue.put({"type": "connection_status", "data": {"status": "connected"}})

            # 3. Perform One-Off queries to get the essential claim ID
            # FIX: The client and player instances must be passed to the get_claim_id method.
            claim_id = self.claim.get_claim_id()
            # claim_id = self.claim.get_claim_id(self.client, self.player)
            if not claim_id:
                logging.error("[DataService] Could not retrieve claim ID.")
                self.data_queue.put({"type": "error", "data": "Could not retrieve claim ID."})
                return

            # Now that the claim object is populated, we can create the services
            self.inventory_service = self.InventoryServiceClass(bitcraft_client=self.client, claim_instance=self.claim)
            self.passive_crafting_service = self.PassiveCraftingServiceClass(
                bitcraft_client=self.client, claim_instance=self.claim
            )

            logging.info(f"[DataService] Acquired Claim ID: {self.claim.claim_id}")

            # Use the populated claim object's data
            self.data_queue.put({"type": "claim_info_update", "data": {"name": self.claim.claim_name}})

            # 4. Build subscription queries
            inventory_query = self.inventory_service.get_subscription_query()
            passive_craft_query = self.passive_crafting_service.get_subscription_query()
            subscriptions = [inventory_query, passive_craft_query]

            # 5. Start the subscription listener
            self.client.start_subscription_listener(subscriptions, self._handle_message)
            logging.info(f"[DataService] Subscription listener started.")

            while not self._stop_event.is_set():
                time.sleep(1)

        except Exception as e:
            logging.error(f"[DataService] An error occurred in the data thread: {e}", exc_info=True)
            self.data_queue.put({"type": "error", "data": f"A connection error occurred: {e}"})
        finally:
            if self.client:
                self.client.close_websocket()
            logging.info("[DataService] Thread stopped and connection closed.")

    def _handle_message(self, message):
        """
        Callback for the client subscription. This method will be called by the
        client's listener thread when a new message arrives.
        """
        update = message.get("SubscriptionUpdate", {})
        db_update = update.get("database_update", {})

        inventory_data = self.inventory_service.parse_inventory_message(db_update)
        if inventory_data:
            self.data_queue.put({"type": "inventory_update", "data": inventory_data})
            return

        passive_crafting_data = self.passive_crafting_service.parse_crafting_message(db_update)
        if passive_crafting_data:
            self.data_queue.put({"type": "passive_crafting_update", "data": passive_crafting_data})
            return
