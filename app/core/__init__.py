"""
Core data processing components for BitCraft Companion.

Contains the refactored data service, message router, and data processors
that handle SpacetimeDB subscription data.
"""

from .data_service import DataService
from .message_router import MessageRouter
from .processors import *

__all__ = [
    "DataService",
    "MessageRouter",
    "BaseProcessor",
    "InventoryProcessor",
    "CraftingProcessor",
    "TasksProcessor",
    "ClaimsProcessor",
    "ActiveCraftingProcessor",
]
