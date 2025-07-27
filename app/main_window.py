"""
Main unified GUI window for Bitcraft Companion using customtkinter.
Phase 11: Restoring the correct UI and table functionality.
"""

import customtkinter as ctk
import queue
import logging
from tkinter import Menu, messagebox

# Import the real DataService
from data_manager import DataService


# --- GUI Classes ---


class FilterPopup(ctk.CTkToplevel):
    def __init__(self, parent, header, all_data, current_selection, callback):
        super().__init__(parent)
        self.title(f"Filter by {header}")
        self.geometry("320x450")
        self.transient(parent)
        self.grab_set()
        self.header = header
        self.callback = callback
        unique_values = sorted(list(set(str(row.get(self.header, "")) for row in all_data)))
        self.check_vars = {}
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Search values...")
        self.search_entry.pack(fill="x", padx=10, pady=(10, 5))
        control_frame = ctk.CTkFrame(self, fg_color="transparent")
        control_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(control_frame, text="Select All", command=self._select_all, width=100).pack(side="left")
        ctk.CTkButton(control_frame, text="Clear", command=self._clear_all, width=100).pack(side="left", padx=5)
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.checkboxes = []
        for value in unique_values:
            var = ctk.StringVar(value="on" if value in current_selection else "off")
            cb = ctk.CTkCheckBox(self.scrollable_frame, text=value, variable=var, onvalue="on", offvalue="off")
            cb.pack(fill="x", padx=5, pady=2)
            self.check_vars[value] = var
            self.checkboxes.append(cb)
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.pack(fill="x", side="bottom", padx=10, pady=10)
        ctk.CTkButton(bottom_frame, text="OK", command=self._on_ok, width=100).pack(side="right")
        ctk.CTkButton(bottom_frame, text="Cancel", command=self.destroy, width=100).pack(side="right", padx=10)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.search_entry.focus()

    def _on_search(self, *args):
        filter_text = self.search_var.get().lower()
        for cb in self.checkboxes:
            if filter_text in cb.cget("text").lower():
                cb.pack(fill="x", padx=5, pady=2)
            else:
                cb.pack_forget()

    def _select_all(self):
        for cb in self.checkboxes:
            if cb.winfo_ismapped():
                self.check_vars[cb.cget("text")].set("on")

    def _clear_all(self):
        for cb in self.checkboxes:
            if cb.winfo_ismapped():
                self.check_vars[cb.cget("text")].set("off")

    def _on_ok(self):
        selected_values = {value for value, var in self.check_vars.items() if var.get() == "on"}
        self.callback(self.header, selected_values)
        self.destroy()


class BaseTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app

    def apply_filter(self):
        logging.warning(f"Filtering not implemented for {self.__class__.__name__}")

    def update_data(self, new_data):
        logging.warning(f"Data update not implemented for {self.__class__.__name__}")


class ClaimInventoryTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        # RESTORED: Correct headers for the table
        self.headers = ["Item", "Tier", "Quantity", "Containers", "Tag"]
        self.all_data = []
        self.data = []
        self.sort_column = None
        self.sort_reverse = False
        self.clicked_header = None
        self.active_filters = {}
        self._create_widgets()
        self._create_context_menu()

    def _create_widgets(self):
        self.table_frame = ctk.CTkFrame(self)
        self.table_frame.grid(row=0, column=0, sticky="nsew")
        self.table_frame.grid_columnconfigure(list(range(len(self.headers))), weight=1)
        self.render_table()

    def _create_context_menu(self):
        self.header_context_menu = Menu(self, tearoff=0, background="#2a2d2e", foreground="white", activebackground="#1f6aa5")
        self.header_context_menu.add_command(label="Sort A-Z", command=lambda: self.sort_by(self.clicked_header, reverse=False))
        self.header_context_menu.add_command(label="Sort Z-A", command=lambda: self.sort_by(self.clicked_header, reverse=True))
        self.header_context_menu.add_separator()
        self.header_context_menu.add_command(label="Filter", command=lambda: self._open_filter_popup(self.clicked_header))
        self.header_context_menu.add_command(
            label="Clear this column's filter", command=lambda: self.clear_column_filter(self.clicked_header)
        )

    def _open_filter_popup(self, header):
        if not self.all_data:
            return
        unique_values = sorted(list(set(str(row.get(header, "")) for row in self.all_data)))
        current_selection = self.active_filters.get(header, unique_values)
        FilterPopup(self, header, self.all_data, current_selection, self._apply_column_filter)

    def _apply_column_filter(self, header, selected_values):
        all_possible_values = set(str(row.get(header, "")) for row in self.all_data)
        if selected_values == all_possible_values:
            if header in self.active_filters:
                del self.active_filters[header]
        else:
            self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def show_header_context_menu(self, event, header):
        self.clicked_header = header
        self.header_context_menu.tk_popup(event.x_root, event.y_root)

    def render_table(self):
        # RESTORED: Correct table rendering logic
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        header_bg_color = "#2c5d8f"
        row_colors = ["#2a2d2e", "#343638"]
        for col, header in enumerate(self.headers):
            sort_indicator = (
                " ↓" if self.sort_column == header and self.sort_reverse else " ↑" if self.sort_column == header else ""
            )
            filter_indicator = " 🔎" if header in self.active_filters else ""
            header_label = ctk.CTkLabel(
                self.table_frame,
                text=header + sort_indicator + filter_indicator,
                font=("Arial", 12, "bold"),
                fg_color=header_bg_color,
                anchor="w",
                padx=5,
            )
            header_label.grid(row=0, column=col, padx=1, pady=1, sticky="nsew")
            header_label.bind("<Button-1>", lambda e, h=header: self.sort_by(h))
            header_label.bind("<Button-3>", lambda e, h=header: self.show_header_context_menu(e, h))
        for row_idx, row_data in enumerate(self.data):
            bg_color = row_colors[row_idx % 2]
            for col_idx, header in enumerate(self.headers):
                val = row_data.get(header, "")
                lbl = ctk.CTkLabel(self.table_frame, text=str(val), anchor="w", padx=5, fg_color=bg_color)
                lbl.grid(row=row_idx + 1, column=col_idx, padx=1, pady=1, sticky="nsew")

    def sort_by(self, header, reverse=None):
        if not self.data:
            return
        if self.sort_column == header:
            self.sort_reverse = not self.sort_reverse if reverse is None else reverse
        else:
            self.sort_column = header
            self.sort_reverse = reverse if reverse is not None else False
        if header in ["Tier", "Quantity"]:
            self.data.sort(key=lambda x: float(x.get(header, 0)), reverse=self.sort_reverse)
        else:
            self.data.sort(key=lambda x: str(x.get(header, "")).lower(), reverse=self.sort_reverse)
        self.render_table()

    def apply_filter(self):
        global_filter_text = self.app.search_var.get().lower()
        filtered_data = self.all_data.copy()
        if self.active_filters:
            filtered_data = [
                row
                for row in filtered_data
                if all(str(row.get(header, "")) in values for header, values in self.active_filters.items())
            ]
        if global_filter_text:
            filtered_data = [row for row in filtered_data if global_filter_text in str(row.values()).lower()]
        self.data = filtered_data
        if self.sort_column:
            self.sort_by(self.sort_column, reverse=self.sort_reverse)
        else:
            self.render_table()

    def update_data(self, new_data):
        logging.info("[GUI] ClaimInventoryTab received data update.")
        self.all_data = new_data
        self.apply_filter()


class PassiveCraftingTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.label = ctk.CTkLabel(self, text="Passive Crafting content goes here.", font=("Arial", 16))
        self.label.pack(expand=True)

    def update_data(self, new_data):
        logging.info("[GUI] PassiveCraftingTab received data update.")
        self.label.configure(text=f"Passive Crafting Update:\n{str(new_data)}")


class TravellersTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        ctk.CTkLabel(self, text="Travellers content goes here.", font=("Arial", 16)).pack(expand=True)


class OtherTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        ctk.CTkLabel(self, text="Other content goes here.", font=("Arial", 16)).pack(expand=True)


class ClaimInfoHeader(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.master = master
        self.grid_columnconfigure(1, weight=1)
        self.claim_name = ctk.CTkLabel(self, text="Claim Name: (Connecting...)", font=("Arial", 16, "bold"))
        self.claim_name.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
        self.claim_supplies = ctk.CTkLabel(self, text="Claim Supplies: N/A")
        self.claim_supplies.grid(row=1, column=0, sticky="w", padx=10)
        self.time_remaining = ctk.CTkLabel(self, text="Time Remaining: N/A")
        self.time_remaining.grid(row=1, column=1, sticky="w", padx=10)
        self.treasury = ctk.CTkLabel(self, text="Treasury: N/A")
        self.treasury.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
        self.user_profile_button = ctk.CTkButton(
            self, text="👤", width=32, height=32, corner_radius=16, command=self.show_user_menu
        )
        self.user_profile_button.grid(row=0, column=2, sticky="e", padx=10, pady=(10, 0))
        self.user_menu = Menu(self, tearoff=0, background="#2a2d2e", foreground="white", activebackground="#1f6aa5")
        self.theme_menu = Menu(self.user_menu, tearoff=0, background="#2a2d2e", foreground="white")
        self.theme_menu.add_command(label="Light", command=lambda: self.set_theme("light"))
        self.theme_menu.add_command(label="Dark", command=lambda: self.set_theme("dark"))
        self.theme_menu.add_command(label="System", command=lambda: self.set_theme("system"))
        self.user_menu.add_cascade(label="Theme", menu=self.theme_menu)
        self.user_menu.add_separator()
        self.user_menu.add_command(label="Logout", command=self.logout)

    def show_user_menu(self):
        self.user_menu.tk_popup(
            self.user_profile_button.winfo_rootx(),
            self.user_profile_button.winfo_rooty() + self.user_profile_button.winfo_height(),
        )

    def set_theme(self, theme):
        ctk.set_appearance_mode(theme)

    def logout(self):
        self.master.on_closing()

    def update_data(self, data):
        self.claim_name.configure(text=f"Claim Name: {data.get('name', 'N/A')}")
        self.claim_supplies.configure(text=f"Claim Supplies: {data.get('supplies', 'N/A')}")
        self.time_remaining.configure(text=f"Time Remaining: {data.get('time', 'N/A')}")
        self.treasury.configure(text=f"Treasury: {data.get('treasury', 'N/A')}")


class MainWindow(ctk.CTk):
    def __init__(self, data_service: DataService):
        super().__init__()
        self.title("Bitcraft Companion")
        self.geometry("900x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.data_service = data_service

        self.claim_info = ClaimInfoHeader(self)
        self.claim_info.grid(row=0, column=0, sticky="ew", padx=10)
        self.tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 0))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        self.search_field = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Search all columns...")
        self.search_field.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        self.tab_content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_content_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.tab_content_area.grid_columnconfigure(0, weight=1)
        self.tab_content_area.grid_rowconfigure(0, weight=1)
        self.tabs = {}
        self.tab_buttons = {}
        self.active_tab_name = None
        self._create_tabs()
        self._create_tab_buttons()
        self.show_tab("Claim Inventory")

        self.after(100, self.process_data_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_tabs(self):
        tab_classes = {
            "Claim Inventory": ClaimInventoryTab,
            "Passive Crafting": PassiveCraftingTab,
            "Travellers": TravellersTab,
            "Other": OtherTab,
        }
        for name, TabClass in tab_classes.items():
            tab = TabClass(self.tab_content_area, app=self)
            tab.grid(row=0, column=0, sticky="nsew")
            self.tabs[name] = tab

    def _create_tab_buttons(self):
        for i, name in enumerate(self.tabs.keys()):
            btn = ctk.CTkButton(self.tab_frame, text=name, width=140, corner_radius=6, command=lambda n=name: self.show_tab(n))
            btn.grid(row=0, column=i, padx=(0 if i == 0 else 8, 0), pady=0, sticky="w")
            self.tab_buttons[name] = btn

    def show_tab(self, tab_name):
        if self.active_tab_name == tab_name:
            return
        self.active_tab_name = tab_name
        tab = self.tabs[tab_name]
        tab.tkraise()
        for name, button in self.tab_buttons.items():
            button.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"] if name == tab_name else "transparent")
        self.on_search_change()

    def on_search_change(self, *args):
        if self.active_tab_name:
            active_tab = self.tabs[self.active_tab_name]
            if hasattr(active_tab, "apply_filter"):
                active_tab.apply_filter()

    def process_data_queue(self):
        try:
            while not self.data_service.data_queue.empty():
                message = self.data_service.data_queue.get_nowait()

                msg_type = message.get("type")
                msg_data = message.get("data")

                if msg_type == "inventory_update":
                    self.tabs.get("Claim Inventory").update_data(msg_data)
                elif msg_type == "passive_crafting_update":
                    self.tabs.get("Passive Crafting").update_data(msg_data)
                elif msg_type == "claim_info_update":
                    self.claim_info.update_data(msg_data)
                elif msg_type == "connection_status":
                    if msg_data.get("status") == "failed":
                        self.claim_info.claim_name.configure(text=f"Connection Failed: {msg_data.get('reason', '')}")
                elif msg_type == "error":
                    messagebox.showerror("Error", msg_data)

        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_data_queue)

    def on_closing(self):
        logging.info("[MainWindow] Closing application...")
        self.data_service.stop()
        self.destroy()
