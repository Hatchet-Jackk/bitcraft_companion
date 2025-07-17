# overlay.py

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import logging
from enum import Enum

from client import BitCraft
from base_window import BaseWindow

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Configure Customtkinter Theme ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- UI States ---
class OverlayState(Enum):
    LOGIN_EMAIL = 1
    ACCESS_CODE = 2
    PLAYER_NAME = 3
    MAIN_TOGGLES = 4

class BitCraftOverlay(BaseWindow):
    def __init__(self):
        super().__init__("BitCraft Login", "400x300")

        # Store data between states
        self.stored_email = None
        self.stored_access_code = None
        self.stored_player_name = None
        self.stored_region = "bitcraft-1"  # Default region

        self._current_ui_state = None

        # Initialize a client to check for stored credentials
        temp_client = BitCraft()
        
        logging.info(f"Debug - Email from client: {temp_client.email}")
        logging.info(f"Debug - Auth token exists: {bool(temp_client.auth)}")
        logging.info(f"Debug - Auth token value: {temp_client.auth[:20] if temp_client.auth else None}...")
        
        # Check if we have stored credentials and determine initial state
        if temp_client.auth and temp_client.email:
            # We have valid stored credentials, initialize services and go to player name
            self.initialize_services(temp_client)
            self.stored_email = temp_client.email
            if hasattr(temp_client, 'player_name') and temp_client.player_name:
                self.stored_player_name = temp_client.player_name
            if hasattr(temp_client, 'region') and temp_client.region:
                self.stored_region = temp_client.region
            
            self.status_label.configure(text="Ready to connect", text_color="green")
            self._transition_to_ui_state(OverlayState.PLAYER_NAME)
        else:
            # No valid stored credentials, initialize services with new client
            self.initialize_services(temp_client)
            self.status_label.configure(text="Enter your email to begin", text_color="yellow")
            self._transition_to_ui_state(OverlayState.LOGIN_EMAIL)

    def setup_ui(self):
        """Setup UI is handled by state transitions in overlay."""
        pass

    def _transition_to_ui_state(self, new_state: OverlayState):
        """Manages clearing current UI and setting up new UI state."""
        if self._current_ui_state == new_state:
            return

        self._clear_content_frame()
        self._current_ui_state = new_state

        if new_state == OverlayState.LOGIN_EMAIL:
            self._setup_login_email_ui()
            self.geometry("400x300")
            self.status_label.configure(text="Enter your email to begin", text_color="yellow")
        elif new_state == OverlayState.ACCESS_CODE:
            self._setup_access_code_ui()
            self.geometry("400x250")
            self.status_label.configure(text="Enter access code from your email", text_color="yellow")
        elif new_state == OverlayState.PLAYER_NAME:
            self._setup_player_name_ui()
            self.geometry("400x400")
            self.status_label.configure(text="Enter your player name", text_color="yellow")
        elif new_state == OverlayState.MAIN_TOGGLES:
            self._setup_main_toggles_ui()
            self.geometry("400x300")
            self.title("BitCraft Companion")
            self.status_label.configure(text="BitCraft Companion ready", text_color="green")

    def _setup_login_email_ui(self):
        """Sets up the UI for email input."""
        self.email_frame = ctk.CTkFrame(self.content_frame)
        self.email_frame.pack(fill="both", expand=True)
        self.email_frame.grid_columnconfigure(0, weight=1)
        for i in range(5):
            self.email_frame.grid_rowconfigure(i, weight=0)
        self.email_frame.grid_rowconfigure(5, weight=1)

        # Title
        title_label = ctk.CTkLabel(self.email_frame, text="First Time Login", 
                                   font=ctk.CTkFont(size=20, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Email input
        self.label_email = ctk.CTkLabel(self.email_frame, text="Email:")
        self.label_email.grid(row=1, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.entry_email = ctk.CTkEntry(self.email_frame, placeholder_text="Enter your email address")
        self.entry_email.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        # Set stored email if available
        if self.stored_email:
            self.entry_email.delete(0, ctk.END)
            self.entry_email.insert(0, self.stored_email)

        # Button frame
        button_frame = ctk.CTkFrame(self.email_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        # Get Access Code button
        self.get_code_button = ctk.CTkButton(
            button_frame, 
            text="Get Access Code", 
            command=self._get_access_code_flow
        )
        self.get_code_button.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")

        # Quit button
        self.quit_button = ctk.CTkButton(
            button_frame, 
            text="Quit", 
            command=self.quit,
            fg_color="red",
            hover_color="darkred"
        )
        self.quit_button.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="ew")

        # Bind Enter key to get access code
        self.entry_email.bind("<Return>", lambda event: self._get_access_code_flow())

    def _setup_access_code_ui(self):
        """Sets up the UI for access code input."""
        self.access_code_frame = ctk.CTkFrame(self.content_frame)
        self.access_code_frame.pack(fill="both", expand=True)
        self.access_code_frame.grid_columnconfigure(0, weight=1)
        for i in range(5):
            self.access_code_frame.grid_rowconfigure(i, weight=0)
        self.access_code_frame.grid_rowconfigure(5, weight=1)

        # Title
        title_label = ctk.CTkLabel(self.access_code_frame, text="Enter Access Code", 
                                   font=ctk.CTkFont(size=20, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Access code input
        self.label_access_code = ctk.CTkLabel(self.access_code_frame, text="Access Code:")
        self.label_access_code.grid(row=1, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.entry_access_code = ctk.CTkEntry(self.access_code_frame, 
                                              placeholder_text="Enter 6-character access code")
        self.entry_access_code.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        # Set stored access code if available
        if self.stored_access_code:
            self.entry_access_code.delete(0, ctk.END)
            self.entry_access_code.insert(0, self.stored_access_code)

        # Button frame
        button_frame = ctk.CTkFrame(self.access_code_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        # Authenticate button
        self.authenticate_button = ctk.CTkButton(
            button_frame, 
            text="Authenticate", 
            command=self._authenticate_flow
        )
        self.authenticate_button.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")

        # Back button
        self.back_button = ctk.CTkButton(
            button_frame, 
            text="Back", 
            command=lambda: self._transition_to_ui_state(OverlayState.LOGIN_EMAIL),
            fg_color="gray",
            hover_color="darkgray"
        )
        self.back_button.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="ew")

        # Bind Enter key to authenticate
        self.entry_access_code.bind("<Return>", lambda event: self._authenticate_flow())

    def _setup_player_name_ui(self):
        """Sets up the UI for player name input."""
        self.player_name_frame = ctk.CTkFrame(self.content_frame)
        self.player_name_frame.pack(fill="both", expand=True)
        self.player_name_frame.grid_columnconfigure(0, weight=1)
        for i in range(8):
            self.player_name_frame.grid_rowconfigure(i, weight=0)
        self.player_name_frame.grid_rowconfigure(8, weight=1)

        # Check if we have stored credentials (authenticated user)
        has_credentials = self.bitcraft_client.auth and self.bitcraft_client.email
        
        if has_credentials:
            # Title for authenticated users
            title_label = ctk.CTkLabel(self.player_name_frame, text="Ready to Connect", 
                                       font=ctk.CTkFont(size=20, weight="bold"))
            title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

            # Show current email
            email_label = ctk.CTkLabel(self.player_name_frame, text=f"Email: {self.stored_email}", 
                                       text_color="gray")
            email_label.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        else:
            # Title for new authentication flow
            title_label = ctk.CTkLabel(self.player_name_frame, text="Enter Player Details", 
                                       font=ctk.CTkFont(size=20, weight="bold"))
            title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

            # Info label
            info_label = ctk.CTkLabel(self.player_name_frame, 
                                      text="Your player name helps us find your claim data",
                                      text_color="gray")
            info_label.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Player name input
        self.label_player_name = ctk.CTkLabel(self.player_name_frame, text="Player Name:")
        self.label_player_name.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.entry_player_name = ctk.CTkEntry(self.player_name_frame, 
                                              placeholder_text="Enter your player name")
        self.entry_player_name.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        # Set stored player name if available
        if self.stored_player_name:
            self.entry_player_name.delete(0, ctk.END)
            self.entry_player_name.insert(0, self.stored_player_name)

        # Region selection
        self.label_region = ctk.CTkLabel(self.player_name_frame, text="Region:")
        self.label_region.grid(row=4, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.regions = ["bitcraft-1", "bitcraft-2", "bitcraft-3", "bitcraft-4", "bitcraft-5"]
        self.region_var = ctk.StringVar(value=self.stored_region)
        self.optionmenu_region = ctk.CTkOptionMenu(self.player_name_frame, values=self.regions,
                                                   variable=self.region_var)
        self.optionmenu_region.grid(row=5, column=0, padx=20, pady=5, sticky="ew")

        # Button frame
        button_frame = ctk.CTkFrame(self.player_name_frame, fg_color="transparent")
        button_frame.grid(row=6, column=0, padx=20, pady=20, sticky="ew")
        
        if has_credentials:
            # For authenticated users: Connect and Logout buttons
            button_frame.grid_columnconfigure((0, 1), weight=1)
            
            self.connect_button = ctk.CTkButton(
                button_frame, 
                text="Connect", 
                command=self._connect_flow
            )
            self.connect_button.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")

            self.logout_button = ctk.CTkButton(
                button_frame, 
                text="Logout", 
                command=self._logout_flow,
                fg_color="red",
                hover_color="darkred"
            )
            self.logout_button.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="ew")
        else:
            # For new users: Connect and Back buttons
            button_frame.grid_columnconfigure((0, 1), weight=1)
            
            self.connect_button = ctk.CTkButton(
                button_frame, 
                text="Connect", 
                command=self._connect_flow
            )
            self.connect_button.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")

            self.back_button_player = ctk.CTkButton(
                button_frame, 
                text="Back", 
                command=lambda: self._transition_to_ui_state(OverlayState.ACCESS_CODE),
                fg_color="gray",
                hover_color="darkgray"
            )
            self.back_button_player.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="ew")

        # Bind Enter key to connect
        self.entry_player_name.bind("<Return>", lambda event: self._connect_flow())

    def _setup_main_toggles_ui(self):
        """Sets up the UI with application toggles and navigation buttons."""
        self.toggles_frame = ctk.CTkFrame(self.content_frame)
        self.toggles_frame.pack(fill="both", expand=True)
        self.toggles_frame.grid_columnconfigure(0, weight=1)
        self.toggles_frame.grid_rowconfigure(0, weight=0) # Toggle row
        self.toggles_frame.grid_rowconfigure(1, weight=1) # Spacer row
        self.toggles_frame.grid_rowconfigure(2, weight=0) # Button row

        # Title
        title_label = ctk.CTkLabel(self.toggles_frame, text="BitCraft Companion", 
                                   font=ctk.CTkFont(size=18, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Toggles section
        self.toggle_claim_inventory = ctk.CTkSwitch(self.toggles_frame, text="Claim Inventory Report", 
                                                   command=self.toggle_claim_inventory_window)
        self.toggle_claim_inventory.grid(row=1, column=0, padx=20, pady=10, sticky="w")

        # Add more toggles here as needed
        # ctk.CTkSwitch(self.toggles_frame, text="Another Feature", command=lambda: logging.info("Another feature toggled")).grid(row=2, column=0, padx=20, pady=10, sticky="w")

        # Button frame for navigation
        button_frame = ctk.CTkFrame(self.toggles_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        # Back button
        self.back_button = ctk.CTkButton(
            button_frame, 
            text="Back", 
            command=self._back_to_login,
            fg_color="gray",
            hover_color="darkgray"
        )
        self.back_button.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")

        # Quit button
        self.quit_button = ctk.CTkButton(
            button_frame, 
            text="Quit", 
            command=self.quit,
            fg_color="red",
            hover_color="darkred"
        )
        self.quit_button.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="ew")

    def _back_to_login(self):
        """Go back to the login screen."""
        # Close any open inventory window
        if self.claim_inventory_window and self.claim_inventory_window.winfo_exists():
            self.claim_inventory_window.destroy()
            self.claim_inventory_window = None
        
        # Reset toggle state
        if hasattr(self, 'toggle_claim_inventory'):
            self.toggle_claim_inventory.deselect()
        
        # Transition back to player name screen (or login email if logged out)
        if self.bitcraft_client.auth and self.bitcraft_client.email:
            self._transition_to_ui_state(OverlayState.PLAYER_NAME)
        else:
            self._transition_to_ui_state(OverlayState.LOGIN_EMAIL)

    def _initialize_claim_data(self, user_id: str):
        """Initialize claim data for an already authenticated client."""
        if self.inventory_service:
            self.inventory_service.initialize_claim_data_async(user_id)

    def get_connection_data(self):
        """Returns the connection data if successful."""
        return {
            'email': self.stored_email,
            'player_name': self.stored_player_name,
            'bitcraft_client': self.bitcraft_client
        }

    def toggle_claim_inventory_window(self):
        """Toggle the claim inventory window on/off."""
        # Use the base class implementation
        super().toggle_claim_inventory_window()







    def _get_access_code_flow(self):
        """Handles getting the access code from the API."""
        email = self.entry_email.get().strip()
        
        if not email:
            messagebox.showerror("Error", "Please enter your email address")
            return
        
        if not self.bitcraft_client._is_valid_email(email):
            messagebox.showerror("Error", "Please enter a valid email address")
            return

        # Store email for later use
        self.stored_email = email
        
        # Disable button and show loading state
        self.get_code_button.configure(state="disabled", text="Sending...")
        self.status_label.configure(text="Sending access code to your email...", text_color="yellow")
        
        # Run in thread to prevent UI blocking
        thread = threading.Thread(target=self._run_get_access_code, args=(email,))
        thread.daemon = True
        thread.start()

    def _run_get_access_code(self, email: str):
        """Runs the get access code request in a separate thread."""
        try:
            success = self.bitcraft_client.get_access_code(email)
            
            # Update UI on main thread
            self.after(0, self._on_get_access_code_complete, success)
            
        except Exception as e:
            logging.error(f"Error getting access code: {e}")
            self.after(0, self._on_get_access_code_complete, False)

    def _on_get_access_code_complete(self, success: bool):
        """Called when access code request completes."""
        if success:
            self.status_label.configure(text="Access code sent! Check your email", text_color="green")
            # Transition to access code input after a short delay
            self.after(1500, lambda: self._transition_to_ui_state(OverlayState.ACCESS_CODE))
        else:
            self.status_label.configure(text="Failed to send access code. Please try again", text_color="red")
            self.get_code_button.configure(state="normal", text="Get Access Code")

    def _authenticate_flow(self):
        """Handles authentication with the access code."""
        access_code = self.entry_access_code.get().strip()
        
        if not access_code:
            messagebox.showerror("Error", "Please enter the access code")
            return
        
        if not self.stored_email:
            messagebox.showerror("Error", "Email not found. Please go back and enter your email")
            return

        # Store access code
        self.stored_access_code = access_code
        
        # Disable button and show loading state
        self.authenticate_button.configure(state="disabled", text="Authenticating...")
        self.status_label.configure(text="Authenticating with access code...", text_color="yellow")
        
        # Run in thread to prevent UI blocking
        thread = threading.Thread(target=self._run_authenticate, args=(self.stored_email, access_code))
        thread.daemon = True
        thread.start()

    def _run_authenticate(self, email: str, access_code: str):
        """Runs the authentication request in a separate thread."""
        try:
            success = self.bitcraft_client.authenticate(email, access_code)
            
            # Update UI on main thread
            self.after(0, self._on_authenticate_complete, success)
            
        except Exception as e:
            logging.error(f"Error authenticating: {e}")
            self.after(0, self._on_authenticate_complete, False)

    def _on_authenticate_complete(self, success: bool):
        """Called when authentication completes."""
        if success:
            self.status_label.configure(text="Authentication successful!", text_color="green")
            # Transition to player name input after a short delay
            self.after(1500, lambda: self._transition_to_ui_state(OverlayState.PLAYER_NAME))
        else:
            self.status_label.configure(text="Authentication failed. Please check your access code", text_color="red")
            self.authenticate_button.configure(state="normal", text="Authenticate")

    def _connect_flow(self):
        """Handles the final connection with player name."""
        player_name = self.entry_player_name.get().strip()
        region = self.region_var.get()
        
        if not player_name:
            messagebox.showerror("Error", "Please enter your player name")
            return

        # Store player name and region
        self.stored_player_name = player_name
        self.stored_region = region
        
        # Update the bitcraft client with the player name and region
        self.bitcraft_client.update_user_data_file('player_name', player_name)
        self.bitcraft_client.update_user_data_file('region', region)
        
        # Also update the client's region property immediately
        self.bitcraft_client.region = region
        self.bitcraft_client.player_name = player_name
        
        # Disable button and show loading state
        self.connect_button.configure(state="disabled", text="Connecting...")
        self.status_label.configure(text="Connecting and fetching player data...", text_color="yellow")
        
        # Run in thread to prevent UI blocking
        thread = threading.Thread(target=self._run_connect, args=(player_name, region))
        thread.daemon = True
        thread.start()

    def _run_connect(self, player_name: str, region: str):
        """Runs the connection process in a separate thread."""
        try:
            # Set up WebSocket connection with the selected region
            self.bitcraft_client.set_region(region)
            self.bitcraft_client.set_endpoint("subscribe")
            self.bitcraft_client.set_websocket_uri()
            self.bitcraft_client.connect_websocket()
            
            # Fetch user ID using the player name
            user_id = self.bitcraft_client.fetch_user_id(player_name)
            
            if user_id:
                # Update UI on main thread
                self.after(0, self._on_connect_complete, True, user_id)
            else:
                self.after(0, self._on_connect_complete, False, None)
            
        except Exception as e:
            logging.error(f"Error connecting: {e}")
            self.after(0, self._on_connect_complete, False, None)

    def _on_connect_complete(self, success: bool, user_id: str):
        """Called when the connection process completes."""
        if success and user_id:
            self.status_label.configure(text="Connected successfully!", text_color="green")
            # Initialize claim data for the user
            self._initialize_claim_data(user_id)
            # Transition to main toggles UI after a short delay
            self.after(1500, lambda: self._transition_to_ui_state(OverlayState.MAIN_TOGGLES))
        else:
            self.status_label.configure(text="Connection failed. Please check your player name and region", text_color="red")
            self.connect_button.configure(state="normal", text="Connect")

    def _logout_flow(self):
        """Handles logout from the overlay."""
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to log out? This will clear your saved credentials."):
            # Clear credentials
            self.bitcraft_client.logout()
            
            # Reset stored data
            self.stored_email = None
            self.stored_access_code = None
            self.stored_player_name = None
            
            # Close any open inventory window
            if self.claim_inventory_window and self.claim_inventory_window.winfo_exists():
                self.claim_inventory_window.destroy()
                self.claim_inventory_window = None
            
            # Reset toggle state
            if hasattr(self, 'toggle_claim_inventory'):
                self.toggle_claim_inventory.deselect()
            
            # Transition to email login
            self._transition_to_ui_state(OverlayState.LOGIN_EMAIL)



def main():
    """Main function to run the overlay."""
    app = BitCraftOverlay()
    app.mainloop()
    
    # Return connection data after the overlay closes
    return app.get_connection_data()


if __name__ == "__main__":
    connection_data = main()
    if connection_data['player_name']:
        print(f"Connected as: {connection_data['player_name']}")
    else:
        print("Connection cancelled or failed")
