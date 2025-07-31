import sys
import customtkinter as ctk
import queue
import logging
import threading
from tkinter import messagebox
from data_manager import DataService
from main_window import MainWindow

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class LoginWindow(ctk.CTk):
    """
    A dynamic login window that adapts based on authentication status.
    """

    def __init__(self):
        super().__init__()
        self.title("Bitcraft Companion - Login")
        self.resizable(False, False)

        self.data_service = DataService()

        # --- Main container ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # Build the UI based on whether a token is stored
        self._setup_widgets()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_widgets(self):
        """Clears and rebuilds the UI based on authentication status."""
        # Clear existing widgets
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.main_frame, text="Login", font=("Arial", 18, "bold")).pack(pady=10)

        # --- Input Fields ---
        self.email_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Email", width=250)
        self.email_entry.pack(pady=5)
        if self.data_service.client.email:
            self.email_entry.insert(0, self.data_service.client.email)

        self.player_name_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Player Name", width=250)
        self.player_name_entry.pack(pady=5)
        if self.data_service.client.player_name:
            self.player_name_entry.insert(0, self.data_service.client.player_name)

        regions = [
            "bitcraft-1",
            "bitcraft-2",
            "bitcraft-3",
            "bitcraft-4",
            "bitcraft-5",
            "bitcraft-6",
            "bitcraft-7",
            "bitcraft-8",
            "bitcraft-9",
        ]
        self.region_menu = ctk.CTkOptionMenu(self.main_frame, values=regions, width=250)
        self.region_menu.pack(pady=5)
        if self.data_service.client.region in regions:
            self.region_menu.set(self.data_service.client.region)

        # --- Dynamic Widgets based on Auth Status ---
        self.auth_token_exists = self.data_service.client.auth is not None

        if self.auth_token_exists:
            # User is likely authenticated, hide access code field
            self.access_code_entry = None  # Ensure it doesn't exist
            self.login_button = ctk.CTkButton(self.main_frame, text="Login", command=self.attempt_login, width=250)
            self.login_button.pack(pady=(10, 5))

            self.logout_button = ctk.CTkButton(self.main_frame, text="Logout", command=self.logout, width=250, fg_color="gray")
            self.logout_button.pack(pady=5)
        else:
            # User needs to authenticate with an access code
            self.access_code_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Access Code", show="*", width=250)
            self.access_code_entry.pack(pady=5)

            self.request_code_button = ctk.CTkButton(
                self.main_frame, text="Request Access Code", command=self.request_access_code, width=250, fg_color="gray"
            )
            self.request_code_button.pack(pady=5)

            self.login_button = ctk.CTkButton(self.main_frame, text="Login", command=self.attempt_login, width=250)
            self.login_button.pack(pady=(10, 5))

        # --- Static Buttons and Labels ---
        self.quit_button = ctk.CTkButton(self.main_frame, text="Quit", command=self.on_closing, width=250, fg_color="#c0392b")
        self.quit_button.pack(pady=5)

        self.status_label = ctk.CTkLabel(self.main_frame, text="", text_color="yellow")
        self.status_label.pack(pady=5)

        # Adjust window size dynamically
        self.update_idletasks()
        height = self.main_frame.winfo_reqheight() + 40
        self.geometry(f"350x{height}")

    def request_access_code(self):
        """Requests a new access code from the API."""
        email = self.email_entry.get()
        if not email:
            self.status_label.configure(text="Email is required to request a code.")
            return

        self.status_label.configure(text="Requesting code...")

        # Run in a thread to avoid freezing the GUI
        def do_request():
            try:
                success = self.data_service.client.get_access_code(email)
                if success:
                    self.status_label.configure(text="Access code sent! Check your email.")
                else:
                    self.status_label.configure(text="Failed to request access code.")
            except Exception as e:
                self.status_label.configure(text=f"Error: {e}")

        threading.Thread(target=do_request, daemon=True).start()

    def logout(self):
        """Logs the user out by clearing credentials and refreshing the UI."""
        logging.info("Logging out and clearing credentials.")
        if self.data_service.client.logout():
            # Refresh the UI to show the access code field
            self._setup_widgets()
        else:
            self.status_label.configure(text="Logout failed. See logs.")

    def attempt_login(self):
        """Validates input and starts the data service."""
        email = self.email_entry.get()
        region = self.region_menu.get()
        player_name = self.player_name_entry.get()
        access_code = self.access_code_entry.get() if self.access_code_entry else None

        if not email or not region or not player_name:
            self.status_label.configure(text="Email, Player Name, and Region are required.")
            return

        if not self.auth_token_exists and not access_code:
            self.status_label.configure(text="Access Code is required.")
            return

        self.status_label.configure(text="Connecting...")
        self.login_button.configure(state="disabled")

        self.data_service.start(email, access_code, region, player_name)
        self.after(100, self.check_connection_status)

    def check_connection_status(self):
        """Checks the data queue for a connection status message from the service."""
        try:
            message = self.data_service.data_queue.get_nowait()
            if message.get("type") == "connection_status":
                status = message.get("data", {}).get("status")
                if status == "connected":
                    self.launch_main_app()
                else:
                    reason = message.get("data", {}).get("reason", "Unknown error")
                    self.status_label.configure(text=f"Login Failed: {reason}")
                    self.login_button.configure(state="normal")
                    # If auth failed with a token, it might be expired.
                    if self.auth_token_exists:
                        self.status_label.configure(text="Login failed. Token may be expired.")
            else:
                self.data_service.data_queue.put(message)
                self.after(100, self.check_connection_status)
        except queue.Empty:
            self.after(100, self.check_connection_status)

    def launch_main_app(self):
        """Closes the login window and opens the main application."""
        self.destroy()
        main_app = MainWindow(self.data_service)
        main_app.mainloop()

    def on_closing(self):
        """Handles cleanup when the login window is closed."""
        logging.info("[LoginWindow] Closing login window...")

        try:
            if hasattr(self, "data_service") and self.data_service:
                logging.info("[LoginWindow] Stopping data service...")
                self.data_service.stop()

            logging.info("[LoginWindow] Destroying login window...")
            self.destroy()

        except Exception as e:
            logging.error(f"[LoginWindow] Error during shutdown: {e}")
            try:
                self.destroy()
            except:
                pass
        finally:
            try:
                self.quit()
            except:
                pass

            sys.exit(0)


if __name__ == "__main__":
    app = LoginWindow()
    app.mainloop()
