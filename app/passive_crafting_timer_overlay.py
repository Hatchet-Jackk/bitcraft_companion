import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import logging
import time
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime

from client import BitCraft
from passive_crafting_service import PassiveCraftingService


class PassiveCraftingTimerOverlay(ctk.CTkToplevel):
    """Timer overlay showing current user's passive crafting operations with remaining time."""
    
    def __init__(self, parent, bitcraft_client: BitCraft, passive_crafting_service: PassiveCraftingService):
        super().__init__(parent)
        
        self.bitcraft_client = bitcraft_client
        self.passive_crafting_service = passive_crafting_service
        
        # Window configuration
        self.title("Passive Crafting Timer")
        
        # Make window resizable with better initial size
        min_width = 700
        min_height = 400
        initial_width = 800
        initial_height = 500

        self.update_idletasks()

        # Position relative to parent
        x = parent.winfo_x() + parent.winfo_width() + 20
        y = parent.winfo_y()
        self.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
        self.minsize(min_width, min_height)
        self.resizable(True, True)

        # Configure window grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)  # Scrollbar column
        self.grid_rowconfigure(0, weight=0)     # Controls frame
        self.grid_rowconfigure(1, weight=0)     # Search frame
        self.grid_rowconfigure(2, weight=1)     # Treeview - main content area
        self.grid_rowconfigure(3, weight=0)     # Status bar

        # Window properties
        self.transient(parent)
        self.attributes('-topmost', True)
        
        # Auto-refresh settings
        self.auto_refresh_enabled = True
        self.refresh_interval = 15  # seconds
        self.refresh_job = None
        self.last_update_time = None
        
        # Data storage
        self.current_timer_data = []
        self.expanded_items = set()  # Track expanded items by their unique key
        
        # Search and filtering
        self.search_term = ""
        self.active_filters = {
            "Tier": {'selected': None, 'min': None, 'max': None},
            "Name": {'selected': None, 'min': None, 'max': None},
            "Quantity": {'selected': None, 'min': None, 'max': None},
            "Refinery": {'selected': None, 'min': None, 'max': None},
            "Tag": {'selected': None, 'min': None, 'max': None},
            "Remaining Time": {'selected': None, 'min': None, 'max': None}
        }
        self.sort_column = "Remaining Time"
        self.sort_direction = False  # False = ascending, True = descending
        
        self.setup_ui()
        
        # Initial data load
        self.refresh_data()
        
        # Start auto-refresh
        self.start_auto_refresh()
        
        # Note: Window close protocol is set by the parent window
    
    def setup_ui(self):
        """Setup the user interface."""
        # Controls frame at the top
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew", columnspan=2)
        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_columnconfigure(1, weight=0)
        controls_frame.grid_columnconfigure(2, weight=0)
        controls_frame.grid_columnconfigure(3, weight=0)
        
        # Title label
        title_label = ctk.CTkLabel(
            controls_frame, 
            text="Passive Crafting Timer", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # Always on Top toggle (moved to top row)
        self.always_on_top_switch = ctk.CTkSwitch(
            controls_frame, 
            text="Always on Top", 
            command=self._toggle_always_on_top
        )
        self.always_on_top_switch.grid(row=0, column=1, padx=10, pady=5, sticky="e")
        self.always_on_top_switch.select()  # Start enabled
        
        # Auto-refresh toggle
        self.toggle_auto_refresh_switch = ctk.CTkSwitch(
            controls_frame,
            text="Auto-refresh",
            command=self.toggle_auto_refresh
        )
        self.toggle_auto_refresh_switch.grid(row=0, column=2, padx=10, pady=5, sticky="e")
        self.toggle_auto_refresh_switch.select()  # Start enabled
        
        # Manual refresh button
        self.refresh_button = ctk.CTkButton(
            controls_frame,
            text="Refresh",
            command=self.refresh_data,
            width=80
        )
        self.refresh_button.grid(row=0, column=3, padx=10, pady=5, sticky="e")
        
        # Search frame
        search_frame = ctk.CTkFrame(self)
        search_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew", columnspan=2)
        search_frame.grid_columnconfigure(1, weight=1)

        # Search label
        search_label = ctk.CTkLabel(search_frame, text="Search:", font=ctk.CTkFont(size=12))
        search_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        # Search entry
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Type to search items...")
        self.search_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.search_entry.bind('<KeyRelease>', self._on_search_change)

        # Clear search button
        self.clear_search_button = ctk.CTkButton(search_frame, text="Clear", width=60, 
                                               command=self._clear_search)
        self.clear_search_button.grid(row=0, column=2, padx=10, pady=5, sticky="e")
        
        # Create a frame for the treeview to control its styling
        tree_frame = ctk.CTkFrame(self)
        tree_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew", columnspan=2)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        
        # Configure treeview style to match dark theme
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure treeview colors to match dark theme
        style.configure("Treeview", 
                       background="#2b2b2b",
                       foreground="white",
                       rowheight=25,
                       fieldbackground="#2b2b2b",
                       borderwidth=0,
                       relief="flat")
        
        style.configure("Treeview.Heading",
                       background="#1f538d",
                       foreground="white",
                       relief="flat",
                       borderwidth=1)
        
        style.map("Treeview.Heading",
                 background=[('active', '#1f538d')])
        
        style.map("Treeview",
                 background=[('selected', '#1f538d')])
        
        # Treeview for timer data
        self.tree = ttk.Treeview(
            tree_frame, 
            columns=("Tier", "Name", "Quantity", "Refinery", "Tag", "Remaining Time", "Completed"), 
            show="tree headings",  # Show both tree structure and headings
            style="Treeview"
        )
        self.tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Configure columns
        column_widths = {
            "Tier": 50,
            "Name": 140,
            "Quantity": 70,
            "Refinery": 110,
            "Tag": 110,
            "Remaining Time": 100,
            "Completed": 80
        }
        
        # Configure the tree column (first column with expand/collapse indicators)
        self.tree.heading("#0", text="", anchor="w")
        self.tree.column("#0", width=20, minwidth=20, anchor="w")
        
        for col in column_widths.keys():
            self.tree.heading(col, text=col, anchor="center")
            self.tree.column(col, width=column_widths[col], minwidth=50, anchor="center")
        
        # Update headers with filtering capability
        self._update_treeview_headers()
        
        # Bind double-click to expand/collapse
        self.tree.bind("<Double-1>", self.on_double_click)
        
        # Vertical scrollbar
        vsb = ctk.CTkScrollbar(tree_frame, command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=10)
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Status bar frame
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew", columnspan=2)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_columnconfigure(1, weight=0)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=11)
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # Last updated label
        self.last_updated_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.last_updated_label.grid(row=0, column=1, padx=10, pady=5, sticky="e")
    
    def _toggle_always_on_top(self):
        """Toggle always on top setting."""
        if self.always_on_top_switch.get():
            self.attributes('-topmost', True)
        else:
            self.attributes('-topmost', False)
    
    def refresh_data(self):
        """Refresh the timer data."""
        self.status_label.configure(text="Refreshing...", text_color="yellow")
        self.passive_crafting_service.get_timer_data(self.on_data_received)
    
    def on_data_received(self, data: List[Dict[str, Any]], success: bool, message: str, has_data: bool):
        """Handle received timer data."""
        if success:
            self.current_timer_data = data
            self.populate_tree(data)
            self.status_label.configure(text=message, text_color="green")
            self.last_update_time = datetime.now()
            self.last_updated_label.configure(text=f"Last updated: {self.last_update_time.strftime('%H:%M:%S')}")
        else:
            self.status_label.configure(text=message, text_color="red")
    
    def save_expansion_state(self):
        """Save the current expansion state of parent items."""
        self.expanded_items.clear()
        
        # Iterate through all top-level items (parents)
        for parent_id in self.tree.get_children():
            if self.tree.get_children(parent_id):  # Has children (is a parent)
                if self.tree.item(parent_id, "open"):  # Is expanded
                    # Create a unique key for this parent based on its values
                    values = self.tree.item(parent_id, "values")
                    if values and len(values) >= 2:
                        # Use tier + name as unique key
                        unique_key = f"{values[0]}_{values[1]}"  # tier_name
                        self.expanded_items.add(unique_key)
    
    def restore_expansion_state(self):
        """Restore the expansion state of parent items."""
        # Iterate through all top-level items (parents)
        for parent_id in self.tree.get_children():
            if self.tree.get_children(parent_id):  # Has children (is a parent)
                # Create a unique key for this parent based on its values
                values = self.tree.item(parent_id, "values")
                if values and len(values) >= 2:
                    # Use tier + name as unique key
                    unique_key = f"{values[0]}_{values[1]}"  # tier_name
                    if unique_key in self.expanded_items:
                        self.tree.item(parent_id, open=True)
                    else:
                        self.tree.item(parent_id, open=False)

    def populate_tree(self, data: List[Dict[str, Any]]):
        """Populate the treeview with hierarchical timer data."""
        # Store raw data for filtering
        self.current_timer_data = data
        
        # Apply search and filters
        self.apply_filters_and_sort()
    
    def apply_filters_and_sort(self):
        """Apply search filters and sorting to the data."""
        if not self.current_timer_data:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            return
            
        # Save current expansion state before clearing
        self.save_expansion_state()
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Start with all data
        filtered_data = list(self.current_timer_data)
        
        # Apply search filtering first
        if self.search_term:
            filtered_data = [
                item for item in filtered_data
                if self.search_term in str(item.get('name', '')).lower() or
                   self.search_term in str(item.get('tag', '')).lower() or
                   self.search_term in str(item.get('refinery', '')).lower()
            ]
        
        # Apply column filters
        for col_name, filter_state in self.active_filters.items():
            selected_values = filter_state.get('selected')
            min_val = filter_state.get('min')
            max_val = filter_state.get('max')

            if selected_values is not None:
                if col_name == "Tier":
                    filtered_data = [item for item in filtered_data if str(item.get('tier', '')) in selected_values]
                elif col_name == "Name":
                    filtered_data = [item for item in filtered_data if str(item.get('name', '')) in selected_values]
                elif col_name == "Quantity":
                    filtered_data = [item for item in filtered_data if str(item.get('quantity', '')) in selected_values]
                elif col_name == "Refinery":
                    filtered_data = [item for item in filtered_data if str(item.get('refinery', '')) in selected_values]
                elif col_name == "Tag":
                    filtered_data = [item for item in filtered_data if str(item.get('tag', '')) in selected_values]
                elif col_name == "Remaining Time":
                    filtered_data = [item for item in filtered_data if str(item.get('remaining_time', '')) in selected_values]

            if (min_val is not None) or (max_val is not None):
                if col_name in ["Tier", "Quantity"]:
                    filtered_data = [
                        item for item in filtered_data
                        if self._can_convert_to_float(item.get(col_name.lower())) and \
                           (min_val is None or float(item.get(col_name.lower())) >= min_val) and \
                           (max_val is None or float(item.get(col_name.lower())) <= max_val)
                    ]
        
        # Sort data
        def sort_key(item):
            if self.sort_column == "Remaining Time":
                remaining_time = item.get('remaining_time', '')
                if remaining_time == "READY":
                    return (0, 0)  # READY items first
                else:
                    return (1, self.parse_time_to_seconds(remaining_time))
            elif self.sort_column == "Tier":
                return int(item.get('tier', 0))
            elif self.sort_column == "Quantity":
                return int(item.get('quantity', 0))
            else:
                return str(item.get(self.sort_column.lower(), ''))
        
        try:
            filtered_data.sort(key=sort_key, reverse=self.sort_direction)
        except (ValueError, TypeError):
            # Fallback to string sorting if there are mixed types
            filtered_data.sort(key=lambda x: str(x.get(self.sort_column.lower(), '')), reverse=self.sort_direction)
        
        # Insert parent and child data into tree
        for parent_item in filtered_data:
            # Insert parent row
            parent_values = (
                parent_item.get('tier', ''),
                parent_item.get('name', ''),
                parent_item.get('quantity', ''),
                parent_item.get('refinery', ''),
                parent_item.get('tag', ''),
                parent_item.get('remaining_time', ''),
                parent_item.get('completed', '')
            )
            
            # Insert parent with text in the tree column
            parent_id = self.tree.insert("", "end", text="", values=parent_values, open=False)
            
            # Insert child rows as children of the parent
            children = parent_item.get('children', [])
            for child_item in children:
                child_values = (
                    child_item.get('tier', ''),
                    child_item.get('name', ''),
                    child_item.get('quantity', ''),
                    child_item.get('refinery', ''),
                    child_item.get('tag', ''),
                    child_item.get('remaining_time', ''),
                    child_item.get('completed', '')
                )
                
                child_id = self.tree.insert(parent_id, "end", text="", values=child_values)
        
        # Restore expansion state after populating
        self.restore_expansion_state()
    
    def _can_convert_to_float(self, value):
        """Helper to check if a value can be safely converted to float."""
        if value is None:
            return False
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _on_search_change(self, event=None):
        """Called when the search entry text changes."""
        self.search_term = self.search_entry.get().lower().strip()
        self.apply_filters_and_sort()
    
    def _clear_search(self):
        """Clears the search entry and resets search filtering."""
        self.search_entry.delete(0, 'end')
        self.search_term = ""
        self.apply_filters_and_sort()
    
    def _update_treeview_headers(self):
        """Updates the treeview column headers with sort direction indicators and filter dropdowns."""
        arrow_up = " ↑"
        arrow_down = " ↓"
        columns = ["Tier", "Name", "Quantity", "Refinery", "Tag", "Remaining Time", "Completed"]

        # Configure the tree column (first column with expand/collapse indicators)
        self.tree.heading("#0", text="", anchor="w")
        self.tree.column("#0", width=20, minwidth=20, anchor="w")
        
        for col in columns:
            # Sort indicator
            sort_indicator = ""
            if self.sort_column == col:
                sort_indicator = arrow_down if not self.sort_direction else arrow_up
                
            # Filter indicator (show if filter is active)
            filter_indicator = ""
            if self._is_filter_active(col):
                filter_indicator = " [F]"
                
            header_text = col + sort_indicator + filter_indicator
            
            # Bind combined sort/filter menu (clicking anywhere on header)
            self.tree.heading(col, text=header_text, anchor="center",
                             command=lambda column=col: self._show_combined_menu(column))
    
    def _is_filter_active(self, column_name: str) -> bool:
        """Check if a filter is active for the given column."""
        filter_state = self.active_filters.get(column_name, {})
        return (filter_state.get('selected') is not None or
                filter_state.get('min') is not None or
                filter_state.get('max') is not None)
    
    def _show_combined_menu(self, column):
        """Shows a combined sort/filter menu for the given column."""
        from tkinter import Menu
        
        menu = Menu(self, tearoff=0)
        
        # Sort options
        menu.add_command(label=f"Sort {column} A-Z", command=lambda: self._sort_column_asc(column))
        menu.add_command(label=f"Sort {column} Z-A", command=lambda: self._sort_column_desc(column))
        menu.add_separator()
        
        # Filter options
        menu.add_command(label=f"Filter {column}...", command=lambda: self._show_filter_dialog(column))
        
        if self._is_filter_active(column):
            menu.add_command(label=f"Clear {column} Filter", command=lambda: self._clear_column_filter(column))
        
        # Show menu at cursor position
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()
    
    def _sort_column_asc(self, column):
        """Sort column in ascending order."""
        self.sort_column = column
        self.sort_direction = False
        self._update_treeview_headers()
        self.apply_filters_and_sort()
    
    def _sort_column_desc(self, column):
        """Sort column in descending order."""
        self.sort_column = column
        self.sort_direction = True
        self._update_treeview_headers()
        self.apply_filters_and_sort()
    
    def _show_filter_dialog(self, column_name: str):
        """Shows a filter dialog for the specified column."""
        # Get unique values for this column
        unique_values = set()
        for item in self.current_timer_data:
            value = item.get(column_name.lower().replace(' ', '_'), '')
            if value:
                unique_values.add(str(value))
        
        unique_values = sorted(list(unique_values))
        current_filter_state = self.active_filters.get(column_name, {'selected': None, 'min': None, 'max': None})
        
        # Import FilterDialog from inventory_window
        from inventory_window import FilterDialog
        
        is_numeric = column_name in ["Tier", "Quantity"]
        dialog = FilterDialog(self, column_name, unique_values, current_filter_state, is_numeric)
    
    def update_filter(self, column_name: str, new_filter_state: dict):
        """Callback from FilterDialog to update filter settings."""
        self.active_filters[column_name] = new_filter_state
        self._update_treeview_headers()
        self.apply_filters_and_sort()
    
    def _clear_column_filter(self, column):
        """Clear the filter for the specified column."""
        self.active_filters[column] = {'selected': None, 'min': None, 'max': None}
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def parse_time_to_seconds(self, time_str: str) -> int:
        """Parse time string (e.g., '1h 30m 45s') to seconds for sorting."""
        if not time_str or time_str == "READY":
            return 0
        
        try:
            total_seconds = 0
            parts = time_str.split()
            
            for part in parts:
                if part.startswith('~'):
                    part = part[1:]  # Remove ~ prefix
                if part.endswith('h'):
                    total_seconds += int(part[:-1]) * 3600
                elif part.endswith('m'):
                    total_seconds += int(part[:-1]) * 60
                elif part.endswith('s'):
                    total_seconds += int(part[:-1])
            
            return total_seconds
        except Exception:
            return 999999  # Put parsing errors at the end

    def on_double_click(self, event):
        """Handle double-click to expand/collapse parent rows."""
        item = self.tree.identify_row(event.y)
        if item:
            # Check if this is a parent item (has children)
            children = self.tree.get_children(item)
            if children:
                # Toggle expand/collapse using TreeView's built-in functionality
                current_state = self.tree.item(item, "open")
                self.tree.item(item, open=not current_state)

    def start_auto_refresh(self):
        """Start the auto-refresh timer."""
        if self.auto_refresh_enabled:
            self.refresh_job = self.after(self.refresh_interval * 1000, self.auto_refresh_callback)
    
    def auto_refresh_callback(self):
        """Callback for auto-refresh timer."""
        if self.auto_refresh_enabled:
            self.refresh_data()
            # Schedule next refresh
            self.refresh_job = self.after(self.refresh_interval * 1000, self.auto_refresh_callback)
    
    def toggle_auto_refresh(self):
        """Toggle auto-refresh on/off."""
        self.auto_refresh_enabled = self.toggle_auto_refresh_switch.get()
        
        if self.auto_refresh_enabled:
            self.start_auto_refresh()
        else:
            if self.refresh_job:
                self.after_cancel(self.refresh_job)
                self.refresh_job = None
    
    def on_closing(self):
        """Handle window closing - this is called by the parent window's protocol."""
        # All cleanup is handled by the parent window's callback
        # This method is kept for consistency but doesn't need to do anything
        pass
