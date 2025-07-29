import customtkinter as ctk
import queue
import logging
from tkinter import messagebox
from typing import Dict

# Import our modular components
from data_manager import DataService
from claim_info_header import ClaimInfoHeader
from claim_inventory_tab import ClaimInventoryTab
from passive_crafting_tab import PassiveCraftingTab


class MainWindow(ctk.CTk):
    """Main application window with modular tab system."""

    def __init__(self, data_service: DataService):
        super().__init__()
        self.title("Bitcraft Companion")
        self.geometry("900x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.data_service = data_service
        self.tabs: Dict[str, ctk.CTkFrame] = {}
        self.tab_buttons: Dict[str, ctk.CTkButton] = {}
        self.active_tab_name = None

        # Create the claim info header
        self.claim_info = ClaimInfoHeader(self, self)
        self.claim_info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        # Create tab button frame
        self.tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 0))

        # Create search section
        self._create_search_section()

        # Create tab content area
        self.tab_content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_content_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.tab_content_area.grid_columnconfigure(0, weight=1)
        self.tab_content_area.grid_rowconfigure(0, weight=1)

        # Initialize tabs and UI
        self._create_tabs()
        self._create_tab_buttons()
        self.show_tab("Claim Inventory")

        # Start data processing
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

    def _create_tabs(self):
        """Creates all tab instances using the modular tab classes."""
        tab_classes = {
            "Claim Inventory": ClaimInventoryTab,
            "Passive Crafting": PassiveCraftingTab,
        }

        for name, TabClass in tab_classes.items():
            tab = TabClass(self.tab_content_area, app=self)
            tab.grid(row=0, column=0, sticky="nsew")
            self.tabs[name] = tab
            logging.info(f"Created tab: {name}")

    def _create_tab_buttons(self):
        """Creates the tab navigation buttons."""
        for i, name in enumerate(self.tabs.keys()):
            btn = ctk.CTkButton(self.tab_frame, text=name, width=140, corner_radius=6, command=lambda n=name: self.show_tab(n))
            btn.grid(row=0, column=i, padx=(0 if i == 0 else 8, 0), pady=0, sticky="w")
            self.tab_buttons[name] = btn

    def show_tab(self, tab_name):
        """Shows the specified tab and updates button states."""
        if self.active_tab_name == tab_name:
            return

        self.active_tab_name = tab_name
        self.tabs[tab_name].tkraise()

        # Update button appearances
        for name, button in self.tab_buttons.items():
            if name == tab_name:
                button.configure(fg_color=("#3B8ED0", "#1F6AA5"))
            else:
                button.configure(fg_color="transparent")

        # Apply current search filter to the new tab
        self.on_search_change()
        logging.info(f"Switched to tab: {tab_name}")

    def on_search_change(self, *args):
        """Applies search filter to the currently active tab."""
        if self.active_tab_name and hasattr(self.tabs[self.active_tab_name], "apply_filter"):
            self.tabs[self.active_tab_name].apply_filter()

    def process_data_queue(self):
        """Processes incoming data from the DataService queue."""
        try:
            while not self.data_service.data_queue.empty():
                message = self.data_service.data_queue.get_nowait()
                msg_type = message.get("type")
                msg_data = message.get("data")

                if msg_type == "inventory_update":
                    if "Claim Inventory" in self.tabs:
                        self.tabs["Claim Inventory"].update_data(msg_data)
                        logging.debug("Inventory data updated in UI")

                elif msg_type == "crafting_update":
                    if "Passive Crafting" in self.tabs:
                        self.tabs["Passive Crafting"].update_data(msg_data)
                        logging.debug("Crafting data updated in UI")

                elif msg_type == "claim_info_update":
                    self.claim_info.update_claim_data(msg_data)
                    logging.debug("Claim info updated in UI")

                elif msg_type == "error":
                    messagebox.showerror("Error", msg_data)
                    logging.error(f"Error message displayed: {msg_data}")

                else:
                    logging.warning(f"Unknown message type received: {msg_type}")

        except queue.Empty:
            pass
        except Exception as e:
            logging.error(f"Error processing data queue: {e}")
        finally:
            self.after(100, self.process_data_queue)

    def on_closing(self):
        """Handles cleanup when the window is closed."""
        logging.info("[MainWindow] Closing application...")
        self.data_service.stop()
        self.destroy()
