"""
Notification service for BitCraft Companion.

Handles showing craft completion notifications with optional sound alerts.
Manages notification settings and coordinates with the notification window.
"""

import logging
import os
import threading
from typing import Optional, Dict, Any

# Platform-specific imports (sound handled by Windows natively)

# Native Windows toast notification import
try:
    from win11toast import toast
    NATIVE_TOAST_AVAILABLE = True
except ImportError:
    NATIVE_TOAST_AVAILABLE = False
    # Fallback to custom notification window if win11toast not available
    try:
        from app.ui.components.notification_window import NotificationWindow
    except ImportError:
        NotificationWindow = None


class NotificationService:
    """
    Service for managing craft completion notifications.
    
    Features:
    - Pop-up notifications for passive and active craft completions
    - Optional sound notifications
    - Settings-based control of notification types
    - Auto-dismiss notifications
    """
    
    def __init__(self, main_app):
        """
        Initialize the notification service.
        
        Args:
            main_app: Reference to the main application window
        """
        self.main_app = main_app
        self.settings = self._load_notification_settings()
        
        logging.info("NotificationService initialized")
    
    def _load_notification_settings(self) -> Dict[str, Any]:
        """Load notification settings from app configuration."""
        try:
            # Default settings
            default_settings = {
                "passive_crafts_enabled": True,
                "active_crafts_enabled": True,
            }
            
            # TODO: Load from actual player_data.json when persistence is implemented
            return default_settings
            
        except Exception as e:
            logging.error(f"Error loading notification settings: {e}")
            return {
                "passive_crafts_enabled": True,
                "active_crafts_enabled": True,
            }
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """
        Update notification settings.
        
        Args:
            new_settings: Dictionary with notification setting updates
        """
        try:
            self.settings.update(new_settings)
            logging.info(f"Notification settings updated: {new_settings}")
            
        except Exception as e:
            logging.error(f"Error updating notification settings: {e}")
    
    def show_passive_craft_notification(self, item_name: str, quantity: int = 1):
        """
        Show a notification for completed passive crafting operations.
        
        Args:
            item_name: Name of the crafted item
            quantity: Number of items completed
        """
        try:
            if not self.settings.get("passive_crafts_enabled", True):
                return
            
            title = "Passive Craft Complete!"
            message = f"{quantity}x {item_name} ready!" if quantity > 1 else f"{item_name} is ready!"
            icon = "⚗️"
            
            self._show_notification(title, message, icon)
                
            logging.info(f"Passive craft notification shown: {quantity}x {item_name}")
            
        except Exception as e:
            logging.error(f"Error showing passive craft notification: {e}")
    
    def show_active_craft_notification(self, item_name: str, quantity: int = 1):
        """
        Show a notification for completed active crafting operations.
        
        Args:
            item_name: Name of the crafted item
            quantity: Number of items completed
        """
        try:
            if not self.settings.get("active_crafts_enabled", True):
                return
            
            title = "Active Craft Complete!"
            message = f"{quantity}x {item_name} ready!" if quantity > 1 else f"{item_name} is ready!"
            icon = "🔨"
            
            self._show_notification(title, message, icon)
                
            logging.info(f"Active craft notification shown: {quantity}x {item_name}")
            
        except Exception as e:
            logging.error(f"Error showing active craft notification: {e}")
    
    def show_test_notification(self):
        """Show a test notification for settings verification."""
        try:
            title = "Test Notification"
            message = "This is a test craft completion notification!"
            icon = "🧪"
            
            self._show_notification(title, message, icon)
                
            logging.info("Test notification shown")
            
        except Exception as e:
            logging.error(f"Error showing test notification: {e}")
    
    def _show_notification(self, title: str, message: str, icon: str):
        """
        Show the notification using native Windows toasts or fallback to custom window.
        Runs in a separate thread to prevent UI freezing.
        
        Args:
            title: Notification title
            message: Notification message
            icon: Icon/emoji for the notification
        """
        def _show_notification_thread():
            """Thread function to show notification without blocking UI."""
            try:
                if NATIVE_TOAST_AVAILABLE:
                    # Use native Windows toast notification
                    toast(
                        title=title,
                        body=message,
                        duration='short',  # 'short' = 7 seconds, 'long' = 25 seconds
                        app_id='BitCraft Companion'
                    )
                    logging.debug(f"Native toast notification shown: {title}")
                elif NotificationWindow:
                    # Fallback to custom notification window (must run on main thread)
                    # Schedule on main thread using after()
                    if hasattr(self.main_app, 'after'):
                        self.main_app.after(0, lambda: self._show_custom_notification(title, message, icon))
                    else:
                        logging.info(f"NOTIFICATION: {title} - {message}")
                else:
                    # Ultimate fallback - just log the notification
                    logging.info(f"NOTIFICATION: {title} - {message}")
                
            except Exception as e:
                logging.error(f"Error showing notification: {e}")
                # Ultimate fallback - just log the notification
                logging.info(f"NOTIFICATION: {title} - {message}")
        
        # Run notification in a separate daemon thread to prevent UI blocking
        notification_thread = threading.Thread(target=_show_notification_thread, daemon=True)
        notification_thread.start()
    
    def _show_custom_notification(self, title: str, message: str, icon: str):
        """
        Show custom notification window on main thread.
        
        Args:
            title: Notification title
            message: Notification message
            icon: Icon/emoji for the notification
        """
        try:
            if NotificationWindow:
                notification = NotificationWindow(
                    parent=self.main_app,
                    title=title,
                    message=message,
                    icon=icon
                )
                logging.debug(f"Custom notification window shown: {title}")
            else:
                logging.info(f"NOTIFICATION: {title} - {message}")
                
        except Exception as e:
            logging.error(f"Error showing custom notification: {e}")
            logging.info(f"NOTIFICATION: {title} - {message}")
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Get current notification settings.
        
        Returns:
            Dictionary with current notification settings
        """
        return self.settings.copy()