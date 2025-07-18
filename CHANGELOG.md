# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - Passive item processing progress
  - Desktop notifications for completed crafting
  - Low inventory alerts
  - Travelers' task monitoring 

