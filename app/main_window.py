import sys
import customtkinter as ctk
import queue
import logging
from tkinter import messagebox
from typing import Dict
import os
from PIL import Image

# Import our modular components
from data_manager import DataService
from claim_info_header import ClaimInfoHeader
from claim_inventory_tab import ClaimInventoryTab
from passive_crafting_tab import PassiveCraftingTab
from traveler_tasks_tab import TravelerTasksTab


class MainWindow(ctk.CTk):
    """Main application window with modular tab system and real-time timer support."""

    def __init__(self, data_service: DataService):
        super().__init__()
        self.title("Bitcraft Companion")
        self.geometry("900x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # Updated to row 3 for content area

        self.data_service = data_service
        self.tabs: Dict[str, ctk.CTkFrame] = {}
        self.tab_buttons: Dict[str, ctk.CTkButton] = {}
        self.active_tab_name = None

        # Create the claim info header
        self.claim_info = ClaimInfoHeader(self, self)
        self.claim_info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        # Create tab button frame with tab-like styling
        self.tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 0))

        # Create search section
        self._create_search_section()

        # Track loading state
        self.is_loading = True
        self.expected_data_types = {"inventory", "crafting", "tasks", "claim_info"}
        self.received_data_types = set()

        # Create tab content area with border/outline
        self.tab_content_area = ctk.CTkFrame(self, fg_color="#2b2b2b", border_width=2, border_color="#404040", corner_radius=10)
        self.tab_content_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.tab_content_area.grid_columnconfigure(0, weight=1)
        self.tab_content_area.grid_rowconfigure(0, weight=1)

        # Create loading overlay
        self.loading_overlay = self._create_loading_overlay()

        # Initialize tabs and UI
        self._create_tabs()

        self._create_tab_buttons()
        self.show_tab("Claim Inventory")

        # Ensure loading overlay is visible on top and lock tab buttons
        self.show_loading()
        self._set_tab_buttons_state("disabled")

        # Start data processing with enhanced timer support
        self.after(100, self.process_data_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _set_tab_buttons_state(self, state: str):
        """Enable or disable all tab buttons."""
        for btn in self.tab_buttons.values():
            btn.configure(state=state)

        # Start data processing with enhanced timer support
        self.after(100, self.process_data_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_search_section(self):
        """Creates the search section with label, field, and clear button."""
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        search_frame.grid_columnconfigure(1, weight=1)  # Make search field expand

        # Search label
        search_label = ctk.CTkLabel(
            search_frame, text="Search:", font=ctk.CTkFont(size=12, weight="normal"), text_color="#cccccc"
        )
        search_label.grid(row=0, column=0, padx=(0, 8), sticky="w")

        # Search variable and field
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)

        self.search_field = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="Type to search items...",
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#2a2d2e",
            border_color="#404040",
            text_color="#ffffff",
        )
        self.search_field.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        # Clear button
        self.clear_button = ctk.CTkButton(
            search_frame,
            text="Clear",
            command=self.clear_search,
            width=60,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color="#666666",
            hover_color="#777777",
        )
        self.clear_button.grid(row=0, column=2, sticky="e")

    def clear_search(self):
        """Clears the search field."""
        self.search_var.set("")
        self.search_field.focus()  # Return focus to search field

    def _create_loading_overlay(self):
        """Creates a loading overlay with a custom image and message."""
        overlay = ctk.CTkFrame(self.tab_content_area, fg_color="#2b2b2b")
        overlay.grid(row=0, column=0, sticky="nsew")
        overlay.grid_columnconfigure(0, weight=1)
        overlay.grid_rowconfigure(0, weight=1)

        # Make sure it starts on top
        overlay.tkraise()

        # Create loading content
        loading_frame = ctk.CTkFrame(overlay, fg_color="transparent")
        loading_frame.grid(row=0, column=0)

        # Load the custom image (replace 'loading.png' with your actual filename if different)
        image_path = os.path.join(os.path.dirname(__file__), "images", "loading.png")
        if os.path.exists(image_path):
            pil_image = Image.open(image_path)
            self.loading_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(192, 192))
            self.loading_image_label = ctk.CTkLabel(loading_frame, image=self.loading_image, text="")
            self.loading_image_label.pack(pady=10)
        else:
            # Fallback to text if image is missing
            self.loading_image_label = ctk.CTkLabel(
                loading_frame, text="Loading...", font=ctk.CTkFont(size=16, weight="bold"), text_color="#3B8ED0"
            )
            self.loading_image_label.pack(pady=10)

        # Loading message
        self.loading_message = ctk.CTkLabel(
            loading_frame,
            text="Connecting to game server and fetching your claim data",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        )
        self.loading_message.pack()

        return overlay

    def show_loading(self):
        """Shows the loading overlay and disables tab buttons."""
        self.is_loading = True
        self.loading_overlay.grid(row=0, column=0, sticky="nsew")
        self.loading_overlay.tkraise()
        self._set_tab_buttons_state("disabled")

    def hide_loading(self):
        """Hides the loading overlay and enables tab buttons."""
        self.is_loading = False
        self.loading_overlay.grid_remove()
        self._set_tab_buttons_state("normal")

    def _create_tabs(self):
        """Creates all tab instances using the modular tab classes."""

        tab_classes = {
            "Claim Inventory": ClaimInventoryTab,
            "Passive Crafting": PassiveCraftingTab,
            "Traveler's Tasks": TravelerTasksTab,
        }

        for name, TabClass in tab_classes.items():
            tab = TabClass(self.tab_content_area, app=self)
            tab.grid(row=0, column=0, sticky="nsew")
            self.tabs[name] = tab
            logging.info(f"Created tab: {name}")

    def _create_tab_buttons(self):
        """Creates the tab navigation buttons with enhanced tab-like styling."""
        for i, name in enumerate(self.tabs.keys()):
            btn = ctk.CTkButton(
                self.tab_frame,
                text=name,
                width=140,
                height=35,
                corner_radius=8,
                border_width=2,
                border_color="#404040",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="transparent",
                text_color="#cccccc",
                hover_color="#3a3a3a",
                command=lambda n=name: self.show_tab(n),
            )
            btn.grid(row=0, column=i, padx=(0 if i == 0 else 4, 0), pady=(0, 2), sticky="w")
            self.tab_buttons[name] = btn

    def show_tab(self, tab_name):
        """Shows the specified tab and updates button states with enhanced visual feedback."""
        if self.active_tab_name == tab_name:
            return

        self.active_tab_name = tab_name
        self.tabs[tab_name].tkraise()

        # Update button appearances with proper tab styling
        for i, (name, button) in enumerate(self.tab_buttons.items()):
            if name == tab_name:
                # Active tab styling - connected to content area
                button.configure(
                    fg_color=("#3B8ED0", "#1F6AA5"),
                    text_color="white",
                    border_color="#3B8ED0",
                    hover_color=("#2E7BB8", "#1A5A8A"),
                )
            else:
                # Inactive tab styling
                button.configure(fg_color="transparent", text_color="#cccccc", border_color="#404040", hover_color="#3a3a3a")

        # Apply current search filter to the new tab
        self.on_search_change()
        logging.info(f"Switched to tab: {tab_name}")

    def on_search_change(self, *args):
        """Applies search filter to the currently active tab."""
        if self.active_tab_name and hasattr(self.tabs[self.active_tab_name], "apply_filter"):
            self.tabs[self.active_tab_name].apply_filter()

    def _check_all_data_loaded(self):
        """Check if all expected data types have been received and hide loading if so."""
        if self.is_loading and self.received_data_types >= self.expected_data_types:
            logging.info(f"All initial data loaded: {self.received_data_types}")
            self.hide_loading()

    def process_data_queue(self):
        """Enhanced data queue processing that handles timer updates and task updates."""
        try:
            while not self.data_service.data_queue.empty():
                message = self.data_service.data_queue.get_nowait()
                msg_type = message.get("type")
                msg_data = message.get("data")

                if msg_type == "inventory_update":
                    if "Claim Inventory" in self.tabs:
                        self.tabs["Claim Inventory"].update_data(msg_data)
                        logging.debug("Inventory data updated in UI")

                        # Track that we've received inventory data
                        if self.is_loading:
                            self.received_data_types.add("inventory")
                            self._check_all_data_loaded()

                elif msg_type == "crafting_update":
                    if "Passive Crafting" in self.tabs:
                        self.tabs["Passive Crafting"].update_data(msg_data)

                        # Check for completion celebrations
                        changes = message.get("changes", {})
                        if changes.get("crafting_completed"):
                            self._celebrate_completions(changes["crafting_completed"])

                        logging.debug("Crafting data updated in UI")

                        # Track that we've received crafting data
                        if self.is_loading:
                            self.received_data_types.add("crafting")
                            self._check_all_data_loaded()

                # NEW: Handle real-time timer updates
                elif msg_type == "timer_update":
                    if "Passive Crafting" in self.tabs:
                        # Update the crafting tab with new timer data
                        self.tabs["Passive Crafting"].update_data(msg_data)
                        logging.debug("Timer data updated in UI")

                elif msg_type == "tasks_update":
                    if "Traveler's Tasks" in self.tabs:
                        self.tabs["Traveler's Tasks"].update_data(msg_data)

                        # Check for task completions
                        changes = message.get("changes", {})
                        if changes.get("completed_tasks"):
                            self._celebrate_task_completions(changes["completed_tasks"])

                        logging.debug("Tasks data updated in UI")

                        # Track that we've received tasks data
                        if self.is_loading:
                            self.received_data_types.add("tasks")
                            self._check_all_data_loaded()

                elif msg_type == "claim_info_update":
                    self.claim_info.update_claim_data(msg_data)
                    logging.debug("Claim info updated in UI")

                    # Track that we've received claim info data
                    if self.is_loading:
                        self.received_data_types.add("claim_info")
                        self._check_all_data_loaded()

                elif msg_type == "error":
                    messagebox.showerror("Error", msg_data)
                    logging.error(f"Error message displayed: {msg_data}")

                    # Hide loading on error
                    if self.is_loading:
                        self.hide_loading()

                else:
                    logging.warning(f"Unknown message type received: {msg_type}")

        except queue.Empty:
            pass
        except Exception as e:
            logging.error(f"Error processing data queue: {e}")
        finally:
            # Check for updates every 100ms for smooth real-time timer updates
            self.after(100, self.process_data_queue)

    def _celebrate_task_completions(self, completed_tasks):
        """
        Celebrate completed tasks with visual feedback.

        Args:
            completed_tasks: List of completed task information
        """
        try:
            if not completed_tasks:
                return

            # Log celebratory message
            count = len(completed_tasks)
            logging.info(f"🎉 {count} task(s) completed!")

            # Update window title briefly to show completion
            original_title = self.title()
            if count == 1:
                task_name = completed_tasks[0].get("task_description", "Task")[:30]
                self.title(f"🎉 Task completed: {task_name}... - {original_title}")
            else:
                self.title(f"🎉 {count} tasks completed! - {original_title}")

            # Reset title after 3 seconds
            self.after(3000, lambda: self.title(original_title))

            # Log each completion
            for task in completed_tasks:
                task_desc = task.get("task_description", "Unknown Task")
                traveler_name = task.get("traveler_name", "Unknown Traveler")
                logging.info(f"✅ Completed: {task_desc} for {traveler_name}")

        except Exception as e:
            logging.error(f"Error celebrating task completions: {e}")

    def _celebrate_completions(self, completed_items):
        """
        Celebrate completed crafting items with visual/audio feedback.

        Args:
            completed_items: List of completed crafting operations
        """
        try:
            if not completed_items:
                return

            # Log celebratory message
            count = len(completed_items)
            logging.info(f"🎉 {count} crafting operation(s) completed!")

            # You could add more celebration features here:
            # - Play a completion sound
            # - Show a brief notification popup
            # - Flash the title bar
            # - Send system notification

            # For now, just update the window title briefly
            original_title = self.title()
            self.title(f"🎉 {count} items ready! - {original_title}")

            # Reset title after 3 seconds
            self.after(3000, lambda: self.title(original_title))

        except Exception as e:
            logging.error(f"Error celebrating completions: {e}")

    def show_completion_notification(self, item_name: str, quantity: int = 1):
        """
        Show a brief notification for completed items.

        Args:
            item_name: Name of the completed item
            quantity: Number of items completed
        """
        try:
            # Create a simple notification window
            notification = ctk.CTkToplevel(self)
            notification.title("Crafting Complete!")
            notification.geometry("300x100")
            notification.attributes("-topmost", True)

            # Center it on the main window
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 150
            y = self.winfo_y() + 100
            notification.geometry(f"300x100+{x}+{y}")

            # Add notification content
            if quantity == 1:
                message = f"✅ {item_name} is ready!"
            else:
                message = f"✅ {quantity}x {item_name} ready!"

            label = ctk.CTkLabel(notification, text=message, font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CAF50")
            label.pack(expand=True)

            # Auto-close after 3 seconds
            notification.after(3000, notification.destroy)

        except Exception as e:
            logging.error(f"Error showing completion notification: {e}")

    def on_closing(self):
        """Handles cleanup when the window is closed."""
        logging.info("[MainWindow] Closing application...")

        try:
            # Stop the data service first - this is critical
            if hasattr(self, "data_service") and self.data_service:
                logging.info("[MainWindow] Stopping data service...")
                self.data_service.stop()

                # Give it a moment to clean up
                import time

                time.sleep(0.5)

            logging.info("[MainWindow] Destroying window...")
            self.destroy()

        except Exception as e:
            logging.error(f"[MainWindow] Error during shutdown: {e}")
            # Force destroy even if there's an error
            try:
                self.destroy()
            except:
                pass
        finally:
            # Ensure we quit the application
            try:
                self.quit()
            except:
                pass

            sys.exit(0)
