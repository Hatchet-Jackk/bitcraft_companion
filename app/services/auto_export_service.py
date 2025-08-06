"""
Auto Export Service for scheduled inventory claim table exports.

Provides timer-based automatic exporting of inventory data to user-specified location.
"""

import logging
import threading
import time
import os
from datetime import datetime
from tkinter import filedialog
from typing import Optional, Callable


class AutoExportService:
    """
    Service for automatically exporting inventory claim table data at regular intervals.

    Uses the existing export infrastructure to create timestamped CSV files
    in a user-specified directory.
    """

    def __init__(self, app):
        """
        Initialize the AutoExportService.

        Args:
            app: Main application instance for accessing data service and inventory data
        """
        self.app = app
        self.is_running = False
        self.export_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Export configuration
        self.export_directory: Optional[str] = None
        self.filename: str = "inventory_export"
        self.interval_minutes: int = 5

        # Callbacks for UI updates
        self.on_export_success: Optional[Callable[[str], None]] = None
        self.on_export_error: Optional[Callable[[str], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None

        logging.info("AutoExportService initialized")

    def set_export_directory(self, directory: str = None) -> bool:
        """
        Set the directory where exported files will be saved.

        Args:
            directory: Directory path, or None to show file dialog

        Returns:
            True if directory was set successfully, False otherwise
        """
        try:
            if directory is None:
                # Show directory selection dialog
                directory = filedialog.askdirectory(title="Select Export Directory", mustexist=True)

            if not directory:
                return False

            if not os.path.exists(directory):
                logging.error(f"Export directory does not exist: {directory}")
                return False

            if not os.access(directory, os.W_OK):
                logging.error(f"Export directory is not writable: {directory}")
                return False

            self.export_directory = directory
            logging.info(f"Export directory set to: {directory}")
            return True

        except Exception as e:
            logging.error(f"Error setting export directory: {e}")
            return False

    def set_filename(self, filename: str):
        """
        Set the base filename for exported files (without extension).

        Args:
            filename: Base filename (extension will be added automatically)
        """
        # Remove extension if user included it
        if filename.endswith((".csv", ".xlsx", ".xls")):
            filename = os.path.splitext(filename)[0]

        self.filename = filename
        logging.info(f"Export filename set to: {filename}")

    def set_interval(self, minutes: int):
        """
        Set the export interval in minutes.

        Args:
            minutes: Export interval (1, 5, or 10 minutes)
        """
        if minutes not in [1, 5, 10]:
            logging.warning(f"Invalid interval: {minutes}. Using 5 minutes.")
            minutes = 5

        self.interval_minutes = minutes
        logging.info(f"Export interval set to: {minutes} minutes")

    def start_auto_export(self) -> bool:
        """
        Start the automatic export process.

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            logging.warning("Auto export is already running")
            return False

        if not self.export_directory:
            logging.error("Cannot start auto export: No export directory set")
            if self.on_export_error:
                self.on_export_error("No export directory set")
            return False

        try:
            self.is_running = True
            self.stop_event.clear()

            # Start the export thread
            self.export_thread = threading.Thread(target=self._export_loop, daemon=True, name="AutoExportThread")
            self.export_thread.start()

            logging.info(f"Auto export started - exporting every {self.interval_minutes} minutes to {self.export_directory}")
            if self.on_status_change:
                self.on_status_change(f"Auto export running - every {self.interval_minutes} min")

            return True

        except Exception as e:
            logging.error(f"Error starting auto export: {e}")
            self.is_running = False
            if self.on_export_error:
                self.on_export_error(f"Failed to start: {e}")
            return False

    def stop_auto_export(self):
        """Stop the automatic export process."""
        if not self.is_running:
            logging.info("Auto export is not running")
            return

        try:
            logging.info("Stopping auto export...")
            self.is_running = False
            self.stop_event.set()

            # Wait for thread to finish (with timeout)
            if self.export_thread and self.export_thread.is_alive():
                self.export_thread.join(timeout=2.0)

                if self.export_thread.is_alive():
                    logging.warning("Auto export thread did not stop within timeout")
                else:
                    logging.info("Auto export thread stopped successfully")

            self.export_thread = None

            if self.on_status_change:
                self.on_status_change("Auto export stopped")

        except Exception as e:
            logging.error(f"Error stopping auto export: {e}")

    def _export_loop(self):
        """Main export loop running in background thread."""
        try:
            # Perform initial export immediately
            self._perform_export()

            # Then continue with regular intervals
            interval_seconds = self.interval_minutes * 60

            while not self.stop_event.is_set():
                # Wait for the interval or stop signal
                if self.stop_event.wait(timeout=interval_seconds):
                    break  # Stop event was set

                # Perform the export
                self._perform_export()

        except Exception as e:
            logging.error(f"Error in export loop: {e}")
            if self.on_export_error:
                self.on_export_error(f"Export loop error: {e}")
        finally:
            self.is_running = False
            logging.info("Auto export loop ended")

    def _perform_export(self):
        """Perform a single export operation."""
        try:
            if not self.app or not hasattr(self.app, "data_service"):
                logging.error("Cannot export: No data service available")
                if self.on_export_error:
                    self.on_export_error("No data service available")
                return

            # Generate timestamped filename
            export_filename = f"{self.filename}.csv"
            export_path = os.path.join(self.export_directory, export_filename)

            # Get current inventory data from the application
            inventory_data = self._get_current_inventory_data()

            if not inventory_data:
                logging.warning("No inventory data available for export")
                if self.on_export_error:
                    self.on_export_error("No inventory data available")
                return

            # Export to CSV using existing export infrastructure
            # The inventory data is a list, so we need to use the single sheet function
            from ..ui.components.export_utils import export_inventory_to_csv

            success = export_inventory_to_csv(inventory_data, export_path)

            if success:
                logging.info(f"Successfully exported inventory data to: {export_path}")
                if self.on_export_success:
                    self.on_export_success(export_path)
            else:
                logging.error(f"Failed to export inventory data to: {export_path}")
                if self.on_export_error:
                    self.on_export_error(f"Export failed: {export_filename}")

        except Exception as e:
            logging.error(f"Error performing export: {e}")
            if self.on_export_error:
                self.on_export_error(f"Export error: {e}")

    def _get_current_inventory_data(self):
        """
        Get current inventory data from the application's data service.

        Returns:
            Current inventory data in the format expected by export_multiple_sheets_to_csv
        """
        try:
            # Access the inventory data through the main window's tabs
            if hasattr(self.app, "tabs") and "Claim Inventory" in self.app.tabs:
                inventory_tab = self.app.tabs["Claim Inventory"]
                if hasattr(inventory_tab, "all_data") and inventory_tab.all_data:
                    logging.info(f"Found {len(inventory_tab.all_data)} inventory items to export")
                    return inventory_tab.all_data

            # Alternative: Try to access through different path structures
            if hasattr(self.app, "main_window") and hasattr(self.app.main_window, "tabs"):
                main_tabs = self.app.main_window.tabs
                if "Claim Inventory" in main_tabs:
                    inventory_tab = main_tabs["Claim Inventory"]
                    if hasattr(inventory_tab, "all_data") and inventory_tab.all_data:
                        logging.info(f"Found {len(inventory_tab.all_data)} inventory items to export (via main_window)")
                        return inventory_tab.all_data

            # Check if app IS the main window (based on the code structure)
            if hasattr(self.app, "tabs") and hasattr(self.app, "tab_content_area"):
                # The app parameter might actually be the MainWindow instance
                if "Claim Inventory" in self.app.tabs:
                    inventory_tab = self.app.tabs["Claim Inventory"]
                    if hasattr(inventory_tab, "all_data") and inventory_tab.all_data:
                        logging.info(f"Found {len(inventory_tab.all_data)} inventory items to export (direct app access)")
                        return inventory_tab.all_data

            # No real data found
            logging.warning("Could not access current inventory data - no data available")
            logging.info("Available app attributes: " + ", ".join(dir(self.app)))
            if hasattr(self.app, "tabs"):
                logging.info("Available tabs: " + ", ".join(self.app.tabs.keys()))
            return None

        except Exception as e:
            logging.error(f"Error getting current inventory data: {e}")
            return None

    def get_status(self) -> dict:
        """
        Get current status of the auto export service.

        Returns:
            Dictionary with current status information
        """
        return {
            "is_running": self.is_running,
            "export_directory": self.export_directory,
            "filename": self.filename,
            "interval_minutes": self.interval_minutes,
            "thread_alive": self.export_thread.is_alive() if self.export_thread else False,
        }
