"""
Data path utilities for BitCraft Companion.

Handles the distinction between bundled read-only data (like data.db)
and user-writable data (like player_data.json) that needs to work
correctly in both development and EXE distribution modes.
"""

import os
import sys
import logging
from pathlib import Path


def get_bundled_data_directory():
    """
    Get the directory for bundled read-only data files like data.db.

    In development: Points to app/data/
    In EXE: Points to the bundled data directory within the EXE

    Returns:
        str: Path to bundled data directory (read-only)
    """
    if getattr(sys, "frozen", False):
        # Running as EXE - data is bundled relative to executable
        return os.path.join(os.path.dirname(sys.executable), "data")
    else:
        # Running in development - data is in app/data/
        return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))


def get_user_data_directory():
    """
    Get the directory for user-writable data files like player_data.json.

    This ensures files are writable in both development and EXE modes.
    Uses the OS-appropriate user data directory for the application.

    Returns:
        str: Path to user data directory (writable)
    """
    if getattr(sys, "frozen", False):
        # Running as EXE - use OS user data directory
        app_name = "BitCraftCompanion"

        if sys.platform == "win32":
            # Windows: %APPDATA%/BitCraftCompanion/
            base_dir = os.getenv("APPDATA")
        elif sys.platform == "darwin":
            # macOS: ~/Library/Application Support/BitCraftCompanion/
            base_dir = os.path.expanduser("~/Library/Application Support")
        else:
            # Linux: ~/.local/share/BitCraftCompanion/
            base_dir = os.path.expanduser("~/.local/share")

        user_data_dir = os.path.join(base_dir, app_name)

        # Ensure directory exists
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)
        return user_data_dir
    else:
        # Running in development - use app directory where player_data.json lives
        return os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def get_bundled_data_path(filename):
    """
    Get the full path to a bundled data file.

    Args:
        filename: Name of the data file (e.g., "data.db")

    Returns:
        str: Full path to the bundled data file
    """
    return os.path.join(get_bundled_data_directory(), filename)


def get_user_data_path(filename):
    """
    Get the full path to a user data file.

    Args:
        filename: Name of the user data file (e.g., "player_data.json")

    Returns:
        str: Full path to the user data file
    """
    return os.path.join(get_user_data_directory(), filename)


def ensure_user_data_directory():
    """
    Ensure the user data directory exists and is writable.

    Returns:
        bool: True if directory is accessible, False otherwise
    """
    try:
        user_dir = get_user_data_directory()
        Path(user_dir).mkdir(parents=True, exist_ok=True)

        # Test write access
        test_file = os.path.join(user_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)

        logging.info(f"User data directory ready: {user_dir}")
        return True

    except Exception as e:
        logging.error(f"Cannot access user data directory: {e}")
        return False


def migrate_user_data_files():
    """
    Migrate existing user data files from old locations to new user data directory.

    This helps with the transition from the old _get_data_directory() approach
    to the new proper user data handling.
    """
    try:
        old_data_dir = os.path.dirname(__file__)  # Old location
        new_data_dir = get_user_data_directory()  # New location

        files_to_migrate = ["player_data.json"]

        for filename in files_to_migrate:
            old_path = os.path.join(old_data_dir, filename)
            new_path = os.path.join(new_data_dir, filename)

            # Only migrate if old file exists and new file doesn't
            if os.path.exists(old_path) and not os.path.exists(new_path):
                try:
                    # Copy file to new location
                    import shutil

                    shutil.copy2(old_path, new_path)
                    logging.info(f"Migrated {filename} to user data directory")

                    # Optionally remove old file (commented out for safety)
                    # os.remove(old_path)

                except Exception as e:
                    logging.warning(f"Could not migrate {filename}: {e}")

    except Exception as e:
        logging.error(f"Error during user data migration: {e}")


# Initialize on import
if __name__ != "__main__":
    # Ensure user data directory is ready when module is imported
    ensure_user_data_directory()
