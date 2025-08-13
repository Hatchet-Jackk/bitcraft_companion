"""
Data processors for handling SpacetimeDB table updates.

Each processor is responsible for handling specific table types and
converting raw database updates into UI-ready data.
"""

from .base_processor import BaseProcessor
from .inventory_processor import InventoryProcessor
from .crafting_processor import CraftingProcessor
from .tasks_processor import TasksProcessor
from .claims_processor import ClaimsProcessor
from .active_crafting_processor import ActiveCraftingProcessor
from .reference_data_processor import ReferenceDataProcessor

__all__ = [
    "BaseProcessor",
    "InventoryProcessor",
    "CraftingProcessor",
    "TasksProcessor",
    "ClaimsProcessor",
    "ActiveCraftingProcessor",
    "ReferenceDataProcessor",
]
