# Data Manager Migration Plan

## Current State Analysis

The current `DataService` class in `data_manager.py` has grown into a monolithic 1,488-line file that handles:

- WebSocket connection management
- Subscription data processing  
- Real-time transaction handling
- Service initialization and coordination
- Data enrichment and transformation
- UI data queue management
- Claim switching logic
- Reference data caching

This violates single responsibility principle and makes the system difficult to maintain, test, and extend.

## Migration Goals

1. **Separation of Concerns**: Break functionality into focused, single-purpose modules
2. **Event-Driven Architecture**: Move from cache-heavy to event streaming
3. **Testability**: Make components independently testable
4. **Maintainability**: Reduce complexity per module
5. **Performance**: Eliminate redundant data transformations
6. **Scalability**: Support future features without architectural changes

## Target Architecture

### Core Modules

```
app/
├── connection/
│   ├── __init__.py
│   ├── websocket_manager.py      # WebSocket connection & message routing
│   └── subscription_manager.py   # Subscription lifecycle management
├── events/
│   ├── __init__.py
│   ├── event_bus.py             # Central event dispatcher
│   ├── event_types.py           # Event type definitions
│   └── event_handlers.py        # Event handler registry
├── processors/
│   ├── __init__.py
│   ├── base_processor.py        # Abstract base for data processors
│   ├── building_processor.py    # Building state processing
│   ├── crafting_processor.py    # Active/passive crafting processing  
│   ├── inventory_processor.py   # Inventory state processing
│   ├── task_processor.py        # Traveler task processing
│   ├── claim_processor.py       # Claim state processing
│   └── member_processor.py      # Claim member processing
├── enrichment/
│   ├── __init__.py
│   ├── enrichment_engine.py     # Data enrichment coordinator
│   ├── reference_cache.py       # Reference data management
│   └── enrichers/
│       ├── __init__.py
│       ├── recipe_enricher.py   # Recipe data enrichment
│       ├── building_enricher.py # Building data enrichment
│       └── item_enricher.py     # Item data enrichment
├── state/
│   ├── __init__.py
│   ├── game_state.py           # Minimal game state store
│   └── state_updater.py        # State update coordinator
└── legacy/
    └── data_manager.py         # Simplified coordinator (phase out)
```

## Migration Phases

### Phase 1: Event Infrastructure (Week 1)

**Goal**: Establish event-driven foundation

**Tasks**:
1. Create `events/event_bus.py` - Central event dispatcher
2. Create `events/event_types.py` - Event type definitions  
3. Create `connection/websocket_manager.py` - Extract WebSocket handling
4. Update `DataService` to emit events instead of direct processing

**Benefits**: 
- Decouples message handling from processing
- Enables parallel processing
- Simplifies testing

**Files Created**:
```python
# events/event_bus.py
class EventBus:
    def __init__(self):
        self._handlers = {}
    
    def subscribe(self, event_type, handler):
        # Register event handlers
        
    def publish(self, event_type, data):
        # Emit events to registered handlers
        
    def unsubscribe(self, event_type, handler):
        # Remove event handlers

# events/event_types.py  
class EventTypes:
    # Subscription events
    INITIAL_SUBSCRIPTION = "initial_subscription"
    SUBSCRIPTION_UPDATE = "subscription_update"
    
    # Transaction events  
    BUILDING_UPDATE = "building_update"
    CRAFTING_UPDATE = "crafting_update"
    INVENTORY_UPDATE = "inventory_update"
    TASK_UPDATE = "task_update"
    CLAIM_UPDATE = "claim_update"
    
    # UI events
    UI_DATA_READY = "ui_data_ready"
    UI_ERROR = "ui_error"
```

### Phase 2: Data Processors (Week 2)

**Goal**: Extract data processing logic into focused processors

**Tasks**:
1. Create `processors/base_processor.py` - Abstract processor interface
2. Create specific processors for each data type
3. Move processing logic from `DataService` to processors
4. Connect processors to event bus

**Benefits**:
- Single responsibility per processor
- Independently testable components
- Easier to add new data types

**Example Processor**:
```python
# processors/building_processor.py
class BuildingProcessor(BaseProcessor):
    def __init__(self, event_bus, enrichment_engine):
        self.event_bus = event_bus
        self.enrichment_engine = enrichment_engine
        
    def process_initial_buildings(self, subscription_data):
        # Process building_state, building_nickname_state
        # Emit enriched building events
        
    def process_building_update(self, transaction_data):
        # Handle real-time building updates
        # Emit delta events to UI
```

### Phase 3: Enrichment Engine (Week 3)

**Goal**: Centralize and optimize data enrichment

**Tasks**:
1. Create `enrichment/enrichment_engine.py` - Enrichment coordinator
2. Create `enrichment/reference_cache.py` - Optimized reference data cache  
3. Create specific enrichers for different data types
4. Replace inline enrichment with engine calls

**Benefits**:
- Consistent enrichment across all processors
- Optimized reference data access
- Cacheable enrichment results

**Example Enricher**:
```python
# enrichment/enrichers/recipe_enricher.py
class RecipeEnricher:
    def __init__(self, reference_cache):
        self.reference_cache = reference_cache
        
    def enrich_crafting_data(self, crafting_state):
        # Add recipe names, item stacks, time requirements
        # Return enriched data ready for UI
```

### Phase 4: State Management (Week 4)

**Goal**: Implement minimal reactive state management

**Tasks**:
1. Create `state/game_state.py` - Minimal state store
2. Create `state/state_updater.py` - State update coordinator
3. Replace complex caching with reactive state updates
4. Implement claim switching via state changes

**Benefits**:
- Single source of truth
- Automatic UI updates via state changes
- Simplified claim switching

**State Structure**:
```python
# state/game_state.py
class GameState:
    def __init__(self):
        self.current_claim_id = None
        self.claim_members = {}  # entity_id -> ClaimMemberState
        self.buildings = {}      # entity_id -> BuildingData
        # Minimal state only, no complex aggregations
        
    def update_claim_members(self, member_data):
        # Update member state, emit change events
        
    def is_claim_member(self, player_entity_id):
        # Centralized member checking
```

### Phase 5: Legacy Cleanup (Week 5)

**Goal**: Remove complex caching and simplify DataService

**Tasks**:
1. Remove processing methods from `DataService`
2. Simplify to connection coordinator + event emitter
3. Remove complex caching logic
4. Update service initialization

**Final DataService**:
```python
class DataService:
    """Simplified connection coordinator and event emitter."""
    
    def __init__(self):
        self.event_bus = EventBus()
        self.websocket_manager = WebSocketManager(self.event_bus)
        self.processors = self._init_processors()
        
    def start(self, username, password, region, player_name):
        # Authenticate and connect
        # Let processors handle data via events
        
    def _handle_message(self, message):
        # Simple event emission, no processing
        if "InitialSubscription" in message:
            self.event_bus.publish(EventTypes.INITIAL_SUBSCRIPTION, message)
        elif "TransactionUpdate" in message:
            self.event_bus.publish(EventTypes.SUBSCRIPTION_UPDATE, message)
```

## Implementation Strategy

### Week 1: Event Infrastructure
- [ ] Create event bus system
- [ ] Extract WebSocket management  
- [ ] Update DataService to emit events
- [ ] Create basic processor interfaces
- [ ] Test event flow with one data type

### Week 2: Core Processors
- [ ] Implement building processor
- [ ] Implement crafting processor  
- [ ] Implement inventory processor
- [ ] Implement task processor
- [ ] Implement claim processor
- [ ] Test each processor independently

### Week 3: Enrichment System
- [ ] Create enrichment engine
- [ ] Implement reference data cache
- [ ] Create specific enrichers
- [ ] Replace inline enrichment
- [ ] Performance test enrichment

### Week 4: State Management  
- [ ] Implement game state store
- [ ] Create state updater
- [ ] Replace complex caching
- [ ] Implement reactive UI updates
- [ ] Test claim switching

### Week 5: Final Cleanup
- [ ] Remove legacy processing from DataService
- [ ] Clean up imports and dependencies
- [ ] Performance testing
- [ ] Documentation update
- [ ] Integration testing

## Benefits After Migration

### Developer Experience
- **Focused Files**: Each file has single responsibility (200-300 lines max)
- **Easy Testing**: Mock individual processors/enrichers
- **Clear Dependencies**: Explicit interfaces between components
- **Simple Debugging**: Event logs show exact data flow

### Performance
- **Event Streaming**: No complex cache invalidation
- **On-Demand Enrichment**: Only enrich data when needed
- **Parallel Processing**: Multiple processors can work simultaneously
- **Memory Efficient**: No duplicate data storage

### Maintainability  
- **Modular**: Add new data types by creating new processors
- **Testable**: Each component independently testable
- **Readable**: Clear separation of concerns
- **Extensible**: Easy to add features without touching core logic

### Architecture
- **Event-Driven**: Natural fit for real-time game data
- **Reactive**: UI automatically updates with state changes
- **Scalable**: Components can be optimized/replaced independently
- **Clean**: No god classes or complex inheritance

## Risk Mitigation

### Backward Compatibility
- Keep current `DataService` working during migration
- Migrate one data type at a time
- Use feature flags for new vs old processing

### Testing Strategy
- Unit tests for each processor
- Integration tests for event flows
- Performance benchmarks during migration
- Rollback plan if performance degrades

### Migration Dependencies
- No external library changes required
- Existing data classes can be reused
- UI changes minimal (just event subscriptions)
- Database schema unchanged

## Success Metrics

- [ ] **Code Complexity**: Average file size under 300 lines
- [ ] **Test Coverage**: >90% coverage on new modules  
- [ ] **Performance**: No regression in UI update speed
- [ ] **Memory Usage**: Reduced memory footprint
- [ ] **Developer Velocity**: Faster to add new features
- [ ] **Bug Rate**: Fewer bugs due to better separation

This migration transforms the monolithic `DataService` into a clean, event-driven architecture that's easier to maintain, test, and extend while improving performance through reduced data transformation overhead.
