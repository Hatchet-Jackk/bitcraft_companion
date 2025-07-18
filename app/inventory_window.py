import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import json
import os
import csv
import webbrowser
from datetime import datetime

from client import BitCraft
from claim import Claim


class FilterDialog(ctk.CTkToplevel):
    def __init__(self, master, column_name: str, unique_values: list, current_filter: dict, is_numeric: bool = False):
        super().__init__(master)
        self.master = master
        self.column_name = column_name
        self.unique_values = sorted([str(val) for val in unique_values])
        self.is_numeric = is_numeric
        self.current_filter = current_filter

        self.title(f"Filter by {column_name}")
        self.transient(master)
        self.grab_set()
        self.attributes('-topmost', True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        options_frame = ctk.CTkFrame(self)
        options_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        options_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(options_frame, text="Select values:").grid(row=0, column=0, padx=5, pady=5, sticky="w")

        initial_select_all = self.current_filter['selected'] is None or \
                             (isinstance(self.current_filter['selected'], set) and \
                              len(self.current_filter['selected']) == len(self.unique_values))

        self.all_selected_var = ctk.BooleanVar(value=initial_select_all)
        self.all_selected_checkbox = ctk.CTkCheckBox(options_frame, text="Select All",
                                                     variable=self.all_selected_var, command=self._toggle_select_all)
        self.all_selected_checkbox.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.checkbox_vars = {}
        for i, value in enumerate(self.unique_values):
            initial_checkbox_state = self.current_filter['selected'] is None or \
                                     (isinstance(self.current_filter['selected'], set) and value in self.current_filter['selected'])
            var = ctk.BooleanVar(value=initial_checkbox_state)
            checkbox = ctk.CTkCheckBox(self.scroll_frame, text=str(value), variable=var)
            checkbox.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            self.checkbox_vars[value] = var

        self._update_select_all_checkbox()

        if self.is_numeric:
            self.range_frame = ctk.CTkFrame(self)
            self.range_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
            self.range_frame.grid_columnconfigure((0,1), weight=1)

            ctk.CTkLabel(self.range_frame, text="Min:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.min_entry = ctk.CTkEntry(self.range_frame, placeholder_text="Min")
            self.min_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
            if self.current_filter['min'] is not None:
                self.min_entry.insert(0, str(self.current_filter['min']))

            ctk.CTkLabel(self.range_frame, text="Max:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            self.max_entry = ctk.CTkEntry(self.range_frame, placeholder_text="Max")
            self.max_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
            if self.current_filter['max'] is not None:
                self.max_entry.insert(0, str(self.current_filter['max']))

        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=3 if self.is_numeric else 2, column=0, padx=10, pady=10, sticky="ew")
        button_frame.grid_columnconfigure((0,1), weight=1)

        ctk.CTkButton(button_frame, text="Apply", command=self.apply_filter).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(button_frame, text="Clear", command=self.clear_filter).grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _toggle_select_all(self):
        select_all = self.all_selected_var.get()
        for var in self.checkbox_vars.values():
            var.set(select_all)

    def _update_select_all_checkbox(self):
        all_checked = all(self.checkbox_vars[val].get() for val in self.unique_values if val in self.checkbox_vars)
        self.all_selected_var.set(all_checked)

    def apply_filter(self):
        selected_values = {value for value, var in self.checkbox_vars.items() if var.get()}

        min_val = None
        max_val = None
        if self.is_numeric:
            try:
                min_val_str = self.min_entry.get().strip()
                if min_val_str:
                    min_val = float(min_val_str)
            except ValueError:
                logging.warning(f"Invalid min value for {self.column_name} filter: '{min_val_str}' - ignoring.")

            try:
                max_val_str = self.max_entry.get().strip()
                if max_val_str:
                    max_val = float(max_val_str)
            except ValueError:
                logging.warning(f"Invalid max value for {self.column_name} filter: '{max_val_str}' - ignoring.")

        if len(selected_values) == len(self.unique_values):
            selected_values = None

        new_filter_state = {
            'selected': selected_values,
            'min': min_val,
            'max': max_val
        }
        self.master.update_filter(self.column_name, new_filter_state)
        self.destroy()

    def clear_filter(self):
        if self.is_numeric:
            self.min_entry.delete(0, ctk.END)
            self.max_entry.delete(0, ctk.END)
        self.all_selected_var.set(True)
        self._toggle_select_all()
        self.apply_filter()

    def on_closing(self):
        self.master.grab_release()
        self.destroy()


class ClaimInventoryWindow(ctk.CTkToplevel):
    def __init__(self, master, bitcraft_client: BitCraft, claim_instance: Claim, initial_display_data: list, last_fetch_time=None):
        print("DEBUG: ClaimInventoryWindow constructor called")
        print(f"DEBUG: Constructor - last_fetch_time parameter: {last_fetch_time}")
        super().__init__(master)
        self.title("Claim Inventory Report")

        # Make window resizable with better initial size
        min_width = 720
        min_height = 500
        initial_width = 800
        initial_height = 600

        self.update_idletasks()

        x = master.winfo_x() + master.winfo_width() + 20
        y = master.winfo_y()
        self.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
        self.minsize(min_width, min_height)

        self.resizable(True, True)

        # Configure window grid to make treeview area expandable
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)  # Scrollbar column
        self.grid_rowconfigure(0, weight=0)     # Controls frame
        self.grid_rowconfigure(1, weight=0)     # Search frame
        self.grid_rowconfigure(2, weight=1)     # Treeview - main content area
        self.grid_rowconfigure(3, weight=0)     # Horizontal scrollbar
        self.grid_rowconfigure(4, weight=0)     # Button frame
        self.grid_rowconfigure(5, weight=0)     # Status bar

        self.transient(master)
        # Removed grab_set() to allow interaction with main window
        self.attributes('-topmost', True)

        self.bitcraft_client = bitcraft_client
        self.claim_instance = claim_instance
        self.current_inventory_data = initial_display_data
        self.active_filters = {
            "Tier": {'selected': None, 'min': None, 'max': None},
            "Name": {'selected': None, 'min': None, 'max': None},
            "Quantity": {'selected': None, 'min': None, 'max': None},
            "Tag": {'selected': None, 'min': None, 'max': None}
        }

        self.auto_refresh_job = None
        self.auto_refresh_interval_minutes = 5
        self.last_fetch_time = last_fetch_time  # Store the original fetch time

        self.sort_column = "Name"
        self.sort_direction = False
        
        # Search functionality
        self.search_term = ""
        
        # Flag to track if timestamp has been properly initialized
        self.timestamp_initialized = False
        
        self.create_widgets()
        
        # Don't call apply_filters_and_sort here - let the parent handle initial data display
        # This prevents timestamp from being reset to "Loading..." before parent sets proper timestamp
        print(f"DEBUG: ClaimInventoryWindow constructor finished - instance id: {id(self)}")
        print(f"DEBUG: Constructor - timestamp_initialized: {self.timestamp_initialized}")
        print(f"DEBUG: Constructor - current timestamp text: {getattr(self, 'last_updated_label', None) and self.last_updated_label.cget('text')}")

    def create_widgets(self):
        # Controls frame at the top (simplified - just the always on top toggle)
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew", columnspan=2)

        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_columnconfigure(1, weight=0)

        # Instructions label
        instructions_label = ctk.CTkLabel(controls_frame, 
                                        text="Click filter arrows (▼) in headers for sorting and filtering options",
                                        font=ctk.CTkFont(size=12))
        instructions_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        # Always on Top toggle
        self.always_on_top_switch = ctk.CTkSwitch(controls_frame, text="Always on Top", 
                                                command=self._toggle_always_on_top)
        self.always_on_top_switch.grid(row=0, column=1, padx=10, pady=5, sticky="e")
        self.always_on_top_switch.select()

        # Search frame
        search_frame = ctk.CTkFrame(self)
        search_frame.grid(row=1, column=0, padx=0, pady=0, sticky="ew", columnspan=2)
        search_frame.grid_columnconfigure(1, weight=1)

        # Search label
        search_label = ctk.CTkLabel(search_frame, text="Search:", font=ctk.CTkFont(size=12))
        search_label.grid(row=0, column=0, padx=5, pady=1, sticky="w")

        # Search entry
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Type to search items...")
        self.search_entry.grid(row=0, column=1, padx=5, pady=1, sticky="ew")
        self.search_entry.bind('<KeyRelease>', self._on_search_change)

        # Clear search button
        self.clear_search_button = ctk.CTkButton(search_frame, text="Clear", width=60, 
                                               command=self._clear_search)
        self.clear_search_button.grid(row=0, column=2, padx=5, pady=1, sticky="e")

        # --- Treeview (main content area) ---
        self.tree = ttk.Treeview(self, columns=("Tier", "Name", "Quantity", "Tag"), show="headings")
        self.tree.grid(row=2, column=0, padx=0, pady=(2, 10), sticky="nsew")

        # Initial header setup with sort indicators
        self._update_treeview_headers()

        # Bind right-click context menu
        self.tree.bind("<Button-3>", self._show_context_menu)

        # Vertical scrollbar for treeview
        vsb = ctk.CTkScrollbar(self, command=self.tree.yview)
        vsb.grid(row=2, column=1, sticky="ns", padx=(0,0), pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set)

        # Horizontal scrollbar for treeview
        hsb = ctk.CTkScrollbar(self, orientation="horizontal", command=self.tree.xview)
        hsb.grid(row=3, column=0, sticky="ew", padx=0, pady=(0, 10))
        self.tree.configure(xscrollcommand=hsb.set)

        # Button frame above status bar
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="ew", columnspan=2)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(button_frame, text="Refresh Data", command=self._refresh_data).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(button_frame, text="Save to File", command=self._save_to_file).grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Status bar frame at the bottom
        self.status_bar_frame = ctk.CTkFrame(self, height=30, fg_color=("gray86", "gray17"))
        self.status_bar_frame.grid(row=5, column=0, padx=0, pady=0, sticky="ew", columnspan=2)
        self.status_bar_frame.grid_columnconfigure(0, weight=1)
        self.status_bar_frame.grid_columnconfigure(1, weight=0)

        # Status bar content - preserve timestamp if already initialized
        initial_timestamp_text = "Last update: Loading..."
        if hasattr(self, 'timestamp_initialized') and self.timestamp_initialized and hasattr(self, 'last_updated_label'):
            # Preserve existing timestamp text if already initialized
            initial_timestamp_text = self.last_updated_label.cget('text')
            print(f"DEBUG: Preserving existing timestamp: {initial_timestamp_text}")
        
        self.last_updated_label = ctk.CTkLabel(self.status_bar_frame, text=initial_timestamp_text, 
                                               font=ctk.CTkFont(size=11))
        self.last_updated_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")

        self.item_count_label = ctk.CTkLabel(self.status_bar_frame, text="Items: 0", 
                                             font=ctk.CTkFont(size=11))
        self.item_count_label.grid(row=0, column=1, padx=10, pady=2, sticky="e")

    def _update_treeview_headers(self):
        """Updates the treeview column headers with sort direction indicators and filter dropdowns."""
        arrow_up = " ↑"
        arrow_down = " ↓"
        filter_arrow = " ▼"
        columns = ["Tier", "Name", "Quantity", "Tag"]

        for col in columns:
            # Sort indicator
            sort_indicator = ""
            if self.sort_column == col:
                sort_indicator = arrow_down if not self.sort_direction else arrow_up
                
            # Filter indicator (show if filter is active)
            filter_indicator = ""
            if self._is_filter_active(col):
                filter_indicator = " [F]"
                
            header_text = col + sort_indicator + filter_indicator + filter_arrow
            
            # Bind combined sort/filter menu (clicking anywhere on header)
            self.tree.heading(col, text=header_text, 
                             command=lambda column=col: self._show_combined_menu(column))

        self.tree.column("Tier", width=80, anchor="center")
        self.tree.column("Name", width=200, anchor="w")
        self.tree.column("Quantity", width=100, anchor="center")
        self.tree.column("Tag", width=300, anchor="w")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                        background="#2b2b2b",
                        foreground="white",
                        fieldbackground="#2b2b2b",
                        rowheight=25)
        style.map("Treeview",
                  background=[("selected", "#3a7ebf")])
        style.configure("Treeview.Heading",
                        background="#3a3a3a",
                        foreground="white",
                        font=('TkDefaultFont', 10, 'bold'))

    def _open_filter_dialog(self, column_name: str, is_numeric: bool = False):
        """Opens a filter dialog for the specified column."""
        if column_name == "Tag":
            all_tags = set()
            for item in self.current_inventory_data:
                tag = item.get("Tag")
                if tag:
                    all_tags.add(tag)
            unique_values = sorted(list(all_tags))
        else:
            unique_values = sorted(list(set(str(item.get(column_name)) for item in self.current_inventory_data if column_name in item and item.get(column_name) is not None)))

        current_filter_state = self.active_filters.get(column_name, {'selected': None, 'min': None, 'max': None})

        dialog = FilterDialog(self, column_name, unique_values, current_filter_state, is_numeric)

    def update_filter(self, column_name: str, new_filter_state: dict):
        """Callback from FilterDialog to update filter settings."""
        self.active_filters[column_name] = new_filter_state
        logging.info(f"Filter for {column_name} updated: {new_filter_state}")
        self.apply_filters_and_sort()

    def _toggle_always_on_top(self):
        """Toggles the 'always on top' attribute of the window."""
        current_state = self.attributes('-topmost')
        new_state = not current_state
        self.attributes('-topmost', new_state)
        logging.info(f"Always on Top set to: {new_state}")

    def _on_search_change(self, event=None):
        """Called when the search entry text changes."""
        self.search_term = self.search_entry.get().lower().strip()
        logging.info(f"Search term changed to: '{self.search_term}'")
        self.apply_filters_and_sort()

    def _clear_search(self):
        """Clears the search entry and resets search filtering."""
        self.search_entry.delete(0, 'end')
        self.search_term = ""
        logging.info("Search cleared")
        self.apply_filters_and_sort()

    def _schedule_auto_refresh(self):
        """Schedules the automatic refresh of inventory data."""
        # Cancel any existing refresh job to prevent multiple schedules
        if self.auto_refresh_job:
            self.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None

        refresh_interval_ms = self.auto_refresh_interval_minutes * 60 * 1000
        self.auto_refresh_job = self.after(refresh_interval_ms, self._auto_refresh_data)
        logging.info(f"Next auto-refresh scheduled in {self.auto_refresh_interval_minutes} minutes.")

    def _cancel_auto_refresh(self):
        """Cancels the currently scheduled automatic refresh."""
        if self.auto_refresh_job:
            self.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None
            logging.info("Auto-refresh cancelled.")

    def _auto_refresh_data(self):
        """Called by the auto-refresh scheduler to refresh data."""
        logging.info("Auto-refreshing inventory data...")
        # Call the master's force refresh method
        if hasattr(self.master, 'force_inventory_refresh'):
            self.master.force_inventory_refresh()
        elif hasattr(self.master, '_force_inventory_refresh'):
            self.master._force_inventory_refresh()

    def _refresh_data(self):
        """Triggers a re-fetch and re-display of inventory data, bypassing cache."""
        if hasattr(self.master, 'status_label'):
            self.master.status_label.configure(text="Refreshing claim inventory data...", text_color="yellow")
        
        # Force a fresh fetch bypassing the cache
        if hasattr(self.master, 'force_inventory_refresh'):
            self.master.force_inventory_refresh()
        elif hasattr(self.master, '_force_inventory_refresh'):
            self.master._force_inventory_refresh()

    def apply_filters_and_sort(self, *args):
        """Applies filters and sorting to the inventory data and updates the treeview."""
        print(f"DEBUG: apply_filters_and_sort called - timestamp before: {self.last_updated_label.cget('text')}")
        filtered_data = list(self.current_inventory_data)

        # Apply search filtering first
        if self.search_term:
            filtered_data = [
                item for item in filtered_data
                if self.search_term in str(item.get('Name', '')).lower() or
                   self.search_term in str(item.get('Tag', '')).lower()
            ]

        for col_name, filter_state in self.active_filters.items():
            selected_values = filter_state.get('selected')
            min_val = filter_state.get('min')
            max_val = filter_state.get('max')

            if selected_values is not None:
                filtered_data = [item for item in filtered_data if str(item.get(col_name, '')) in selected_values]

            if (min_val is not None) or (max_val is not None):
                if col_name in ["Tier", "Quantity"]:
                    filtered_data = [
                        item for item in filtered_data
                        if self._can_convert_to_float(item.get(col_name)) and \
                           (min_val is None or float(item.get(col_name)) >= min_val) and \
                           (max_val is None or float(item.get(col_name)) <= max_val)
                    ]

        sort_by = self.sort_column

        if sort_by in ["Tier", "Name", "Quantity", "Tag"]:
            logging.info(f"Sorting data by '{sort_by}', direction: {'DESC' if self.sort_direction else 'ASC'}, data length: {len(filtered_data)}")
            if sort_by in ["Tier", "Quantity"]:
                # For numeric columns, convert to numbers for proper sorting
                def numeric_sort_key(x):
                    val = x.get(sort_by)
                    if val is None:
                        return -float('inf')
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return -float('inf')
                filtered_data.sort(key=numeric_sort_key, reverse=self.sort_direction)
            elif sort_by == "Tag":
                filtered_data.sort(key=lambda x: x.get("Tag", "").lower(), reverse=self.sort_direction)
            else:
                filtered_data.sort(key=lambda x: str(x.get(sort_by, '')).lower(), reverse=self.sort_direction)
            
            # Log first few items to verify sort order
            if len(filtered_data) > 0:
                logging.info(f"First 3 items after sort: {[item.get(sort_by) for item in filtered_data[:3]]}")
        else:
            logging.info(f"No sorting applied - sort_by: {sort_by}")

        self.update_treeview(filtered_data)
        
        # Update only the item count, not the timestamp (sorting/filtering doesn't change last update time)
        self._update_item_count()
        print(f"DEBUG: apply_filters_and_sort finished - timestamp after: {self.last_updated_label.cget('text')}")

    def _can_convert_to_float(self, value):
        """Helper to check if a value can be safely converted to float."""
        if value is None:
            return False
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def update_treeview(self, data):
        """
        Updates the Treeview with new data.
        For sorting operations, we need to rebuild to maintain correct order.
        """
        # Clear all existing items to ensure proper ordering
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Insert all items in the correct order
        for item_data in data:
            self.tree.insert("", "end", values=(
                item_data["Tier"],
                item_data["Name"],
                item_data["Quantity"],
                item_data["Tag"]
            ))
        
        logging.debug(f"Updated Treeview with {len(data)} items in sorted order.")

    def _update_item_count(self):
        """Updates only the item count in the status bar without changing the timestamp."""
        # Update item count based on currently visible items in treeview
        visible_items = len(self.tree.get_children())
        total_items = len(self.current_inventory_data)
        
        if visible_items == total_items:
            self.item_count_label.configure(text=f"Items: {total_items}")
        else:
            self.item_count_label.configure(text=f"Items: {visible_items} of {total_items}")

    def update_last_updated_time(self, schedule_refresh=True):
        """Updates the status bar with last update time and item count."""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"DEBUG: update_last_updated_time called, setting to: {current_time}")
        self.last_updated_label.configure(text=f"Last update: {current_time}")
        logging.info(f"Timestamp updated to: {current_time}")
        
        # Mark timestamp as properly initialized
        self.timestamp_initialized = True
        
        # Update item count as well when timestamp is updated
        self._update_item_count()

        # Only schedule refresh when explicitly requested (e.g., after new data fetch)
        if schedule_refresh:
            self._schedule_auto_refresh()
            
    def _set_timestamp_from_fetch_time(self, fetch_time):
        """Set timestamp display from a cached fetch time."""
        if isinstance(fetch_time, (int, float)):
            time_str = datetime.fromtimestamp(fetch_time).strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(fetch_time, datetime):
            time_str = fetch_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(fetch_time)
        print(f"DEBUG: _set_timestamp_from_fetch_time called with: {fetch_time}, formatted as: {time_str}")
        self.last_updated_label.configure(text=f"Last update: {time_str}")
        
        # Mark timestamp as properly initialized
        self.timestamp_initialized = True

    def sort_treeview_column(self, col):
        """Handles sorting when a column header is clicked, updates header indicators."""
        print(f"DEBUG: sort_treeview_column called for column: {col}")
        print(f"DEBUG: Before sort - timestamp label text: {self.last_updated_label.cget('text')}")
        # Always toggle direction if clicking the same column, else set to ascending
        if self.sort_column == col:
            self.sort_direction = not self.sort_direction
        else:
            self.sort_column = col
            self.sort_direction = False
        self._update_treeview_headers()
        self.apply_filters_and_sort()
        print(f"DEBUG: After sort - timestamp label text: {self.last_updated_label.cget('text')}")

    def on_closing(self):
        """Handles window closing event, cancels auto-refresh."""
        self._cancel_auto_refresh()
        if hasattr(self.master, 'toggle_claim_inventory'):
            self.master.toggle_claim_inventory.deselect()  # Deselect toggle in main window
        if hasattr(self.master, 'grab_release'):
            self.master.grab_release()
        self.destroy()

    def _save_to_file(self):
        """Save the current inventory data to a file."""
        if not self.current_inventory_data:
            messagebox.showwarning("No Data", "No inventory data to save.")
            return

        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        claim_name = getattr(self.claim_instance, 'claim_name', 'Unknown_Claim').replace(' ', '_')
        default_filename = f"claim_inventory_{claim_name}_{timestamp}"

        # Ask user for file location and format
        file_path = filedialog.asksaveasfilename(
            title="Save Inventory Data",
            defaultextension=".csv",
            initialfile=default_filename,
            filetypes=[
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return  # User cancelled

        try:
            file_extension = os.path.splitext(file_path.lower())[1]
            
            if file_extension == '.csv':
                self._save_as_csv(file_path)
            elif file_extension == '.json':
                self._save_as_json(file_path)
            else:
                self._save_as_text(file_path)
                
            messagebox.showinfo("Success", f"Inventory data saved to:\n{file_path}")
            logging.info(f"Inventory data saved to: {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to save file: {str(e)}"
            messagebox.showerror("Save Error", error_msg)
            logging.error(f"Error saving inventory data: {e}")

    def _save_as_csv(self, file_path: str):
        """Save inventory data as CSV file."""
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Tier', 'Name', 'Quantity', 'Tag']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write data
            for item in self.current_inventory_data:
                writer.writerow({
                    'Name': item.get('Name', ''),
                    'Quantity': item.get('Quantity', 0),
                    'Tier': item.get('Tier', 0),
                    'Tag': item.get('Tag', '')
                })

    def _save_as_json(self, file_path: str):
        """Save inventory data as JSON file."""
        # Create metadata
        save_data = {
            'metadata': {
                'claim_name': getattr(self.claim_instance, 'claim_name', 'Unknown'),
                'player_name': getattr(self.bitcraft_client, 'player_name', 'Unknown'),
                'region': getattr(self.bitcraft_client, 'region', 'Unknown'),
                'export_timestamp': datetime.now().isoformat(),
                'total_items': len(self.current_inventory_data)
            },
            'inventory': self.current_inventory_data
        }
        
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(save_data, jsonfile, indent=2, ensure_ascii=False)

    def _save_as_text(self, file_path: str):
        """Save inventory data as formatted text file."""
        with open(file_path, 'w', encoding='utf-8') as textfile:
            # Write header
            textfile.write("BitCraft Claim Inventory Report\n")
            textfile.write("=" * 50 + "\n\n")
            
            # Write metadata
            textfile.write(f"Claim: {getattr(self.claim_instance, 'claim_name', 'Unknown')}\n")
            textfile.write(f"Player: {getattr(self.bitcraft_client, 'player_name', 'Unknown')}\n")
            textfile.write(f"Region: {getattr(self.bitcraft_client, 'region', 'Unknown')}\n")
            textfile.write(f"Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            textfile.write(f"Total Items: {len(self.current_inventory_data)}\n\n")
            
            # Write table header
            textfile.write(f"{'Tier':<6} {'Name':<30} {'Quantity':<10} {'Tag':<20}\n")
            textfile.write("-" * 66 + "\n")
            
            # Write data
            for item in self.current_inventory_data:
                tier = str(item.get('Tier', 0))
                name = str(item.get('Name', ''))[:29]  # Truncate if too long
                quantity = str(item.get('Quantity', 0))
                tag = str(item.get('Tag', ''))[:19]  # Truncate if too long

                textfile.write(f"{tier:<6} {name:<30} {quantity:<10} {tag:<20}\n")

    def _is_filter_active(self, column_name: str) -> bool:
        """Check if a filter is currently active for the specified column."""
        filter_state = self.active_filters.get(column_name, {})
        return (filter_state.get('selected') is not None or 
                filter_state.get('min') is not None or 
                filter_state.get('max') is not None)

    def _show_combined_menu(self, column):
        """Shows a combined sorting and filtering menu like Google Sheets."""
        import tkinter as tk
        
        # Create popup menu
        menu = tk.Menu(self, tearoff=0)
        
        # Add sorting options
        menu.add_command(label=f"Sort A to Z", command=lambda: self._sort_column_asc(column))
        menu.add_command(label=f"Sort Z to A", command=lambda: self._sort_column_desc(column))
        
        menu.add_separator()
        
        # Add filter option
        menu.add_command(label="Filter by values...", command=lambda: self._show_filter_values_menu(column))
        
        # Get unique values for this column to show filter status
        if self._is_filter_active(column):
            menu.add_separator()
            menu.add_command(label="Clear filter", command=lambda: self._clear_column_filter(column))
        
        # Show menu at mouse position
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _sort_column_asc(self, column):
        """Sort column in ascending order."""
        logging.info(f"Sorting column '{column}' in ascending order")
        print(f"DEBUG: _sort_column_asc called on instance {id(self)}")
        print(f"DEBUG: _sort_column_asc - timestamp_initialized: {self.timestamp_initialized}")
        print(f"DEBUG: _sort_column_asc - current timestamp: {self.last_updated_label.cget('text')}")
        self.sort_column = column
        self.sort_direction = False
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _sort_column_desc(self, column):
        """Sort column in descending order."""
        logging.info(f"Sorting column '{column}' in descending order")
        print(f"DEBUG: _sort_column_desc called on instance {id(self)}")
        print(f"DEBUG: _sort_column_desc - timestamp_initialized: {self.timestamp_initialized}")
        print(f"DEBUG: _sort_column_desc - current timestamp: {self.last_updated_label.cget('text')}")
        self.sort_column = column
        self.sort_direction = True
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _show_filter_values_menu(self, column):
        """Show the filter values selection for a column with Google Sheets style."""
        # Get unique values for the column
        if column == "Tag":
            all_values = set()
            for item in self.current_inventory_data:
                tag = item.get("Tag")
                if tag:
                    all_values.add(tag)
            unique_values = sorted(list(all_values))
        else:
            unique_values = sorted(list(set(str(item.get(column)) for item in self.current_inventory_data if column in item and item.get(column) is not None)))

        # Create a new window for filter selection
        filter_window = ctk.CTkToplevel(self)
        filter_window.title(f"Filter by {column}")
        filter_window.geometry("350x500")
        filter_window.transient(self)
        filter_window.grab_set()
        filter_window.attributes('-topmost', True)
        
        # Position relative to main window
        x = self.winfo_x() + 50
        y = self.winfo_y() + 50
        filter_window.geometry(f"350x500+{x}+{y}")
        
        # Configure grid
        filter_window.grid_columnconfigure(0, weight=1)
        filter_window.grid_rowconfigure(2, weight=1)  # Make scrollable area expandable
        
        # Get current filter state
        current_filter = self.active_filters.get(column, {'selected': None, 'min': None, 'max': None})
        current_selected = current_filter.get('selected', set(unique_values))
        if current_selected is None:
            current_selected = set(unique_values)
        
        # Create checkboxes storage
        checkboxes = []
        
        def apply_filter():
            selected_values = set()
            for value, var in checkboxes:
                if var.get():
                    selected_values.add(value)
            
            # Update filter
            if len(selected_values) == len(unique_values):
                # All selected = no filter
                self.active_filters[column] = {'selected': None, 'min': None, 'max': None}
            else:
                self.active_filters[column] = {'selected': selected_values, 'min': None, 'max': None}
            
            self._update_treeview_headers()
            self.apply_filters_and_sort()
            filter_window.destroy()
        
        def cancel_filter():
            filter_window.destroy()
        
        def select_all():
            for _, var in checkboxes:
                var.set(True)
        
        def clear_all():
            for _, var in checkboxes:
                var.set(False)
        
        # Title
        title_label = ctk.CTkLabel(filter_window, text=f"Filter by {column}", 
                                  font=ctk.CTkFont(size=16, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Select/Clear all buttons (outside scroll area)
        select_frame = ctk.CTkFrame(filter_window, fg_color="transparent")
        select_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        select_frame.grid_columnconfigure(0, weight=1)
        select_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(select_frame, text="Select All", command=select_all, 
                     height=28, font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(select_frame, text="Clear All", command=clear_all, 
                     height=28, font=ctk.CTkFont(size=12)).grid(row=0, column=1, padx=(5, 0), sticky="ew")
        
        # Scrollable frame for checkboxes
        scroll_frame = ctk.CTkScrollableFrame(filter_window)
        scroll_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="nsew")
        scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Create checkboxes for each unique value
        for i, value in enumerate(unique_values):
            var = ctk.BooleanVar()
            var.set(str(value) in current_selected)
            
            cb = ctk.CTkCheckBox(scroll_frame, text=str(value), variable=var)
            cb.grid(row=i, column=0, padx=10, pady=2, sticky="w")
            checkboxes.append((str(value), var))
        
        # Bottom Apply/Cancel buttons
        bottom_button_frame = ctk.CTkFrame(filter_window, fg_color="transparent")
        bottom_button_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        bottom_button_frame.grid_columnconfigure(0, weight=1)
        bottom_button_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(bottom_button_frame, text="Apply", command=apply_filter, 
                     width=100).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(bottom_button_frame, text="Cancel", command=cancel_filter, 
                     width=100, fg_color="gray").grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _clear_column_filter(self, column):
        """Clear the filter for a specific column."""
        self.active_filters[column] = {'selected': None, 'min': None, 'max': None}
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _show_context_menu(self, event):
        """Show right-click context menu for item wiki links."""
        # Get the item that was clicked
        item = self.tree.identify_row(event.y)
        if not item:
            return
        
        # Get the item data
        item_values = self.tree.item(item, "values")
        if not item_values or len(item_values) < 2:
            return
        
        item_name = item_values[1]  
        if not item_name:
            return
        
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(
            label="Go to Wiki",
            command=lambda: self._open_wiki_page(item_name)
        )
        
        # Show menu at click position
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _open_wiki_page(self, item_name):
        """Open the BitCraft wiki page for the specified item."""
        # Replace spaces with underscores for wiki URL format
        wiki_name = item_name.replace(" ", "_")
        wiki_url = f"https://bitcraft.wiki.gg/wiki/{wiki_name}"
        
        try:
            webbrowser.open(wiki_url)
            logging.info(f"Opened wiki page for item: {item_name}")
        except Exception as e:
            logging.error(f"Failed to open wiki page for {item_name}: {e}")
            messagebox.showerror("Error", f"Failed to open wiki page for {item_name}")

    def _on_header_click(self, event):
        """Handle clicks on treeview headers - no longer needed with new approach."""
        pass
