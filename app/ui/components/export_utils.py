"""
Export utilities for BitCraft Companion.

Provides functions to export inventory and other data to CSV format.
"""

import logging
import csv
from datetime import datetime


def export_inventory_to_csv(inventory_data, file_path):
    """
    Export inventory data to CSV format.

    Args:
        inventory_data: List of inventory items from ClaimInventoryTab.all_data
        file_path: Path where to save the CSV file

    Returns:
        bool: True if export succeeded, False otherwise
    """
    try:
        if not inventory_data:
            logging.warning("No inventory data provided for export")
            return False

        # Define headers to match the real inventory data format
        headers = ["Name", "Tier", "Quantity", "Tag", "Containers"]

        # Open CSV file for writing
        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write headers
            writer.writerow(headers)

            # Write data rows
            for item in inventory_data:
                if isinstance(item, dict):
                    # Extract values using the correct field names from inventory tab
                    name = item.get("name", "")
                    tier = item.get("tier", "")
                    quantity = item.get("quantity", "")
                    tag = item.get("tag", "")
                    containers = item.get("containers", {})

                    # Format containers dict into readable string
                    if isinstance(containers, dict):
                        if len(containers) == 0:
                            containers_str = ""
                        elif len(containers) == 1:
                            # Single container: "Container Name: 123"
                            container_name, container_qty = next(iter(containers.items()))
                            containers_str = f"{container_name}: {container_qty}"
                        else:
                            # Multiple containers: "Container1: 50, Container2: 25"
                            container_strs = [f"{name}: {qty}" for name, qty in containers.items()]
                            containers_str = ", ".join(container_strs)
                    else:
                        containers_str = str(containers) if containers else ""

                    # Write the row data
                    row_values = [name, tier, quantity, tag, containers_str]
                    writer.writerow(row_values)
                else:
                    # Fallback for non-dict items
                    logging.warning(f"Unexpected item format: {type(item)} - {item}")
                    writer.writerow([str(item)])

        logging.info(f"Successfully exported {len(inventory_data)} inventory items to: {file_path}")
        return True

    except Exception as e:
        logging.error(f"Error exporting inventory data to CSV: {e}")
        return False


def export_multiple_sheets_to_csv(sheets_data, base_file_path):
    """
    Export multiple sheets of data to CSV format.
    Creates separate CSV files for each sheet.

    Args:
        sheets_data: Dictionary with sheet_name -> data mappings
        base_file_path: Base path for CSV files (sheet names will be appended)

    Returns:
        bool: True if export succeeded, False otherwise
    """
    try:
        if not sheets_data:
            logging.warning("No sheets data provided for export")
            return False

        # Extract base path and extension
        if base_file_path.lower().endswith(".csv"):
            base_path = base_file_path[:-4]
        else:
            base_path = base_file_path

        exported_files = []

        # Create CSV files for each sheet
        for sheet_name, sheet_data in sheets_data.items():
            if not sheet_data:
                continue

            # Create file path for this sheet
            safe_sheet_name = "".join(c for c in sheet_name if c.isalnum() or c in (" ", "-", "_")).rstrip()
            file_path = f"{base_path}_{safe_sheet_name}.csv"

            # Determine headers
            if isinstance(sheet_data, list) and len(sheet_data) > 0:
                if isinstance(sheet_data[0], dict):
                    headers = list(sheet_data[0].keys())
                elif hasattr(sheet_data[0], "__iter__") and not isinstance(sheet_data[0], str):
                    headers = [f"Column_{i+1}" for i in range(len(sheet_data[0]))]
                else:
                    headers = ["Value"]
            else:
                headers = ["Value"]

            # Write CSV file
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write headers
                writer.writerow(headers)

                # Write data
                for item in sheet_data:
                    if isinstance(item, dict):
                        row_values = [item.get(header, "") for header in headers]
                        writer.writerow(row_values)
                    elif hasattr(item, "__iter__") and not isinstance(item, str):
                        row_values = list(item)[: len(headers)]
                        # Pad with empty strings if needed
                        while len(row_values) < len(headers):
                            row_values.append("")
                        writer.writerow(row_values)
                    else:
                        writer.writerow([item])

            exported_files.append(file_path)

        logging.info(f"Successfully exported {len(sheets_data)} sheets to {len(exported_files)} CSV files")
        return True

    except Exception as e:
        logging.error(f"Error exporting multiple sheets to CSV: {e}")
        return False
