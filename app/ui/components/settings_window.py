import os
import json
import logging
import toml
import webbrowser
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from tkinter import messagebox

from ...core.data_paths import get_user_data_path
from app.services.notification_service import NotificationService


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.parent = parent

        # Window configuration - narrower and taller
        self.title("Settings - BitCraft Companion")
        self.geometry("450x500")
        self.resizable(False, False)

        # Make window modal and stay on top
        self.transient(parent)
        self.grab_set()
        self.attributes("-topmost", True)

        # Center on parent window
        self._center_on_parent()

        # Handle window closing
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Load current settings
        self.settings = self._load_settings()

        # Initialize notification service for test notifications
        self.notification_service = NotificationService(self.app)

        # Get version information
        self.version_info = self._get_version_info()

        # Create UI
        self._create_widgets()

        logging.info("Settings window opened")

    def _center_on_parent(self):
        """Center the settings window on the parent window."""
        try:
            self.update_idletasks()

            # Get parent window position and size
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()

            # Get our window size
            window_width = 450
            window_height = 500

            # Calculate center position
            x = parent_x + (parent_width - window_width) // 2
            y = parent_y + (parent_height - window_height) // 2

            self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        except Exception as e:
            logging.error(f"Error centering settings window: {e}")

    def _get_version_info(self):
        """Get version information from pyproject.toml."""
        try:
            # Try to read from pyproject.toml
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            toml_path = os.path.join(project_root, "pyproject.toml")

            if os.path.exists(toml_path):
                with open(toml_path, "r", encoding="utf-8") as f:
                    data = toml.load(f)
                    return data.get("tool", {}).get("poetry", {}).get("version", "Unknown")
            else:
                return "Development Build"

        except Exception as e:
            logging.error(f"Error reading version info: {e}")
            return "Unknown"

    def _create_widgets(self):
        """Create the settings interface with improved UX."""
        # Main scrollable container
        main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Configure grid for left alignment
        main_frame.grid_columnconfigure(0, weight=1)

        # Data Management Section
        self._create_data_management_section(main_frame)

        # Add spacing
        ctk.CTkLabel(main_frame, text="", height=20).pack(fill="x", pady=5)

        # Notifications Section
        self._create_notifications_section(main_frame)

        # Add spacing
        ctk.CTkLabel(main_frame, text="", height=20).pack(fill="x", pady=5)

        # About Section
        self._create_about_section(main_frame)

        # Close button at bottom
        close_frame = ctk.CTkFrame(self, fg_color="transparent")
        close_frame.pack(fill="x", padx=20, pady=(10, 20))

        close_button = ctk.CTkButton(
            close_frame,
            text="Close",
            command=self._on_closing,
            width=100,
            height=32,
            fg_color=("#666666", "#707070"),
            hover_color=("#777777", "#808080"),
        )
        close_button.pack(side="right")

    def _create_data_management_section(self, parent):
        """Create the data management section."""
        # Section header
        header_label = ctk.CTkLabel(parent, text="Data Management", font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        header_label.pack(fill="x", pady=(0, 10))

        # Refresh button
        self.refresh_button = ctk.CTkButton(
            parent,
            text="Refresh Claim Data",
            command=self._refresh_data,
            width=200,
            height=36,
            anchor="w",
            fg_color=("#404040", "#505050"),
            hover_color=("#5a5a5a", "#707070"),
        )
        self.refresh_button.pack(fill="x", pady=(0, 8))

        # Export button
        self.export_button = ctk.CTkButton(
            parent,
            text="Export Data",
            command=self._export_data,
            width=200,
            height=36,
            anchor="w",
            fg_color=("#2E7D32", "#388E3C"),
            hover_color=("#1B5E20", "#2E7D32"),
        )
        self.export_button.pack(fill="x", pady=(0, 8))

    def _create_notifications_section(self, parent):
        """Create the notifications section."""
        # Section header
        header_label = ctk.CTkLabel(parent, text="Notifications", font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        header_label.pack(fill="x", pady=(0, 10))

        # Passive crafts toggle
        self.passive_crafts_var = ctk.BooleanVar(value=self.settings.get("notifications", {}).get("passive_crafts_enabled", True))
        passive_switch = ctk.CTkSwitch(
            parent,
            text="Passive Craft Notifications",
            variable=self.passive_crafts_var,
            command=self._on_setting_change,
            font=ctk.CTkFont(size=13),
        )
        passive_switch.pack(fill="x", anchor="w", pady=(0, 8))

        # Active crafts toggle
        self.active_crafts_var = ctk.BooleanVar(value=self.settings.get("notifications", {}).get("active_crafts_enabled", True))
        active_switch = ctk.CTkSwitch(
            parent,
            text="Active Craft Notifications",
            variable=self.active_crafts_var,
            command=self._on_setting_change,
            font=ctk.CTkFont(size=13),
        )
        active_switch.pack(fill="x", anchor="w", pady=(0, 15))

        # Test notification button (modular)
        if self.settings.get("debug", {}).get("show_test_notification", True):
            test_button = ctk.CTkButton(
                parent,
                text="Test Notification",
                command=self._test_notification,
                width=180,
                height=32,
                fg_color=("#3B8ED0", "#2980B9"),
                hover_color=("#2E7BB8", "#1A5A8A"),
            )
            test_button.pack(fill="x", pady=(0, 8))

    def _create_about_section(self, parent):
        """Create the about section with version and debug info."""
        # Section header
        header_label = ctk.CTkLabel(parent, text="About", font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        header_label.pack(fill="x", pady=(0, 10))

        # Version info
        version_label = ctk.CTkLabel(parent, text=f"Version: {self.version_info}", font=ctk.CTkFont(size=13), anchor="w")
        version_label.pack(fill="x", pady=(0, 5))

        # Developer link
        developer_label = ctk.CTkLabel(
            parent,
            text="Developer: https://github.com/Hatchet-Jackk",
            font=ctk.CTkFont(size=13),
            text_color=("#3B8ED0", "#2980B9"),
            anchor="w",
            cursor="hand2",
        )
        developer_label.pack(fill="x", pady=(0, 15))
        developer_label.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Hatchet-Jackk"))

        # Debug information header
        debug_header = ctk.CTkLabel(parent, text="Debug Information:", font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        debug_header.pack(fill="x", pady=(0, 5))

        # Get debug info from app
        debug_info = self._get_debug_info()

        # Player info
        player_label = ctk.CTkLabel(
            parent,
            text=f"Player: {debug_info.get('player', 'Unknown')}",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray40"),
            anchor="w",
        )
        player_label.pack(fill="x", pady=(0, 2))

        # Region info
        region_label = ctk.CTkLabel(
            parent,
            text=f"Region: {debug_info.get('region', 'Unknown')}",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray40"),
            anchor="w",
        )
        region_label.pack(fill="x", pady=(0, 2))

        # Claims info
        claims_label = ctk.CTkLabel(
            parent,
            text=f"Claims loaded: {debug_info.get('claims_count', 0)}",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray40"),
            anchor="w",
        )
        claims_label.pack(fill="x", pady=(0, 2))

    def _get_debug_info(self):
        """Get debug information from the app."""
        try:
            debug_info = {}

            # Get player name
            if hasattr(self.app, "data_service") and self.app.data_service:
                client = self.app.data_service.client
                debug_info["player"] = getattr(client, "player_name", "Unknown")
                debug_info["region"] = getattr(client, "region", "Unknown")

            # Get claims count
            if hasattr(self.app, "claim_info") and self.app.claim_info:
                claims = getattr(self.app.claim_info, "available_claims", [])
                debug_info["claims_count"] = len(claims)
            else:
                debug_info["claims_count"] = 0

            return debug_info

        except Exception as e:
            logging.error(f"Error getting debug info: {e}")
            return {"player": "Error", "region": "Error", "claims_count": 0}

    def _load_settings(self):
        """Load settings with default values."""
        try:
            # Default settings structure
            default_settings = {
                "notifications": {
                    "passive_crafts_enabled": True,
                    "active_crafts_enabled": True,
                },
                "debug": {"show_test_notification": True},
            }

            # Load from player_data.json
            try:
                file_path = get_user_data_path("player_data.json")
                with open(file_path, "r") as f:
                    player_data = json.load(f)
                    
                # Extract settings from player_data, merge with defaults
                saved_settings = player_data.get("settings", {})
                if saved_settings:
                    # Deep merge: update defaults with saved settings
                    for category, options in saved_settings.items():
                        if category in default_settings and isinstance(options, dict):
                            default_settings[category].update(options)
                        else:
                            default_settings[category] = options
                    
                logging.info("Settings loaded from player_data.json")
                
            except FileNotFoundError:
                logging.info("No player_data.json found, using default settings")
            except json.JSONDecodeError:
                logging.warning("player_data.json is malformed, using default settings")
            except Exception as e:
                logging.error(f"Error reading player_data.json: {e}, using defaults")

            return default_settings

        except Exception as e:
            logging.error(f"Error loading settings: {e}")
            return {
                "notifications": {"passive_crafts_enabled": True, "active_crafts_enabled": True},
                "debug": {"show_test_notification": True},
            }

    def _save_settings(self):
        """Save settings to persistent storage."""
        try:
            # Update settings based on UI state
            self.settings["notifications"]["passive_crafts_enabled"] = self.passive_crafts_var.get()
            self.settings["notifications"]["active_crafts_enabled"] = self.active_crafts_var.get()

            # Send updated settings to notification service
            if hasattr(self.app, 'data_service') and self.app.data_service and hasattr(self.app.data_service, 'notification_service'):
                self.app.data_service.notification_service.update_settings(self.settings)
                logging.info(f"Settings sent to notification service: {self.settings['notifications']}")
            else:
                logging.warning("Could not access notification service to update settings")

            # Save to player_data.json
            try:
                file_path = get_user_data_path("player_data.json")
                
                # Load existing player data or create new
                player_data = {}
                try:
                    with open(file_path, "r") as f:
                        player_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    pass  # Start with empty dict if file doesn't exist or is corrupted
                
                # Update settings section
                player_data["settings"] = self.settings
                
                # Write back to file
                with open(file_path, "w") as f:
                    json.dump(player_data, f, indent=4)
                
                logging.info("Settings saved to player_data.json")
                
            except Exception as e:
                logging.error(f"Error saving to player_data.json: {e}")

        except Exception as e:
            logging.error(f"Error saving settings: {e}")

    def _on_setting_change(self):
        """Called when any setting changes."""
        self._save_settings()
        logging.info("Settings updated")

    def _refresh_data(self):
        """Trigger data refresh for current claim."""
        try:
            # Disable button during refresh
            self.refresh_button.configure(state="disabled", text="Refreshing...")

            # Request current claim data refresh from the data service
            logging.info("[Settings] Refresh claim data button clicked - starting refresh process")
            if hasattr(self.app, "data_service") and self.app.data_service:
                logging.debug("[Settings] DataService found - calling refresh_current_claim_data()")
                success = self.app.data_service.refresh_current_claim_data()
                if success:
                    logging.info("[Settings] Current claim data refresh completed successfully")
                else:
                    logging.warning("[Settings] Current claim data refresh failed")
            else:
                logging.error("[Settings] Data service not available for claim data refresh")

            # Re-enable button after delay
            self.after(2000, lambda: self.refresh_button.configure(state="normal", text="Refresh Claim Data"))

        except Exception as e:
            logging.error(f"Error triggering data refresh: {e}")
            messagebox.showerror("Refresh Error", f"Failed to refresh data: {e}")
            # Re-enable button on error
            self.refresh_button.configure(state="normal", text="Refresh Claim Data")

    def _export_data(self):
        """Trigger data export."""
        try:
            if hasattr(self.app, "claim_info") and self.app.claim_info:
                # Call the existing export method in the claim_info_header
                self.app.claim_info._export_data()
                logging.info("Data export triggered from settings")
            else:
                logging.error("Claim info not available for data export")
                messagebox.showerror("Export Error", "Unable to access claim information for export")

        except Exception as e:
            logging.error(f"Error triggering data export: {e}")
            messagebox.showerror("Export Error", f"Failed to export data: {e}")

    def _test_notification(self):
        """Show a test notification."""
        try:
            # Update notification service settings from UI
            notification_settings = {
                "passive_crafts_enabled": self.passive_crafts_var.get(),
                "active_crafts_enabled": self.active_crafts_var.get(),
            }
            self.notification_service.update_settings(notification_settings)

            # Show test notification
            self.notification_service.show_test_notification()
            logging.info("Test notification triggered from settings")

        except Exception as e:
            logging.error(f"Error showing test notification: {e}")
            messagebox.showerror("Test Error", f"Failed to show test notification: {e}")

    def _on_closing(self):
        """Handle window closing."""
        try:
            self._save_settings()
            self.destroy()
            logging.info("Settings window closed")

        except Exception as e:
            logging.error(f"Error closing settings window: {e}")
            self.destroy()
