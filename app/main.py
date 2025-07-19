import customtkinter as ctk
import threading
import logging
import os
from logging.handlers import RotatingFileHandler

from base_window import BaseWindow
from overlay import BitCraftOverlay as LoginOverlay

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def configure_logging():
    """Configure logging with file rotation and console output.

    Sets up rotating file logging that writes to ./logs/bc-companion.log
    with automatic rotation when the file reaches 5MB. Also enables
    console output for real-time monitoring.

    The log files are rotated with a maximum of 1 backup file maintained.
    All logs use UTF-8 encoding for proper character support.
    """
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create rotating file handler (5MB max, 1 backup file)
    log_file = os.path.join(log_dir, "bc-companion.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8"  # 5MB
    )

    # Configure logging with both file and console output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[file_handler, logging.StreamHandler()],
    )


class BitCraftMainWindow(BaseWindow):
    """Main application window for BitCraft Companion.

    Provides the primary user interface with toggles for different features
    like inventory reporting and passive crafting timer overlay. Handles
    initialization of services and claim data for authenticated clients.

    Inherits from BaseWindow to get common window functionality including
    service initialization and window management.
    """

    def __init__(self, authenticated_client=None):
        """Initialize the main BitCraft Companion window.

        Args:
            authenticated_client (BitCraft, optional): An authenticated BitCraft
                client instance. If provided, services will be initialized and
                claim data will be loaded automatically.
        """
        super().__init__("BitCraft Companion", "400x400")

        # Initialize services with authenticated client
        if authenticated_client:
            self.initialize_services(authenticated_client)
            self.setup_ui()
            self._initialize_claim_data()
        else:
            self.status_label.configure(
                text="No authenticated client provided", text_color="red"
            )

    def setup_ui(self):
        """Setup the main user interface with feature toggles.

        Creates a frame containing toggle switches for different application
        features including claim inventory reporting and passive crafting
        timer overlay. Configures the layout and styling for the main window.
        """
        self.toggles_frame = ctk.CTkFrame(self.content_frame)
        self.toggles_frame.pack(fill="both", expand=True)
        self.toggles_frame.grid_columnconfigure(0, weight=1)
        self.toggles_frame.grid_rowconfigure(0, weight=0)
        self.toggles_frame.grid_rowconfigure(1, weight=0)
        self.toggles_frame.grid_rowconfigure(2, weight=1)

        self.toggle_claim_inventory = ctk.CTkSwitch(
            self.toggles_frame,
            text="Claim Inventory Report",
            command=self.toggle_claim_inventory_window,
        )
        self.toggle_claim_inventory.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        self.toggle_timer_overlay = ctk.CTkSwitch(
            self.toggles_frame,
            text="Passive Crafting Timer Overlay",
            command=self.toggle_passive_crafting_timer_overlay,
        )
        self.toggle_timer_overlay.grid(row=1, column=0, padx=20, pady=10, sticky="w")

        # Spacer to push any future elements to the bottom
        ctk.CTkFrame(self.toggles_frame, fg_color="transparent").grid(
            row=2, column=0, sticky="nsew", pady=(0, 10)
        )

        self.status_label.configure(text="BitCraft Companion ready", text_color="green")

    def _initialize_claim_data(self):
        """Initialize claim data for an authenticated client.

        Performs the initial setup sequence including WebSocket connection,
        user ID lookup, and claim data loading. Runs in a background thread
        to avoid blocking the UI during the initialization process.

        Updates the status label to reflect the current initialization state
        and handles errors gracefully by displaying appropriate messages.
        """
        if not self.bitcraft_client:
            logging.error(
                "No authenticated client available for claim data initialization"
            )
            return

        def run_initialization():
            try:
                # Get player name and region from stored data
                player_name_from_file = self.bitcraft_client.player_name
                region_from_file = self.bitcraft_client.region

                # If no region is set, this indicates a problem with authentication flow
                if not region_from_file:
                    logging.error(
                        "No region found in client - authentication may be incomplete"
                    )
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text="No region set - please re-authenticate",
                            text_color="red",
                        ),
                    )
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
                            callback=lambda: self.after(0, self._on_claim_data_ready),
                        )
                    else:
                        logging.warning("Could not fetch user ID from player name.")
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text="Ready (user ID unavailable)", text_color="yellow"
                            ),
                        )
                else:
                    logging.warning("Player name not available for initialization.")
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text="Ready (player name unavailable)", text_color="yellow"
                        ),
                    )

            except Exception as e:
                logging.error(f"Error during claim data initialization: {e}")
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text="Ready (claim data unavailable)", text_color="yellow"
                    ),
                )

        # Run initialization in background thread
        threading.Thread(target=run_initialization, daemon=True).start()

    def _on_claim_data_ready(self):
        """Handle completion of claim data initialization.

        Called when the background claim data initialization process
        completes successfully. Updates the status label to indicate
        the application is ready for use.
        """
        self.status_label.configure(text="BitCraft Companion ready", text_color="green")


if __name__ == "__main__":
    configure_logging()
    app = LoginOverlay()
    app.mainloop()
