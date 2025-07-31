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

        # Add claim management attributes
        self.available_claims = []
        self.current_claim_id = None
        self.claim_switching = False

        # Initialize data
        self.claim_name = "Loading..."
        self.treasury = 0
        self.supplies = 0
        self.tile_count = 0
        self.supplies_per_hour = 0
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
        Calculate total supplies consumption per hour based on tile count and cost_per_tile.
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

    def _create_claim_info_section(self):
        """Creates the left side claim information display with CTkOptionMenu dropdown."""
        claim_frame = ctk.CTkFrame(self, fg_color="transparent")
        claim_frame.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        # IMPROVED: Use CTkOptionMenu instead of custom dropdown
        self.claim_dropdown = ctk.CTkOptionMenu(
            claim_frame,
            values=["Loading..."],
            command=self._on_claim_selected,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff",
            fg_color=("#2b2b2b", "#3a3a3a"),
            button_color=("#404040", "#505050"),
            button_hover_color=("#505050", "#606060"),
            dropdown_fg_color=("#2a2d2e", "#3a3a3a"),
            dropdown_hover_color=("#1f6aa5", "#2c7bc7"),
            dropdown_text_color="#ffffff",
            corner_radius=8,
            anchor="w",
            state="disabled",  # Start disabled
            height=40,
            width=300,
        )
        self.claim_dropdown.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        # Create info row with treasury, supplies, and supplies run out
        info_frame = ctk.CTkFrame(claim_frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="w")

        # Treasury with icon
        treasury_frame = self._create_enhanced_info_item(info_frame, "💰 Treasury", "0", "#FFD700")
        treasury_frame.grid(row=0, column=0, padx=(0, 20))
        self.treasury_value_label = treasury_frame.winfo_children()[1]

        # Supplies with icon
        supplies_frame = self._create_enhanced_info_item(info_frame, "⚡ Supplies", "0", "#4CAF50")
        supplies_frame.grid(row=0, column=1, padx=(0, 20))
        self.supplies_value_label = supplies_frame.winfo_children()[1]

        # Supplies Run Out with icon
        supplies_runout_frame = self._create_enhanced_info_item(info_frame, "⏱️ Depletes In", "Calculating...", "#FF9800")
        supplies_runout_frame.grid(row=0, column=2)
        self.supplies_runout_label = supplies_runout_frame.winfo_children()[1]

        # Add tooltip to supplies run out label
        self._add_tooltip(self.supplies_runout_label, "This value is approximate and may not exactly match in-game.")

    def _create_enhanced_info_item(self, parent, label_text, value_text, color):
        """Creates an enhanced label-value pair with better styling."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        # Label with better styling
        label = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=11, weight="normal"), text_color="#b0b0b0")
        label.grid(row=0, column=0, sticky="w")

        # Value with enhanced styling
        value = ctk.CTkLabel(frame, text=value_text, font=ctk.CTkFont(size=14, weight="bold"), text_color=color)
        value.grid(row=1, column=0, sticky="w", pady=(2, 0))

        return frame

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
                tooltip,
                text=text,
                background="#222",
                foreground="#fff",
                borderwidth=1,
                relief="solid",
                font=("Arial", 9),
            )
            label.pack(ipadx=4, ipady=2)

        def on_leave(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _on_claim_selected(self, selected_claim_name: str):
        """
        Handles claim selection from the CTkOptionMenu dropdown.
        """
        if self.claim_switching:
            return

        # Find the claim ID from the selected name
        for claim in self.available_claims:
            if claim["claim_name"] == selected_claim_name:
                claim_id = claim["claim_id"]

                # Only switch if it's different from current
                if claim_id != self.current_claim_id:
                    logging.info(f"User selected claim: {selected_claim_name} ({claim_id})")

                    # Start claim switching
                    self.set_claim_switching(True, f"Switching to {selected_claim_name}...")

                    # Notify the main app to perform the switch
                    if hasattr(self.app, "switch_to_claim"):
                        self.app.switch_to_claim(claim_id)
                    else:
                        logging.error("Main app does not support claim switching")
                        self.set_claim_switching(False)
                break

    def update_claim_data(self, claim_data):
        """
        Updates the header with new claim information.
        """
        try:
            # Update stored values
            self.claim_name = claim_data.get("name", "Unknown Claim")
            self.treasury = claim_data.get("treasury", 0)
            self.supplies = claim_data.get("supplies", 0)
            self.tile_count = claim_data.get("tile_count", 0)

            # Calculate supplies per hour based on tile count
            self.supplies_per_hour = self._calculate_supplies_per_hour(self.tile_count)

            # Update UI labels
            if not self.claim_switching:
                self._update_dropdown_selection()

            self.treasury_value_label.configure(text=f"{self.treasury:,}")
            self.supplies_value_label.configure(text=f"{self.supplies:,}")

            # Calculate and update supplies run out time
            self._update_supplies_runout()

            logging.debug(
                f"Claim header updated: {self.claim_name}, Treasury: {self.treasury}, "
                f"Supplies: {self.supplies}, Tiles: {self.tile_count}, "
                f"Consumption: {self.supplies_per_hour:.4f}/hour"
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

    def update_available_claims(self, claims_list: list, current_claim_id: str = None):
        """
        Updates the list of available claims using CTkOptionMenu.
        """
        self.available_claims = claims_list
        if current_claim_id:
            self.current_claim_id = current_claim_id

        # Extract claim names for the dropdown
        claim_names = [claim["claim_name"] for claim in claims_list]

        # Update dropdown state and values based on available claims
        if len(claims_list) > 1:
            # Multiple claims - enable dropdown
            self.claim_dropdown.configure(values=claim_names, state="normal")

            # Set current selection
            current_claim_name = None
            for claim in claims_list:
                if claim["claim_id"] == current_claim_id:
                    current_claim_name = claim["claim_name"]
                    break

            if current_claim_name:
                self.claim_dropdown.set(current_claim_name)
                self.claim_name = current_claim_name

        elif len(claims_list) == 1:
            # Single claim - show name but disable interaction
            single_claim = claims_list[0]
            self.claim_dropdown.configure(values=[single_claim["claim_name"]], state="disabled")
            self.claim_dropdown.set(single_claim["claim_name"])
            self.current_claim_id = single_claim["claim_id"]
            self.claim_name = single_claim["claim_name"]

        else:
            # No claims - show error state
            self.claim_dropdown.configure(values=["❌ No Claims Available"], state="disabled")
            self.claim_dropdown.set("❌ No Claims Available")

        logging.info(f"Updated available claims: {len(claims_list)} claims, current: {current_claim_id}")

    def _update_dropdown_selection(self):
        """Updates the dropdown to show the current claim name."""
        if self.available_claims and not self.claim_switching:
            # Find current claim name and update dropdown
            for claim in self.available_claims:
                if claim["claim_id"] == self.current_claim_id:
                    self.claim_dropdown.set(claim["claim_name"])
                    break

    def set_claim_switching(self, switching: bool, message: str = ""):
        """
        Sets the claim switching state. Instead of showing loading in dropdown,
        this signals the main app to show the loading overlay.
        """
        self.claim_switching = switching

        if switching:
            # Disable dropdown during switching
            self.claim_dropdown.configure(state="disabled")

            # Notify main app to show loading overlay with custom message
            if hasattr(self.app, "show_loading_with_message"):
                self.app.show_loading_with_message(message)

            logging.debug(f"Claim switching started: {message}")
        else:
            # Re-enable dropdown and restore normal state
            if len(self.available_claims) > 1:
                self.claim_dropdown.configure(state="normal")
            else:
                self.claim_dropdown.configure(state="disabled")

            # Notify main app to hide loading overlay
            if hasattr(self.app, "hide_loading"):
                self.app.hide_loading()

            # Restore proper selection
            self._update_dropdown_selection()

            logging.debug("Claim switching completed")

    def handle_claim_switch_complete(self, claim_id: str, claim_name: str):
        """
        Handles the completion of a claim switch operation.
        """
        self.current_claim_id = claim_id
        self.claim_name = claim_name

        # End switching state
        self.set_claim_switching(False)

        # Update dropdown selection
        self._update_dropdown_selection()

        logging.info(f"Claim switch completed: {claim_name}")

    def handle_claim_switch_error(self, error_message: str):
        """
        Handles errors during claim switching.
        """
        # End switching state
        self.set_claim_switching(False)

        logging.error(f"Claim switch error: {error_message}")

    def get_claims_summary(self) -> str:
        """Returns a summary of available claims for debugging."""
        if not self.available_claims:
            return "No claims available"

        current_name = "None"
        if self.current_claim_id:
            for claim in self.available_claims:
                if claim["claim_id"] == self.current_claim_id:
                    current_name = claim["claim_name"]
                    break

        return f"{len(self.available_claims)} claims, current: {current_name}, switching: {self.claim_switching}"

    def initialize_with_claims(self, claims_list: list, current_claim_id: str = None):
        """
        Initializes the header with the claims list on first load.
        """
        try:
            self.update_available_claims(claims_list, current_claim_id)

            # If we have a current claim, update the display
            if current_claim_id:
                current_claim = None
                for claim in claims_list:
                    if claim["claim_id"] == current_claim_id:
                        current_claim = claim
                        break

                if current_claim:
                    # Update header with initial claim data
                    self.update_claim_data(
                        {
                            "name": current_claim["claim_name"],
                            "treasury": current_claim.get("treasury", 0),
                            "supplies": current_claim.get("supplies", 0),
                            "tile_count": current_claim.get("tile_count", 0),
                        }
                    )

            logging.info(f"Header initialized with {len(claims_list)} claims")

        except Exception as e:
            logging.error(f"Error initializing header with claims: {e}")
