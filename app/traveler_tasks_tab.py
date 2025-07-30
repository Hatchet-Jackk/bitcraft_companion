import customtkinter as ctk
import logging
from tkinter import Menu, ttk
from typing import List, Dict
from filter_popup import FilterPopup


class TravelerTasksTab(ctk.CTkFrame):
    """The tab for displaying traveler tasks with expandable traveler groups."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.headers = ["Traveler", "Task", "Required Items", "Complete"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Traveler"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        # Track expansion state for better user experience
        self.has_had_first_load = False

        self._create_widgets()
        self._create_context_menu()

    def _create_widgets(self):
        """Creates the styled Treeview and its scrollbars."""
        style = ttk.Style()
        style.theme_use("default")

        # Configure the Treeview colors - consistent with other tabs
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

        # Create the Treeview with support for child items
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Configure tags for different completion statuses - neutral colors with green for completed
        self.tree.tag_configure("completed", background="#2d4a2d", foreground="#4CAF50")  # Green for fully completed
        self.tree.tag_configure("incomplete", background="#2a2d2e", foreground="white")  # Neutral for incomplete
        self.tree.tag_configure("partial", background="#2a2d2e", foreground="white")  # Neutral for partial
        self.tree.tag_configure("child", background="#3a3a3a")
        self.tree.tag_configure("child_completed", background="#3a4a3a", foreground="#4CAF50")  # Green for completed tasks
        self.tree.tag_configure("child_incomplete", background="#3a3a3a", foreground="white")  # Neutral for incomplete tasks

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
        column_widths = {"Traveler": 200, "Task": 320, "Required Items": 250, "Complete": 80}

        for header in self.headers:
            self.tree.heading(header, text=header, command=lambda h=header: self.sort_by(h), anchor="w")
            self.tree.column(header, width=column_widths.get(header, 150), minwidth=50, anchor="w")

        # Configure the tree column for expansion
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

    def _get_filter_data_for_column(self, header):
        """Gets the appropriate data for filtering based on the column."""
        if header.lower() == "traveler":
            # Extract unique traveler names (without completion info)
            unique_travelers = set()
            for row in self.all_data:
                traveler_full = row.get("traveler", "")
                # Remove the completion count part: "Traveler Name (2/3)" -> "Traveler Name"
                traveler_name = traveler_full.split(" (")[0] if " (" in traveler_full else traveler_full
                unique_travelers.add(traveler_name)
            return sorted(list(unique_travelers))
        elif header.lower() == "complete":
            # Special completion status values
            return ["✅", "❌"]
        else:
            field_name = header.lower().replace(" ", "_")
            return sorted(list(set(str(row.get(field_name, "")) for row in self.all_data)))

    def _open_filter_popup(self, header):
        if not self.all_data:
            return

        if header.lower() in ["traveler", "complete"]:
            unique_values = self._get_filter_data_for_column(header)
            filter_data = [{f"{header.lower()}_display": val} for val in unique_values]
            current_selection = self.active_filters.get(header, set(unique_values))
            FilterPopup(
                self, header, filter_data, current_selection, self._apply_column_filter, custom_key=f"{header.lower()}_display"
            )
        else:
            field_name = header.lower().replace(" ", "_")
            current_selection = self.active_filters.get(header, {str(row.get(field_name, "")) for row in self.all_data})
            FilterPopup(self, header, self.all_data, current_selection, self._apply_column_filter)

    def _apply_column_filter(self, header, selected_values):
        self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def update_data(self, new_data):
        """Receives new tasks data (already grouped by traveler)."""
        if isinstance(new_data, list):
            self.all_data = new_data
        else:
            self.all_data = []

        self.apply_filter()
        logging.debug(f"Traveler tasks data updated: {len(self.all_data)} traveler groups")

    def apply_filter(self):
        """Filters the master data list based on search and column filters."""
        search_term = self.app.search_var.get().lower()
        temp_data = self.all_data[:]

        if self.active_filters:
            for header, values in self.active_filters.items():
                if header.lower() == "traveler":
                    temp_data = [row for row in temp_data if self._traveler_matches_filter(row, values)]
                elif header.lower() == "complete":
                    temp_data = [row for row in temp_data if str(row.get("complete", "")) in values]
                else:
                    field_name = header.lower().replace(" ", "_")
                    temp_data = [row for row in temp_data if str(row.get(field_name, "")) in values]

        if search_term:
            temp_data = [row for row in temp_data if self._row_matches_search(row, search_term)]

        self.filtered_data = temp_data
        self.sort_by(self.sort_column, self.sort_reverse)

    def _traveler_matches_filter(self, row, selected_values):
        """Checks if a row matches the traveler filter."""
        traveler_full = row.get("traveler", "")
        traveler_name = traveler_full.split(" (")[0] if " (" in traveler_full else traveler_full
        return traveler_name in selected_values

    def _row_matches_search(self, row, search_term):
        """Checks if a row matches the search term, including task data."""
        # Check main row data
        main_fields = ["traveler", "task", "required_items", "complete"]
        for field in main_fields:
            if search_term in str(row.get(field, "")).lower():
                return True

        # Check individual task data
        operations = row.get("operations", [])
        for operation in operations:
            operation_fields = ["task_description", "required_items", "traveler_name", "completion_status"]
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

        # Special sorting logic
        if sort_key == "traveler":
            # Sort by traveler name without completion count
            def traveler_sort_key(x):
                traveler_full = str(x.get("traveler", ""))
                return traveler_full.split(" (")[0] if " (" in traveler_full else traveler_full

            self.filtered_data.sort(key=traveler_sort_key, reverse=self.sort_reverse)
        elif sort_key == "complete":
            # Sort by completion status: ✅ first, then ❌
            def completion_sort_key(x):
                status = str(x.get("complete", ""))
                if status == "✅":
                    return 0
                else:
                    return 1

            self.filtered_data.sort(key=completion_sort_key, reverse=self.sort_reverse)
        else:
            # Standard string sorting
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
        """Renders the traveler tasks data with expandable traveler groups."""
        # Save current expansion state
        is_first_load = not self.has_had_first_load
        if self.has_had_first_load:
            expanded_items = self._save_expansion_state()
        else:
            expanded_items = set()
            self.has_had_first_load = True

        # Clear the tree
        self.tree.delete(*self.tree.get_children())

        for row_data in self.filtered_data:
            traveler_name = row_data.get("traveler", "Unknown Traveler")
            task_summary = row_data.get("task", "")
            required_items = row_data.get("required_items", "")
            completion_status = row_data.get("complete", "❌")
            operations = row_data.get("operations", [])
            is_expandable = row_data.get("is_expandable", False)

            # Create a unique identifier for expansion tracking
            traveler_id = row_data.get("traveler_id", "")
            row_id = f"traveler_{traveler_id}"

            # Prepare main row values
            values = [traveler_name, task_summary, required_items, completion_status]

            # Determine tag based on completion status - only green for fully completed
            if completion_status == "✅":
                tag = "completed"
            else:
                tag = "incomplete"  # Neutral for all non-completed states

            if is_expandable and operations:
                # Create expandable parent row
                parent_id = self.tree.insert("", "end", values=values, tags=(tag,))

                # Determine if this traveler should be expanded
                should_expand = False
                if is_first_load:
                    # Auto-expand on first load to show tasks
                    should_expand = True
                elif not is_first_load and row_id in expanded_items:
                    # Previously expanded
                    should_expand = True

                # Add individual tasks as children
                for task_data in operations:
                    self._render_task_row(parent_id, task_data)

                # Apply expansion state
                if should_expand:
                    self.tree.item(parent_id, open=True)
            else:
                # Non-expandable row
                self.tree.insert("", "end", values=values, tags=(tag,))

    def _save_expansion_state(self):
        """Save the current expansion state of traveler groups."""
        expanded_items = set()

        def check_item(item_id):
            # Get the item's values to create identifier
            values = self.tree.item(item_id, "values")
            if values and len(values) >= 1:
                # Extract traveler info for identifier (remove completion count)
                traveler_full = values[0]
                # This is a simplification - in practice you'd want to use traveler_id
                traveler_base = traveler_full.split(" (")[0] if " (" in traveler_full else traveler_full
                row_id = f"traveler_{traveler_base}"

                # If this item is expanded, save its identifier
                if self.tree.item(item_id, "open"):
                    expanded_items.add(row_id)

            # Check children recursively
            for child_id in self.tree.get_children(item_id):
                check_item(child_id)

        # Check all top-level items
        for item_id in self.tree.get_children():
            check_item(item_id)

        return expanded_items

    def _render_task_row(self, parent_id, task_data):
        """Renders an individual task as a child row."""
        task_description = task_data.get("task_description", "Unknown Task")
        required_items = task_data.get("required_items", "")
        completion_status = task_data.get("completion_status", "❌")

        # Prepare child values - no traveler name, no indent prefix for task description
        child_values = ["", task_description, required_items, completion_status]

        # Determine child tag
        if completion_status == "✅":
            child_tag = ("child", "child_completed")
        else:
            child_tag = ("child", "child_incomplete")

        # Insert the child row
        self.tree.insert(parent_id, "end", values=child_values, tags=child_tag)
