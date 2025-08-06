import customtkinter as ctk
import logging
from tkinter import Menu, ttk
from typing import List, Dict
from app.ui.components.filter_popup import FilterPopup


class ActiveCraftingTab(ctk.CTkFrame):
    """The tab for displaying active crafting status with item-focused, expandable rows."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        # Updated headers to include Accept Help column
        self.headers = ["Item", "Tier", "Quantity", "Tag", "Progress", "Accept Help", "Crafter", "Building"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Item"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        # Track expansion state for better user experience
        self.auto_expand_on_first_load = False
        self.has_had_first_load = False

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

        # Style scrollbars BEFORE creating the Treeview to ensure consistency
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

        # Create the Treeview with tree structure support
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Configure tags for different progress colors based on active crafting status
        self.tree.tag_configure("ready", background="#2d4a2d", foreground="#4CAF50")  # Green for ready/complete
        self.tree.tag_configure("crafting", background="#3d3d2d", foreground="#FFA726")  # Orange for in progress
        self.tree.tag_configure("empty", background="#2a2d2e", foreground="#888888")  # Gray for empty
        self.tree.tag_configure("child", background="#3a3a3a")  # Darker for child rows
        self.tree.tag_configure("preparing", background="#2e2e3a", foreground="#B39DDB")  # Purple for preparation

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
            "Tier": 50,
            "Quantity": 70,
            "Tag": 70,
            "Progress": 120,
            "Accept Help": 90,
            "Crafter": 90,
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
        if header.lower() in ["building", "crafter", "accept help"]:
            unique_values = self._get_filter_data_for_expandable_column(header)
            filter_data = [{f"{header.lower().replace(' ', '_')}_display": val} for val in unique_values]
            current_selection = self.active_filters.get(header, set(unique_values))
            FilterPopup(
                self,
                header,
                filter_data,
                current_selection,
                self._apply_column_filter,
                custom_key=f"{header.lower().replace(' ', '_')}_display",
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
                    # For building, include building + crafter info
                    building = operation.get("building_name", "")
                    crafter = operation.get("crafter", "")
                    if building and crafter:
                        unique_values.add(f"{building} (by {crafter})")
                elif header.lower() == "crafter":
                    # For crafter, just the crafter name
                    crafter = operation.get("crafter", "")
                    if crafter:
                        unique_values.add(crafter)
                elif header.lower() == "accept help":
                    # For accept help, just the accept help value
                    accept_help = operation.get("accept_help", "")
                    if accept_help:
                        unique_values.add(accept_help)

        return sorted(list(unique_values))

    def _apply_column_filter(self, header, selected_values):
        self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def update_data(self, new_data):
        """Receives new active crafting data (already item-focused and grouped)."""
        if isinstance(new_data, list):
            self.all_data = new_data
        else:
            self.all_data = []

        self.apply_filter()

    def apply_filter(self):
        """Filters the master data list based on search and column filters."""
        search_term = self.app.search_var.get().lower()
        temp_data = self.all_data[:]

        if self.active_filters:
            for header, values in self.active_filters.items():
                if header.lower() in ["building", "crafter", "accept help"]:
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
                # For building, check building + crafter combination
                building = operation.get("building_name", "")
                crafter = operation.get("crafter", "")
                if building and crafter:
                    display_name = f"{building} (by {crafter})"
                    if display_name in selected_values:
                        return True
            elif header.lower() == "crafter":
                # For crafter, just check crafter name
                crafter = operation.get("crafter", "")
                if crafter in selected_values:
                    return True
            elif header.lower() == "accept help":
                # For accept help, check accept help value
                accept_help = operation.get("accept_help", "")
                if accept_help in selected_values:
                    return True

        return False

    def _row_matches_search(self, row, search_term):
        """Checks if a row matches the search term, including operation data."""
        # Check main row data
        main_fields = ["item", "tag", "progress", "accept_help", "crafter", "building"]
        for field in main_fields:
            if search_term in str(row.get(field, "")).lower():
                return True

        # Check individual operation data
        operations = row.get("operations", [])
        for operation in operations:
            operation_fields = ["item", "tag", "progress", "accept_help", "crafter", "building_name"]
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

        # Special sorting for progress - convert to numerical value for proper sorting
        if sort_key == "progress":

            def progress_sort_key(x):
                progress_str = str(x.get(sort_key, ""))
                if "%" in progress_str:
                    try:
                        return int(progress_str.replace("%", ""))
                    except ValueError:
                        return 999
                elif progress_str.lower() == "preparation":
                    return -1  # Preparation comes first
                else:
                    return 999  # Unknown progress comes last

            self.filtered_data.sort(key=progress_sort_key, reverse=self.sort_reverse)
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

    def update_header_sort_indicators(self):
        """Updates the arrows on column headers."""
        for header in self.headers:
            text = header
            if self.sort_column == header:
                text += " ↓" if not self.sort_reverse else " ↑"
            filter_indicator = " 🔎" if header in self.active_filters else ""
            self.tree.heading(header, text=text + filter_indicator)

    def render_table(self):
        """Renders the hierarchical active crafting data with mandatory two-level expansion, preserving expansion state."""
        # Save current expansion state before clearing (unless it's the first load)
        is_first_load = not self.has_had_first_load

        if self.has_had_first_load:
            expanded_items = self._save_expansion_state()
        else:
            expanded_items = set()
            self.has_had_first_load = True

        # Clear the tree
        self.tree.delete(*self.tree.get_children())

        for row_data in self.filtered_data:
            item_name = row_data.get("item", "Unknown Item")
            tier = row_data.get("tier", 0)
            quantity = row_data.get("total_quantity", 0)
            tag = row_data.get("tag", "empty")
            progress = row_data.get("progress", "Unknown")
            accept_help = row_data.get("accept_help", "Unknown")
            crafter = row_data.get("crafter", "Unknown")
            building = row_data.get("building_name", "Unknown")
            operations = row_data.get("operations", [])
            is_expandable = row_data.get("is_expandable", False)

            # Create a unique identifier for this row to track expansion state
            row_id = f"{item_name}|{tier}|{tag}"

            # Prepare main row values
            values = [item_name, str(tier), str(quantity), tag, progress, accept_help, crafter, building]

            # Determine tag based on progress
            tag = self._get_progress_tag(progress)

            if is_expandable and operations:
                # Create expandable parent row
                parent_id = self.tree.insert("", "end", values=values, tags=(tag,))

                # Determine if this item should be expanded
                should_expand = False
                if is_first_load and self.auto_expand_on_first_load:
                    # Auto-expand on first load
                    should_expand = True
                elif not is_first_load and row_id in expanded_items:
                    # Previously expanded (only check this after first load)
                    should_expand = True

                # Process child operations
                for child_data in operations:
                    self._render_child_row(parent_id, child_data, 1, row_id, expanded_items, is_first_load)

                # Apply expansion state
                if should_expand:
                    self.tree.item(parent_id, open=True)
            else:
                # Non-expandable row or no operations
                self.tree.insert("", "end", values=values, tags=(tag,))

    def _save_expansion_state(self):
        """Save the current expansion state of all tree items."""
        expanded_items = set()

        def check_item(item_id):
            # Get the item's values to create identifier
            values = self.tree.item(item_id, "values")
            if values and len(values) >= 3:
                # Create identifier from item, tier, tag
                item_identifier = f"{values[0]}|{values[1]}|{values[3]}"

                # If this item is expanded, save its identifier
                if self.tree.item(item_id, "open"):
                    expanded_items.add(item_identifier)

                # Check children recursively
                for child_id in self.tree.get_children(item_id):
                    check_item(child_id)

        # Check all top-level items
        for item_id in self.tree.get_children():
            check_item(item_id)

        return expanded_items

    def _render_child_row(self, parent_id, child_data, level, parent_row_id=None, expanded_items=None, is_first_load=False):
        """
        Renders a child row, potentially with its own children for second-level expansion.

        Args:
            parent_id: The parent tree item ID
            child_data: The child data dictionary
            level: Expansion level (1 for first level, 2 for second level)
            parent_row_id: The identifier of the parent row for expansion tracking
            expanded_items: Set of previously expanded item identifiers
            is_first_load: Whether this is the first time loading data
        """
        if expanded_items is None:
            expanded_items = set()

        # Extract child data
        item_name = child_data.get("item", child_data.get("item_name", "Unknown Item"))
        tier = child_data.get("tier", 0)
        quantity = child_data.get("quantity", 0)
        tag = child_data.get("tag", "empty")
        progress = child_data.get("progress", "Unknown")
        accept_help = child_data.get("accept_help", "Unknown")
        crafter = child_data.get("crafter", "Unknown")
        building = child_data.get("building_name", child_data.get("building", "Unknown"))
        is_expandable = child_data.get("is_expandable", False)
        child_operations = child_data.get("operations", [])

        # Create indentation based on level
        indent = "  " + "  " * (level - 1) + "└─ "
        indented_item_name = f"{indent}{item_name}"

        # Create identifier for this child row for expansion tracking
        child_row_id = f"{item_name}|{tier}|{tag}|{crafter}"
        if level > 1:
            child_row_id += f"|{building}"

        # Prepare child values
        child_values = [indented_item_name, str(tier), str(quantity), tag, progress, accept_help, crafter, building]

        # Determine tag
        child_tag = self._get_progress_tag(progress)

        # Insert the child row
        if is_expandable and child_operations:
            # This child has its own children (second level expansion)
            child_id = self.tree.insert(parent_id, "end", values=child_values, tags=("child", child_tag))

            # Determine if this child should be expanded
            should_expand_child = False
            if is_first_load and self.auto_expand_on_first_load:
                # Auto-expand on first load
                should_expand_child = True
            elif not is_first_load and child_row_id in expanded_items:
                # Previously expanded
                should_expand_child = True

            # Add grandchildren (second level)
            for grandchild_data in child_operations:
                self._render_child_row(child_id, grandchild_data, level + 1, child_row_id, expanded_items, is_first_load)

            # Apply expansion state for this child
            if should_expand_child:
                self.tree.item(child_id, open=True)
        else:
            # Leaf node - no further expansion
            self.tree.insert(parent_id, "end", values=child_values, tags=("child", child_tag))

    def _get_progress_tag(self, progress):
        """Determines the appropriate tag for color coding based on progress."""
        progress_str = str(progress).lower()

        if progress_str == "preparation":
            return "preparing"
        elif "%" in progress_str:
            try:
                progress_value = int(progress_str.replace("%", ""))
                if progress_value >= 100:
                    return "ready"
                else:
                    return "crafting"
            except ValueError:
                return "empty"
        else:
            return "empty"
