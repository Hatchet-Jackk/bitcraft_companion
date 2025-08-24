"""
LoadingStateMixin for BitCraft Companion.

Provides loading state management for tabs that need to show loading overlays
during data processing and async rendering operations.
"""

import logging
from typing import Optional
from app.ui.components.loading_overlay import LoadingOverlay


class LoadingStateMixin:
    """
    Mixin class that provides loading state management for tab classes.
    
    Classes that use this mixin should:
    1. Call _setup_loading_state() during initialization
    2. Use _show_loading() / _hide_loading() to control loading states
    3. Optionally override _get_loading_message() for custom messages
    """
    
    def _setup_loading_state(self):
        """Set up loading state management."""
        self.loading_overlay: Optional[LoadingOverlay] = None
        self.is_loading = False
        self._loading_message = "Loading..."
        self.logger = logging.getLogger(__name__)
    
    def _show_loading(self, message: Optional[str] = None):
        """
        Show loading overlay with optional custom message.
        
        Args:
            message: Custom loading message (defaults to tab-specific message)
        """
        if self.is_loading:
            # Already showing loading - just update message if needed
            if message and self.loading_overlay:
                self.loading_overlay.update_message(message)
            return
            
        try:
            # Get the loading message
            loading_message = message or self._get_loading_message()
            
            # Create and show loading overlay
            self.loading_overlay = LoadingOverlay(self.winfo_toplevel(), loading_message)
            self.is_loading = True
            
            self.logger.debug(f"[{self.__class__.__name__}] Showing loading overlay: {loading_message}")
            
        except Exception as e:
            self.logger.error(f"Error showing loading overlay: {e}")
    
    def _hide_loading(self):
        """Hide the loading overlay."""
        if not self.is_loading:
            return
            
        try:
            if self.loading_overlay:
                self.loading_overlay.close_overlay()
                self.loading_overlay = None
            
            self.is_loading = False
            self.logger.debug(f"[{self.__class__.__name__}] Hiding loading overlay")
            
        except Exception as e:
            self.logger.error(f"Error hiding loading overlay: {e}")
    
    def _update_loading_message(self, message: str):
        """
        Update the loading message without hiding/showing the overlay.
        
        Args:
            message: New loading message
        """
        if self.is_loading and self.loading_overlay:
            try:
                self.loading_overlay.update_message(message)
            except Exception as e:
                self.logger.error(f"Error updating loading message: {e}")
    
    def _get_loading_message(self) -> str:
        """
        Get the loading message for this tab.
        Override this method in subclasses for custom messages.
        
        Returns:
            Loading message string
        """
        # Try to get tab name if available
        tab_name = getattr(self, '_tab_name', self.__class__.__name__.replace('Tab', ''))
        return f"Loading {tab_name}..."
    
    def _cleanup_loading_state(self):
        """Clean up loading state resources."""
        try:
            self._hide_loading()
        except Exception as e:
            self.logger.error(f"Error cleaning up loading state: {e}")