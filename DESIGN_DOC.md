# BitCraft Companion - Passive Crafting Advanced Features
## Design Document v2.0

### Current State ✅
We have successfully implemented the foundational passive crafting system:

- **Item-focused display** with proper item names extracted from `crafted_item_stacks`
- **Claim member filtering** to show only relevant crafting operations
- **Expandable rows** grouped by item type with individual refinery operations as children
- **Proper building/crafter logic** showing unique types rather than operation counts
- **Time calculation** using recipe duration and start timestamps
- **Clean UI** with columns: Item | Tier | Quantity | Recipe | Time Remaining | Crafter | Building

### Key Implementation Details 🔧

#### Current Architecture:
```python
# Main service class
class PassiveCraftingService:
    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim, reference_data: dict)
    def get_all_crafting_data(self) -> List[Dict]  # Main data fetcher
    def _format_crafting_entry_item_focused(self, craft_state: Dict, building_info: Dict, user_lookup: Dict)
    def _group_crafting_data_by_item_name(self, operations: List[Dict]) -> List[Dict]
    def calculate_remaining_time(self, crafting_entry: Dict) -> str
```

#### Critical Data Flow:
1. **Claim member filtering**: Query `claim_member_state` to build `claim_member_ids` set
2. **Building discovery**: Query `building_state` + `building_nickname_state` for processing buildings
3. **Crafting operations**: Query `passive_craft_state` per building, filter by claim members
4. **Item extraction**: Parse `crafted_item_stacks` (already a list, not string) to get actual item names
5. **Grouping logic**: Group by `item_name|tier`, track unique building types and crafters

#### Data Structure Format:
```python
# Service returns this format to GUI:
{
    "item": "Exquisite Embergrain Plant",
    "tier": 5,
    "quantity": 10,
    "recipe": "Grow", 
    "time_remaining": "1h 23m 33s",
    "crafter": "Melly",  # Single name or "X crafters"
    "building": "Long Farming Field Row",  # Single type or "X building types"
    "operations": [...],  # Individual operations for expansion
    "is_expandable": True/False
}
```

#### Time Calculation Logic:
```python
# Current working formula:
start_time = timestamp_micros / 1_000_000  # Convert to seconds
elapsed_time = current_time - start_time
remaining_time = duration_seconds - elapsed_time
# Status [2, {}] means READY, [1, {}] means Crafting
```

#### UI Component Structure:
- **PassiveCraftingTab**: CustomTkinter frame with ttk.Treeview
- **Headers**: `["Item", "Tier", "Quantity", "Recipe", "Time Remaining", "Crafter", "Building"]`
- **Expandable rows**: Parent shows summary, children show individual operations
- **Color coding**: Tags for "ready" (green), "crafting" (orange), "empty" (gray)

#### Integration Points:
- **DataService**: Calls `get_all_crafting_data()` and pushes to `data_queue`
- **WebSocket subscriptions**: Uses `get_subscription_queries(building_ids)`
- **Reference data**: Loaded from `crafting_recipe_desc`, `item_desc`, `building_desc` tables

### Critical Lessons Learned 💡

#### Major Gotchas Fixed:
1. **`crafted_item_stacks` format**: It's already a list `[[item_id, quantity, ...]]`, NOT a string needing `ast.literal_eval()`
2. **Claim member filtering**: MUST filter `owner_entity_id` against `claim_member_ids` set to avoid showing external crafters
3. **Building grouping**: Group by unique building TYPES, not individual building instances (10 operations on same building = 1 building type)
4. **Time calculation**: Status field `[2, {}]` = READY, `[1, {}]` = Crafting. Use `timestamp.__timestamp_micros_since_unix_epoch__` 
5. **Item lookup**: Combine `resource_desc`, `item_desc`, and `cargo_desc` into single `item_descriptions` dict

#### Database Schema Understanding:
```sql
-- Key tables and their relationships:
claim_member_state: claim_entity_id -> player_entity_id, user_name
building_state: claim_entity_id -> entity_id, building_description_id  
passive_craft_state: building_entity_id -> recipe_id, owner_entity_id, status, timestamp
crafting_recipe_desc: id -> name, time_requirement, crafted_item_stacks
```

#### Working Code Patterns:
```python
# Correct item extraction:
crafted_item_stacks = recipe_info.get("crafted_item_stacks", [])
if isinstance(crafted_item_stacks, list) and crafted_item_stacks:
    item_id, quantity = crafted_item_stacks[0][0], crafted_item_stacks[0][1]

# Correct claim filtering:
claim_member_ids = {member["player_entity_id"] for member in claim_members}
if owner_entity_id not in claim_member_ids: continue

# Correct building grouping:
building_types = set()  # Track unique building types, not instances
building_types.add(operation.get("refinery"))  # Add building type name
```

### Phase 2 Objectives 🎯

## 1. Real-Time Updates ⏱️
**Goal**: Make timers tick down live and update UI automatically

### Implementation Plan:
- **Timer Thread**: Background thread that updates every second
- **Time Recalculation**: Recalculate remaining time for all active operations
- **UI Updates**: Push timer updates to GUI thread safely
- **Status Changes**: Detect when items transition from "Crafting" to "READY"
- **Color Coding**: Real-time visual feedback (red for urgent, green for ready)

### Technical Requirements:
```python
# Timer service that runs independently
class PassiveCraftingTimer:
    def start_timer_thread(self)
    def update_all_timers(self)
    def detect_status_changes(self)
    def notify_ui_updates(self)
```

## 2. WebSocket Subscription Handling 📡
**Goal**: Get live data updates from the game server

### Implementation Plan:
- **Subscription Queries**: Monitor `passive_craft_state` table changes
- **Message Parsing**: Handle real-time database updates from WebSocket
- **Incremental Updates**: Only refresh changed data, not entire dataset
- **Connection Management**: Handle disconnections and reconnections gracefully

### Technical Requirements:
```python
# Enhanced subscription management
def get_subscription_queries(self, building_ids: List[str]) -> List[str]
def parse_crafting_update(self, db_update: dict) -> bool
def handle_websocket_reconnection(self)
def process_incremental_updates(self, updates: List[Dict])
```

## 3. Performance Optimization 🚀
**Goal**: Handle large amounts of crafting data efficiently

### Implementation Plan:
- **Data Caching**: Smart caching with TTL for expensive operations
- **Lazy Loading**: Only load visible data initially
- **Virtual Scrolling**: Handle thousands of rows efficiently
- **Debounced Updates**: Batch multiple updates to prevent UI thrashing
- **Memory Management**: Cleanup old timer references and cached data

### Technical Requirements:
```python
# Performance monitoring and optimization
class CraftingDataCache:
    def cache_with_ttl(self, key: str, data: Any, ttl: int)
    def invalidate_cache(self, pattern: str)
    def get_cache_stats(self) -> Dict

# Virtual scrolling for large datasets
class VirtualizedCraftingView:
    def render_visible_rows_only(self)
    def handle_scroll_events(self)
```

## 4. Advanced Features 🔥
**Goal**: Add powerful user experience enhancements

### Features to Implement:

#### A. Smart Notifications
- **Ready Alerts**: Desktop notifications when items complete
- **Batch Notifications**: "5 items ready" instead of individual alerts
- **Sound Options**: Configurable audio alerts
- **Priority System**: Different alerts for different item tiers

#### B. Batch Operations
- **Multi-Select**: Select multiple items for bulk actions
- **Collection Planning**: "Collect all ready items" workflow
- **Production Queuing**: Plan next crafting operations
- **Resource Tracking**: Monitor input materials needed

#### C. Analytics & Insights
- **Production Statistics**: Items/hour, completion rates
- **Efficiency Metrics**: Building utilization, bottlenecks
- **Historical Data**: Track production over time
- **Recommendations**: Suggest optimal crafting strategies

### Technical Requirements:
```python
# Notification system
class CraftingNotifications:
    def schedule_ready_alerts(self, items: List[Dict])
    def send_desktop_notification(self, message: str)
    def play_alert_sound(self, sound_type: str)

# Analytics engine
class CraftingAnalytics:
    def calculate_production_rates(self) -> Dict
    def identify_bottlenecks(self) -> List[str]
    def generate_recommendations(self) -> List[Dict]
```

## 5. Data Synchronization 🔄
**Goal**: Keep UI perfectly in sync with game state

### Implementation Plan:
- **State Management**: Central state store with immutable updates
- **Conflict Resolution**: Handle concurrent updates gracefully
- **Rollback Capability**: Undo incorrect state changes
- **Health Monitoring**: Detect and recover from sync issues
- **Audit Trail**: Log all state changes for debugging

### Technical Requirements:
```python
# Centralized state management
class CraftingStateManager:
    def update_state(self, operation_id: str, new_data: Dict)
    def rollback_to_checkpoint(self, timestamp: datetime)
    def validate_state_consistency(self) -> bool
    def create_state_snapshot(self) -> Dict

# Sync health monitoring
class SyncHealthMonitor:
    def check_connection_health(self) -> bool
    def detect_data_inconsistencies(self) -> List[str]
    def auto_recover_from_issues(self)
```

### Architecture Overview 🏗️

```
┌─────────────────────────────────────────────────────────────┐
│                     UI Layer (CustomTkinter)                │
├─────────────────────────────────────────────────────────────┤
│  PassiveCraftingTab  │  NotificationSystem  │  Analytics   │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                             │
├─────────────────────────────────────────────────────────────┤
│ CraftingTimer │ StateManager │ CacheManager │ SyncMonitor  │
├─────────────────────────────────────────────────────────────┤
│                    Data Layer                                │
├─────────────────────────────────────────────────────────────┤
│  WebSocket Client  │  Local Cache  │  Performance Monitor   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                   BitCraft Game Server
```

### Success Metrics 📊
- **Real-time accuracy**: Timers accurate within 1 second
- **Performance**: Handle 1000+ concurrent crafting operations
- **Reliability**: 99.9% uptime with auto-recovery
- **User experience**: < 100ms UI response time
- **Memory efficiency**: < 50MB memory footprint

### Priority Order 📋
1. **Real-time updates** (Foundation for everything else)
2. **WebSocket subscriptions** (Live data source)
3. **Performance optimization** (Scalability)
4. **Basic notifications** (User value)
5. **Data synchronization** (Reliability)
6. **Advanced features** (Enhancement)

This represents the evolution from a basic passive crafting display to a comprehensive, real-time production management system for BitCraft players.