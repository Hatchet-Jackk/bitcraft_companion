import customtkinter as ctk
import logging
from tkinter import Menu, ttk
from typing import List, Dict
from filter_popup import FilterPopup


class ActiveCraftingTab(ctk.CTkFrame):
    """The tab for displaying active crafting status with simplified flat structure."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        # Updated headers - added Quantity, removed expandability
        self.headers = ["Item", "Tier", "Quantity", "Progress", "Status", "Accept Help", "Crafter", "Building"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Item"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        self._create_widgets()
        self._create_context_menu()

    def _create_widgets(self):
        """Creates the styled Treeview and scrollbars for active crafting."""
        style = ttk.Style()
        style.theme_use("default")

        # Configure Treeview colors - consistent with other tabs
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

        # Create Treeview - NO tree column, flat table only
        self.tree = ttk.Treeview(self, columns=self.headers, show="headings", style="Treeview")

        # Configure tags for different statuses with improved colors
        self.tree.tag_configure("ready_to_claim", background="#2d4a2d", foreground="#4CAF50")  # Green for ready to claim
        self.tree.tag_configure("crafting", background="#2a2d2e", foreground="#2196F3")  # Blue for active crafting
        self.tree.tag_configure("paused", background="#3d3d2d", foreground="#FF9800")  # Orange for paused
        self.tree.tag_configure("preparing", background="#2e2e3a", foreground="#B39DDB")  # Softer purple for preparing

        # Create scrollbars
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.hsb = hsb
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Updated column widths with Quantity column
        column_widths = {
            "Item": 180,
            "Tier": 50,
            "Quantity": 70,
            "Progress": 120,
            "Status": 100,
            "Accept Help": 90,
            "Crafter": 100,
            "Building": 200,
        }

        for header in self.headers:
            self.tree.heading(header, text=header, command=lambda h=header: self.sort_by(h), anchor="w")
            self.tree.column(header, width=column_widths.get(header, 100), minwidth=50, anchor="w")

        # Bind events
        self.tree.bind("<Button-3>", self.show_header_context_menu)
        self.tree.bind("<Configure>", self.on_tree_configure)

    def on_tree_configure(self, event):
        """Manages horizontal scrollbar visibility."""
        total_width = sum(self.tree.column(col, "width") for col in self.headers)
        widget_width = self.tree.winfo_width()

        if total_width > widget_width:
            self.hsb.grid(row=1, column=0, sticky="ew")
        else:
            self.hsb.grid_remove()

    def _create_context_menu(self):
        """Creates the right-click context menu for filtering."""
        self.header_context_menu = Menu(self, tearoff=0, background="#2a2d2e", foreground="white", activebackground="#1f6aa5")
        self.header_context_menu.add_command(label="Filter by...", command=lambda: self._open_filter_popup(self.clicked_header))
        self.header_context_menu.add_command(label="Clear Filter", command=lambda: self.clear_column_filter(self.clicked_header))

    def show_header_context_menu(self, event):
        """Shows context menu on header right-click."""
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            column_id = self.tree.identify_column(event.x)
            self.clicked_header = self.tree.column(column_id, "id")
            self.header_context_menu.tk_popup(event.x_root, event.y_root)

    def _get_filter_data_for_column(self, header):
        """Gets unique values for filtering by column."""
        if header.lower() == "status":
            # Extract unique status values
            unique_statuses = set()
            for row in self.all_data:
                status = row.get("status", "")
                if status:
                    unique_statuses.add(status)
            return sorted(list(unique_statuses))

        elif header.lower() == "accept help":
            return ["Yes", "No", "N/A"]

        elif header.lower() == "quantity":
            # Extract unique quantities
            unique_quantities = set()
            for row in self.all_data:
                quantity = row.get("quantity", 1)
                unique_quantities.add(str(quantity))
            return sorted(list(unique_quantities), key=lambda x: int(x) if x.isdigit() else 0)

        else:
            # Standard field extraction
            field_name = header.lower().replace(" ", "_")
            unique_values = set()
            for row in self.all_data:
                value = str(row.get(field_name, ""))
                if value:
                    unique_values.add(value)
            return sorted(list(unique_values))

    def _open_filter_popup(self, header):
        """Opens the filter popup for the specified header."""
        if not self.all_data:
            return

        unique_values = self._get_filter_data_for_column(header)
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

    def _apply_column_filter(self, header, selected_values):
        """Applies the selected filter values."""
        self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        """Clears the filter for the specified header."""
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def update_data(self, new_data):
        """Updates the tab with new active crafting data."""
        if isinstance(new_data, list):
            self.all_data = new_data
        else:
            self.all_data = []

        self.apply_filter()
        logging.debug(f"Active crafting data updated: {len(self.all_data)} operations")

    def apply_filter(self):
        """Applies search and column filters to the data."""
        search_term = self.app.search_var.get().lower()
        temp_data = self.all_data[:]

        # Apply column filters
        if self.active_filters:
            for header, values in self.active_filters.items():
                temp_data = [row for row in temp_data if self._row_matches_column_filter(row, header, values)]

        # Apply search filter
        if search_term:
            temp_data = [row for row in temp_data if self._row_matches_search(row, search_term)]

        self.filtered_data = temp_data
        self.sort_by(self.sort_column, self.sort_reverse)

    def _row_matches_column_filter(self, row, header, selected_values):
        """Checks if a row matches the column filter."""
        header_lower = header.lower()

        if header_lower == "status":
            return row.get("status", "") in selected_values
        elif header_lower == "accept help":
            return row.get("accept_help", "") in selected_values
        elif header_lower == "quantity":
            return str(row.get("quantity", 1)) in selected_values
        else:
            # Standard field matching
            field_name = header_lower.replace(" ", "_")
            return str(row.get(field_name, "")) in selected_values

    def _row_matches_search(self, row, search_term):
        """Checks if a row matches the search term."""
        # Check main row fields
        search_fields = ["item_name", "status", "crafter", "building", "recipe"]
        for field in search_fields:
            if search_term in str(row.get(field, "")).lower():
                return True
        return False

    def sort_by(self, header, reverse=None):
        """Sorts the data by the specified header."""
        if self.sort_column == header and reverse is None:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = header
            self.sort_reverse = reverse if reverse is not None else False

        sort_key = self.sort_column.lower().replace(" ", "_")

        # Special sorting for progress (parse numbers)
        if sort_key == "progress":

            def progress_sort_key(x):
                progress_str = str(x.get("progress", "0/0"))
                if "/" in progress_str:
                    try:
                        current, total = progress_str.split("/")
                        return int(current) / int(total) if int(total) > 0 else 0
                    except:
                        return 0
                return 0

            self.filtered_data.sort(key=progress_sort_key, reverse=self.sort_reverse)

        elif sort_key in ["tier", "quantity"]:
            # Numeric sorting
            self.filtered_data.sort(key=lambda x: int(x.get(sort_key, 0)), reverse=self.sort_reverse)

        else:
            # String sorting
            self.filtered_data.sort(key=lambda x: str(x.get(sort_key, "")).lower(), reverse=self.sort_reverse)

        self.render_table()
        self.update_header_sort_indicators()

    def update_header_sort_indicators(self):
        """Updates sort arrows and filter indicators on headers."""
        for header in self.headers:
            text = header
            if self.sort_column == header:
                text += " ↓" if not self.sort_reverse else " ↑"
            filter_indicator = " 🔎" if header in self.active_filters else ""
            self.tree.heading(header, text=text + filter_indicator)

    def render_table(self):
        """Renders the active crafting data in the tree view - FLAT STRUCTURE ONLY."""
        # Clear tree
        self.tree.delete(*self.tree.get_children())

        for row_data in self.filtered_data:
            item_name = row_data.get("item_name", "Unknown Item")
            tier = row_data.get("tier", 0)
            quantity = row_data.get("quantity", 1)
            progress = row_data.get("progress", "0/0")
            status = row_data.get("status", "Unknown")
            accept_help = row_data.get("accept_help", "N/A")
            crafter = row_data.get("crafter", "Unknown")
            building = row_data.get("building", "Unknown")

            # Prepare row values - NO tree structure, flat table
            values = [item_name, str(tier), str(quantity), progress, status, accept_help, crafter, building]

            # Determine tag based on status with consistent colors
            tag = self._get_status_tag(status)

            # Insert flat row - no children, no grouping
            self.tree.insert("", "end", values=values, tags=(tag,))

    def _get_status_tag(self, status):
        """Determines the appropriate tag for status-based color coding."""
        status_lower = status.lower()

        if "ready to claim" in status_lower:
            return "ready_to_claim"
        elif "paused" in status_lower or "idle" in status_lower:
            return "paused"
        elif "preparing" in status_lower:
            return "preparing"
        elif "crafting" in status_lower or "active" in status_lower:
            return "crafting"
        else:
            return "crafting"
