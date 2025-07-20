import customtkinter as ctk
import logging
import os
from logging.handlers import RotatingFileHandler

from overlay import BitCraftOverlay as LoginOverlay

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def configure_logging():
    """Configure logging with file rotation and console output.

    Sets up rotating file logging that writes to ./logs/bc-companion.log
    with automatic rotation when the file reaches 5MB. Also enables
    console output for real-time monitoring.

    The log files are rotated with a maximum of 1 backup file maintained.
    All logs use UTF-8 encoding for proper character support.
    """
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create rotating file handler (5MB max, 1 backup file)
    log_file = os.path.join(log_dir, "bc-companion.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8")  # 5MB

    # Configure logging with both file and console output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[file_handler, logging.StreamHandler()],
    )


if __name__ == "__main__":
    configure_logging()
    app = LoginOverlay()
    app.mainloop()
