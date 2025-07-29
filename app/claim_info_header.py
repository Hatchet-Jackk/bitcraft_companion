import customtkinter as ctk
import logging


class ClaimInfoHeader(ctk.CTkFrame):
    """
    Header widget displaying claim information including name, treasury, supplies,
    and time remaining until supplies are depleted.
    """

    def __init__(self, master, app):
        super().__init__(master, fg_color="#1a1a1a", corner_radius=8)
        self.app = app

        # Initialize data
        self.claim_name = "Loading..."
        self.treasury = 0
        self.supplies = 0
        self.time_remaining = "Calculating..."
        self.supplies_per_hour = 0  # Will be calculated based on claim size/buildings

        self._create_widgets()

    def _create_widgets(self):
        """Creates and arranges the header widgets."""
        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Left side - Claim information
        self._create_claim_info_section()

        # Right side - User profile (placeholder for now)
        self._create_user_profile_section()

    def _create_claim_info_section(self):
        """Creates the left side claim information display."""
        claim_frame = ctk.CTkFrame(self, fg_color="transparent")
        claim_frame.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        # Claim name (larger, prominent)
        self.claim_name_label = ctk.CTkLabel(
            claim_frame, text=self.claim_name, font=ctk.CTkFont(size=20, weight="bold"), text_color="#ffffff"
        )
        self.claim_name_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        # Create info row with treasury, supplies, and time remaining
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

        # Time remaining
        time_frame = self._create_info_item(info_frame, "Time Remaining:", "Calculating...", "#FF9800")
        time_frame.grid(row=0, column=2)
        self.time_remaining_label = time_frame.winfo_children()[1]  # Store reference to value label

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
                Expected keys: name, treasury, supplies, supplies_per_hour
        """
        try:
            # Update stored values
            self.claim_name = claim_data.get("name", "Unknown Claim")
            self.treasury = claim_data.get("treasury", 0)
            self.supplies = claim_data.get("supplies", 0)
            self.supplies_per_hour = claim_data.get("supplies_per_hour", 0)

            # Update UI labels
            self.claim_name_label.configure(text=self.claim_name)
            self.treasury_value_label.configure(text=f"{self.treasury:,}")
            self.supplies_value_label.configure(text=f"{self.supplies:,}")

            # Calculate and update time remaining
            self._update_time_remaining()

            logging.info(f"Claim header updated: {self.claim_name}, Treasury: {self.treasury}, Supplies: {self.supplies}")

        except Exception as e:
            logging.error(f"Error updating claim data in header: {e}")

    def _update_time_remaining(self):
        """Calculates and updates the time remaining until supplies are depleted."""
        try:
            if self.supplies_per_hour <= 0:
                self.time_remaining = "N/A"
                color = "#cccccc"
            elif self.supplies <= 0:
                self.time_remaining = "Depleted"
                color = "#f44336"
            else:
                hours_remaining = self.supplies / self.supplies_per_hour

                if hours_remaining < 1:
                    minutes = int(hours_remaining * 60)
                    self.time_remaining = f"{minutes}m"
                    color = "#f44336"  # Red for urgent
                elif hours_remaining < 24:
                    hours = int(hours_remaining)
                    minutes = int((hours_remaining - hours) * 60)
                    self.time_remaining = f"{hours}h {minutes}m"
                    color = "#FF9800"  # Orange for warning
                else:
                    days = int(hours_remaining / 24)
                    hours = int(hours_remaining % 24)
                    self.time_remaining = f"{days}d {hours}h"
                    color = "#4CAF50"  # Green for safe

            # Update the label with appropriate color
            self.time_remaining_label.configure(text=self.time_remaining, text_color=color)

        except Exception as e:
            logging.error(f"Error calculating time remaining: {e}")
            self.time_remaining = "Error"
            self.time_remaining_label.configure(text=self.time_remaining, text_color="#f44336")

    def refresh_time_remaining(self):
        """Manually refresh the time remaining calculation (for periodic updates)."""
        self._update_time_remaining()
