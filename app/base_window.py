# base_window.py

import customtkinter as ctk
import logging
from abc import ABC, abstractmethod
from typing import Optional

from client import BitCraft
from claim import Claim
from inventory_service import InventoryService


class BaseWindow(ctk.CTk, ABC):
    """Base class for main application windows with common functionality."""
    
    def __init__(self, title: str = "BitCraft Companion", geometry: str = "400x350"):
        super().__init__()
        
        self.title(title)
        self.geometry(geometry)
        self.resizable(False, False)
        
        # Initialize services
        self.bitcraft_client: Optional[BitCraft] = None
        self.claim_instance: Optional[Claim] = None
        self.inventory_service: Optional[InventoryService] = None
        self.claim_inventory_window = None
        
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
        """Initialize the services with an authenticated client."""
        self.bitcraft_client = authenticated_client
        self.claim_instance = Claim()
        self.inventory_service = InventoryService(self.bitcraft_client, self.claim_instance)
    
    def toggle_claim_inventory_window(self):
        """Toggle the claim inventory window on/off."""
        if not hasattr(self, 'toggle_claim_inventory'):
            logging.error("toggle_claim_inventory switch not found")
            return
            
        if self.toggle_claim_inventory.get():
            # Opening the window
            if self.bitcraft_client is None or not self.bitcraft_client.ws_connection:
                self.status_label.configure(text="Not authenticated or WS not connected. Please log in.", text_color="red")
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
                self.after(100, self._on_inventory_data_ready, cached_data, True, "Cached inventory data loaded.", False)  # False = cached data
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
    
    def _on_inventory_data_ready(self, display_data: list, success: bool, message: str, is_fresh_data: bool = False):
        """Callback when inventory data is ready."""
        if hasattr(self, 'toggle_claim_inventory'):
            self.toggle_claim_inventory.configure(state="normal")
        self.status_label.configure(text=message, text_color="green" if success else "red")

        if success:
            # Import here to avoid circular imports
            from inventory_window import ClaimInventoryWindow
            
            print(f"DEBUG: About to check if window exists. Current window: {self.claim_inventory_window}")
            if self.claim_inventory_window and self.claim_inventory_window.winfo_exists():
                print("DEBUG: Window exists, updating existing window")
                # Window already exists, just update its data
                self.claim_inventory_window.current_inventory_data = display_data
                
                # Update timestamp if this is fresh data (from refresh button or auto-refresh)
                if is_fresh_data:
                    print(f"DEBUG: Updating timestamp on existing window for fresh data")
                    self.claim_inventory_window.update_last_updated_time(schedule_refresh=True)
                else:
                    print(f"DEBUG: Not updating timestamp - cached data")
                
                self.claim_inventory_window.apply_filters_and_sort()
                self.claim_inventory_window.focus_set()
            else:
                print("DEBUG: Window doesn't exist or not valid, will create new one")
                print("DEBUG: Creating new ClaimInventoryWindow")
                self.claim_inventory_window = ClaimInventoryWindow(
                    self, 
                    self.bitcraft_client, 
                    self.claim_instance, 
                    initial_display_data=display_data, 
                    last_fetch_time=self.inventory_service.last_inventory_fetch_time
                )
                print(f"DEBUG: Created window instance: {id(self.claim_inventory_window)}")
                self.claim_inventory_window.protocol("WM_DELETE_WINDOW", self.on_claim_inventory_window_close)
                self.claim_inventory_window.focus_set()
                
                # Set timestamp immediately after creation, before any other operations
                if is_fresh_data:
                    # This is fresh data, update with current time and schedule refresh
                    print(f"DEBUG: Setting fresh data timestamp on window instance {id(self.claim_inventory_window)}")
                    self.claim_inventory_window.update_last_updated_time(schedule_refresh=True)
                else:
                    # We have cached data, show the original fetch time
                    print(f"DEBUG: Setting cached data timestamp on window instance {id(self.claim_inventory_window)}: {self.inventory_service.last_inventory_fetch_time}")
                    if self.inventory_service.last_inventory_fetch_time:
                        self.claim_inventory_window._set_timestamp_from_fetch_time(self.inventory_service.last_inventory_fetch_time)
                
                # Now that timestamp is set, apply filters and sort to display the data
                print(f"DEBUG: Calling apply_filters_and_sort on window instance {id(self.claim_inventory_window)}")
                self.claim_inventory_window.apply_filters_and_sort()
        else:
            if hasattr(self, 'toggle_claim_inventory'):
                self.toggle_claim_inventory.deselect()

    def on_claim_inventory_window_close(self):
        """Callback when the claim inventory window is closed by user."""
        if hasattr(self, 'toggle_claim_inventory'):
            self.toggle_claim_inventory.deselect()
        if self.claim_inventory_window:
            self.claim_inventory_window._cancel_auto_refresh()
            self.claim_inventory_window.destroy()
            self.claim_inventory_window = None

    def force_inventory_refresh(self):
        """Force a fresh inventory refresh, bypassing any cache."""
        if (hasattr(self, 'toggle_claim_inventory') and 
            self.toggle_claim_inventory.get() and 
            self.claim_inventory_window and 
            self.claim_inventory_window.winfo_exists()):
            
            # Clear cache and refresh
            self.inventory_service.clear_cache()
            self.status_label.configure(text="Refreshing claim inventory data...", text_color="yellow")
            self.inventory_service.fetch_inventory_async(self._on_inventory_data_ready)

    def _clear_content_frame(self):
        """Clears all widgets from the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    @abstractmethod
    def setup_ui(self):
        """Abstract method to setup the specific UI for this window."""
        pass
