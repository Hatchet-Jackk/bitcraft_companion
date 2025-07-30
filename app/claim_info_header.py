import customtkinter as ctk
import logging
import tkinter as tk


class ClaimInfoHeader(ctk.CTkFrame):
    """
    Header widget displaying claim information including name, treasury, supplies,
    and time remaining until supplies are depleted based on tile count.
    """

    def __init__(self, master, app):
        super().__init__(master, fg_color="#1a1a1a", corner_radius=8)
        self.app = app

        # Initialize data
        self.claim_name = "Loading..."
        self.treasury = 0
        self.supplies = 0
        self.tile_count = 0  # NEW: Track tile count for supplies calculation
        self.supplies_per_hour = 0  # Will be calculated based on tile count
        self.time_remaining = "Calculating..."

        # Load tile cost data from the app's data service
        self.tile_cost_lookup = {}
        self._load_tile_cost_data()

        self._create_widgets()

    def _load_tile_cost_data(self):
        """Load claim tile cost data for supplies calculation."""
        try:
            if hasattr(self.app, "data_service") and self.app.data_service and hasattr(self.app.data_service, "client"):
                client = self.app.data_service.client
                tile_cost_data = client._load_reference_data("claim_tile_cost")

                if tile_cost_data:
                    # Create lookup table: tile_count -> cost_per_tile
                    for entry in tile_cost_data:
                        tile_count = entry.get("tile_count", 0)
                        cost_per_tile = entry.get("cost_per_tile", 0.0)
                        self.tile_cost_lookup[tile_count] = cost_per_tile
                    logging.info(f"Loaded {len(self.tile_cost_lookup)} tile cost entries")
                else:
                    logging.warning("No tile cost data found")
        except Exception as e:
            logging.error(f"Error loading tile cost data: {e}")
            self.tile_cost_lookup = {1: 0.01, 1001: 0.0125}  # fallback values

    def _calculate_supplies_per_hour(self, tile_count):
        """
        Calculate total supplies consumption per hour based on tile count and cost_per_tile (step, not interpolation).
        """
        if not tile_count or tile_count <= 0:
            return 0.0

        sorted_tile_counts = sorted(self.tile_cost_lookup.keys())
        if tile_count in self.tile_cost_lookup:
            cost_per_tile = self.tile_cost_lookup[tile_count]
        elif tile_count <= sorted_tile_counts[0]:
            cost_per_tile = self.tile_cost_lookup[sorted_tile_counts[0]]
        elif tile_count >= sorted_tile_counts[-1]:
            cost_per_tile = self.tile_cost_lookup[sorted_tile_counts[-1]]
        else:
            # Use the largest tile_count less than or equal to the current tile_count
            lower_tiles = max(t for t in sorted_tile_counts if t <= tile_count)
            cost_per_tile = self.tile_cost_lookup[lower_tiles]
        return tile_count * cost_per_tile

    def _create_widgets(self):
        """Creates and arranges the header widgets."""
        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Left side - Claim information
        self._create_claim_info_section()

        # Right side - User profile (placeholder for now)
        # self._create_user_profile_section()

    def _create_claim_info_section(self):
        """Creates the left side claim information display."""
        claim_frame = ctk.CTkFrame(self, fg_color="transparent")
        claim_frame.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        # Claim name (larger, prominent)
        self.claim_name_label = ctk.CTkLabel(
            claim_frame, text=self.claim_name, font=ctk.CTkFont(size=20, weight="bold"), text_color="#ffffff"
        )
        self.claim_name_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        # Create info row with treasury, supplies, and supplies run out
        info_frame = ctk.CTkFrame(claim_frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="w")

        # Treasury
        treasury_frame = self._create_info_item(info_frame, "Treasury:", "0", "#FFD700")
        treasury_frame.grid(row=0, column=0, padx=(0, 20))
        self.treasury_value_label = treasury_frame.winfo_children()[1]  # Store reference to value label

        # Supplies
        supplies_frame = self._create_info_item(info_frame, "Supplies:", "0", "#4CAF50")
        supplies_frame.grid(row=0, column=1, padx=(0, 20))
        self.supplies_value_label = supplies_frame.winfo_children()[1]  # Store reference to value label

        # UPDATED: Supplies Run Out (instead of Time Remaining)
        supplies_runout_frame = self._create_info_item(info_frame, "Supplies Run Out:", "Calculating...", "#FF9800")
        supplies_runout_frame.grid(row=0, column=2)
        self.supplies_runout_label = supplies_runout_frame.winfo_children()[1]  # Store reference to value label

        # Add tooltip to supplies run out label
        self._add_tooltip(self.supplies_runout_label, "This value is approximate and may not exactly match in-game.")

    def _add_tooltip(self, widget, text):
        """Adds a simple tooltip to a widget."""
        tooltip = None

        def on_enter(event):
            nonlocal tooltip
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 20
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")
            label = tk.Label(
                tooltip, text=text, background="#222", foreground="#fff", borderwidth=1, relief="solid", font=("Arial", 9)
            )
            label.pack(ipadx=4, ipady=2)

        def on_leave(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _create_info_item(self, parent, label_text, value_text, color):
        """Creates a label-value pair with styling."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        # Label
        label = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=12), text_color="#cccccc")
        label.grid(row=0, column=0, sticky="w")

        # Value
        value = ctk.CTkLabel(frame, text=value_text, font=ctk.CTkFont(size=14, weight="bold"), text_color=color)
        value.grid(row=1, column=0, sticky="w")

        return frame

    def _create_user_profile_section(self):
        """Creates the right side user profile area."""
        profile_frame = ctk.CTkFrame(self, fg_color="transparent")
        profile_frame.grid(row=0, column=1, sticky="e", padx=15, pady=10)

        # User profile button (clickable for options)
        self.profile_button = ctk.CTkButton(
            profile_frame,
            text="⚙️ Options",
            width=100,
            height=32,
            corner_radius=6,
            fg_color="#2c5d8f",
            hover_color="#3a75b4",
            command=self._show_options_menu,
        )
        self.profile_button.pack()

    def _show_options_menu(self):
        """Shows the options menu (placeholder for now)."""
        # TODO: Implement options menu with theme selection and logout
        logging.info("Options menu clicked - to be implemented")

    def update_claim_data(self, claim_data):
        """
        Updates the header with new claim information.

        Args:
            claim_data (dict): Dictionary containing claim information
                Expected keys: name, treasury, supplies, tile_count (NEW)
        """
        try:
            # Update stored values
            self.claim_name = claim_data.get("name", "Unknown Claim")
            self.treasury = claim_data.get("treasury", 0)
            self.supplies = claim_data.get("supplies", 0)
            self.tile_count = claim_data.get("tile_count", 0)  # NEW: Get tile count

            # Calculate supplies per hour based on tile count
            self.supplies_per_hour = self._calculate_supplies_per_hour(self.tile_count)

            # Update UI labels
            self.claim_name_label.configure(text=self.claim_name)
            self.treasury_value_label.configure(text=f"{self.treasury:,}")
            self.supplies_value_label.configure(text=f"{self.supplies:,}")

            # Calculate and update supplies run out time
            self._update_supplies_runout()

            logging.debug(
                f"Claim header updated: {self.claim_name}, Treasury: {self.treasury}, Supplies: {self.supplies}, Tiles: {self.tile_count}, Consumption: {self.supplies_per_hour:.4f}/hour"
            )

        except Exception as e:
            logging.error(f"Error updating claim data in header: {e}")

    def _update_supplies_runout(self):
        """Calculates and updates the time until supplies run out based on tile count."""
        try:
            if self.supplies_per_hour <= 0:
                self.time_remaining = "N/A"
                color = "#cccccc"
            elif self.supplies <= 0:
                self.time_remaining = "Depleted"
                color = "#f44336"
            else:
                total_seconds = int(self.supplies * 3600 / self.supplies_per_hour)
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60

                if total_seconds < 1800:  # less than 30 minutes
                    self.time_remaining = f"{minutes}m {seconds}s"
                    color = "#f44336"  # Red for urgent
                elif days == 0 and hours == 0:
                    self.time_remaining = f"{minutes}m"
                    color = "#f44336"
                elif days == 0:
                    self.time_remaining = f"{hours}h {minutes}m"
                    color = "#FF9800"  # Orange for warning
                elif days < 7:
                    self.time_remaining = f"{days}d {hours}h {minutes}m"
                    color = "#FFC107"  # Amber for caution
                else:
                    self.time_remaining = f"{days}d {hours}h {minutes}m"
                    color = "#4CAF50"  # Green for safe

            # Update the label with appropriate color
            self.supplies_runout_label.configure(text=self.time_remaining, text_color=color)

        except Exception as e:
            logging.error(f"Error calculating supplies run out time: {e}")
            self.time_remaining = "Error"
            self.supplies_runout_label.configure(text=self.time_remaining, text_color="#f44336")

    def refresh_supplies_runout(self):
        """Manually refresh the supplies run out calculation (for periodic updates)."""
        self._update_supplies_runout()
