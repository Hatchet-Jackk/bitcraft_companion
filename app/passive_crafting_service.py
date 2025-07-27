import logging
from typing import List, Dict
import re
import time
from datetime import datetime, timedelta

# Type hints for clarity
from client import BitCraft
from claim import Claim


class PassiveCraftingService:
    """Service to handle passive crafting status and data processing."""

    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim, reference_data: dict):
        """Initializes the service with its dependencies."""
        self.client = bitcraft_client
        self.claim = claim_instance

        # --- Injected Reference Data ---
        self.crafting_recipes = {r["id"]: r for r in reference_data.get("crafting_recipe_desc", [])}
        # Add other reference data if needed by this service

    def get_subscription_queries(self, building_ids: List[str]) -> List[str]:
        """Returns a list of SQL query strings for subscribing to passive crafting updates."""
        if not building_ids:
            return []

        logging.info(f"Generating passive crafting subscription queries for {len(building_ids)} buildings.")
        return [f"SELECT * FROM passive_craft_state WHERE building_entity_id = '{bid}';" for bid in building_ids]

    def parse_crafting_message(self, db_update: dict) -> bool:
        """
        Parses a database update message to check if it's relevant to passive crafting.
        """
        if "passive_craft_state" in str(db_update):
            logging.info("Received a passive crafting update.")
            # Here you would typically trigger a refresh of crafting data
            return True
        return False

    # Other methods like calculate_remaining_time, format_time, etc. remain unchanged...
    def calculate_remaining_time(self, crafting_entry: Dict) -> str:
        """Calculate remaining time for a crafting operation."""
        try:
            status = crafting_entry.get("status")
            if status and isinstance(status, list) and status[0] == 2:
                return "READY"

            recipe_id = crafting_entry.get("recipe_id")
            if not recipe_id or recipe_id not in self.crafting_recipes:
                return "Unknown"

            recipe = self.crafting_recipes[recipe_id]
            duration_seconds = recipe.get("time_requirement", 0)

            timestamp_data = crafting_entry.get("timestamp")
            if not timestamp_data:
                return f"~{self.format_time(duration_seconds)}"

            timestamp_micros = timestamp_data.get("__timestamp_micros_since_unix_epoch__")
            if not timestamp_micros:
                return f"~{self.format_time(duration_seconds)}"

            start_time = timestamp_micros / 1_000_000
            elapsed_time = time.time() - start_time
            remaining_time = duration_seconds - elapsed_time

            if remaining_time <= 1:
                return "READY"

            return self.format_time(remaining_time)

        except Exception as e:
            logging.error(f"Error calculating remaining time: {e}")
            return "Error"

    def format_time(self, seconds: float) -> str:
        """Format seconds into a human-readable time string."""
        if seconds <= 0:
            return "READY"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
