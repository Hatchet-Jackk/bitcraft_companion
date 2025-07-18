import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import Optional
from datetime import datetime
from abc import ABC, abstractmethod


class BaseOverlay(ctk.CTkToplevel, ABC):
    """Base class for overlay windows with consistent styling and behavior."""
    
    def __init__(self, parent, title: str, min_width: int = 700, min_height: int = 400, 
                 initial_width: int = 800, initial_height: int = 500):
        super().__init__(parent)
        
        self.title(title)
        
        # Window sizing and positioning
        self.update_idletasks()
        x = parent.winfo_x() + parent.winfo_width() + 20
        y = parent.winfo_y()
        self.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
        self.minsize(min_width, min_height)
        self.resizable(True, True)
        
        # Window properties
        self.transient(parent)
        self.attributes('-topmost', True)
        
                # Configure window grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)  # For scrollbars
        self.grid_rowconfigure(0, weight=0)     # Controls frame
        self.grid_rowconfigure(1, weight=0)     # Content row 1 (search, etc.)
        self.grid_rowconfigure(2, weight=1)     # Main content area (treeview)
        self.grid_rowconfigure(3, weight=0)     # Status bar
        
        # Auto-refresh settings (can be overridden by subclasses)
        self.auto_refresh_enabled = True
        self.refresh_interval = 15  # seconds
        self.refresh_job = None
        self.last_update_time = None
        
        # Setup UI components
        self.setup_base_ui()
        
        # Abstract method for subclass-specific UI setup
        self.setup_content_ui()
        
        # Setup status bar
        self.setup_status_bar()
        
        # Allow subclasses to add custom status bar content
        if hasattr(self, 'setup_status_bar_content'):
            self.setup_status_bar_content()
    
    def setup_base_ui(self):
        """Setup the base UI components (controls frame)."""
        # Controls frame at the top
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew", columnspan=2)
        self.controls_frame.grid_columnconfigure(0, weight=1)
        self.controls_frame.grid_columnconfigure(1, weight=0)
        self.controls_frame.grid_columnconfigure(2, weight=0)
        self.controls_frame.grid_columnconfigure(3, weight=0)
        self.controls_frame.grid_columnconfigure(4, weight=0)
        self.controls_frame.grid_columnconfigure(5, weight=0)
        
                # Title label (can be customized by subclasses)
        self.title_label = ctk.CTkLabel(
            self.controls_frame,
            text=self.title(),
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # Always on Top switch
        self.always_on_top_switch = ctk.CTkSwitch(
            self.controls_frame, 
            text="Always on Top",
            command=self._toggle_always_on_top
        )
        self.always_on_top_switch.grid(row=0, column=1, padx=10, pady=5, sticky="e")
        self.always_on_top_switch.select()
        
        # Auto-refresh switch
        self.auto_refresh_switch = ctk.CTkSwitch(
            self.controls_frame,
            text="Auto-refresh",
            command=self.toggle_auto_refresh
        )
        self.auto_refresh_switch.grid(row=0, column=2, padx=10, pady=5, sticky="e")
        self.auto_refresh_switch.select()
        
        # Refresh button
        self.refresh_button = ctk.CTkButton(
            self.controls_frame,
            text="Refresh",
            width=80,
            command=self.refresh_data
        )
        self.refresh_button.grid(row=0, column=3, padx=10, pady=5, sticky="e")
        
        # Save button (optional - can be enabled by subclasses)
        self.save_button = None
        if hasattr(self, 'enable_save_button') and self.enable_save_button:
            self.save_button = ctk.CTkButton(
                self.controls_frame,
                text="Save",
                width=80,
                command=self._on_save_clicked if hasattr(self, '_on_save_clicked') else None
            )
            self.save_button.grid(row=0, column=4, padx=10, pady=5, sticky="e")
    
    def setup_status_bar(self):
        """Setup the status bar at the bottom."""
        # Status bar frame
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew", columnspan=2)
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_frame.grid_columnconfigure(1, weight=0)
        self.status_frame.grid_columnconfigure(2, weight=0)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=11)
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # Last updated label
        self.last_updated_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.last_updated_label.grid(row=0, column=1, padx=10, pady=5, sticky="e")
    
    def setup_treeview_styling(self):
        """Setup consistent treeview styling for dark theme."""
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
    
    def create_treeview_frame(self, row=2):
        """Create and return a properly configured treeview frame."""
        tree_frame = ctk.CTkFrame(self)
        tree_frame.grid(row=row, column=0, padx=10, pady=(0, 10), sticky="nsew", columnspan=2)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        return tree_frame
    
    def add_vertical_scrollbar(self, tree_frame, treeview):
        """Add a vertical scrollbar to the treeview."""
        vsb = ctk.CTkScrollbar(tree_frame, command=treeview.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=10)
        treeview.configure(yscrollcommand=vsb.set)
        return vsb
    
    def _toggle_always_on_top(self):
        """Toggle always on top setting."""
        if self.always_on_top_switch.get():
            self.attributes('-topmost', True)
        else:
            self.attributes('-topmost', False)
    
    def update_status(self, message: str, color: str = "white"):
        """Update the status label with consistent color coding."""
        self.status_label.configure(text=message, text_color=color)
    
    def update_timestamp(self):
        """Update the last updated timestamp."""
        self.last_update_time = datetime.now()
        self.last_updated_label.configure(text=f"Last updated: {self.last_update_time.strftime('%H:%M:%S')}")
    
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
        self.auto_refresh_enabled = self.auto_refresh_switch.get()
        
        if self.auto_refresh_enabled:
            self.start_auto_refresh()
        else:
            if self.refresh_job:
                self.after_cancel(self.refresh_job)
                self.refresh_job = None
    
    def hide_auto_refresh_controls(self):
        """Hide auto-refresh controls if not needed by subclass."""
        self.auto_refresh_switch.grid_forget()
        self.refresh_button.grid_forget()
    
    def hide_search_controls(self):
        """Hide search controls if not needed by subclass."""
        # This can be overridden by subclasses that don't need search
        pass
    
    def set_title_text(self, text: str):
        """Update the title label text."""
        self.title_label.configure(text=text)
    
    # Abstract methods that subclasses must implement
    @abstractmethod
    def setup_content_ui(self):
        """Setup the main content area of the overlay."""
        pass
    
    @abstractmethod
    def refresh_data(self):
        """Refresh the data displayed in the overlay."""
        pass
    
    def on_closing(self):
        """Handle window closing - can be overridden by subclasses."""
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None
    
    def destroy(self):
        """Override destroy to ensure proper cleanup."""
        self.on_closing()
        super().destroy()
