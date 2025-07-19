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


class FilterDialog(ctk.CTkToplevel):
    """Dialog window for filtering inventory columns by value or range.

    Allows users to select specific values or numeric ranges for filtering
    inventory data in the treeview. Supports select all, clear all, and range filtering.
    """

    def __init__(
        self,
        master,
        column_name: str,
        unique_values: list,
        current_filter: dict,
        is_numeric: bool = False,
    ):
        super().__init__(master)
        self.master = master
        self.column_name = column_name
        self.unique_values = sorted([str(val) for val in unique_values])
        self.is_numeric = is_numeric
        self.current_filter = current_filter

        self.title(f"Filter by {column_name}")
        self.transient(master)
        self.grab_set()
        self.attributes("-topmost", True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        options_frame = ctk.CTkFrame(self)
        options_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        options_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(options_frame, text="Select values:").grid(row=0, column=0, padx=5, pady=5, sticky="w")

        initial_select_all = self.current_filter["selected"] is None or (
            isinstance(self.current_filter["selected"], set) and len(self.current_filter["selected"]) == len(self.unique_values)
        )

        self.all_selected_var = ctk.BooleanVar(value=initial_select_all)
        self.all_selected_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="Select All",
            variable=self.all_selected_var,
            command=self._toggle_select_all,
        )
        self.all_selected_checkbox.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.checkbox_vars = {}
        for i, value in enumerate(self.unique_values):
            initial_checkbox_state = self.current_filter["selected"] is None or (
                isinstance(self.current_filter["selected"], set) and value in self.current_filter["selected"]
            )
            var = ctk.BooleanVar(value=initial_checkbox_state)
            checkbox = ctk.CTkCheckBox(self.scroll_frame, text=str(value), variable=var)
            checkbox.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            self.checkbox_vars[value] = var

        self._update_select_all_checkbox()

        if self.is_numeric:
            self.range_frame = ctk.CTkFrame(self)
            self.range_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
            self.range_frame.grid_columnconfigure((0, 1), weight=1)

            ctk.CTkLabel(self.range_frame, text="Min:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.min_entry = ctk.CTkEntry(self.range_frame, placeholder_text="Min")
            self.min_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
            if self.current_filter["min"] is not None:
                self.min_entry.insert(0, str(self.current_filter["min"]))

            ctk.CTkLabel(self.range_frame, text="Max:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            self.max_entry = ctk.CTkEntry(self.range_frame, placeholder_text="Max")
            self.max_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
            if self.current_filter["max"] is not None:
                self.max_entry.insert(0, str(self.current_filter["max"]))

        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=3 if self.is_numeric else 2, column=0, padx=10, pady=10, sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

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
        """Apply the selected filter values and/or range to the parent window."""
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

        new_filter_state = {"selected": selected_values, "min": min_val, "max": max_val}
        self.master.update_filter(self.column_name, new_filter_state)
        self.destroy()

    def clear_filter(self):
        """Clear all filter selections and reset to default (all selected)."""
        if self.is_numeric:
            self.min_entry.delete(0, ctk.END)
            self.max_entry.delete(0, ctk.END)
        self.all_selected_var.set(True)
        self._toggle_select_all()
        self.apply_filter()

    def on_closing(self):
        """Handle closing of the filter dialog and release grab from parent."""
        self.master.grab_release()
        self.destroy()


class ClaimInventoryWindow(BaseOverlay):
    """Overlay window for displaying and managing claim inventory data.

    Provides advanced filtering, sorting, searching, and export features for
    BitCraft claim inventory. Supports expandable rows for container details
    and integrates with the main application for live data refresh.
    """

    def __init__(
        self,
        master,
        bitcraft_client: BitCraft,
        claim_instance: Claim,
        initial_display_data: list,
        last_fetch_time=None,
    ):
        logging.debug("ClaimInventoryWindow constructor called")
        logging.debug(f"Constructor - last_fetch_time parameter: {last_fetch_time}")

        # Initialize attributes that are needed in setup_content_ui BEFORE calling super().__init__
        self.bitcraft_client = bitcraft_client
        self.claim_instance = claim_instance
        self.current_inventory_data = initial_display_data
        self.active_filters = {
            "Tier": {"selected": None, "min": None, "max": None},
            "Name": {"selected": None, "min": None, "max": None},
            "Quantity": {"selected": None, "min": None, "max": None},
            "Containers": {"selected": None, "min": None, "max": None},
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
            min_width=720,
            min_height=500,
            initial_width=800,
            initial_height=600,
        )

        # Set custom title text
        self.set_title_text("Claim Inventory")

        # Override auto-refresh settings for inventory
        self.refresh_interval = 300  # 5 minutes for inventory

        logging.debug(f"ClaimInventoryWindow constructor finished - instance id: {id(self)}")
        logging.debug(f"Constructor - timestamp_initialized: {self.timestamp_initialized}")
        logging.debug(
            f"Constructor - current timestamp text: {getattr(self, 'last_updated_label', None) and self.last_updated_label.cget('text')}"
        )

    def setup_content_ui(self):
        """Setup the main content area of the overlay.

        Initializes search bar, treeview, scrollbars, and binds all UI events.
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

        # Create treeview frame using base class method (at row 2)
        self.tree_frame = self.create_treeview_frame(row=2)

        # Setup treeview styling
        self.setup_treeview_styling()

        # Create treeview
        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=("Tier", "Name", "Quantity", "Containers", "Tag"),
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
        """Handle save button click and delegate to file save functionality."""
        self._save_to_file()

    def setup_status_bar_content(self):
        """Setup additional content in the status bar (e.g., item count label)."""
        # Add item count label to status bar
        self.item_count_label = ctk.CTkLabel(self.status_frame, text="Items: 0", font=ctk.CTkFont(size=11))
        self.item_count_label.grid(row=0, column=2, padx=10, pady=5, sticky="e")

    def refresh_data(self):
        """Refresh the data displayed in the overlay by triggering a re-fetch."""
        self._refresh_data()

    def create_widgets(self):
        """Legacy method, replaced by setup_content_ui (kept for compatibility)."""
        pass

    def _update_treeview_headers(self):
        """Update the treeview column headers with sort and filter indicators."""
        arrow_up = " ↑"
        arrow_down = " ↓"
        columns = ["Tier", "Name", "Quantity", "Containers", "Tag"]

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
        self.tree.column("Containers", width=120, anchor="w")  # Left-aligned for better readability
        self.tree.column("Tag", width=300, anchor="w")

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

    def _open_filter_dialog(self, column_name: str, is_numeric: bool = False):
        """Open a filter dialog for the specified column."""
        if column_name == "Tag":
            all_tags = set()
            for item in self.current_inventory_data:
                tag = item.get("Tag")
                if tag:
                    all_tags.add(tag)
            unique_values = sorted(list(all_tags))
        elif column_name == "Containers":
            # For containers, show the number of containers as unique values
            container_counts = set()
            for item in self.current_inventory_data:
                containers = item.get("containers", {})
                container_counts.add(str(len(containers)))
            unique_values = sorted(list(container_counts), key=int)
        else:
            unique_values = sorted(
                list(
                    set(
                        str(item.get(column_name))
                        for item in self.current_inventory_data
                        if column_name in item and item.get(column_name) is not None
                    )
                )
            )

        current_filter_state = self.active_filters.get(column_name, {"selected": None, "min": None, "max": None})

        dialog = FilterDialog(self, column_name, unique_values, current_filter_state, is_numeric)

    def update_filter(self, column_name: str, new_filter_state: dict):
        """Callback from FilterDialog to update filter settings for a column."""
        self.active_filters[column_name] = new_filter_state
        logging.info(f"Filter for {column_name} updated: {new_filter_state}")
        self.apply_filters_and_sort()

    def _on_search_change(self, event=None):
        """Handle search entry text changes and update filtering."""
        self.search_term = self.search_entry.get().lower().strip()
        logging.info(f"Search term changed to: '{self.search_term}'")
        self.apply_filters_and_sort()

    def _clear_search(self):
        """Clear the search entry and reset search filtering."""
        self.search_entry.delete(0, "end")
        self.search_term = ""
        logging.info("Search cleared")
        self.apply_filters_and_sort()

    def _refresh_data(self):
        """Trigger a re-fetch and re-display of inventory data, bypassing cache."""
        if hasattr(self.master, "status_label"):
            self.master.status_label.configure(text="Refreshing claim inventory data...", text_color="yellow")

        # Force a fresh fetch bypassing the cache
        if hasattr(self.master, "force_inventory_refresh"):
            self.master.force_inventory_refresh()
        elif hasattr(self.master, "_force_inventory_refresh"):
            self.master._force_inventory_refresh()

    def apply_filters_and_sort(self, *args):
        """Apply filters and sorting to the inventory data and update the treeview."""
        logging.debug(f"apply_filters_and_sort called - timestamp before: {self.last_updated_label.cget('text')}")
        filtered_data = list(self.current_inventory_data)

        # Apply search filtering first
        if self.search_term:
            filtered_data = [
                item
                for item in filtered_data
                if self.search_term in str(item.get("Name", "")).lower() or self.search_term in str(item.get("Tag", "")).lower()
            ]

        for col_name, filter_state in self.active_filters.items():
            selected_values = filter_state.get("selected")
            min_val = filter_state.get("min")
            max_val = filter_state.get("max")

            if selected_values is not None:
                if col_name == "Containers":
                    # For containers, filter by number of containers
                    filtered_data = [item for item in filtered_data if str(len(item.get("containers", {}))) in selected_values]
                else:
                    filtered_data = [item for item in filtered_data if str(item.get(col_name, "")) in selected_values]

            if (min_val is not None) or (max_val is not None):
                if col_name in ["Tier", "Quantity"]:
                    filtered_data = [
                        item
                        for item in filtered_data
                        if self._can_convert_to_float(item.get(col_name))
                        and (min_val is None or float(item.get(col_name)) >= min_val)
                        and (max_val is None or float(item.get(col_name)) <= max_val)
                    ]
                elif col_name == "Containers":
                    # For containers, filter by number of containers
                    filtered_data = [
                        item
                        for item in filtered_data
                        if (min_val is None or len(item.get("containers", {})) >= min_val)
                        and (max_val is None or len(item.get("containers", {})) <= max_val)
                    ]

        sort_by = self.sort_column

        if sort_by in ["Tier", "Name", "Quantity", "Containers", "Tag"]:
            logging.debug(
                f"Sorting data by '{sort_by}', direction: {'DESC' if self.sort_direction else 'ASC'}, data length: {len(filtered_data)}"
            )
            if sort_by in ["Tier", "Quantity"]:
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
            elif sort_by == "Containers":
                # Sort by number of containers
                def containers_sort_key(x):
                    containers = x.get("containers", {})
                    return len(containers) if containers else 0

                filtered_data.sort(key=containers_sort_key, reverse=self.sort_direction)
            elif sort_by == "Tag":
                filtered_data.sort(key=lambda x: x.get("Tag", "").lower(), reverse=self.sort_direction)
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
        """Check if a value can be safely converted to float."""
        if value is None:
            return False
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def update_treeview(self, data):
        """Update the Treeview with new data, rebuilding for correct order.

        Args:
            data: List of inventory items to display in the treeview
        """
        # Remember which rows were expanded
        expanded_items = set()
        for item_id in self.tree.get_children():
            item_name = self.tree.item(item_id)["values"][1]  # Name is at index 1
            if item_name in self.expanded_rows:
                expanded_items.add(item_name)

        # Clear all existing items to ensure proper ordering
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Clear the data map
        self.row_data_map.clear()

        # Insert all items in the correct order
        for item_data in data:
            # Format container display - show name if single container, count if multiple
            containers_data = item_data.get("containers", {})
            container_count = len(containers_data)

            if container_count == 1:
                container_display = list(containers_data.keys())[0]  # Show single container name
            else:
                container_display = f"{container_count}×📦" if container_count > 0 else "0×📦"

            # Create main row - use tree column for item name
            item_id = self.tree.insert(
                "",
                "end",
                text=item_data["Name"],
                values=(
                    item_data["Tier"],
                    "",  # Name column now empty since it's in the tree column
                    item_data["Quantity"],
                    container_display,
                    item_data["Tag"],
                ),
            )

            # If item has multiple containers, make it expandable by adding child rows immediately
            if container_count > 1:
                # Add child rows immediately so they're visible
                for container_name, quantity in containers_data.items():
                    detail_id = self.tree.insert(
                        item_id,
                        "end",
                        text="",
                        values=(
                            "",  # Empty tier for detail rows
                            "",  # Empty name column since it's in the tree column
                            quantity,  # Quantity in this container
                            container_name,  # Container name in container column
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
            if item_name in expanded_items:
                self.expanded_rows.add(item_name)
                self._expand_row(item_id, item_data)

        logging.debug(f"Updated Treeview with {len(data)} items in sorted order.")

    def _update_item_count(self):
        """Update only the item count in the status bar without changing the timestamp."""
        # Count only parent rows (not detail rows that are children)
        visible_items = 0
        for item_id in self.tree.get_children():
            if not self.tree.parent(item_id):  # Only count top-level items
                visible_items += 1

        total_items = len(self.current_inventory_data)

        if visible_items == total_items:
            self.item_count_label.configure(text=f"Items: {total_items}")
        else:
            self.item_count_label.configure(text=f"Items: {visible_items} of {total_items}")

    def update_last_updated_time(self, schedule_refresh=True):
        """Update the status bar with last update time and item count."""
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
        """Set timestamp display from a cached fetch time value."""
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

    def sort_treeview_column(self, col):
        """Handle sorting when a column header is clicked and update indicators."""
        logging.debug(f"sort_treeview_column called for column: {col}")
        logging.debug(f"Before sort - timestamp label text: {self.last_updated_label.cget('text')}")
        # Always toggle direction if clicking the same column, else set to ascending
        if self.sort_column == col:
            self.sort_direction = not self.sort_direction
        else:
            self.sort_column = col
            self.sort_direction = False
        self._update_treeview_headers()
        self.apply_filters_and_sort()
        logging.debug(f"After sort - timestamp label text: {self.last_updated_label.cget('text')}")

    def on_closing(self):
        """Handle window closing event and perform cleanup."""
        # Handle the specific cleanup for this window
        if hasattr(self.master, "toggle_claim_inventory"):
            self.master.toggle_claim_inventory.deselect()  # Deselect toggle in main window
        if hasattr(self.master, "grab_release"):
            self.master.grab_release()
        # Call parent's on_closing for base cleanup (refresh job cancellation)
        super().on_closing()

    def _save_to_file(self):
        """Save the current inventory data to a file (CSV, JSON, or text)."""
        if not self.current_inventory_data:
            messagebox.showwarning("No Data", "No inventory data to save.")
            return

        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        claim_name = getattr(self.claim_instance, "claim_name", "Unknown_Claim").replace(" ", "_")
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

            messagebox.showinfo("Success", f"Inventory data saved to:\n{file_path}")
            logging.info(f"Inventory data saved to: {file_path}")

        except Exception as e:
            error_msg = f"Failed to save file: {str(e)}"
            messagebox.showerror("Save Error", error_msg)
            logging.error(f"Error saving inventory data: {e}")

    def _save_as_csv(self, file_path: str):
        """Save inventory data as a CSV file.

        Args:
            file_path: Path to save the CSV file
        """
        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["Tier", "Name", "Quantity", "Tag"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header
            writer.writeheader()

            # Write data
            for item in self.current_inventory_data:
                writer.writerow(
                    {
                        "Name": item.get("Name", ""),
                        "Quantity": item.get("Quantity", 0),
                        "Tier": item.get("Tier", 0),
                        "Tag": item.get("Tag", ""),
                    }
                )

    def _save_as_json(self, file_path: str):
        """Save inventory data as a JSON file.

        Args:
            file_path: Path to save the JSON file
        """
        # Create metadata
        save_data = {
            "metadata": {
                "claim_name": getattr(self.claim_instance, "claim_name", "Unknown"),
                "player_name": getattr(self.bitcraft_client, "player_name", "Unknown"),
                "region": getattr(self.bitcraft_client, "region", "Unknown"),
                "export_timestamp": datetime.now().isoformat(),
                "total_items": len(self.current_inventory_data),
            },
            "inventory": self.current_inventory_data,
        }

        with open(file_path, "w", encoding="utf-8") as jsonfile:
            json.dump(save_data, jsonfile, indent=2, ensure_ascii=False)

    def _save_as_text(self, file_path: str):
        """Save inventory data as a formatted text file.

        Args:
            file_path: Path to save the text file
        """
        with open(file_path, "w", encoding="utf-8") as textfile:
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
                tier = str(item.get("Tier", 0))
                name = str(item.get("Name", ""))[:29]  # Truncate if too long
                quantity = str(item.get("Quantity", 0))
                tag = str(item.get("Tag", ""))[:19]  # Truncate if too long

                textfile.write(f"{tier:<6} {name:<30} {quantity:<10} {tag:<20}\n")

    def _is_filter_active(self, column_name: str) -> bool:
        """Check if a filter is currently active for the specified column.

        Args:
            column_name: Name of the column to check filter status for
        Returns:
            bool: True if filter is active, False otherwise
        """
        filter_state = self.active_filters.get(column_name, {})
        return (
            filter_state.get("selected") is not None or filter_state.get("min") is not None or filter_state.get("max") is not None
        )

    def _show_combined_menu(self, column):
        """Show a combined sorting and filtering menu like Google Sheets."""
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
        """Sort the specified column in ascending order."""
        logging.info(f"Sorting column '{column}' in ascending order")
        logging.debug(f"_sort_column_asc called on instance {id(self)}")
        logging.debug(f"_sort_column_asc - timestamp_initialized: {self.timestamp_initialized}")
        logging.debug(f"_sort_column_asc - current timestamp: {self.last_updated_label.cget('text')}")
        self.sort_column = column
        self.sort_direction = False
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _sort_column_desc(self, column):
        """Sort the specified column in descending order."""
        logging.info(f"Sorting column '{column}' in descending order")
        logging.debug(f"_sort_column_desc called on instance {id(self)}")
        logging.debug(f"_sort_column_desc - timestamp_initialized: {self.timestamp_initialized}")
        logging.debug(f"_sort_column_desc - current timestamp: {self.last_updated_label.cget('text')}")
        self.sort_column = column
        self.sort_direction = True
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _show_filter_values_menu(self, column):
        """Show the filter values selection for a column (Google Sheets style)."""
        # Get unique values for the column
        if column == "Tag":
            all_values = set()
            for item in self.current_inventory_data:
                tag = item.get("Tag")
                if tag:
                    all_values.add(tag)
            unique_values = sorted(list(all_values))
        else:
            unique_values = sorted(
                list(
                    set(
                        str(item.get(column))
                        for item in self.current_inventory_data
                        if column in item and item.get(column) is not None
                    )
                )
            )

        # Create a new window for filter selection
        filter_window = ctk.CTkToplevel(self)
        filter_window.title(f"Filter by {column}")
        filter_window.geometry("350x500")
        filter_window.transient(self)
        filter_window.grab_set()
        filter_window.attributes("-topmost", True)

        # Position relative to main window
        x = self.winfo_x() + 50
        y = self.winfo_y() + 50
        filter_window.geometry(f"350x500+{x}+{y}")

        # Configure grid
        filter_window.grid_columnconfigure(0, weight=1)
        filter_window.grid_rowconfigure(2, weight=1)  # Make scrollable area expandable

        # Get current filter state
        current_filter = self.active_filters.get(column, {"selected": None, "min": None, "max": None})
        current_selected = current_filter.get("selected", set(unique_values))
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
                self.active_filters[column] = {
                    "selected": None,
                    "min": None,
                    "max": None,
                }
            else:
                self.active_filters[column] = {
                    "selected": selected_values,
                    "min": None,
                    "max": None,
                }

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
        title_label = ctk.CTkLabel(
            filter_window,
            text=f"Filter by {column}",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Select/Clear all buttons (outside scroll area)
        select_frame = ctk.CTkFrame(filter_window, fg_color="transparent")
        select_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        select_frame.grid_columnconfigure(0, weight=1)
        select_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            select_frame,
            text="Select All",
            command=select_all,
            height=28,
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(
            select_frame,
            text="Clear All",
            command=clear_all,
            height=28,
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=1, padx=(5, 0), sticky="ew")

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

        ctk.CTkButton(bottom_button_frame, text="Apply", command=apply_filter, width=100).grid(
            row=0, column=0, padx=(0, 5), sticky="ew"
        )
        ctk.CTkButton(
            bottom_button_frame,
            text="Cancel",
            command=cancel_filter,
            width=100,
            fg_color="gray",
        ).grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _clear_column_filter(self, column):
        """Clear the filter for a specific column."""
        self.active_filters[column] = {"selected": None, "min": None, "max": None}
        self._update_treeview_headers()
        self.apply_filters_and_sort()

    def _show_context_menu(self, event):
        """Show right-click context menu for item wiki links and container details."""
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
            label="View Containers",
            command=lambda: self._show_container_details(item_name),
        )
        context_menu.add_command(label="Go to Wiki", command=lambda: self._open_wiki_page(item_name))

        # Show menu at click position
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _open_wiki_page(self, item_name):
        """Open the BitCraft wiki page for the specified item.

        Args:
            item_name: Name of the item to open in the wiki
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

    def _on_header_click(self, event):
        """Handle clicks on treeview headers (deprecated, not used)."""
        pass

    def _on_hover(self, event):
        """Handle hover events for tooltips on the containers column."""
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        if item and column == "#4":  # Containers column (4th column, 0-indexed)
            if self.tooltip_item != item:
                self._hide_tooltip()
                self._show_tooltip(event, item)
                self.tooltip_item = item
        else:
            self._hide_tooltip()
            self.tooltip_item = None

    def _on_leave(self, event):
        """Handle leave events for tooltips and hide tooltip window."""
        self._hide_tooltip()
        self.tooltip_item = None

    def _show_tooltip(self, event, item):
        """Show tooltip with container information for the hovered item."""
        # Get the item data
        item_values = self.tree.item(item, "values")
        if not item_values or len(item_values) < 5:
            return

        item_name = item_values[1]  # Name column

        # Find the corresponding data item
        data_item = None
        for data in self.current_inventory_data:
            if data.get("Name") == item_name:
                data_item = data
                break

        if not data_item:
            return

        # Get container details
        containers_data = data_item.get("containers", {})
        if not containers_data:
            return

        # Create tooltip content
        tooltip_text = f"Containers for {item_name}:\n"
        for container_name, quantity in containers_data.items():
            tooltip_text += f"• {container_name}: {quantity}\n"

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
        """Hide the tooltip window if it exists."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _show_container_details(self, item_name):
        """Show detailed container information in a popup window.

        Args:
            item_name: Name of the item to show container details for
        """
        # Find the corresponding data item
        data_item = None
        for data in self.current_inventory_data:
            if data.get("Name") == item_name:
                data_item = data
                break

        if not data_item:
            messagebox.showwarning("No Data", f"No container data found for {item_name}")
            return

        # Get container details
        containers_data = data_item.get("containers", {})
        if not containers_data:
            messagebox.showinfo("No Containers", f"No containers found for {item_name}")
            return

        # Create detail window
        detail_window = ctk.CTkToplevel(self)
        detail_window.title(f"Container Details - {item_name}")
        detail_window.geometry("400x300")
        detail_window.transient(self)
        detail_window.grab_set()

        # Configure grid
        detail_window.grid_columnconfigure(0, weight=1)
        detail_window.grid_rowconfigure(1, weight=1)

        # Title label
        title_label = ctk.CTkLabel(
            detail_window,
            text=f"Containers for {item_name}",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # Create text widget for container list
        text_widget = ctk.CTkTextbox(detail_window)
        text_widget.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Add container information
        total_quantity = sum(containers_data.values())
        text_widget.insert("0.0", f"Total Quantity: {total_quantity}\n")
        text_widget.insert("end", f"Found in {len(containers_data)} container(s):\n\n")

        for container_name, quantity in containers_data.items():
            text_widget.insert("end", f"• {container_name}: {quantity}\n")

        text_widget.configure(state="disabled")

        # Close button
        close_button = ctk.CTkButton(detail_window, text="Close", command=detail_window.destroy)
        close_button.grid(row=2, column=0, padx=10, pady=10)

    def _on_double_click(self, event):
        """Handle double-click on treeview items to expand or collapse rows."""
        logging.debug("Double-click detected!")
        item_id = self.tree.selection()[0] if self.tree.selection() else None
        if not item_id:
            logging.debug("No item selected")
            return

        logging.debug(f"Selected item ID: {item_id}")

        # Check if this is already a detail row (child row)
        parent = self.tree.parent(item_id)
        if parent:
            logging.debug("This is a detail row, not expanding")
            return

        # Get the item data
        item_data = self.row_data_map.get(item_id)
        if not item_data:
            logging.debug("No item data found for this row")
            return

        item_name = item_data["Name"]
        containers_data = item_data.get("containers", {})

        logging.debug(f"Item name: {item_name}")
        logging.debug(f"Container count: {len(containers_data)}")
        logging.debug(f"Containers: {containers_data}")

        # Only expand if there are multiple containers
        if len(containers_data) <= 1:
            logging.debug("Not expanding - only one container or no containers")
            return

        # Toggle expansion state
        if item_name in self.expanded_rows:
            logging.debug("Collapsing row")
            self._collapse_row(item_id, item_name)
        else:
            logging.debug("Expanding row")
            self._expand_row(item_id, item_data)

    def _expand_row(self, item_id, item_data):
        """Expand a row to show container details for the item."""
        item_name = item_data["Name"]

        logging.debug(f"Expanding row for {item_name}")

        # Add to expanded set
        self.expanded_rows.add(item_name)

        # Expand the tree item to show children (children are already populated)
        self.tree.item(item_id, open=True)
        logging.debug(f"Row expanded successfully")

        # Check if children are actually visible
        children = self.tree.get_children(item_id)
        logging.debug(f"Number of children after expansion: {len(children)}")
        for i, child in enumerate(children):
            child_values = self.tree.item(child)["values"]
            logging.debug(f"Child {i+1}: {child_values}")

        # Force tree to update display
        self.tree.update_idletasks()

    def _collapse_row(self, item_id, item_name):
        """Collapse a row to hide container details for the item."""
        # Remove from expanded set
        self.expanded_rows.discard(item_name)

        # Simply collapse the tree item (children remain but are hidden)
        self.tree.item(item_id, open=False)
