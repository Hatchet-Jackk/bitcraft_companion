import customtkinter as ctk
import logging
from abc import ABC, abstractmethod
from typing import Optional

from client import BitCraft
from claim import Claim
from inventory_service import InventoryService
from passive_crafting_service import PassiveCraftingService


class BaseWindow(ctk.CTk, ABC):
    """Base class for main application windows with common functionality.

    Provides common window setup, service initialization, and UI management
    for BitCraft Companion application windows. Includes status bar, content
    frame, and service integration for inventory and passive crafting features.

    Attributes:
        bitcraft_client: Optional BitCraft client instance for API communication
        claim_instance: Optional Claim instance for claim data management
        inventory_service: Optional service for inventory data operations
        passive_crafting_service: Optional service for passive crafting operations
        content_frame: Main content frame for dynamic UI changes
        status_bar_frame: Bottom status bar frame for user feedback
        status_label: Label for displaying status messages
    """

    def __init__(self, title: str = "BitCraft Companion", geometry: str = "400x350"):
        """Initialize the base window with common UI elements and services.

        Args:
            title: Window title text
            geometry: Window size in WxH format (e.g., "400x350")
        """
        super().__init__()

        self.title(title)
        self.geometry(geometry)
        self.resizable(False, False)

        # Initialize services
        self.bitcraft_client: Optional[BitCraft] = None
        self.claim_instance: Optional[Claim] = None
        self.inventory_service: Optional[InventoryService] = None
        self.passive_crafting_service: Optional[PassiveCraftingService] = None
        self.claim_inventory_window = None
        self.passive_crafting_window = None
        self.passive_crafting_timer_overlay = None

        # Setup basic grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # Main content frame for dynamic UI changes
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=0, column=0, padx=20, pady=10, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Status bar frame
        self.status_bar_frame = ctk.CTkFrame(self, height=30, fg_color=("gray86", "gray17"))
        self.status_bar_frame.grid(row=1, column=0, padx=0, pady=0, sticky="ew")
        self.status_bar_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(self.status_bar_frame, text="", text_color="yellow")
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

    def initialize_services(self, authenticated_client: BitCraft):
        """Initialize the services with an authenticated client.

        Args:
            authenticated_client: Authenticated BitCraft client instance
        """
        self.bitcraft_client = authenticated_client
        self.claim_instance = Claim()
        self.inventory_service = InventoryService(self.bitcraft_client, self.claim_instance)
        self.passive_crafting_service = PassiveCraftingService(self.bitcraft_client, self.claim_instance)

    def toggle_claim_inventory_window(self):
        """Toggle the claim inventory window on/off.

        Opens or closes the claim inventory window based on toggle state.
        Handles authentication checks, cached data loading, and window
        lifecycle management. Updates status messages for user feedback.
        """
        if not hasattr(self, "toggle_claim_inventory"):
            logging.error("toggle_claim_inventory switch not found")
            return

        if self.toggle_claim_inventory.get():
            # Opening the window
            if self.bitcraft_client is None or not self.bitcraft_client.ws_connection:
                self.status_label.configure(
                    text="Not authenticated or WS not connected. Please log in.",
                    text_color="red",
                )
                self.toggle_claim_inventory.deselect()
                return

            if self.claim_inventory_window and self.claim_inventory_window.winfo_exists():
                self.claim_inventory_window.focus_set()
                return

            # Check if we have cached data that's still valid
            cached_data = self.inventory_service.get_cached_data()
            if cached_data:
                self.status_label.configure(text="Using cached inventory data...", text_color="yellow")
                # Use cached data immediately
                self.after(
                    100,
                    self._on_inventory_data_ready,
                    cached_data,
                    True,
                    "Cached inventory data loaded.",
                    False,  # False = cached data
                )
            else:
                # Temporarily disable toggle while loading
                self.toggle_claim_inventory.configure(state="disabled")
                self.status_label.configure(text="Loading claim inventory data...", text_color="yellow")
                self.inventory_service.fetch_inventory_async(self._on_inventory_data_ready)
        else:
            # Closing the window
            if self.claim_inventory_window and self.claim_inventory_window.winfo_exists():
                self.claim_inventory_window.destroy()
                self.claim_inventory_window = None
            self.status_label.configure(text="Claim inventory window closed.", text_color="green")

    def _on_inventory_data_ready(
        self,
        display_data: list,
        success: bool,
        message: str,
        is_fresh_data: bool = False,
    ):
        """Callback when inventory data is ready.

        Args:
            display_data: List of inventory items for display
            success: Whether data fetch was successful
            message: Status message to display to user
            is_fresh_data: Whether data is freshly fetched or from cache
        """
        if hasattr(self, "toggle_claim_inventory"):
            self.toggle_claim_inventory.configure(state="normal")
        self.status_label.configure(text=message, text_color="green" if success else "red")

        if success:
            # Import here to avoid circular imports
            from inventory_window import ClaimInventoryWindow

            if self.claim_inventory_window and self.claim_inventory_window.winfo_exists():
                # Window already exists, just update its data
                self.claim_inventory_window.current_inventory_data = display_data

                # Update timestamp if this is fresh data (from refresh button or auto-refresh)
                if is_fresh_data:
                    self.claim_inventory_window.update_last_updated_time(schedule_refresh=True)
                else:
                    logging.debug(f"Not updating timestamp - cached data")

                self.claim_inventory_window.apply_filters_and_sort()
                self.claim_inventory_window.focus_set()
            else:
                logging.debug("Window doesn't exist or not valid, will create new one")
                logging.debug("Creating new ClaimInventoryWindow")
                self.claim_inventory_window = ClaimInventoryWindow(
                    self,
                    self.bitcraft_client,
                    self.claim_instance,
                    initial_display_data=display_data,
                    last_fetch_time=self.inventory_service.last_inventory_fetch_time,
                )
                logging.debug(f"Created window instance: {id(self.claim_inventory_window)}")
                self.claim_inventory_window.protocol("WM_DELETE_WINDOW", self.on_claim_inventory_window_close)
                self.claim_inventory_window.focus_set()

                # Set timestamp immediately after creation, before any other operations
                if is_fresh_data:
                    # This is fresh data, update with current time and schedule refresh
                    logging.debug(f"Setting fresh data timestamp on window instance {id(self.claim_inventory_window)}")
                    self.claim_inventory_window.update_last_updated_time(schedule_refresh=True)
                else:
                    # We have cached data, show the original fetch time
                    logging.debug(
                        f"Setting cached data timestamp on window instance {id(self.claim_inventory_window)}: {self.inventory_service.last_inventory_fetch_time}"
                    )
                    if self.inventory_service.last_inventory_fetch_time:
                        self.claim_inventory_window._set_timestamp_from_fetch_time(
                            self.inventory_service.last_inventory_fetch_time
                        )

                # Now that timestamp is set, apply filters and sort to display the data
                logging.debug(f"Calling apply_filters_and_sort on window instance {id(self.claim_inventory_window)}")
                self.claim_inventory_window.apply_filters_and_sort()
        else:
            if hasattr(self, "toggle_claim_inventory"):
                self.toggle_claim_inventory.deselect()

    def on_claim_inventory_window_close(self):
        """Callback when the claim inventory window is closed by user.

        Handles cleanup when user closes the inventory window, including
        toggle state reset and window instance cleanup.
        """
        if hasattr(self, "toggle_claim_inventory"):
            self.toggle_claim_inventory.deselect()
        if self.claim_inventory_window:
            # BaseOverlay handles auto-refresh cancellation in its destroy method
            self.claim_inventory_window.destroy()
            self.claim_inventory_window = None

    def force_inventory_refresh(self):
        """Force a fresh inventory refresh, bypassing any cache.

        Clears cached inventory data and triggers a fresh fetch from the
        server. Only works when inventory window is currently open.
        """
        if (
            hasattr(self, "toggle_claim_inventory")
            and self.toggle_claim_inventory.get()
            and self.claim_inventory_window
            and self.claim_inventory_window.winfo_exists()
        ):

            # Clear cache and refresh
            self.inventory_service.clear_cache()
            self.status_label.configure(text="Refreshing claim inventory data...", text_color="yellow")
            self.inventory_service.fetch_inventory_async(self._on_inventory_data_ready)

    def toggle_passive_crafting_window(self):
        """Toggle the passive crafting window on/off.

        Opens or closes the passive crafting window based on toggle state.
        Handles authentication checks, cached data loading, and window
        lifecycle management. Updates status messages for user feedback.
        """
        if not hasattr(self, "toggle_passive_crafting"):
            logging.error("toggle_passive_crafting switch not found")
            return

        if self.toggle_passive_crafting.get():
            # Opening the window
            if self.bitcraft_client is None or not self.bitcraft_client.ws_connection:
                self.status_label.configure(
                    text="Not authenticated or WS not connected. Please log in.",
                    text_color="red",
                )
                self.toggle_passive_crafting.deselect()
                return

            if self.passive_crafting_window and self.passive_crafting_window.winfo_exists():
                self.passive_crafting_window.focus_set()
                return

            # Check if we have cached data that's still valid
            cached_data = self.passive_crafting_service.get_cached_data()
            if cached_data:
                self.status_label.configure(text="Using cached passive crafting data...", text_color="yellow")
                # Use cached data immediately
                self.after(
                    100,
                    self._on_passive_crafting_data_ready,
                    cached_data,
                    True,
                    "Cached passive crafting data loaded.",
                    False,
                )  # False = cached data
            else:
                # Temporarily disable toggle while loading
                self.toggle_passive_crafting.configure(state="disabled")
                self.status_label.configure(text="Loading passive crafting data...", text_color="yellow")
                self.passive_crafting_service.fetch_passive_crafting_async(self._on_passive_crafting_data_ready)
        else:
            # Closing the window
            if self.passive_crafting_window and self.passive_crafting_window.winfo_exists():
                self.passive_crafting_window.destroy()
                self.passive_crafting_window = None
            self.status_label.configure(text="Passive crafting window closed.", text_color="green")

    def _on_passive_crafting_data_ready(
        self,
        display_data: list,
        success: bool,
        message: str,
        is_fresh_data: bool = False,
    ):
        """Callback when passive crafting data is ready.

        Args:
            display_data: List of passive crafting items for display
            success: Whether data fetch was successful
            message: Status message to display to user
            is_fresh_data: Whether data is freshly fetched or from cache
        """
        if hasattr(self, "toggle_passive_crafting"):
            self.toggle_passive_crafting.configure(state="normal")
        self.status_label.configure(text=message, text_color="green" if success else "red")

        if success:
            # Import here to avoid circular imports
            from passive_crafting_window import PassiveCraftingWindow

            logging.debug(f"About to check if passive crafting window exists. Current window: {self.passive_crafting_window}")
            if self.passive_crafting_window and self.passive_crafting_window.winfo_exists():
                logging.debug("Passive crafting window exists, updating existing window")
                # Window already exists, just update its data
                self.passive_crafting_window.current_crafting_data = display_data

                # Update timestamp if this is fresh data (from refresh button or auto-refresh)
                if is_fresh_data:
                    logging.debug(f"Updating timestamp on existing passive crafting window for fresh data")
                    self.passive_crafting_window.update_last_updated_time(schedule_refresh=True)
                else:
                    logging.debug(f"Not updating timestamp - cached data")

                self.passive_crafting_window.apply_filters_and_sort()
                self.passive_crafting_window.focus_set()
            else:
                logging.debug("Passive crafting window doesn't exist or not valid, will create new one")
                logging.debug("Creating new PassiveCraftingWindow")
                self.passive_crafting_window = PassiveCraftingWindow(
                    self,
                    self.bitcraft_client,
                    self.claim_instance,
                    initial_display_data=display_data,
                    last_fetch_time=self.passive_crafting_service.last_crafting_fetch_time,
                )
                logging.debug(f"Created passive crafting window instance: {id(self.passive_crafting_window)}")
                self.passive_crafting_window.protocol("WM_DELETE_WINDOW", self.on_passive_crafting_window_close)
                self.passive_crafting_window.focus_set()

                # Set timestamp immediately after creation, before any other operations
                if is_fresh_data:
                    # This is fresh data, update with current time and schedule refresh
                    logging.debug(
                        f"Setting fresh data timestamp on passive crafting window instance {id(self.passive_crafting_window)}"
                    )
                    self.passive_crafting_window.update_last_updated_time(schedule_refresh=True)
                else:
                    # We have cached data, show the original fetch time
                    logging.debug(
                        f"Setting cached data timestamp on passive crafting window instance {id(self.passive_crafting_window)}: {self.passive_crafting_service.last_crafting_fetch_time}"
                    )
                    if self.passive_crafting_service.last_crafting_fetch_time:
                        self.passive_crafting_window._set_timestamp_from_fetch_time(
                            self.passive_crafting_service.last_crafting_fetch_time
                        )

                # Now that timestamp is set, apply filters and sort to display the data
                logging.debug(
                    f"Calling apply_filters_and_sort on passive crafting window instance {id(self.passive_crafting_window)}"
                )
                self.passive_crafting_window.apply_filters_and_sort()
        else:
            if hasattr(self, "toggle_passive_crafting"):
                self.toggle_passive_crafting.deselect()

    def on_passive_crafting_window_close(self):
        """Callback when the passive crafting window is closed by user.

        Handles cleanup when user closes the passive crafting window,
        including toggle state reset and window instance cleanup.
        """
        if hasattr(self, "toggle_passive_crafting"):
            self.toggle_passive_crafting.deselect()
        if self.passive_crafting_window:
            # BaseOverlay handles auto-refresh cancellation in its destroy method
            self.passive_crafting_window.destroy()
            self.passive_crafting_window = None

    def force_passive_crafting_refresh(self):
        """Force a fresh passive crafting refresh, bypassing any cache.

        Clears cached passive crafting data and triggers a fresh fetch from
        the server. Only works when passive crafting window is currently open.
        """
        logging.debug(f"force_passive_crafting_refresh called")
        logging.debug(f"  - has toggle_passive_crafting: {hasattr(self, 'toggle_passive_crafting')}")
        if hasattr(self, "toggle_passive_crafting"):
            logging.debug(f"  - toggle state: {self.toggle_passive_crafting.get()}")
        logging.debug(f"  - passive_crafting_window exists: {self.passive_crafting_window is not None}")
        if self.passive_crafting_window:
            logging.debug(f"  - window still valid: {self.passive_crafting_window.winfo_exists()}")

        if (
            hasattr(self, "toggle_passive_crafting")
            and self.toggle_passive_crafting.get()
            and self.passive_crafting_window
            and self.passive_crafting_window.winfo_exists()
        ):
            logging.info("Executing force_passive_crafting_refresh - clearing cache and fetching new data")
            # Clear cache and refresh
            self.passive_crafting_service.clear_cache()
            self.status_label.configure(text="Refreshing passive crafting data...", text_color="yellow")
            self.passive_crafting_service.fetch_passive_crafting_async(self._on_passive_crafting_data_ready)
        else:
            logging.debug("force_passive_crafting_refresh conditions not met - skipping refresh")

    def toggle_passive_crafting_timer_overlay(self):
        """Toggle the passive crafting timer overlay on/off.

        Opens or closes the passive crafting timer overlay based on toggle
        state. Handles authentication checks and overlay lifecycle management.
        Updates status messages for user feedback.
        """
        if not hasattr(self, "toggle_timer_overlay"):
            logging.error("toggle_timer_overlay switch not found")
            return

        if self.toggle_timer_overlay.get():
            # Opening the overlay
            if self.bitcraft_client is None or not self.bitcraft_client.ws_connection:
                self.status_label.configure(
                    text="Not authenticated or WS not connected. Please log in.",
                    text_color="red",
                )
                self.toggle_timer_overlay.deselect()
                return

            if self.passive_crafting_timer_overlay and self.passive_crafting_timer_overlay.winfo_exists():
                self.passive_crafting_timer_overlay.focus_set()
                return

            # Import here to avoid circular imports
            from passive_crafting_timer_overlay import PassiveCraftingTimerOverlay

            self.passive_crafting_timer_overlay = PassiveCraftingTimerOverlay(
                self, self.bitcraft_client, self.passive_crafting_service
            )
            self.passive_crafting_timer_overlay.protocol("WM_DELETE_WINDOW", self.on_passive_crafting_timer_overlay_close)
            self.passive_crafting_timer_overlay.focus_set()
            self.status_label.configure(text="Passive crafting timer opened.", text_color="green")
        else:
            # Closing the overlay
            if self.passive_crafting_timer_overlay and self.passive_crafting_timer_overlay.winfo_exists():
                self.passive_crafting_timer_overlay.destroy()
                self.passive_crafting_timer_overlay = None
            self.status_label.configure(text="Passive crafting timer closed.", text_color="green")

    def on_passive_crafting_timer_overlay_close(self):
        """Callback when the passive crafting timer overlay is closed by user.

        Handles cleanup when user closes the timer overlay, including
        toggle state reset and overlay instance cleanup.
        """
        if hasattr(self, "toggle_timer_overlay"):
            self.toggle_timer_overlay.deselect()
        if self.passive_crafting_timer_overlay:
            # BaseOverlay handles auto-refresh cancellation in its destroy method
            self.passive_crafting_timer_overlay.destroy()
            self.passive_crafting_timer_overlay = None
        self.status_label.configure(text="Passive crafting timer closed.", text_color="green")

    def _clear_content_frame(self):
        """Clear all widgets from the content frame.

        Destroys all child widgets in the main content frame to prepare
        for new UI elements or window state changes.
        """
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    @abstractmethod
    def setup_ui(self):
        """Abstract method to setup the specific UI for this window.

        Must be implemented by subclasses to define their specific
        user interface elements and layout within the content frame.
        """
        pass
