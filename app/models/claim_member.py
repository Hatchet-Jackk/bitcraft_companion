import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ClaimActivity:
    """Represents an activity performed by a claim member."""

    activity_type: str  # 'crafting', 'building', 'inventory_move', etc.
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    location: Optional[str] = None


@dataclass
class InventoryItem:
    """Represents an inventory item owned by a claim member."""

    item_id: str
    item_name: str
    quantity: int
    location: str  # building_id or 'personal'
    tier: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OwnedObject:
    """Represents an object owned by a claim member."""

    object_id: str
    object_type: str  # 'building', 'vehicle', 'storage', etc.
    object_name: str
    location: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ClaimMember:
    """
    Lightweight representation of a claim member with extensible tracking capabilities.
    Designed to coexist with Player class without modification.
    """

    def __init__(self, entity_id: str, username: str, claim_id: str):
        # Core identity
        self.entity_id = entity_id
        self.username = username
        self.claim_id = claim_id

        # Display and metadata
        self.display_name = username
        self.role = None
        self.last_seen = None
        self.is_online = False

        # Extensible tracking systems
        self.activities: List[ClaimActivity] = []
        self.inventory_items: List[InventoryItem] = []
        self.owned_objects: List[OwnedObject] = []
        self.equipment: Dict[str, Any] = {}

        # Flexible metadata for future expansion
        self.metadata: Dict[str, Any] = {}

        # Performance tracking
        self._last_updated = datetime.now()

    def get_display_name(self) -> str:
        """Get the display name for UI purposes."""
        return self.display_name or self.username

    def update_last_seen(self, timestamp: Optional[datetime] = None):
        """Update the last seen timestamp."""
        self.last_seen = timestamp or datetime.now()
        self._last_updated = datetime.now()

    def add_activity(self, activity_type: str, details: Dict[str, Any] = None, location: str = None):
        """Add a new activity to the member's history."""
        activity = ClaimActivity(activity_type=activity_type, timestamp=datetime.now(), details=details or {}, location=location)
        self.activities.append(activity)

        # Keep only last 100 activities for performance
        if len(self.activities) > 100:
            self.activities = self.activities[-100:]

        self.update_last_seen()

    def get_recent_activities(self, activity_type: str = None, limit: int = 10) -> List[ClaimActivity]:
        """Get recent activities, optionally filtered by type."""
        activities = self.activities
        if activity_type:
            activities = [a for a in activities if a.activity_type == activity_type]

        return sorted(activities, key=lambda a: a.timestamp, reverse=True)[:limit]

    def update_inventory_item(self, item_id: str, item_name: str, quantity: int, location: str, **kwargs):
        """Update or add an inventory item."""
        # Find existing item
        existing_item = None
        for item in self.inventory_items:
            if item.item_id == item_id and item.location == location:
                existing_item = item
                break

        if existing_item:
            existing_item.quantity = quantity
            existing_item.metadata.update(kwargs)
        else:
            new_item = InventoryItem(
                item_id=item_id,
                item_name=item_name,
                quantity=quantity,
                location=location,
                tier=kwargs.get("tier", 0),
                metadata=kwargs,
            )
            self.inventory_items.append(new_item)

        self.update_last_seen()

    def remove_inventory_item(self, item_id: str, location: str = None):
        """Remove an inventory item."""
        self.inventory_items = [
            item
            for item in self.inventory_items
            if not (item.item_id == item_id and (location is None or item.location == location))
        ]
        self.update_last_seen()

    def get_inventory_summary(self) -> Dict[str, Any]:
        """Get a summary of the member's inventory."""
        total_items = len(self.inventory_items)
        total_quantity = sum(item.quantity for item in self.inventory_items)
        locations = set(item.location for item in self.inventory_items)

        return {
            "total_items": total_items,
            "total_quantity": total_quantity,
            "locations": list(locations),
            "last_updated": self._last_updated,
        }

    def add_owned_object(self, object_id: str, object_type: str, object_name: str, **kwargs):
        """Add an owned object."""
        owned_object = OwnedObject(
            object_id=object_id,
            object_type=object_type,
            object_name=object_name,
            location=kwargs.get("location"),
            metadata=kwargs,
        )
        self.owned_objects.append(owned_object)

        # Track as activity
        self.add_activity("object_acquired", {"object_type": object_type, "object_name": object_name, "object_id": object_id})

    def remove_owned_object(self, object_id: str):
        """Remove an owned object."""
        removed = [obj for obj in self.owned_objects if obj.object_id == object_id]
        self.owned_objects = [obj for obj in self.owned_objects if obj.object_id != object_id]

        for obj in removed:
            self.add_activity(
                "object_lost", {"object_type": obj.object_type, "object_name": obj.object_name, "object_id": obj.object_id}
            )

    def get_owned_objects_by_type(self, object_type: str) -> List[OwnedObject]:
        """Get owned objects filtered by type."""
        return [obj for obj in self.owned_objects if obj.object_type == object_type]

    def update_equipment(self, slot: str, item_data: Dict[str, Any]):
        """Update equipment in a specific slot."""
        old_item = self.equipment.get(slot)
        self.equipment[slot] = item_data

        # Track equipment changes
        self.add_activity("equipment_changed", {"slot": slot, "old_item": old_item, "new_item": item_data})

    def remove_equipment(self, slot: str):
        """Remove equipment from a slot."""
        if slot in self.equipment:
            old_item = self.equipment.pop(slot)
            self.add_activity("equipment_removed", {"slot": slot, "item": old_item})

    def set_metadata(self, key: str, value: Any):
        """Set custom metadata for future expansion."""
        self.metadata[key] = value
        self.update_last_seen()

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get custom metadata."""
        return self.metadata.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entity_id": self.entity_id,
            "username": self.username,
            "claim_id": self.claim_id,
            "display_name": self.display_name,
            "role": self.role,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_online": self.is_online,
            "activity_count": len(self.activities),
            "inventory_count": len(self.inventory_items),
            "owned_objects_count": len(self.owned_objects),
            "equipment_slots": list(self.equipment.keys()),
            "metadata": self.metadata,
            "last_updated": self._last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClaimMember":
        """Create ClaimMember from dictionary."""
        member = cls(entity_id=data["entity_id"], username=data["username"], claim_id=data["claim_id"])
        member.display_name = data.get("display_name", data["username"])
        member.role = data.get("role")
        member.is_online = data.get("is_online", False)
        member.metadata = data.get("metadata", {})

        if data.get("last_seen"):
            try:
                member.last_seen = datetime.fromisoformat(data["last_seen"])
            except:
                pass

        return member

    def __str__(self) -> str:
        return f"ClaimMember({self.username}, {self.claim_id})"

    def __repr__(self) -> str:
        return f"ClaimMember(entity_id='{self.entity_id}', username='{self.username}', claim_id='{self.claim_id}')"
