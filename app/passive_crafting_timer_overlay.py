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
        self.grid_rowconfigure(1, weight=1)     # Treeview - main content area
        self.grid_rowconfigure(2, weight=0)     # Button frame
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
            text="Passive Crafting Timer - Your Active Operations", 
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
        
        # Create a frame for the treeview to control its styling
        tree_frame = ctk.CTkFrame(self)
        tree_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew", columnspan=2)
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
            text="Loading...",
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
        # Save current expansion state before clearing
        self.save_expansion_state()
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not data:
            return
        
        # Sort parent groups by highest remaining time (READY items first, then by time)
        def sort_key(item):
            remaining_time = item.get('remaining_time', '')
            if remaining_time == "READY":
                return (0, 0)  # READY items first
            else:
                return (1, self.parse_time_to_seconds(remaining_time))
        
        sorted_data = sorted(data, key=sort_key)
        
        # Insert parent and child data into tree
        for parent_item in sorted_data:
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
