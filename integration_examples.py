# Example of how to integrate ClaimMember tracking in existing services


# In ActiveCraftingService - track crafting activities
def process_crafting_action(self, progressive_action_data):
    """Example of tracking member activities during crafting."""
    player_id = progressive_action_data.get("player_entity_id")
    item_id = progressive_action_data.get("item_description_id")
    building_id = progressive_action_data.get("building_entity_id")

    if player_id and self.claim_members_service:
        # Track the crafting activity
        self.claim_members_service.update_member_activity(
            entity_id=player_id,
            activity_type="active_crafting",
            details={
                "item_id": item_id,
                "action": "crafting_started",
                "recipe_id": progressive_action_data.get("recipe_id"),
                "progress": progressive_action_data.get("progress", 0),
            },
            location=building_id,
        )


# In InventoryService - track inventory changes
def track_inventory_change(self, owner_entity_id, item_data):
    """Example of tracking inventory changes."""
    if self.claim_members_service:
        self.claim_members_service.update_member_inventory(
            entity_id=owner_entity_id,
            item_id=item_data["item_id"],
            item_name=item_data["item_name"],
            quantity=item_data["quantity"],
            location=item_data["building_id"],
            tier=item_data.get("tier", 0),
            last_updated=datetime.now(),
        )


# In DataManager - track building ownership
def track_building_ownership(self, building_data):
    """Example of tracking building ownership."""
    owner_id = building_data.get("owner_entity_id")
    if owner_id and self.claim_members_service:
        self.claim_members_service.add_member_owned_object(
            entity_id=owner_id,
            object_id=building_data["entity_id"],
            object_type="building",
            object_name=building_data.get("nickname") or "Building",
            building_type=building_data.get("building_description_id"),
            location=building_data.get("position"),
        )


# Usage Examples:


# Get member activity summary
def get_member_activity_report(self, entity_id: str):
    member = self.claim_members_service.get_claim_member_by_id(entity_id)
    if member:
        return {
            "username": member.get_display_name(),
            "recent_activities": member.get_recent_activities(limit=20),
            "inventory_summary": member.get_inventory_summary(),
            "owned_buildings": member.get_owned_objects_by_type("building"),
            "equipment": member.equipment,
            "last_seen": member.last_seen,
        }


# Find most active members
def get_most_active_members(self):
    members = self.claim_members_service.get_claim_members()
    return sorted(members, key=lambda m: len(m.activities), reverse=True)[:10]


# Get equipment distribution
def get_equipment_distribution(self):
    members = self.claim_members_service.get_claim_members()
    equipment_stats = {}
    for member in members:
        for slot, item in member.equipment.items():
            item_name = item.get("name", "Unknown")
            if item_name not in equipment_stats:
                equipment_stats[item_name] = 0
            equipment_stats[item_name] += 1
    return equipment_stats
