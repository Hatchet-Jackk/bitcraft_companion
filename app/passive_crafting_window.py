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
from base_overlay import BaseOverlay


class PassiveCraftingWindow(BaseOverlay):
    """
    Overlay window for displaying and managing passive crafting inventory.

    Provides filtering, sorting, exporting, and detailed views for passive crafting operations.
    """

    def __init__(
        self,
        master,
        bitcraft_client: BitCraft,
        claim_instance: Claim,
        initial_display_data: list,
        last_fetch_time=None,
    ):
        """
        Initialize the PassiveCraftingWindow overlay.

        Args:
            master: The parent tkinter widget.
            bitcraft_client (BitCraft): The BitCraft client instance.
            claim_instance (Claim): The claim instance for this overlay.
            initial_display_data (list): Initial crafting data to display.
            last_fetch_time (optional): Timestamp of last data fetch.
        """
        # Initialize attributes that are needed in setup_content_ui BEFORE calling super().__init__
        self.bitcraft_client = bitcraft_client
        self.claim_instance = claim_instance
        self.current_crafting_data = initial_display_data
        self.active_filters = {
            "Tier": {"selected": None, "min": None, "max": None},
            "Name": {"selected": None, "min": None, "max": None},
            "Quantity": {"selected": None, "min": None, "max": None},
            "Refinery": {"selected": None, "min": None, "max": None},
            "Crafters": {"selected": None, "min": None, "max": None},
            "Tag": {"selected": None, "min": None, "max": None},
        }
        self.last_fetch_time = last_fetch_time
        self.sort_column = "Name"
        self.sort_direction = False
        self.search_term = ""
        self.timestamp_initialized = False
        self.expanded_rows = set()  # Track which rows are expanded
        self.row_data_map = {}  # Map tree item IDs to data

        # Enable save button for this overlay
        self.enable_save_button = True

        # Initialize with BaseOverlay - this will call setup_content_ui()
        super().__init__(
            master,
            "BitCraft Companion",
            min_width=800,
            min_height=500,
            initial_width=900,
            initial_height=600,
        )

        # Set custom title text
        self.set_title_text("Claim Passive Crafting Inventory")

        # Override auto-refresh settings for passive crafting
        self.refresh_interval = 30  # 30 seconds for passive crafting

        # Flag to track if timestamp has been properly initialized
        self.timestamp_initialized = False

        # Expandable rows functionality
        self.expanded_rows = set()  # Track which rows are expanded
        self.row_data_map = {}  # Map tree item IDs to data

        logging.debug(f"PassiveCraftingWindow constructor finished - instance id: {id(self)}")
        logging.debug(f"Constructor - timestamp_initialized: {self.timestamp_initialized}")

    def setup_content_ui(self):
        """
        Set up the main content area of the overlay, including search, treeview, and scrollbars.
        """
        # Search frame - positioned at row 1 (after controls at row 0)
        search_frame = ctk.CTkFrame(self)
        search_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew", columnspan=2)
        search_frame.grid_columnconfigure(1, weight=1)

        # Search label
        search_label = ctk.CTkLabel(search_frame, text="Search:", font=ctk.CTkFont(size=12))
        search_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        # Search entry
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Type to search items...")
        self.search_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search_change)

        # Clear search button
        self.clear_search_button = ctk.CTkButton(search_frame, text="Clear", width=60, command=self._clear_search)
        self.clear_search_button.grid(row=0, column=2, padx=10, pady=5, sticky="e")

        # Create treeview frame using base class method
        self.tree_frame = self.create_treeview_frame(row=2)

        # Setup treeview styling
        self.setup_treeview_styling()

        # Create treeview
        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=("Tier", "Name", "Quantity", "Refinery", "Crafters", "Tag"),
            show="tree headings",
        )
        self.tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Configure the tree column (column #0) - this shows the tree structure
        self.tree.heading("#0", text="Item", anchor="w")
        self.tree.column("#0", width=200, minwidth=100)

        # Initial header setup with sort indicators
        self._update_treeview_headers()

        # Bind right-click context menu
        self.tree.bind("<Button-3>", self._show_context_menu)

        # Bind hover for tooltips
        self.tree.bind("<Motion>", self._on_hover)
        self.tree.bind("<Leave>", self._on_leave)

        # Bind double-click for expandable rows
        self.tree.bind("<Double-1>", self._on_double_click)

        # Tooltip variables
        self.tooltip_window = None
        self.tooltip_item = None

        # Add vertical scrollbar using base class method
        self.add_vertical_scrollbar(self.tree_frame, self.tree)

        # Horizontal scrollbar for treeview
        hsb = ctk.CTkScrollbar(self.tree_frame, orientation="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.tree.configure(xscrollcommand=hsb.set)

    def _on_save_clicked(self):
        """
        Handle save button click and delegate to the save functionality.
        """
        self._save_to_file()

    def setup_status_bar_content(self):
        """
        Set up additional content in the status bar, such as the item count label.
        """
        # Add item count label to status bar
        self.item_count_label = ctk.CTkLabel(self.status_frame, text="Operations: 0", font=ctk.CTkFont(size=11))
        self.item_count_label.grid(row=0, column=2, padx=10, pady=5, sticky="e")

    def refresh_data(self):
        """
        Refresh the data displayed in the overlay.
        """
        self._refresh_data()

    def _update_treeview_headers(self):
        """
        Update the treeview column headers with sort direction indicators and filter dropdowns.
        """
        arrow_up = " ↑"
        arrow_down = " ↓"
        columns = ["Tier", "Name", "Quantity", "Refinery", "Crafters", "Tag"]

        # Update tree column header for Name sorting
        tree_sort_indicator = ""
        if self.sort_column == "Name":
            tree_sort_indicator = arrow_down if not self.sort_direction else arrow_up
        tree_filter_indicator = " [F]" if self._is_filter_active("Name") else ""
        tree_header_text = "Item" + tree_sort_indicator + tree_filter_indicator
        self.tree.heading(
            "#0",
            text=tree_header_text,
            anchor="w",
            command=lambda: self._show_combined_menu("Name"),
        )

        for col in columns:
            # Sort indicator
            sort_indicator = ""
            if self.sort_column == col:
                sort_indicator = arrow_down if not self.sort_direction else arrow_up

            # Filter indicator (show if filter is active)
            filter_indicator = ""
            if self._is_filter_active(col):
                filter_indicator = " [F]"

            # Hide the Name column header since we're using the tree column
            if col == "Name":
                header_text = ""
            else:
                header_text = col + sort_indicator + filter_indicator

            # Bind combined sort/filter menu (clicking anywhere on header)
            self.tree.heading(
                col,
                text=header_text,
                command=lambda column=col: self._show_combined_menu(column),
            )

        self.tree.column("Tier", width=80, anchor="center")
        self.tree.column("Name", width=0, minwidth=0, stretch=False)  # Hide name column since it's now in tree column
        self.tree.column("Quantity", width=100, anchor="center")
        self.tree.column("Refinery", width=200, anchor="w")
        self.tree.column("Crafters", width=80, anchor="center")
        self.tree.column("Tag", width=200, anchor="w")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b",
            rowheight=25,
        )
        style.map("Treeview", background=[("selected", "#3a7ebf")])
        style.configure(
            "Treeview.Heading",
            background="#3a3a3a",
            foreground="white",
            font=("TkDefaultFont", 10, "bold"),
        )

        # Configure tag for child rows with lighter background
        self.tree.tag_configure("child", background="#3a3a3a")

    def _on_search_change(self, event=None):
        """
        Called when the search entry text changes. Updates the search term and applies filters.

        Args:
            event: The triggering event (optional).
        """
        self.search_term = self.search_entry.get().lower().strip()
        logging.info(f"Search term changed to: '{self.search_term}'")
        self.apply_filters_and_sort()

    def _clear_search(self):
        """
        Clear the search entry and reset search filtering.
        """
        self.search_entry.delete(0, "end")
        self.search_term = ""
        logging.info("Search cleared")
        self.apply_filters_and_sort()

    def _refresh_data(self):
        """
        Trigger a re-fetch and re-display of passive crafting data, bypassing cache.
        """
        if hasattr(self.master, "status_label"):
            self.master.status_label.configure(text="Refreshing passive crafting data...", text_color="yellow")

        # Force a fresh fetch bypassing the cache
        if hasattr(self.master, "force_passive_crafting_refresh"):
            self.master.force_passive_crafting_refresh()
        elif hasattr(self.master, "_force_passive_crafting_refresh"):
            self.master._force_passive_crafting_refresh()

    def apply_filters_and_sort(self, *args):
        """
        Apply filters and sorting to the passive crafting data and update the treeview.

        Args:
            *args: Optional arguments for compatibility with callbacks.
        """
        logging.debug(f"apply_filters_and_sort called - timestamp before: {self.last_updated_label.cget('text')}")
        filtered_data = list(self.current_crafting_data)

        # Apply search filtering first
        if self.search_term:
            filtered_data = [
                item
                for item in filtered_data
                if self.search_term in str(item.get("Name", "")).lower()
                or self.search_term in str(item.get("Refinery", "")).lower()
                or self.search_term in str(item.get("Tag", "")).lower()
            ]

        for col_name, filter_state in self.active_filters.items():
            selected_values = filter_state.get("selected")
            min_val = filter_state.get("min")
            max_val = filter_state.get("max")

            if selected_values is not None:
                filtered_data = [item for item in filtered_data if str(item.get(col_name, "")) in selected_values]

            if (min_val is not None) or (max_val is not None):
                if col_name in ["Quantity", "Tier"]:
                    filtered_data = [
                        item
                        for item in filtered_data
                        if self._can_convert_to_float(item.get(col_name))
                        and (min_val is None or float(item.get(col_name)) >= min_val)
                        and (max_val is None or float(item.get(col_name)) <= max_val)
                    ]

        sort_by = self.sort_column

        if sort_by in ["Tier", "Name", "Quantity", "Refinery", "Tag"]:
            logging.debug(
                f"Sorting data by '{sort_by}', direction: {'DESC' if self.sort_direction else 'ASC'}, data length: {len(filtered_data)}"
            )
            if sort_by in ["Quantity", "Tier"]:
                # For numeric columns, convert to numbers for proper sorting
                def numeric_sort_key(x):
                    val = x.get(sort_by)
                    if val is None:
                        return -float("inf")
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return -float("inf")

                filtered_data.sort(key=numeric_sort_key, reverse=self.sort_direction)
            elif sort_by in ["Tag", "Refinery"]:
                filtered_data.sort(
                    key=lambda x: x.get(sort_by, "").lower(),
                    reverse=self.sort_direction,
                )
            else:
                filtered_data.sort(
                    key=lambda x: str(x.get(sort_by, "")).lower(),
                    reverse=self.sort_direction,
                )

            # Log first few items to verify sort order
            if len(filtered_data) > 0:
                logging.debug(f"First 3 items after sort: {[item.get(sort_by) for item in filtered_data[:3]]}")
        else:
            logging.info(f"No sorting applied - sort_by: {sort_by}")

        self.update_treeview(filtered_data)

        # Update only the item count, not the timestamp (sorting/filtering doesn't change last update time)
        self._update_item_count()
        logging.debug(f"apply_filters_and_sort finished - timestamp after: {self.last_updated_label.cget('text')}")

    def _can_convert_to_float(self, value):
        """
        Helper to check if a value can be safely converted to float.

        Args:
            value: The value to check.

        Returns:
            bool: True if value can be converted to float, False otherwise.
        """
        if value is None:
            return False
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def update_treeview(self, data):
        """
        Update the Treeview with new data.

        Args:
            data (list): List of crafting data to display.
        """
        # Remember which rows were expanded
        expanded_items = set()
        for item_id in self.tree.get_children():
            item_values = self.tree.item(item_id)["values"]
            if len(item_values) > 1:
                item_name = item_values[1]  # Name is at index 1
                refinery = item_values[3]  # Refinery is at index 3
                item_key = f"{item_name}|{refinery}"
                if item_key in self.expanded_rows:
                    expanded_items.add(item_key)

        # Clear all existing items to ensure proper ordering
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Clear the data map
        self.row_data_map.clear()

        # Insert all items in the correct order
        for item_data in data:
            # Format crafter display - show name if single crafter, count if multiple
            crafter_count = item_data.get("Crafters", 0)
            crafter_details = item_data.get("CrafterDetails", [])

            if crafter_count == 1 and crafter_details:
                crafter_display = crafter_details[0]  # Show single crafter name
            else:
                crafter_display = f"{crafter_count}×👤" if crafter_count > 0 else "0×👤"

            # Create main row - use tree column for item name
            item_id = self.tree.insert(
                "",
                "end",
                text=item_data["Name"],
                values=(
                    item_data["Tier"],
                    "",  # Name column now empty since it's in the tree column
                    item_data["Quantity"],
                    item_data["Refinery"],
                    crafter_display,
                    item_data["Tag"],
                ),
            )

            # Check if item should be expandable (multiple crafters or multiple refineries)
            has_multiple_crafters = crafter_count > 1
            has_multiple_refineries = len(item_data.get("refineries", [])) > 1

            # If item has multiple crafters or refineries, make it expandable by adding child rows immediately
            if has_multiple_crafters or has_multiple_refineries:
                # Add child rows immediately so they're visible
                if has_multiple_crafters:
                    # Show breakdown by crafter
                    for crafter in crafter_details:
                        detail_id = self.tree.insert(
                            item_id,
                            "end",
                            text="",
                            values=(
                                "",  # Empty tier for detail rows
                                "",  # Empty name column since it's in the tree column
                                "",  # Quantity (we'd need to calculate per crafter)
                                "",  # Empty refinery for detail rows
                                crafter,  # Crafter name
                                "",  # Empty tag for detail rows
                            ),
                            tags=("child",),
                        )
                        # Store reference to indicate this is a detail row
                        self.row_data_map[detail_id] = {
                            "is_detail": True,
                            "parent_data": item_data,
                        }
                elif has_multiple_refineries:
                    # Show breakdown by refinery
                    refineries = list(item_data.get("refineries", []))
                    refinery_quantities = item_data.get("refinery_quantities", {})
                    for refinery in refineries:
                        refinery_quantity = refinery_quantities.get(refinery, 0)
                        detail_id = self.tree.insert(
                            item_id,
                            "end",
                            text="",
                            values=(
                                "",  # Empty tier for detail rows
                                "",  # Empty name column since it's in the tree column
                                refinery_quantity,  # Quantity for this refinery
                                refinery,  # Refinery name
                                crafter_display,  # Show the crafter
                                "",  # Empty tag for detail rows
                            ),
                            tags=("child",),
                        )
                        # Store reference to indicate this is a detail row
                        self.row_data_map[detail_id] = {
                            "is_detail": True,
                            "parent_data": item_data,
                        }

                # Store the data for this row
                self.row_data_map[item_id] = item_data.copy()
            else:
                # Store the data for this row
                self.row_data_map[item_id] = item_data

            # If this row was expanded before, expand it again
            item_name = item_data["Name"]
            refinery = item_data["Refinery"]
            item_key = f"{item_name}|{refinery}"
            if item_key in expanded_items:
                self.expanded_rows.add(item_key)
                self._expand_row(item_id, item_data)

        logging.debug(f"Updated Treeview with {len(data)} items in sorted order.")

    def _update_item_count(self):
        """
        Update only the item count in the status bar without changing the timestamp.
        """
        # Count only parent rows (not detail rows that are children)
        visible_items = 0
        for item_id in self.tree.get_children():
            if not self.tree.parent(item_id):  # Only count top-level items
                visible_items += 1

        total_items = len(self.current_crafting_data)

        if visible_items == total_items:
            self.item_count_label.configure(text=f"Operations: {total_items}")
        else:
            self.item_count_label.configure(text=f"Operations: {visible_items} of {total_items}")

    def update_last_updated_time(self, schedule_refresh=True):
        """
        Update the status bar with last update time and item count.

        Args:
            schedule_refresh (bool): Whether to schedule the next refresh (default True).
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.debug(f"update_last_updated_time called, setting to: {current_time}")
        self.last_updated_label.configure(text=f"Last update: {current_time}")
        logging.info(f"Timestamp updated to: {current_time}")

        # Mark timestamp as properly initialized
        self.timestamp_initialized = True

        # Update item count as well when timestamp is updated
        self._update_item_count()

        # Note: BaseOverlay handles auto-refresh scheduling

    def _set_timestamp_from_fetch_time(self, fetch_time):
        """
        Set timestamp display from a cached fetch time.

        Args:
            fetch_time: The fetch time as a timestamp, datetime, or string.
        """
        if isinstance(fetch_time, (int, float)):
            time_str = datetime.fromtimestamp(fetch_time).strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(fetch_time, datetime):
            time_str = fetch_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(fetch_time)
        logging.debug(f"_set_timestamp_from_fetch_time called with: {fetch_time}, formatted as: {time_str}")
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
        logging.debug(f"_set_timestamp_from_fetch_time called with: {fetch_time}, formatted as: {time_str}")
        self.last_updated_label.configure(text=f"Last update: {time_str}")

        # Mark timestamp as properly initialized
        self.timestamp_initialized = True

    def _is_filter_active(self, column_name: str) -> bool:
        """
        Check if a filter is currently active for the specified column.

        Args:
            column_name (str): The column name to check.

        Returns:
            bool: True if a filter is active, False otherwise.
        """
        filter_state = self.active_filters.get(column_name, {})
        return (
            filter_state.get("selected") is not None or filter_state.get("min") is not None or filter_state.get("max") is not None
        )

    def _show_combined_menu(self, column):
        """
        Show a combined sorting and filtering menu for the specified column.

        Args:
            column (str): The column name.
        """
        import tkinter as tk

        # Create popup menu
        menu = tk.Menu(self, tearoff=0)

        # Add sorting options
        menu.add_command(label=f"Sort A to Z", command=lambda: self._sort_column_asc(column))
        menu.add_command(label=f"Sort Z to A", command=lambda: self._sort_column_desc(column))

        menu.add_separator()

        # Add filter option
        menu.add_command(
            label="Filter by values...",
            command=lambda: self._show_filter_values_menu(column),
        )

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
        """
        Sort the specified column in ascending order.

        Args:
            column (str): The column name.
        """
        logging.info(f"Sorting column '{column}' in ascending order")
        self.sort_column = column
        self.sort_direction = False
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _sort_column_desc(self, column):
        """
        Sort the specified column in descending order.

        Args:
            column (str): The column name.
        """
        logging.info(f"Sorting column '{column}' in descending order")
        self.sort_column = column
        self.sort_direction = True
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _show_filter_values_menu(self, column):
        """
        Show the filter values selection dialog for a column.

        Args:
            column (str): The column name.
        """
        # Get unique values for the column
        unique_values = sorted(
            list(
                set(
                    str(item.get(column))
                    for item in self.current_crafting_data
                    if column in item and item.get(column) is not None
                )
            )
        )

        if not unique_values:
            messagebox.showinfo("No Values", f"No values found for column '{column}'")
            return

        # Create filter dialog
        self._show_filter_dialog(column, unique_values)

    def _show_filter_dialog(self, column, unique_values):
        """
        Show a dialog for filtering by values for a specific column.

        Args:
            column (str): The column name.
            unique_values (list): List of unique values for the column.
        """
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
        title_label = ctk.CTkLabel(
            filter_window,
            text=f"Filter by {column}",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        # Create main frame for checkboxes
        main_frame = ctk.CTkScrollableFrame(filter_window)
        main_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)

        # Get currently selected values
        current_filter = self.active_filters.get(column, {})
        currently_selected = current_filter.get("selected", set(unique_values))  # Default to all selected
        if currently_selected is None:
            currently_selected = set(unique_values)

        # Variables to track checkbox states
        checkbox_vars = {}

        # Select All checkbox
        select_all_var = tk.BooleanVar(value=len(currently_selected) == len(unique_values))
        select_all_checkbox = ctk.CTkCheckBox(
            main_frame,
            text="Select All",
            variable=select_all_var,
            command=lambda: self._toggle_select_all(checkbox_vars, select_all_var),
        )
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

            checkbox = ctk.CTkCheckBox(
                main_frame,
                text=display_value,
                variable=var,
                command=lambda: self._update_select_all_state(checkbox_vars, select_all_var),
            )
            checkbox.grid(row=i + 2, column=0, padx=10, pady=2, sticky="w")

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
                self.active_filters[column]["selected"] = None
            else:
                self.active_filters[column]["selected"] = selected_values

            self._update_treeview_headers()
            self.apply_filters_and_sort()
            filter_window.destroy()

        def clear_filter():
            self.active_filters[column]["selected"] = None
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
        """
        Toggle all checkboxes when Select All is clicked in the filter dialog.

        Args:
            checkbox_vars (dict): Checkbox variable mapping.
            select_all_var (tk.BooleanVar): The Select All variable.
        """
        select_all = select_all_var.get()
        for var in checkbox_vars.values():
            var.set(select_all)

    def _update_select_all_state(self, checkbox_vars, select_all_var):
        """
        Update the Select All checkbox state based on individual checkboxes.

        Args:
            checkbox_vars (dict): Checkbox variable mapping.
            select_all_var (tk.BooleanVar): The Select All variable.
        """
        all_selected = all(var.get() for var in checkbox_vars.values())
        none_selected = not any(var.get() for var in checkbox_vars.values())

        if all_selected:
            select_all_var.set(True)
        elif none_selected:
            select_all_var.set(False)
        # If some but not all are selected, leave Select All as is

    def _clear_column_filter(self, column):
        """
        Clear the filter for a specific column.

        Args:
            column (str): The column name.
        """
        self.active_filters[column] = {"selected": None, "min": None, "max": None}
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _save_to_file(self):
        """
        Save the current passive crafting data to a file (CSV, JSON, or text).
        """
        if not self.current_crafting_data:
            messagebox.showwarning("No Data", "No passive crafting data to save.")
            return

        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        claim_name = getattr(self.claim_instance, "claim_name", "Unknown_Claim").replace(" ", "_")
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
                ("All files", "*.*"),
            ],
        )

        if not file_path:
            return  # User cancelled

        try:
            file_extension = os.path.splitext(file_path.lower())[1]

            if file_extension == ".csv":
                self._save_as_csv(file_path)
            elif file_extension == ".json":
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
        """
        Save passive crafting data as a CSV file.

        Args:
            file_path (str): The file path to save to.
        """
        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["Tier", "Name", "Quantity", "Refinery", "Tag"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header
            writer.writeheader()

            # Write data
            for item in self.current_crafting_data:
                writer.writerow(
                    {
                        "Tier": item.get("Tier", 0),
                        "Name": item.get("Name", ""),
                        "Quantity": item.get("Quantity", 0),
                        "Refinery": item.get("Refinery", ""),
                        "Tag": item.get("Tag", ""),
                    }
                )

    def _save_as_json(self, file_path: str):
        """
        Save passive crafting data as a JSON file.

        Args:
            file_path (str): The file path to save to.
        """
        # Create metadata
        save_data = {
            "metadata": {
                "claim_name": getattr(self.claim_instance, "claim_name", "Unknown"),
                "player_name": getattr(self.bitcraft_client, "player_name", "Unknown"),
                "region": getattr(self.bitcraft_client, "region", "Unknown"),
                "export_timestamp": datetime.now().isoformat(),
                "total_operations": len(self.current_crafting_data),
            },
            "passive_crafting": self.current_crafting_data,
        }

        with open(file_path, "w", encoding="utf-8") as jsonfile:
            json.dump(save_data, jsonfile, indent=2, ensure_ascii=False)

    def _save_as_text(self, file_path: str):
        """
        Save passive crafting data as a formatted text file.

        Args:
            file_path (str): The file path to save to.
        """
        with open(file_path, "w", encoding="utf-8") as textfile:
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
                tier = str(item.get("Tier", 0))
                name = str(item.get("Name", ""))[:24]  # Truncate if too long
                quantity = str(item.get("Quantity", 0))
                refinery = str(item.get("Refinery", ""))[:29]  # Truncate if too long
                tag = str(item.get("Tag", ""))[:19]  # Truncate if too long

                textfile.write(f"{tier:<6} {name:<25} {quantity:<5} {refinery:<30} {tag:<20}\n")

    def _on_hover(self, event):
        """
        Handle hover events for tooltips in the crafters column.

        Args:
            event: The triggering event.
        """
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        if item and column == "#5":  # Crafters column (5th column, 0-indexed)
            if self.tooltip_item != item:
                self._hide_tooltip()
                self._show_tooltip(event, item)
                self.tooltip_item = item
        else:
            self._hide_tooltip()
            self.tooltip_item = None

    def _on_leave(self, event):
        """
        Handle leave events for tooltips.

        Args:
            event: The triggering event.
        """
        self._hide_tooltip()
        self.tooltip_item = None

    def _show_tooltip(self, event, item):
        """
        Show tooltip with crafter information for the given item.

        Args:
            event: The triggering event.
            item: The treeview item ID.
        """
        # Get the item data
        item_values = self.tree.item(item, "values")
        if not item_values or len(item_values) < 6:
            return

        item_name = item_values[1]  # Name column

        # Find the corresponding data item
        data_item = None
        for data in self.current_crafting_data:
            if data.get("Name") == item_name:
                data_item = data
                break

        if not data_item:
            return

        # Get crafter details
        crafter_details = data_item.get("CrafterDetails", [])
        if not crafter_details:
            return

        # Create tooltip content
        tooltip_text = f"Crafters for {item_name}:\n"
        for crafter in crafter_details:
            tooltip_text += f"• {crafter}\n"

        # Create tooltip window
        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.configure(bg="lightyellow")

        # Position tooltip
        x = event.x_root + 10
        y = event.y_root + 10
        self.tooltip_window.geometry(f"+{x}+{y}")

        # Add tooltip text
        label = tk.Label(
            self.tooltip_window,
            text=tooltip_text,
            justify="left",
            bg="lightyellow",
            fg="black",
            font=("Arial", 9),
            padx=5,
            pady=3,
        )
        label.pack()

    def _hide_tooltip(self):
        """
        Hide the tooltip window if it exists.
        """
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _show_context_menu(self, event):
        """
        Show right-click context menu for item wiki links and crafter details.

        Args:
            event: The triggering event.
        """
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
        context_menu.add_command(label="View Crafters", command=lambda: self._show_crafters_detail(item_name))
        context_menu.add_command(label="Go to Wiki", command=lambda: self._open_wiki_page(item_name))

        # Show menu at click position
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _open_wiki_page(self, item_name):
        """
        Open the BitCraft wiki page for the specified item.

        Args:
            item_name (str): The item name to open in the wiki.
        """
        # Replace spaces with underscores for wiki URL format
        wiki_name = item_name.replace(" ", "_")
        wiki_url = f"https://bitcraft.wiki.gg/wiki/{wiki_name}"

        try:
            webbrowser.open(wiki_url)
            logging.info(f"Opened wiki page for item: {item_name}")
        except Exception as e:
            logging.error(f"Failed to open wiki page for {item_name}: {e}")
            messagebox.showerror("Error", f"Failed to open wiki page for {item_name}")

    def _show_crafters_detail(self, item_name):
        """
        Show detailed crafter information in a popup window for the given item.

        Args:
            item_name (str): The item name to show crafters for.
        """
        # Find the corresponding data item
        data_item = None
        for data in self.current_crafting_data:
            if data.get("Name") == item_name:
                data_item = data
                break

        if not data_item:
            messagebox.showwarning("No Data", f"No crafter data found for {item_name}")
            return

        # Get crafter details
        crafter_details = data_item.get("CrafterDetails", [])
        if not crafter_details:
            messagebox.showinfo("No Crafters", f"No crafters found for {item_name}")
            return

        # Create detail window
        detail_window = ctk.CTkToplevel(self)
        detail_window.title(f"Crafters for {item_name}")
        detail_window.geometry("400x300")
        detail_window.transient(self)
        detail_window.grab_set()
        detail_window.attributes("-topmost", True)

        # Position relative to main window
        x = self.winfo_x() + 50
        y = self.winfo_y() + 50
        detail_window.geometry(f"400x300+{x}+{y}")

        # Configure grid
        detail_window.grid_columnconfigure(0, weight=1)
        detail_window.grid_rowconfigure(1, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            detail_window,
            text=f"Crafters for {item_name}",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Scrollable frame for crafters
        scroll_frame = ctk.CTkScrollableFrame(detail_window)
        scroll_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
        scroll_frame.grid_columnconfigure(0, weight=1)

        # Add crafter information
        for i, crafter in enumerate(crafter_details):
            crafter_label = ctk.CTkLabel(scroll_frame, text=f"👤 {crafter}", font=ctk.CTkFont(size=12))
            crafter_label.grid(row=i, column=0, padx=10, pady=5, sticky="w")

        # Close button
        close_button = ctk.CTkButton(detail_window, text="Close", command=detail_window.destroy)
        close_button.grid(row=2, column=0, padx=20, pady=(0, 20))

    def _on_double_click(self, event):
        """
        Handle double-click on treeview items to expand or collapse rows.

        Args:
            event: The triggering event.
        """
        item_id = self.tree.selection()[0] if self.tree.selection() else None
        if not item_id:
            return

        # Check if this is already a detail row (child row)
        parent = self.tree.parent(item_id)
        if parent:
            # This is a detail row, don't expand it
            return

        # Get the item data
        item_data = self.row_data_map.get(item_id)
        if not item_data:
            return

        item_name = item_data["Name"]
        refinery = item_data["Refinery"]
        crafter_details = item_data.get("CrafterDetails", [])

        # Check if item should be expandable (multiple crafters or multiple refineries)
        has_multiple_crafters = len(crafter_details) > 1
        has_multiple_refineries = len(item_data.get("refineries", set())) > 1

        # Only expand if there are multiple crafters or refineries
        if not (has_multiple_crafters or has_multiple_refineries):
            return

        # Use combination of name and refinery as key
        item_key = f"{item_name}|{refinery}"

        # Toggle expansion state
        if item_key in self.expanded_rows:
            self._collapse_row(item_id, item_key)
        else:
            self._expand_row(item_id, item_data)

    def _expand_row(self, item_id, item_data):
        """
        Expand a row to show crafter or refinery details.

        Args:
            item_id: The treeview item ID.
            item_data: The data for the item.
        """
        item_name = item_data["Name"]
        refinery = item_data["Refinery"]

        # Create key for this specific item/refinery combination
        item_key = f"{item_name}|{refinery}"

        # Add to expanded set
        self.expanded_rows.add(item_key)

        # Expand the tree item to show children (children are already populated)
        self.tree.item(item_id, open=True)

    def _collapse_row(self, item_id, item_key):
        """
        Collapse a row to hide crafter or refinery details.

        Args:
            item_id: The treeview item ID.
            item_key: The key for the item (name|refinery).
        """
        # Remove from expanded set
        self.expanded_rows.discard(item_key)

        # Simply collapse the tree item (children remain but are hidden)
        self.tree.item(item_id, open=False)

    def on_closing(self):
        """
        Handle window closing event and perform cleanup for this overlay.
        """
        # Handle the specific cleanup for this window
        if hasattr(self.master, "toggle_passive_crafting"):
            self.master.toggle_passive_crafting.deselect()  # Deselect toggle in main window
        if hasattr(self.master, "grab_release"):
            self.master.grab_release()
        # Call parent's on_closing for base cleanup (refresh job cancellation)
        super().on_closing()
