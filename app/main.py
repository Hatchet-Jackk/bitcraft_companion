import customtkinter as ctk
import tkinter as tk
import threading
import logging
from datetime import datetime
from enum import Enum

from client import BitCraft
from claim import Claim
from base_window import BaseWindow
from inventory_service import InventoryService
from overlay import BitCraftOverlay as LoginOverlay

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class BitCraftMainWindow(BaseWindow):
    def __init__(self, authenticated_client=None):
        super().__init__("BitCraft Companion", "400x400")

        # Initialize services with authenticated client
        if authenticated_client:
            self.initialize_services(authenticated_client)
            self.setup_ui()
            self._initialize_claim_data()
        else:
            self.status_label.configure(text="No authenticated client provided", text_color="red")

    def setup_ui(self):
        """Setup the main toggles UI."""
        self.toggles_frame = ctk.CTkFrame(self.content_frame)
        self.toggles_frame.pack(fill="both", expand=True)
        self.toggles_frame.grid_columnconfigure(0, weight=1)
        self.toggles_frame.grid_rowconfigure(0, weight=0)  
        self.toggles_frame.grid_rowconfigure(1, weight=0)
        self.toggles_frame.grid_rowconfigure(2, weight=1) 

        self.toggle_claim_inventory = ctk.CTkSwitch(
            self.toggles_frame, 
            text="Claim Inventory Report", 
            command=self.toggle_claim_inventory_window
        )
        self.toggle_claim_inventory.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        self.toggle_timer_overlay = ctk.CTkSwitch(
            self.toggles_frame, 
            text="Passive Crafting Timer Overlay", 
            command=self.toggle_passive_crafting_timer_overlay
        )
        self.toggle_timer_overlay.grid(row=1, column=0, padx=20, pady=10, sticky="w")

        # Spacer to push any future elements to the bottom
        ctk.CTkFrame(self.toggles_frame, fg_color="transparent").grid(row=2, column=0, sticky="nsew", pady=(0,10))

        self.status_label.configure(text="BitCraft Companion ready", text_color="green")

    def _initialize_claim_data(self):
        """Initialize claim data for an already authenticated client."""
        if not self.bitcraft_client:
            logging.error("No authenticated client available for claim data initialization")
            return

        def run_initialization():
            try:
                # Get player name and region from stored data
                player_name_from_file = self.bitcraft_client.player_name
                region_from_file = self.bitcraft_client.region
                
                # If no region is set, this indicates a problem with authentication flow
                if not region_from_file:
                    logging.error("No region found in client - authentication may be incomplete")
                    self.after(0, lambda: self.status_label.configure(text="No region set - please re-authenticate", text_color="red"))
                    return

                # Set up connection
                self.bitcraft_client.set_region(region_from_file)
                self.bitcraft_client.set_endpoint("subscribe")
                self.bitcraft_client.set_websocket_uri()
                self.bitcraft_client.connect_websocket()

                if player_name_from_file:
                    user_id = self.bitcraft_client.fetch_user_id(player_name_from_file)
                    if user_id:
                        # Use the inventory service to initialize claim data
                        self.inventory_service.initialize_claim_data_async(
                            user_id, 
                            callback=lambda: self.after(0, self._on_claim_data_ready)
                        )
                    else:
                        logging.warning("Could not fetch user ID from player name.")
                        self.after(0, lambda: self.status_label.configure(text="Ready (user ID unavailable)", text_color="yellow"))
                else:
                    logging.warning("Player name not available for initialization.")
                    self.after(0, lambda: self.status_label.configure(text="Ready (player name unavailable)", text_color="yellow"))

            except Exception as e:
                logging.error(f"Error during claim data initialization: {e}")
                self.after(0, lambda: self.status_label.configure(text="Ready (claim data unavailable)", text_color="yellow"))

        # Run initialization in background thread
        threading.Thread(target=run_initialization, daemon=True).start()

    def _on_claim_data_ready(self):
        """Called when claim data initialization is complete."""
        self.status_label.configure(text="BitCraft Companion ready", text_color="green")

if __name__ == "__main__":
    app = LoginOverlay()
    app.mainloop()