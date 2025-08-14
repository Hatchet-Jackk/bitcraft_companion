import logging
from typing import Dict, List

import customtkinter as ctk
from tkinter import Menu, ttk

from app.ui.components.filter_popup import FilterPopup
from app.ui.styles import TreeviewStyles


class TravelerTasksTab(ctk.CTkFrame):
    """The tab for displaying traveler tasks with expandable traveler groups."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        # Updated headers - removed Task column, focus on item-based structure
        self.headers = ["Traveler", "Item", "Quantity", "Tier", "Tag", "Status"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Traveler"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        # Track expansion state for better user experience
        self.has_had_first_load = False
        self.expansion_state = set()  # Store traveler IDs that should be expanded

        self._create_widgets()
        self._create_context_menu()

    def _create_widgets(self):
        """Creates the styled Treeview and its scrollbars."""
        style = ttk.Style()
        
        # Apply centralized Treeview styling
        TreeviewStyles.apply_treeview_style(style)
        
        # Apply centralized scrollbar styling and get style names
        self.v_scrollbar_style, self.h_scrollbar_style = TreeviewStyles.apply_scrollbar_style(style, "TravelerTasks")

        # Create the Treeview with support for child items
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Apply common tree tags using centralized styling
        TreeviewStyles.configure_tree_tags(self.tree)
        
        # Configure custom tags specific to traveler tasks
        self.tree.tag_configure("completed", background="#2d4a2d", foreground="#4CAF50")  # Green for fully completed
        self.tree.tag_configure("child_completed", background="#3a4a3a", foreground="#4CAF50")  # Green for completed tasks
        self.tree.tag_configure("child_incomplete", background="#3a3a3a", foreground="white")  # Neutral for incomplete tasks

        # Create scrollbars with unique styles
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, style=self.v_scrollbar_style)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview, style=self.h_scrollbar_style)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.hsb = hsb
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Updated column widths for new structure
        column_widths = {
            "Traveler": 90,
            "Item": 200,
            "Quantity": 80,
            "Tier": 50,
            "Tag": 100,
            "Status": 70,
        }

        for header in self.headers:
            self.tree.heading(header, text=header, command=lambda h=header: self.sort_by(h), anchor="w")
            width = column_widths.get(header, 150)

            # Configure column properties
            if header in ["Traveler", "Completed"]:
                # Fixed width for traveler and completion columns
                self.tree.column(header, width=width, minwidth=width, stretch=False, anchor="w")
            elif header == "Tier":
                # Center-aligned tier column
                self.tree.column(header, width=width, minwidth=width, stretch=False, anchor="center")
            elif header in ["Quantity", "Status"]:
                # Fixed width for quantity and status
                self.tree.column(header, width=width, minwidth=width, stretch=False, anchor="center")
            else:
                # Stretchable columns for Item and Tag
                self.tree.column(header, width=width, minwidth=50, anchor="w")

        # Configure the tree column for expansion - CONSISTENT with other tabs
        self.tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.tree.heading("#0", text="", anchor="w")

        # Configure event debouncing for better resize performance
        self.resize_timer = None
        self.cached_total_width = None
        
        # Bind events
        self.tree.bind("<Button-3>", self.show_header_context_menu)
        self.tree.bind("<Configure>", self.on_tree_configure)

    def on_tree_configure(self, event):
        """Manages horizontal scrollbar visibility with debouncing for smooth resize."""
        # Cancel previous timer if it exists
        if self.resize_timer:
            self.after_cancel(self.resize_timer)
        
        # Schedule the actual configure handling with debouncing
        self.resize_timer = self.after(150, self._handle_tree_configure)

    def _handle_tree_configure(self):
        """Actual handler for tree configure events."""
        try:
            total_width = sum(self.tree.column(col, "width") for col in ["#0"] + list(self.headers))
            widget_width = self.tree.winfo_width()
            
            # Only update if width actually changed to avoid unnecessary operations
            if self.cached_total_width != total_width:
                self.cached_total_width = total_width
                
                if total_width > widget_width:
                    self.hsb.grid(row=1, column=0, sticky="ew")
                else:
                    self.hsb.grid_remove()
        except Exception as e:
            logging.error(f"Error in tree configure handler: {e}")
        finally:
            self.resize_timer = None

    def _create_context_menu(self):
        """Creates the right-click menu for column headers."""
        menu_config = TreeviewStyles.get_menu_style_config()
        self.header_context_menu = Menu(self, **menu_config)
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
                traveler_name = traveler_full.split(" (")[0] if " (" in traveler_full else traveler_full
                unique_travelers.add(traveler_name)
            return sorted(list(unique_travelers))
        elif header.lower() == "status":
            # Special completion status values
            return ["✅", "❌"]
        elif header.lower() == "item":
            # Extract unique required item names from all tasks
            unique_items = set()
            for row in self.all_data:
                operations = row.get("operations", [])
                for operation in operations:
                    required_item = operation.get("required_item", "")
                    if required_item and required_item != "No items required":
                        unique_items.add(required_item)
            return sorted(list(unique_items))
        elif header.lower() == "tier":
            # Extract unique tier values from all tasks
            unique_tiers = set()
            for row in self.all_data:
                operations = row.get("operations", [])
                for operation in operations:
                    tier = operation.get("tier", 0)
                    if tier > 0:  # Only include non-zero tiers
                        unique_tiers.add(str(tier))
            return sorted(list(unique_tiers), key=lambda x: int(x) if x.isdigit() else 0)
        elif header.lower() == "quantity":
            # Extract unique quantities
            unique_quantities = set()
            for row in self.all_data:
                operations = row.get("operations", [])
                for operation in operations:
                    quantity = operation.get("quantity", "")
                    if quantity:
                        unique_quantities.add(str(quantity))
            return sorted(list(unique_quantities), key=lambda x: int(x) if x.isdigit() else 0)
        elif header.lower() == "tag":
            # Extract unique item tags from all tasks
            unique_tags = set()
            for row in self.all_data:
                operations = row.get("operations", [])
                for operation in operations:
                    tag = operation.get("tag", "")
                    if tag and tag not in ["", "Unknown"]:
                        unique_tags.add(tag)
            return sorted(list(unique_tags))
        else:
            field_name = header.lower().replace(" ", "_")
            return sorted(list(set(str(row.get(field_name, "")) for row in self.all_data)))

    def _open_filter_popup(self, header):
        if not self.all_data:
            return

        # Updated for new column names
        if header.lower() in ["traveler", "status", "item", "tier", "quantity", "tag", "completed"]:
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
        """Receives new tasks data and processes it for the new column structure."""
        if isinstance(new_data, list):
            # Process the data to split required items into separate columns including tier
            processed_data = self._process_tasks_for_split_columns(new_data)
            self.all_data = processed_data
        else:
            self.all_data = []

        self.apply_filter()

    def _process_tasks_for_split_columns(self, raw_data):
        """
        Processes raw task data for new item-focused structure without task descriptions.
        """
        processed_data = []

        for traveler_group in raw_data:
            traveler_name = traveler_group.get("traveler", "Unknown Traveler")
            completed_count = traveler_group.get("completed_count", 0)
            total_count = traveler_group.get("total_count", 0)
            completion_summary = f"{completed_count}/{total_count}"
            completion_status = traveler_group.get("complete", "❌")
            traveler_id = traveler_group.get("traveler_id", "")
            operations = traveler_group.get("operations", [])

            # Process each task to handle multiple required items with tier support
            processed_operations = []

            for task in operations:
                task_description = task.get("task_description", "Unknown Task")
                completion_status_task = task.get("completion_status", "❌")

                # Use detailed required items if available, fallback to string parsing
                required_items_detailed = task.get("required_items_detailed", [])

                if required_items_detailed:
                    # Use the detailed format (preferred) - now includes tier
                    for item_data in required_items_detailed:
                        item_name = item_data.get("item_name", "Unknown Item")
                        item_tier = item_data.get("tier", 0)
                        quantity = item_data.get("quantity", 1)
                        tag = item_data.get("tag", "")

                        processed_operations.append(
                            {
                                "item": item_name,
                                "tier": item_tier,
                                "quantity": str(quantity) if quantity > 0 else "",
                                "tag": tag,
                                "status": completion_status_task,
                                **task,  # Include all original task data
                            }
                        )
                else:
                    # Fallback to string parsing (backward compatibility) - tier will be 0
                    required_items_str = task.get("required_items", "")

                    if required_items_str and required_items_str != "No items required":
                        # Split by comma and parse each item
                        items = [item.strip() for item in required_items_str.split(",")]

                        for item_str in items:
                            # Parse "Item Name x5" format
                            if " x" in item_str:
                                item_name, quantity_str = item_str.rsplit(" x", 1)
                                try:
                                    quantity = int(quantity_str)
                                except ValueError:
                                    quantity = 1
                            else:
                                item_name = item_str
                                quantity = 1

                            # Create a row for each required item (tier will be 0 for fallback)
                            processed_operations.append(
                                {
                                    "item": item_name.strip(),
                                    "tier": 0,  # Fallback parsing doesn't have tier info
                                    "quantity": str(quantity),
                                    "tag": "",  # Fallback parsing doesn't have tag info
                                    "status": completion_status_task,
                                    **task,  # Include all original task data
                                }
                            )
                    else:
                        # Task with no required items
                        processed_operations.append(
                            {
                                "item": "No items required",
                                "tier": 0,  # No tier for empty requirements
                                "quantity": "",
                                "tag": "",
                                "status": completion_status_task,
                                **task,
                            }
                        )

            # Create the processed traveler group
            processed_group = {
                "traveler": traveler_name,
                "completed": completion_summary,
                "item": "",  # Empty for parent row
                "quantity": "",  # Empty for parent row
                "tier": "",  # Empty for parent row
                "tag": "",  # Empty for parent row
                "status": completion_status,
                "operations": processed_operations,
                "is_expandable": True,
                "expansion_level": 0,
                "traveler_id": traveler_id,
                "completed_count": completed_count,
                "total_count": total_count,
            }

            processed_data.append(processed_group)

        return processed_data

    def apply_filter(self):
        """
        Filters the master data list based on search and column filters.
        """
        search_term = self.app.search_var.get().lower()
        temp_data = []

        for row in self.all_data:
            # Start with a copy of the traveler group
            filtered_row = row.copy()
            original_operations = row.get("operations", [])

            # Filter individual operations (tasks) based on active filters
            filtered_operations = []

            for operation in original_operations:
                operation_matches = True

                # Apply column filters to individual operations
                if self.active_filters:
                    for header, values in self.active_filters.items():
                        if header.lower() == "required item":
                            required_item = operation.get("required_item", "")
                            if required_item not in values:
                                operation_matches = False
                                break
                        elif header.lower() == "tier":
                            tier = str(operation.get("tier", 0))
                            if tier not in values:
                                operation_matches = False
                                break
                        elif header.lower() == "quantity":
                            quantity = str(operation.get("quantity", ""))
                            if quantity not in values:
                                operation_matches = False
                                break
                        elif header.lower() == "tag":
                            tag = operation.get("tag", "")
                            if tag not in values:
                                operation_matches = False
                                break
                        elif header.lower() == "complete":
                            completion_status = operation.get("completion_status", "")
                            if completion_status not in values:
                                operation_matches = False
                                break

                # Apply search filter to individual operations
                if operation_matches and search_term:
                    if not self._operation_matches_search(operation, search_term):
                        operation_matches = False

                # If operation matches all filters, include it
                if operation_matches:
                    filtered_operations.append(operation)

            # Apply traveler-level filters
            traveler_matches = True
            if self.active_filters:
                for header, values in self.active_filters.items():
                    if header.lower() == "traveler":
                        if not self._traveler_matches_filter(row, values):
                            traveler_matches = False
                            break
                    elif header.lower() == "complete" and not filtered_operations:
                        # If filtering by completion status and no operations match, check traveler completion
                        if str(row.get("complete", "")) not in values:
                            traveler_matches = False
                            break

            # Apply search to traveler level
            if traveler_matches and search_term and not filtered_operations:
                # If no operations matched search, check if traveler info matches
                main_fields = ["traveler", "completed", "status"]
                traveler_search_matches = False
                for field in main_fields:
                    if search_term in str(row.get(field, "")).lower():
                        traveler_search_matches = True
                        break
                if not traveler_search_matches:
                    traveler_matches = False

            # Include traveler group if it matches and has matching operations (or no operation-level filters)
            if traveler_matches:
                # If we have operation-level filters, only include if some operations match
                operation_level_filters = any(
                    header.lower() in ["item", "tier", "quantity", "tag"] for header in self.active_filters.keys()
                )

                if operation_level_filters:
                    if filtered_operations:
                        # Update the operations list and completion counts
                        filtered_row["operations"] = filtered_operations

                        # Recalculate completion counts based on filtered operations
                        completed_count = sum(1 for op in filtered_operations if op.get("status") == "✅")
                        total_count = len(filtered_operations)

                        filtered_row["completed_count"] = completed_count
                        filtered_row["total_count"] = total_count
                        filtered_row["completed"] = f"{completed_count}/{total_count}"
                        filtered_row["status"] = "✅" if completed_count == total_count else "❌"

                        temp_data.append(filtered_row)
                else:
                    # No operation-level filters, include as-is (but still apply search to operations)
                    if search_term and filtered_operations != original_operations:
                        filtered_row["operations"] = filtered_operations
                        completed_count = sum(1 for op in filtered_operations if op.get("status") == "✅")
                        total_count = len(filtered_operations)
                        filtered_row["completed_count"] = completed_count
                        filtered_row["total_count"] = total_count
                        filtered_row["completed"] = f"{completed_count}/{total_count}"
                        filtered_row["status"] = "✅" if completed_count == total_count else "❌"
                    temp_data.append(filtered_row)

        self.filtered_data = temp_data
        self.sort_by(self.sort_column, self.sort_reverse)

    def _operation_matches_search(self, operation, search_term):
        """Checks if an individual operation matches the search term."""
        operation_fields = ["task_description", "item", "tier", "quantity", "tag", "status"]
        for field in operation_fields:
            if search_term in str(operation.get(field, "")).lower():
                return True
        return False

    def _traveler_matches_filter(self, row, selected_values):
        """Checks if a row matches the traveler filter."""
        traveler_full = row.get("traveler", "")
        traveler_name = traveler_full.split(" (")[0] if " (" in traveler_full else traveler_full
        return traveler_name in selected_values

    def _item_matches_filter(self, row, selected_values):
        """Checks if a row matches the item filter."""
        operations = row.get("operations", [])
        for operation in operations:
            item = operation.get("item", "")
            if item in selected_values:
                return True
        return False

    def _tier_matches_filter(self, row, selected_values):
        """NEW: Checks if a row matches the tier filter."""
        operations = row.get("operations", [])
        for operation in operations:
            tier = str(operation.get("tier", 0))
            if tier in selected_values:
                return True
        return False

    def _quantity_matches_filter(self, row, selected_values):
        """Checks if a row matches the quantity filter."""
        operations = row.get("operations", [])
        for operation in operations:
            quantity = str(operation.get("quantity", ""))
            if quantity in selected_values:
                return True
        return False

    def _tag_matches_filter(self, row, selected_values):
        """Checks if a row matches the tag filter."""
        operations = row.get("operations", [])
        for operation in operations:
            tag = operation.get("tag", "")
            if tag in selected_values:
                return True
        return False

    def _row_matches_search(self, row, search_term):
        """Checks if a row matches the search term, including task data."""
        # Check main row data
        main_fields = ["traveler", "completed", "status"]
        for field in main_fields:
            if search_term in str(row.get(field, "")).lower():
                return True

        # Check individual task data (now includes tier)
        operations = row.get("operations", [])
        for operation in operations:
            operation_fields = ["task_description", "item", "tier", "quantity", "tag", "status"]
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
        elif sort_key == "status":
            # Sort by completion status: ✅ first, then ❌
            def completion_sort_key(x):
                status = str(x.get("status", ""))
                return 0 if status == "✅" else 1

            self.filtered_data.sort(key=completion_sort_key, reverse=self.sort_reverse)
        elif sort_key == "tier":

            def tier_sort_key(x):
                operations = x.get("operations", [])
                if operations:
                    # Use the first operation's tier for sorting the parent
                    tier = operations[0].get("tier", 0)
                    return int(tier) if isinstance(tier, (int, str)) and str(tier).isdigit() else 0
                return 0

            self.filtered_data.sort(key=tier_sort_key, reverse=self.sort_reverse)
        elif sort_key == "quantity":
            # Sort by numeric quantity (from child operations)
            def quantity_sort_key(x):
                operations = x.get("operations", [])
                if operations:
                    # Use the first operation's quantity for sorting the parent
                    qty_str = operations[0].get("quantity", "0")
                    return int(qty_str) if qty_str.isdigit() else 0
                return 0

            self.filtered_data.sort(key=quantity_sort_key, reverse=self.sort_reverse)
        elif sort_key == "tag":
            # Sort by item tag (from child operations)
            def tag_sort_key(x):
                operations = x.get("operations", [])
                if operations:
                    # Use the first operation's tag for sorting the parent
                    return operations[0].get("tag", "").lower()
                return ""

            self.filtered_data.sort(key=tag_sort_key, reverse=self.sort_reverse)
        elif sort_key == "item":
            # Sort by item name (from child operations)
            def item_sort_key(x):
                operations = x.get("operations", [])
                if operations:
                    # Use the first operation's item for sorting the parent
                    return operations[0].get("item", "").lower()
                return ""

            self.filtered_data.sort(key=item_sort_key, reverse=self.sort_reverse)
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
        """Renders the traveler tasks data with expandable traveler groups, PRESERVING expansion state."""
        # Save current expansion state before clearing
        self._save_current_expansion_state()

        # Clear the tree
        self.tree.delete(*self.tree.get_children())

        for row_data in self.filtered_data:
            traveler_name = row_data.get("traveler", "Unknown Traveler")
            completed_summary = row_data.get("completed", "")
            completion_status = row_data.get("status", "❌")
            operations = row_data.get("operations", [])
            is_expandable = row_data.get("is_expandable", False)
            traveler_id = row_data.get("traveler_id", "")

            # Create a stable identifier for expansion tracking
            expansion_key = f"traveler_{traveler_id}_{traveler_name}"

            # UPDATED: Prepare main row values for new column structure
            # Include completion status in the Item column for parent rows
            item_with_completion = f"Tasks ({completed_summary} completed)"
            values = [traveler_name, item_with_completion, "", "", "", completion_status]

            # Determine tag based on completion status
            if completion_status == "✅":
                tag = "completed"
            else:
                tag = "incomplete"

            if is_expandable and operations:
                # Create expandable parent row
                parent_id = self.tree.insert("", "end", values=values, tags=(tag,))

                # Check if this traveler should be expanded based on saved state
                should_expand = expansion_key in self.expansion_state

                # Add individual tasks as children
                for task_data in operations:
                    self._render_task_row(parent_id, task_data)

                # Apply expansion state
                if should_expand:
                    self.tree.item(parent_id, open=True)
            else:
                # Non-expandable row
                self.tree.insert("", "end", values=values, tags=(tag,))

        # Mark that we've had our first load
        if not self.has_had_first_load:
            self.has_had_first_load = True

    def _save_current_expansion_state(self):
        """Save the current expansion state of traveler groups."""
        if not self.has_had_first_load:
            return

        self.expansion_state = set()

        def check_item(item_id):
            values = self.tree.item(item_id, "values")
            if values and len(values) >= 1:
                traveler_name = values[0]

                # Find the corresponding data to get traveler_id
                for row_data in self.filtered_data:
                    if row_data.get("traveler", "") == traveler_name:
                        traveler_id = row_data.get("traveler_id", "")
                        expansion_key = f"traveler_{traveler_id}_{traveler_name}"

                        if self.tree.item(item_id, "open"):
                            self.expansion_state.add(expansion_key)
                        break

            for child_id in self.tree.get_children(item_id):
                check_item(child_id)

        for item_id in self.tree.get_children():
            check_item(item_id)

    def _render_task_row(self, parent_id, task_data):
        """UPDATED: Renders an individual task as a child row with new column structure."""
        task_description = task_data.get("task_description", "Unknown Task")
        item = task_data.get("item", "")
        tier = task_data.get("tier", 0)
        quantity = task_data.get("quantity", "")
        tag = task_data.get("tag", "")
        completion_status = task_data.get("status", "❌")

        # UPDATED: Prepare child values with new column structure (no task description shown)
        child_values = ["", item, quantity, str(tier) if tier > 0 else "", tag, completion_status]

        # Determine child tag
        if completion_status == "✅":
            child_tag = ("child", "child_completed")
        else:
            child_tag = ("child", "child_incomplete")

        # Insert the child row
        self.tree.insert(parent_id, "end", values=child_values, tags=child_tag)
