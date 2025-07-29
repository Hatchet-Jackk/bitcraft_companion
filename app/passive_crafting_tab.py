import customtkinter as ctk
import logging
from tkinter import Menu, ttk
from typing import List, Dict
from filter_popup import FilterPopup


class PassiveCraftingTab(ctk.CTkFrame):
    """The tab for displaying passive crafting status with item-focused, expandable rows."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        # Updated headers - removed Status, added Crafter
        self.headers = ["Item", "Tier", "Quantity", "Recipe", "Time Remaining", "Crafter", "Building"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Item"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        self._create_widgets()
        self._create_context_menu()

    def _create_widgets(self):
        """Creates the styled Treeview and its scrollbars."""
        style = ttk.Style()
        style.theme_use("default")

        # Configure the Treeview colors
        style.configure(
            "Treeview",
            background="#2a2d2e",
            foreground="white",
            fieldbackground="#343638",
            borderwidth=0,
            rowheight=28,
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#1f6aa5")])

        # Configure headers
        style.configure(
            "Treeview.Heading",
            background="#1e2124",
            foreground="#e0e0e0",
            font=("Segoe UI", 11, "normal"),
            padding=(8, 6),
            relief="flat",
            borderwidth=0,
        )
        style.map("Treeview.Heading", background=[("active", "#2c5d8f")])

        # Style scrollbars
        style.configure(
            "Vertical.TScrollbar",
            background="#1e2124",
            borderwidth=0,
            arrowcolor="#666",
            troughcolor="#2a2d2e",
            darkcolor="#1e2124",
            lightcolor="#1e2124",
            width=12,
        )
        style.configure(
            "Horizontal.TScrollbar",
            background="#1e2124",
            borderwidth=0,
            arrowcolor="#666",
            troughcolor="#2a2d2e",
            darkcolor="#1e2124",
            lightcolor="#1e2124",
            height=12,
        )

        # Create the Treeview
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Configure tags for different status colors based on time remaining
        self.tree.tag_configure("ready", background="#2d4a2d", foreground="#4CAF50")  # Green for ready
        self.tree.tag_configure("crafting", background="#3d3d2d", foreground="#FFA726")  # Orange for crafting
        self.tree.tag_configure("empty", background="#2a2d2e", foreground="#888888")  # Gray for empty
        self.tree.tag_configure("child", background="#3a3a3a")

        # Create scrollbars
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview, style="Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.hsb = hsb
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Set up headings and column widths
        column_widths = {
            "Item": 180,
            "Tier": 60,
            "Quantity": 80,
            "Recipe": 120,
            "Time Remaining": 120,
            "Crafter": 100,
            "Building": 200,
        }

        for header in self.headers:
            self.tree.heading(header, text=header, command=lambda h=header: self.sort_by(h), anchor="w")
            self.tree.column(header, width=column_widths.get(header, 100), minwidth=50, anchor="w")

        # Configure the tree column
        self.tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.tree.heading("#0", text="", anchor="w")

        # Bind events
        self.tree.bind("<Button-3>", self.show_header_context_menu)
        self.tree.bind("<Configure>", self.on_tree_configure)

    def on_tree_configure(self, event):
        """Manages horizontal scrollbar visibility based on content width."""
        total_width = sum(self.tree.column(col, "width") for col in ["#0"] + list(self.headers))
        widget_width = self.tree.winfo_width()

        if total_width > widget_width:
            self.hsb.grid(row=1, column=0, sticky="ew")
        else:
            self.hsb.grid_remove()

    def _create_context_menu(self):
        """Creates the right-click menu for column headers."""
        self.header_context_menu = Menu(self, tearoff=0, background="#2a2d2e", foreground="white", activebackground="#1f6aa5")
        self.header_context_menu.add_command(label="Filter by...", command=lambda: self._open_filter_popup(self.clicked_header))
        self.header_context_menu.add_command(label="Clear Filter", command=lambda: self.clear_column_filter(self.clicked_header))

    def show_header_context_menu(self, event):
        """Identifies the clicked header and displays the context menu."""
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            column_id = self.tree.identify_column(event.x)
            self.clicked_header = self.tree.column(column_id, "id")
            self.header_context_menu.tk_popup(event.x_root, event.y_root)

    def _open_filter_popup(self, header):
        if not self.all_data:
            return

        # Handle special cases for filters
        if header.lower() in ["building", "crafter"]:
            unique_values = self._get_filter_data_for_expandable_column(header)
            filter_data = [{f"{header.lower()}_display": val} for val in unique_values]
            current_selection = self.active_filters.get(header, set(unique_values))
            FilterPopup(
                self, header, filter_data, current_selection, self._apply_column_filter, custom_key=f"{header.lower()}_display"
            )
        else:
            field_name = header.lower().replace(" ", "_")
            current_selection = self.active_filters.get(header, {str(row.get(field_name, "")) for row in self.all_data})
            FilterPopup(self, header, self.all_data, current_selection, self._apply_column_filter)

    def _get_filter_data_for_expandable_column(self, header):
        """Gets unique values for expandable columns (Building/Crafter) including individual operations."""
        unique_values = set()

        for row in self.all_data:
            # Add the summary value
            summary_value = row.get(header.lower(), "")
            if summary_value:
                unique_values.add(summary_value)

            # Add individual operation values
            operations = row.get("operations", [])
            for operation in operations:
                if header.lower() == "building":
                    # For building, include refinery + crafter info
                    refinery = operation.get("refinery", "")
                    crafter = operation.get("crafter", "")
                    if refinery and crafter:
                        unique_values.add(f"{refinery} (by {crafter})")
                elif header.lower() == "crafter":
                    # For crafter, just the crafter name
                    crafter = operation.get("crafter", "")
                    if crafter:
                        unique_values.add(crafter)

        return sorted(list(unique_values))

    def _apply_column_filter(self, header, selected_values):
        self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def update_data(self, new_data):
        """Receives new crafting data (already item-focused and grouped)."""
        if isinstance(new_data, list):
            self.all_data = new_data
        else:
            self.all_data = []

        self.apply_filter()
        logging.info(f"Passive crafting data updated: {len(self.all_data)} item groups")

    def apply_filter(self):
        """Filters the master data list based on search and column filters."""
        search_term = self.app.search_var.get().lower()
        temp_data = self.all_data[:]

        if self.active_filters:
            for header, values in self.active_filters.items():
                if header.lower() in ["building", "crafter"]:
                    temp_data = [row for row in temp_data if self._expandable_column_matches_filter(row, header, values)]
                else:
                    field_name = header.lower().replace(" ", "_")
                    temp_data = [row for row in temp_data if str(row.get(field_name, "")) in values]

        if search_term:
            temp_data = [row for row in temp_data if self._row_matches_search(row, search_term)]

        self.filtered_data = temp_data
        self.sort_by(self.sort_column, self.sort_reverse)

    def _expandable_column_matches_filter(self, row, header, selected_values):
        """Checks if a row matches the filter for expandable columns (Building/Crafter)."""
        # Check summary value
        summary_value = row.get(header.lower(), "")
        if summary_value in selected_values:
            return True

        # Check individual operation values
        operations = row.get("operations", [])
        for operation in operations:
            if header.lower() == "building":
                # For building, check refinery + crafter combination
                refinery = operation.get("refinery", "")
                crafter = operation.get("crafter", "")
                if refinery and crafter:
                    display_name = f"{refinery} (by {crafter})"
                    if display_name in selected_values:
                        return True
            elif header.lower() == "crafter":
                # For crafter, just check crafter name
                crafter = operation.get("crafter", "")
                if crafter in selected_values:
                    return True

        return False

    def _row_matches_search(self, row, search_term):
        """Checks if a row matches the search term, including operation data."""
        # Check main row data
        main_fields = ["item", "recipe", "time_remaining", "crafter", "building"]
        for field in main_fields:
            if search_term in str(row.get(field, "")).lower():
                return True

        # Check individual operation data
        operations = row.get("operations", [])
        for operation in operations:
            operation_fields = ["item_name", "recipe", "time_remaining", "crafter", "refinery"]
            for field in operation_fields:
                if search_term in str(operation.get(field, "")).lower():
                    return True

        return False

    def sort_by(self, header, reverse=None):
        """Sorts the filtered data and re-renders the table."""
        if self.sort_column == header and reverse is None:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = header
            self.sort_reverse = reverse if reverse is not None else False

        sort_key = self.sort_column.lower().replace(" ", "_")

        # Special sorting for time remaining - convert to seconds for proper numerical sorting
        if sort_key == "time_remaining":

            def time_sort_key(x):
                time_str = str(x.get(sort_key, ""))
                if time_str == "READY":
                    return 0
                elif time_str in ["Empty", "Error", "N/A", "Unknown"]:
                    return 999999
                else:
                    return self._time_to_seconds(time_str)

            self.filtered_data.sort(key=time_sort_key, reverse=self.sort_reverse)
        elif sort_key in ["tier", "quantity"]:
            # Numeric sorting
            self.filtered_data.sort(
                key=lambda x: float(x.get(sort_key, 0)),
                reverse=self.sort_reverse,
            )
        else:
            # String sorting
            self.filtered_data.sort(
                key=lambda x: str(x.get(sort_key, "")).lower(),
                reverse=self.sort_reverse,
            )

        self.render_table()
        self.update_header_sort_indicators()

    def _time_to_seconds(self, time_str):
        """Convert time string like '2h 30m 15s' to total seconds."""
        if not time_str or time_str in ["READY", "Empty", "Error", "N/A", "Unknown"]:
            return 0 if time_str == "READY" else 999999

        total_seconds = 0
        try:
            # Remove ~ prefix if present
            time_str = time_str.replace("~", "")

            # Parse formats like "2h 30m 15s", "30m 15s", "15s"
            parts = time_str.split()
            for part in parts:
                if "h" in part:
                    total_seconds += int(part.replace("h", "")) * 3600
                elif "m" in part:
                    total_seconds += int(part.replace("m", "")) * 60
                elif "s" in part:
                    total_seconds += int(part.replace("s", ""))
        except:
            return 999999  # Put parsing errors at the end

        return total_seconds

    def update_header_sort_indicators(self):
        """Updates the arrows on column headers."""
        for header in self.headers:
            text = header
            if self.sort_column == header:
                text += " ↓" if not self.sort_reverse else " ↑"
            filter_indicator = " 🔎" if header in self.active_filters else ""
            self.tree.heading(header, text=text + filter_indicator)

    def render_table(self):
        """Clears and re-populates the Treeview with item-based parent/operation child structure."""
        self.tree.delete(*self.tree.get_children())

        for row_data in self.filtered_data:
            item_name = row_data.get("item", "Unknown Item")
            tier = row_data.get("tier", 0)
            quantity = row_data.get("quantity", 0)
            recipe = row_data.get("recipe", "Unknown Recipe")
            time_remaining = row_data.get("time_remaining", "Unknown")
            crafter = row_data.get("crafter", "Unknown")
            building = row_data.get("building", "Unknown")
            operations = row_data.get("operations", [])
            is_expandable = row_data.get("is_expandable", False)

            # Prepare main row values for the parent
            values = [item_name, str(tier), str(quantity), recipe, time_remaining, crafter, building]

            # Determine the tag based on time remaining for color coding
            tag = ""
            if time_remaining == "READY":
                tag = "ready"
            elif time_remaining not in ["Empty", "Unknown", "Error", "N/A"]:
                tag = "crafting"
            else:
                tag = "empty"

            # Insert the main item row
            if is_expandable:
                # Multiple operations - create expandable parent row
                item_id = self.tree.insert("", "end", values=values, tags=(tag,))

                # Add child rows for each operation
                for operation in operations:
                    child_item_name = operation.get("item_name", item_name)
                    child_tier = operation.get("tier", tier)
                    child_quantity = operation.get("quantity", 0)
                    child_recipe = operation.get("recipe", "Unknown Recipe")
                    child_time = operation.get("time_remaining", "Unknown")
                    child_crafter = operation.get("crafter", "Unknown")
                    child_refinery = operation.get("refinery", "Unknown Refinery")

                    # FIXED: Building display - just show the refinery name, no crafter info
                    child_building_display = child_refinery

                    child_values = [
                        f"  └─ {child_item_name}",  # Indented item name
                        str(child_tier),
                        str(child_quantity),
                        child_recipe,
                        child_time,
                        child_crafter,  # Crafter in separate column
                        child_building_display,  # Building without crafter info
                    ]

                    # Determine child tag based on individual operation time
                    child_tag = ""
                    if child_time == "READY":
                        child_tag = "ready"
                    elif child_time not in ["Empty", "Unknown", "Error", "N/A"]:
                        child_tag = "crafting"
                    else:
                        child_tag = "empty"

                    # Insert child with appropriate styling
                    self.tree.insert(item_id, "end", text="", values=child_values, tags=("child", child_tag))
            else:
                # Single operation - create non-expandable row
                item_id = self.tree.insert("", "end", text="", values=values, tags=(tag,), open=False)
