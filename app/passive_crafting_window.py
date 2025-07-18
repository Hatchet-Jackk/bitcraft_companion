import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import json
import os
import csv
from datetime import datetime

from client import BitCraft
from claim import Claim


class PassiveCraftingWindow(ctk.CTkToplevel):
    def __init__(self, master, bitcraft_client: BitCraft, claim_instance: Claim, initial_display_data: list, last_fetch_time=None):
        print("DEBUG: PassiveCraftingWindow constructor called")
        print(f"DEBUG: Constructor - last_fetch_time parameter: {last_fetch_time}")
        super().__init__(master)
        self.title("Passive Crafting Status")

        # Make window resizable with better initial size
        min_width = 800
        min_height = 500
        initial_width = 900
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
        self.attributes('-topmost', True)

        self.bitcraft_client = bitcraft_client
        self.claim_instance = claim_instance
        self.current_crafting_data = initial_display_data
        self.active_filters = {
            "Tier": {'selected': None, 'min': None, 'max': None},
            "Name": {'selected': None, 'min': None, 'max': None},
            "Quantity": {'selected': None, 'min': None, 'max': None},
            "Refinery": {'selected': None, 'min': None, 'max': None},
            "Tag": {'selected': None, 'min': None, 'max': None}
        }

        self.auto_refresh_job = None
        self.auto_refresh_interval_minutes = 2  # More frequent refresh for passive crafting
        self.last_fetch_time = last_fetch_time

        self.sort_column = "Name"
        self.sort_direction = False
        
        # Search functionality
        self.search_term = ""
        
        # Flag to track if timestamp has been properly initialized
        self.timestamp_initialized = False
        
        self.create_widgets()
        
        print(f"DEBUG: PassiveCraftingWindow constructor finished - instance id: {id(self)}")
        print(f"DEBUG: Constructor - timestamp_initialized: {self.timestamp_initialized}")

    def create_widgets(self):
        # Controls frame at the top
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew", columnspan=2)

        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_columnconfigure(1, weight=0)

        # Instructions label
        instructions_label = ctk.CTkLabel(controls_frame, 
                                        text="Click filter arrows (▼) for sorting and filtering",
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
        self.tree = ttk.Treeview(self, columns=("Tier", "Name", "Quantity", "Refinery", "Tag"), show="headings")
        self.tree.grid(row=2, column=0, padx=0, pady=(0, 10), sticky="nsew")

        # Initial header setup with sort indicators
        self._update_treeview_headers()

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

        # Status bar content
        initial_timestamp_text = "Last update: Loading..."
        if hasattr(self, 'timestamp_initialized') and self.timestamp_initialized and hasattr(self, 'last_updated_label'):
            # Preserve existing timestamp text if already initialized
            initial_timestamp_text = self.last_updated_label.cget('text')
            print(f"DEBUG: Preserving existing timestamp: {initial_timestamp_text}")
        
        self.last_updated_label = ctk.CTkLabel(self.status_bar_frame, text=initial_timestamp_text, 
                                               font=ctk.CTkFont(size=11))
        self.last_updated_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")

        self.item_count_label = ctk.CTkLabel(self.status_bar_frame, text="Operations: 0", 
                                             font=ctk.CTkFont(size=11))
        self.item_count_label.grid(row=0, column=1, padx=10, pady=2, sticky="e")

    def _update_treeview_headers(self):
        """Updates the treeview column headers with sort direction indicators and filter dropdowns."""
        arrow_up = " ↑"
        arrow_down = " ↓"
        filter_arrow = " ▼"
        columns = ["Tier", "Name", "Quantity", "Refinery", "Tag"]

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
        self.tree.column("Refinery", width=250, anchor="w")
        self.tree.column("Tag", width=200, anchor="w")

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

    def _refresh_data(self):
        """Triggers a re-fetch and re-display of passive crafting data, bypassing cache."""
        if hasattr(self.master, 'status_label'):
            self.master.status_label.configure(text="Refreshing passive crafting data...", text_color="yellow")
        
        # Force a fresh fetch bypassing the cache
        if hasattr(self.master, 'force_passive_crafting_refresh'):
            self.master.force_passive_crafting_refresh()
        elif hasattr(self.master, '_force_passive_crafting_refresh'):
            self.master._force_passive_crafting_refresh()

    def apply_filters_and_sort(self, *args):
        """Applies filters and sorting to the passive crafting data and updates the treeview."""
        print(f"DEBUG: apply_filters_and_sort called - timestamp before: {self.last_updated_label.cget('text')}")
        filtered_data = list(self.current_crafting_data)

        # Apply search filtering first
        if self.search_term:
            filtered_data = [
                item for item in filtered_data
                if self.search_term in str(item.get('Name', '')).lower() or
                   self.search_term in str(item.get('Refinery', '')).lower() or
                   self.search_term in str(item.get('Tag', '')).lower()
            ]

        for col_name, filter_state in self.active_filters.items():
            selected_values = filter_state.get('selected')
            min_val = filter_state.get('min')
            max_val = filter_state.get('max')

            if selected_values is not None:
                filtered_data = [item for item in filtered_data if str(item.get(col_name, '')) in selected_values]

            if (min_val is not None) or (max_val is not None):
                if col_name in ["Quantity", "Tier"]:
                    filtered_data = [
                        item for item in filtered_data
                        if self._can_convert_to_float(item.get(col_name)) and \
                           (min_val is None or float(item.get(col_name)) >= min_val) and \
                           (max_val is None or float(item.get(col_name)) <= max_val)
                    ]

        sort_by = self.sort_column

        if sort_by in ["Tier", "Name", "Quantity", "Refinery", "Tag"]:
            logging.info(f"Sorting data by '{sort_by}', direction: {'DESC' if self.sort_direction else 'ASC'}, data length: {len(filtered_data)}")
            if sort_by in ["Quantity", "Tier"]:
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
            elif sort_by in ["Tag", "Refinery"]:
                filtered_data.sort(key=lambda x: x.get(sort_by, "").lower(), reverse=self.sort_direction)
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
        """Updates the Treeview with new data."""
        # Clear all existing items to ensure proper ordering
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Insert all items in the correct order
        for item_data in data:
            self.tree.insert("", "end", values=(
                item_data["Tier"],
                item_data["Name"],
                item_data["Quantity"],
                item_data["Refinery"],
                item_data["Tag"]
            ))
        
        logging.debug(f"Updated Treeview with {len(data)} passive crafting operations in sorted order.")

    def _update_item_count(self):
        """Updates only the item count in the status bar without changing the timestamp."""
        # Update item count based on currently visible items in treeview
        visible_items = len(self.tree.get_children())
        total_items = len(self.current_crafting_data)
        
        if visible_items == total_items:
            self.item_count_label.configure(text=f"Operations: {total_items}")
        else:
            self.item_count_label.configure(text=f"Operations: {visible_items} of {total_items}")

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

    def _schedule_auto_refresh(self):
        """Schedules the automatic refresh of passive crafting data."""
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
        logging.info("Auto-refreshing passive crafting data...")
        # Call the master's force refresh method
        if hasattr(self.master, 'force_passive_crafting_refresh'):
            self.master.force_passive_crafting_refresh()
        elif hasattr(self.master, '_force_passive_crafting_refresh'):
            self.master._force_passive_crafting_refresh()

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
        self.sort_column = column
        self.sort_direction = False
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _sort_column_desc(self, column):
        """Sort column in descending order."""
        logging.info(f"Sorting column '{column}' in descending order")
        self.sort_column = column
        self.sort_direction = True
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _show_filter_values_menu(self, column):
        """Show the filter values selection for a column."""
        # Get unique values for the column
        unique_values = sorted(list(set(str(item.get(column)) for item in self.current_crafting_data if column in item and item.get(column) is not None)))
        
        if not unique_values:
            messagebox.showinfo("No Values", f"No values found for column '{column}'")
            return
            
        # Create filter dialog
        self._show_filter_dialog(column, unique_values)
    
    def _show_filter_dialog(self, column, unique_values):
        """Show a dialog for filtering by values."""
        # Create a new window for the filter dialog
        filter_window = ctk.CTkToplevel(self)
        filter_window.title(f"Filter by {column}")
        filter_window.geometry("400x500")
        filter_window.transient(self)
        filter_window.grab_set()
        
        # Center the dialog
        filter_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (400 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (500 // 2)
        filter_window.geometry(f"400x500+{x}+{y}")
        
        # Configure grid
        filter_window.grid_columnconfigure(0, weight=1)
        filter_window.grid_rowconfigure(1, weight=1)
        
        # Title label
        title_label = ctk.CTkLabel(filter_window, text=f"Filter by {column}", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        # Create main frame for checkboxes
        main_frame = ctk.CTkScrollableFrame(filter_window)
        main_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Get currently selected values
        current_filter = self.active_filters.get(column, {})
        currently_selected = current_filter.get('selected', set(unique_values))  # Default to all selected
        if currently_selected is None:
            currently_selected = set(unique_values)
        
        # Variables to track checkbox states
        checkbox_vars = {}
        
        # Select All checkbox
        select_all_var = tk.BooleanVar(value=len(currently_selected) == len(unique_values))
        select_all_checkbox = ctk.CTkCheckBox(main_frame, text="Select All", 
                                              variable=select_all_var,
                                              command=lambda: self._toggle_select_all(checkbox_vars, select_all_var))
        select_all_checkbox.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # Separator
        separator = ctk.CTkLabel(main_frame, text="─" * 50, text_color="gray")
        separator.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        # Create checkboxes for each unique value
        for i, value in enumerate(unique_values):
            var = tk.BooleanVar(value=str(value) in currently_selected)
            checkbox_vars[value] = var
            
            # Truncate long values for display
            display_value = str(value)
            if len(display_value) > 40:
                display_value = display_value[:37] + "..."
            
            checkbox = ctk.CTkCheckBox(main_frame, text=display_value, variable=var,
                                       command=lambda: self._update_select_all_state(checkbox_vars, select_all_var))
            checkbox.grid(row=i+2, column=0, padx=10, pady=2, sticky="w")
        
        # Button frame
        button_frame = ctk.CTkFrame(filter_window, fg_color="transparent")
        button_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)
        
        # Buttons
        def apply_filter():
            selected_values = {str(value) for value, var in checkbox_vars.items() if var.get()}
            
            if len(selected_values) == len(unique_values):
                # All selected = no filter
                self.active_filters[column]['selected'] = None
            else:
                self.active_filters[column]['selected'] = selected_values
            
            self._update_treeview_headers()
            self.apply_filters_and_sort()
            filter_window.destroy()
        
        def clear_filter():
            self.active_filters[column]['selected'] = None
            self._update_treeview_headers()
            self.apply_filters_and_sort()
            filter_window.destroy()
        
        def cancel():
            filter_window.destroy()
        
        ctk.CTkButton(button_frame, text="Apply", command=apply_filter).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(button_frame, text="Clear", command=clear_filter).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(button_frame, text="Cancel", command=cancel).grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        # Focus the window
        filter_window.focus()
    
    def _toggle_select_all(self, checkbox_vars, select_all_var):
        """Toggle all checkboxes when Select All is clicked."""
        select_all = select_all_var.get()
        for var in checkbox_vars.values():
            var.set(select_all)
    
    def _update_select_all_state(self, checkbox_vars, select_all_var):
        """Update the Select All checkbox state based on individual checkboxes."""
        all_selected = all(var.get() for var in checkbox_vars.values())
        none_selected = not any(var.get() for var in checkbox_vars.values())
        
        if all_selected:
            select_all_var.set(True)
        elif none_selected:
            select_all_var.set(False)
        # If some but not all are selected, leave Select All as is

    def _clear_column_filter(self, column):
        """Clear the filter for a specific column."""
        self.active_filters[column] = {'selected': None, 'min': None, 'max': None}
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _save_to_file(self):
        """Save the current passive crafting data to a file."""
        if not self.current_crafting_data:
            messagebox.showwarning("No Data", "No passive crafting data to save.")
            return

        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        claim_name = getattr(self.claim_instance, 'claim_name', 'Unknown_Claim').replace(' ', '_')
        default_filename = f"passive_crafting_{claim_name}_{timestamp}"

        # Ask user for file location and format
        file_path = filedialog.asksaveasfilename(
            title="Save Passive Crafting Data",
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
                
            messagebox.showinfo("Success", f"Passive crafting data saved to:\n{file_path}")
            logging.info(f"Passive crafting data saved to: {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to save file: {str(e)}"
            messagebox.showerror("Save Error", error_msg)
            logging.error(f"Error saving passive crafting data: {e}")

    def _save_as_csv(self, file_path: str):
        """Save passive crafting data as CSV file."""
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Tier', 'Name', 'Quantity', 'Refinery', 'Tag']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write data
            for item in self.current_crafting_data:
                writer.writerow({
                    'Tier': item.get('Tier', 0),
                    'Name': item.get('Name', ''),
                    'Quantity': item.get('Quantity', 0),
                    'Refinery': item.get('Refinery', ''),
                    'Tag': item.get('Tag', '')
                })

    def _save_as_json(self, file_path: str):
        """Save passive crafting data as JSON file."""
        # Create metadata
        save_data = {
            'metadata': {
                'claim_name': getattr(self.claim_instance, 'claim_name', 'Unknown'),
                'player_name': getattr(self.bitcraft_client, 'player_name', 'Unknown'),
                'region': getattr(self.bitcraft_client, 'region', 'Unknown'),
                'export_timestamp': datetime.now().isoformat(),
                'total_operations': len(self.current_crafting_data)
            },
            'passive_crafting': self.current_crafting_data
        }
        
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(save_data, jsonfile, indent=2, ensure_ascii=False)

    def _save_as_text(self, file_path: str):
        """Save passive crafting data as formatted text file."""
        with open(file_path, 'w', encoding='utf-8') as textfile:
            # Write header
            textfile.write("BitCraft Passive Crafting Status Report\n")
            textfile.write("=" * 50 + "\n\n")
            
            # Write metadata
            textfile.write(f"Claim: {getattr(self.claim_instance, 'claim_name', 'Unknown')}\n")
            textfile.write(f"Player: {getattr(self.bitcraft_client, 'player_name', 'Unknown')}\n")
            textfile.write(f"Region: {getattr(self.bitcraft_client, 'region', 'Unknown')}\n")
            textfile.write(f"Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            textfile.write(f"Total Operations: {len(self.current_crafting_data)}\n\n")
            
            # Write table header
            textfile.write(f"{'Tier':<6} {'Name':<25} {'Qty':<5} {'Refinery':<30} {'Tag':<20}\n")
            textfile.write("-" * 86 + "\n")
            
            # Write data
            for item in self.current_crafting_data:
                tier = str(item.get('Tier', 0))
                name = str(item.get('Name', ''))[:24]  # Truncate if too long
                quantity = str(item.get('Quantity', 0))
                refinery = str(item.get('Refinery', ''))[:29]  # Truncate if too long
                tag = str(item.get('Tag', ''))[:19]  # Truncate if too long

                textfile.write(f"{tier:<6} {name:<25} {quantity:<5} {refinery:<30} {tag:<20}\n")

    def on_closing(self):
        """Handles window closing event, cancels auto-refresh."""
        self._cancel_auto_refresh()
        if hasattr(self.master, 'toggle_passive_crafting'):
            self.master.toggle_passive_crafting.deselect()  # Deselect toggle in main window
        if hasattr(self.master, 'grab_release'):
            self.master.grab_release()
        self.destroy()
