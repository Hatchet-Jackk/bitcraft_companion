"""
Centralized Treeview styling for BitCraft Companion tabs.

Provides consistent dark theme styling for all Treeview components across tabs,
eliminating code duplication and ensuring visual consistency.
"""

from tkinter import ttk


class TreeviewStyles:
    """Centralized Treeview styling utility for consistent UI theming."""
    
    # Color constants for dark theme
    COLORS = {
        'background': '#2a2d2e',
        'foreground': 'white', 
        'field_background': '#343638',
        'selected_background': '#1f6aa5',
        'header_background': '#1e2124',
        'header_foreground': '#e0e0e0',
        'header_active': '#2c5d8f',
        'scrollbar_background': '#1e2124',
        'scrollbar_trough': '#2a2d2e',
        'scrollbar_arrow': '#666',
        'menu_background': '#2a2d2e',
        'menu_foreground': 'white',
        'menu_active': '#1f6aa5',
        'child_row_background': '#3a3a3a',
        'empty_foreground': '#888888'
    }
    
    @classmethod
    def apply_treeview_style(cls, style: ttk.Style):
        """Apply standard Treeview styling."""
        style.theme_use("default")
        
        # Configure main Treeview
        style.configure(
            "Treeview",
            background=cls.COLORS['background'],
            foreground=cls.COLORS['foreground'],
            fieldbackground=cls.COLORS['field_background'],
            borderwidth=0,
            rowheight=28,
            relief="flat",
        )
        style.map("Treeview", background=[("selected", cls.COLORS['selected_background'])])
        
        # Configure headers
        style.configure(
            "Treeview.Heading",
            background=cls.COLORS['header_background'],
            foreground=cls.COLORS['header_foreground'],
            font=("Segoe UI", 11, "normal"),
            padding=(8, 6),
            relief="flat",
            borderwidth=0,
        )
        style.map("Treeview.Heading", background=[("active", cls.COLORS['header_active'])])
    
    @classmethod
    def apply_scrollbar_style(cls, style: ttk.Style, tab_name: str):
        """
        Apply custom scrollbar styling with unique style names.
        
        Args:
            style: ttk.Style instance
            tab_name: Name of the tab (e.g., "ActiveCrafting", "PassiveCrafting")
        
        Returns:
            tuple: (vertical_style_name, horizontal_style_name)
        """
        v_style = f"{tab_name}.Vertical.TScrollbar"
        h_style = f"{tab_name}.Horizontal.TScrollbar"
        
        # Configure vertical scrollbar
        style.configure(
            v_style,
            background=cls.COLORS['scrollbar_background'],
            borderwidth=0,
            arrowcolor=cls.COLORS['scrollbar_arrow'],
            troughcolor=cls.COLORS['scrollbar_trough'],
            darkcolor=cls.COLORS['scrollbar_background'],
            lightcolor=cls.COLORS['scrollbar_background'],
            width=12,
        )
        
        # Configure horizontal scrollbar
        style.configure(
            h_style,
            background=cls.COLORS['scrollbar_background'],
            borderwidth=0,
            arrowcolor=cls.COLORS['scrollbar_arrow'],
            troughcolor=cls.COLORS['scrollbar_trough'],
            darkcolor=cls.COLORS['scrollbar_background'],
            lightcolor=cls.COLORS['scrollbar_background'],
            height=12,
        )
        
        # Configure state-specific scrollbar colors for both orientations
        scrollbar_state_map = {
            'background': [
                ("active", cls.COLORS['scrollbar_background']),
                ("pressed", cls.COLORS['scrollbar_background']),
                ("disabled", cls.COLORS['scrollbar_background']),
                ("!active", cls.COLORS['scrollbar_background'])
            ],
            'troughcolor': [
                ("active", cls.COLORS['scrollbar_trough']),
                ("pressed", cls.COLORS['scrollbar_trough']),
                ("disabled", cls.COLORS['scrollbar_trough']),
                ("!active", cls.COLORS['scrollbar_trough'])
            ],
            'arrowcolor': [
                ("active", cls.COLORS['scrollbar_arrow']),
                ("pressed", cls.COLORS['scrollbar_arrow']),
                ("disabled", cls.COLORS['scrollbar_arrow']),
                ("!active", cls.COLORS['scrollbar_arrow'])
            ]
        }
        
        style.map(v_style, **scrollbar_state_map)
        style.map(h_style, **scrollbar_state_map)
        
        return v_style, h_style
    
    @classmethod
    def get_menu_style_config(cls):
        """Get consistent menu styling configuration."""
        return {
            'tearoff': 0,
            'background': cls.COLORS['menu_background'],
            'foreground': cls.COLORS['menu_foreground'],
            'activebackground': cls.COLORS['menu_active']
        }
    
    @classmethod
    def configure_tree_tags(cls, tree: ttk.Treeview):
        """Configure common tree tags with consistent styling."""
        tree.tag_configure(
            "child", 
            background=cls.COLORS['child_row_background']
        )
        tree.tag_configure(
            "empty", 
            background=cls.COLORS['background'], 
            foreground=cls.COLORS['empty_foreground']
        )
        tree.tag_configure(
            "incomplete", 
            background=cls.COLORS['background'], 
            foreground=cls.COLORS['foreground']
        )
        tree.tag_configure(
            "partial", 
            background=cls.COLORS['background'], 
            foreground=cls.COLORS['foreground']
        )