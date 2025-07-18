# BitCraft Companion

A comprehensive desktop application for managing and monitoring your BitCraft game data. The BitCraft Companion provides real-time access to your claim information, inventory management, passive crafting monitoring, and building data through an intuitive GUI interface.

## 🎮 What it does

BitCraft Companion connects to the BitCraft game servers via WebSocket to provide real-time data about your claim inventory and passive crafting operations. The application serves as an external tool to help you manage your BitCraft experience more effectively.

### Core Features

#### 🏠 **Claim Management**
- **Real-time Claim Data**: Connects to your BitCraft claim and displays current inventory
- **Live Updates**: Automatically syncs with your in-game changes

#### 📦 **Inventory Management**
- **Comprehensive Inventory View**: Aggregates items from all storage buildings in your claim
- **Advanced Search**: Real-time search across item names and tags with instant filtering
- **Tier-based Sorting**: Groups items by tier for easy resource planning
- **Quantity Tracking**: Shows exact quantities of each item across all storage locations
- **Auto-refresh**: Keeps inventory data current with configurable refresh intervals
- **Data Export**: Save inventory data to CSV, JSON, or text formats

#### 🔧 **Passive Crafting Monitor**
- **Passive Operations**: View all passive crafting operations
- **Recipe Tracking**: See what items are being crafted
- **Search & Filter**: Find specific crafting operations quickly
- **Real-time Updates**: Monitor crafting progress as it happens

#### ⏰ **Passive Crafting Timer Overlay**
- **Always-on-Top Timer**: Compact overlay showing your active crafting timers
- **Countdowns**: See exactly how much time remains for each crafting operation
- **Completion Alerts**: Visual indicators when crafting operations are ready
- **Grouped Display**: Items are grouped by type with total quantities and completion counts

#### 🔐 **Secure Authentication**
- **Email-based Login**: Uses your BitCraft account email for authentication. Nothing is shared externally.
- **Token Management**: Securely stores authentication tokens using Windows Credential Manager
- **Region Selection**: Choose your preferred BitCraft server region
- **Persistent Sessions**: Remembers your login details between sessions

#### 🎨 **User Interface**
- **Dark Theme**: Easy on the eyes with a modern dark interface
- **Responsive Design**: Clean, intuitive layout that adapts to window resizing
- **Status Indicators**: Real-time feedback on connection status and data loading
- **Toggle Controls**: Simple switches to enable/disable different features
- **Popup Windows**: Dedicated inventory and crafting windows that can be opened on demand
- **Always on Top**: Keep important windows visible while playing the game

### Data Sources

The application uses reference data files to interpret game data:
- **Building Descriptions**: Maps building IDs to human-readable names
- **Item Descriptions**: Provides item metadata (names, tiers, tags)
- **Crafting Recipes**: Recipe definitions for passive crafting operations
- **Resource Descriptions**: Information about game resources
- **Building Type Mappings**: Categorizes buildings by their function

## 🚀 Getting Started

### Prerequisites

- Windows 10/11 (for Windows Credential Manager support)
- BitCraft game account with valid credentials
- Python 3.10+ (if running from source)

### Installation Options

#### Option 1: Executable (Recommended)
1. **Download the latest release** from the releases page
2. **Extract** the executable to your preferred location
3. **Run** `BitCraft_Companion-v{version}.exe`

#### Option 2: Run from Source
1. **Clone the repository** or download the source code
2. **Install Poetry** if you haven't already: `pip install poetry`
3. **Install dependencies**: `poetry install`
4. **Run the application**: `poetry run python app/main.py`

### First Time Setup

1. **Launch the application** - you'll see the login overlay
2. **Enter your BitCraft email** - the same email used for your game account
3. **Check your email** for the access code from BitCraft
4. **Enter the access code** in the application
5. **Select your player name** 
6. **Choose your region** (e.g., bitcraft-1) from the dropdown
7. **Start using the features** - your credentials are securely saved for future use

## 📱 How to Use

### Viewing Claim Inventory

1. **Toggle "Claim Inventory Report"** - turns on inventory monitoring
2. **Inventory Window Opens** - shows all items across your storage buildings
3. **Use the Search Bar** - type to instantly filter items by name or tag
4. **Filter & Sort** - click column headers for advanced filtering options
5. **Auto-refresh** - data updates automatically every few minutes
6. **Manual Refresh** - use the refresh button for immediate updates
7. **Export Data** - save inventory reports to CSV, JSON, or text files

### Monitoring Passive Crafting

1. **Toggle "Passive Crafting Status"** - opens the passive crafting monitor
2. **View Active Operations** - see all currently running crafting processes
3. **Search for Recipes** - find specific crafting operations quickly
4. **Monitor Progress** - track completion status and remaining time
5. **Always on Top** - keep the window visible while playing

### Using the Passive Crafting Timer Overlay

1. **Toggle "Passive Crafting Timer Overlay"** - opens a compact always-on-top timer
2. **Countdown** - see exactly how much time remains for each operation
3. **Grouped Display** - items are grouped by type with total quantities shown
4. **Completion Status** - shows "READY" when crafting operations are complete
6. **Auto-refresh** - timer updates automatically as operations progress

### Advanced Features

#### Search Functionality
- **Real-time Search**: Type in the search bar to instantly filter results
- **Multi-field Search**: Search across item names, tags, and other properties
- **Clear Search**: Use the "Clear" button to reset search filters

#### Filtering & Sorting
- **Column Headers**: Click the dropdown arrow (▼) on any column header
- **Sort Options**: Choose ascending or descending order
- **Value Filters**: Select specific values to show or hide
- **Combined Filters**: Use multiple filters simultaneously
- **Clear Filters**: Remove individual or all filters easily

### Understanding the Data

- **Quantities**: Shows total amounts across all storage buildings
- **Tiers**: Items are organized by their tier level (T1, T2, T3, etc.)
- **Tags**: Categories and metadata for items (e.g., "Building Material", "Tool")
- **Timestamps**: Last update times for data freshness indicators
- **Remaining Time**: For passive crafting timers, shows exact time remaining until completion
- **Completion Status**: "READY" indicates when crafting operations are finished

## ⚙️ Configuration

### User Data

The application automatically creates a `player_data.json` file to store:
- Last used player name
- Preferred region selection

### Secure Storage

Sensitive data is stored in Windows Credential Manager:
- Authentication tokens
- Email addresses
- Access credentials

## 🚨 Known Issues

### Windows Security Scanning
- **PyInstaller executables** may trigger Windows Defender scanning
- **This is normal behavior** for compiled Python applications
- **Solutions**: Add exclusions to Windows Defender or run from source during development

### Performance Notes
- **Large inventories** may take longer to load and filter
- **Search operations** are optimized for real-time filtering

## 📝 License
This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.