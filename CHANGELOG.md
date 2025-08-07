# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.12]
### Added
* Settings persistence in player_data.json with robust error handling
* Enhanced notification settings structure for better organization

### Improved
* Crafting processors notification handling and item tracking
* Active crafting notifications with better bundling and timing
* Settings loading and saving with proper fallback mechanisms
* Error handling throughout settings management system

## [0.2.11]
### Fixed
* Notification timing. Now they trigger when the tasks is READY not when you claim the item.
* Notifications now bundle items to prevent notification spam for each item.

## [0.2.10]
### Fixed 
* Update Accept Help value in real time

### Added
* Settings menu
* Notifications
* Move export and refresh claim to settings

## [0.2.9]
### Fixed
* Traveler tasks no longer clear at login

### Improved
* Progress tracking in Active Tasks converted to Remaining Effort. The value counts down until craft is completed.

## [0.2.7]
### Patch
* When exporting claim inventory, break out containers into their own rows for improved processing

## [0.2.6]
### Fixed
* Build path references
* Traveler task timeout reset failure

## [0.2.5]
### Improvements
* Vastly improved network performance
* Vastly improved data loading
* Vastly improved claim switching performance
* Data presentation in passive and active crafting tabs

### Added
* Real time countdowns for passive crafting
* Real time countdown for traveler task resets
* Logout and Quit buttons in main window
* Accept help value in active crafting
* Claim supply depletion value

### Fixed
* Re-added data export
* Scrollbar colors now use the correct color when disabled

## [0.1.11]
### Fixed
- Resolved issue where certain items were not appearing in the claim inventory

### Refactored
- Migrated reference data storage from JSON files to a database for improved performance and scalability

### Known Issues
- Inventory overlay reappears unexpectedly after being closed when processing the inventory list
- Updated overlays automatically move to the foreground

## [0.1.10]
### Added
- **Missing Regions**: Added support for additional regions to improve compatibility and coverage.

## [0.1.9]
### Fix
- **WebSocket Optimization**: Switched from `Subscribe` to `OneOffQuery` to prevent multiple simultaneous WebSocket connections 
and reduce resource usage.
- **Overlay Update Reliability**: Fixed an issue where overlays were not updating properly, ensuring inventory and passive crafting overlays now refresh as expected.
- **Overlay Table In-Place Updates**: Fixed overlay tables so they now update in place without requiring a full redraw, eliminating flickering and ensuring smoother refreshes.


### Change
- **Reduced Overlay Refresh Intervals**: Lowered the refresh intervals for inventory and passive crafting overlays for more 
- **Status Bar Consistency**: Standardized the display of "Last Update" datetimes across all status bars for a uniform user experience.

### Add
- **Tooltip for Auto Refresh Toggle**: Added informative tooltip to the auto refresh toggle for improved user guidance.

## [0.1.7]
### Added
- **Passive Crafting Timers**
- **Unified UI**

### Removed
- **Cleaned up unused imports**

## [0.1.6]

### Added
- **Expandable Rows (Phase 2: Advanced Features)**
  - Immediate dropdown arrows for expandable items
  - Tree structure support with proper hierarchical display
  
- **Inventory Window Enhancements**
  - Items with multiple containers now expand to show individual container quantities
  - Container names properly aligned in the Containers column
  - Single container items display actual container name instead of "1×📦"
  
- **Passive Crafting Window Enhancements**
  - Items with multiple refineries expand to show individual refinery quantities
  - Per-refinery quantity tracking (child row quantities add up to parent total)
  - Support for multiple crafters when applicable
  - Enhanced data structure for accurate refinery-specific information

- **Visual Design Improvements**
  - Lighter background (#3a3a3a) for child rows to distinguish from parent rows
  - Clean appearance with no bullet points in expanded rows
  - Left-aligned container names for better readability
  - Consistent tag-based styling across both windows

### Technical Improvements
- **Immediate Child Population**: Child rows are populated immediately when tree is created
- **Efficient Data Structure**: Per-refinery quantity tracking in the service layer
- **Robust Expand/Collapse**: Simple show/hide logic without complex dummy child management
- **Enhanced Service Layer**: Modified `passive_crafting_service.py` to include detailed refinery information

## [0.1.5]

- **Wiki Integration**
  - Right-click context menu on inventory and passive crafting items
  - "Go to Wiki" option that opens the BitCraft wiki (https://bitcraft.wiki.gg) page for the selected item
  - Automatic URL formatting for wiki links (e.g., "Rough Tree Bark" → "Rough_Tree_Bark")

## [0.1.4]

### Added
- **Real-time Search Functionality**
  - Added comprehensive search bars to both inventory and passive crafting windows
  - Real-time filtering across item names and tags as you type
  - Clear search button for easy reset functionality
  - Search persists across data refreshes while maintaining user context


- **Passive Crafting Monitor**
  - Complete passive crafting status window with real-time updates
  - Recipe tracking and progress monitoring
  - Search functionality for crafting operations
  - Always on top window option for gameplay convenience

- **Data Export Features**
  - Save inventory data to CSV, JSON, or text formats
  - Comprehensive export with metadata and timestamps
  - Multiple file format support for different use cases

- **Enhanced User Interface**
  - Optimized spacing and padding throughout the interface
  - Always on top window toggle for better gameplay integration
  - Improved responsive design with proper grid weight configuration
  - Status indicators with data freshness timestamps

### Fixed
- **Critical Bug Fixes**
  - Fixed "Unknown Item" display issue in passive crafting window
  - Resolved reference data loading problems causing missing item names
  - Fixed grid row configuration issues causing layout problems
  - Corrected import statements and syntax errors in passive crafting module

- **UI/UX Improvements**
  - Fixed excessive spacing in search and filter areas
  - Improved timestamp management to preserve data freshness indicators
  - Enhanced error handling and logging for search operations
  - Optimized grid layouts for better responsiveness

### Changed
- **Enhanced Documentation**
  - Updated README.md with comprehensive feature descriptions
  - Added detailed usage instructions for new search functionality
  - Documented installation options for both executable and source
  - Added troubleshooting section for Windows security scanning

- **Code Quality Improvements**
  - Refactored `apply_filters_and_sort()` method for better search integration
  - Enhanced reference data loading mechanisms
  - Improved error handling throughout the application
  - Better separation of concerns in window management


### Known Issues
- **Windows Security Scanning**
  - PyInstaller executables may trigger Windows Defender scanning
  - This is normal behavior for compiled Python applications
  - Solutions: Add exclusions to Windows Defender or run from source during development

- **Performance Considerations**
  - Large inventories may take longer to load and filter
  - Search operations are optimized for real-time filtering
  - Auto-refresh can be disabled for better performance on slower systems

---

## Future Roadmap

### Planned Features
  - Desktop notifications for completed crafting
  - Low inventory alerts
  - Travelers' task monitoring 
  - Claim supplies 

