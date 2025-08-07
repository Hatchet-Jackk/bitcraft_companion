# BitCraft Companion

A comprehensive desktop application for managing and monitoring your BitCraft game data in real-time. BitCraft Companion provides live access to your claim information, inventory management, crafting monitoring, task tracking, and completion notifications through an intuitive tabbed interface.

## 🎮 What it does

BitCraft Companion connects directly to BitCraft game servers via WebSocket to provide real-time monitoring of your gameplay data. The application serves as your external command center, helping you manage multiple claims, track crafting progress, monitor inventory, and receive notifications when items are ready - all while you play the game.

### Core Features

#### 🏠 **Multi-Claim Management**
- **Claim Switching**: Seamlessly switch between multiple claims via dropdown selector
- **Real-time Claim Data**: Live connection to your active BitCraft claim
- **Claim Information Header**: Shows current claim name, member count, and connection status

#### 📦 **Claim Inventory Tab**
- **Comprehensive View**: Aggregates all items from storage buildings across your entire claim
- **Real-time Updates**: Instantly reflects in-game inventory changes
- **Advanced Search & Filtering**: Search across item names, tags, and properties with instant results
- **Tier-based Organization**: Groups items by tier (T1, T2, T3, etc.) for resource planning
- **Quantity Tracking**: Shows exact quantities and locations of every item
- **Column Filtering**: Right-click any column header for advanced filtering options
- **Data Export**: Export inventory data to CSV or JSON formats

#### 🔧 **Passive Crafting Tab**
- **Live Crafting Monitor**: View all active passive crafting operations in real-time
- **Smart Timer System**: Shows exact countdown timers for each crafting operation
- **Item Information**: Displays what items are being crafted and their progress
- **Building Integration**: Shows which buildings are running crafting operations
- **Crafter Tracking**: Identifies which player started each crafting operation
- **Completion Status**: Clear "READY" indicators when crafts finish

#### ⚡ **Active Crafting Tab**
- **Real-time Progress**: Monitor active crafting operations with live progress updates
- **Remaining Effort Display**: Shows exact effort remaining until completion 
- **Accept Help Status**: Track which buildings are accepting help from other players
- **Multi-building Support**: View active crafts across all buildings simultaneously
- **Crafter Information**: See who is working on each active crafting project
- **Instant Updates**: Reflects progress changes immediately as you work in-game

#### 📋 **Traveler's Tasks Tab**
- **Task Management**: Complete overview of all available traveler tasks
- **Completion Tracking**: Monitor task progress and completion status
- **Task Information**: Detailed task descriptions and requirements
- **Refresh Timer**: Shows when new tasks will become available

#### 🔔 **Smart Notification System**
- **Native Windows Toasts**: Notification integration with Windows 11/10
- **Perfect Timing**: 
  - Active crafts notify when remaining effort reaches 0 (READY status)
  - Passive crafts notify when timer countdown completes
- **Bundled Notifications**: Multiple items completing simultaneously show as single notification
- **Sound Integration**: Notifications include system sound with "reminder" priority for better visibility over games

#### 🔐 **Secure Authentication**
- **Email-based Login**: Uses your BitCraft account email for authentication. Nothing is shared externally.
- **Token Management**: Securely stores authentication tokens using Windows Credential Manager
- **Persistent Sessions**: Remembers your login details between sessions

#### 🎨 **Modern User Interface**
- **Tabbed Navigation**: Clean, professional interface with four main tabs
- **Dark Theme**: Easy on the eyes with a modern dark color scheme
- **Smart Loading States**: Loading overlays with progress indicators during data fetching
- **Advanced Search**: Unified search bar with real-time filtering across all tabs
- **Settings Integration**: Settings window with notification controls and preferences

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

### Getting Started
1. **Launch the application** and complete the login process
2. **Select your claim** from the dropdown in the header (if you have multiple)
3. **Navigate between tabs** - Claim Inventory, Passive Crafting, Active Crafting, Traveler's Tasks
4. **Use the search bar** for instant filtering across any tab's data
5. **Enable notifications** in Settings window for craft completion alerts

### Claim Inventory Tab
1. **Real-time View** - all storage items across your claim update automatically  
2. **Search & Filter** - use the search bar or right-click column headers for advanced filtering
3. **Sort by Tier** - click the "Tier" column to organize items by T1, T2, T3, etc.
4. **Export Data** - save current inventory to CSV or JSON files
5. **Track Changes** - watch quantities update live as you move items in-game

### Passive Crafting Tab
1. **Monitor Operations** - see all active passive crafting across your claim
2. **Timer Countdown** - watch exact time remaining for each crafting operation
3. **Track Builders** - see which claim member started each craft
4. **Ready Status** - items show "READY" when crafting completes
5. **Get Notifications** - receive Windows toast notifications when items finish
6. **Filter by Building** - right-click columns to filter by specific buildings or crafters

### Active Crafting Tab  
1. **Real-time Progress** - monitor active crafting operations as they happen
2. **Remaining Effort** - see exact effort remaining (not percentages)
3. **Accept Help Status** - track which buildings are accepting help
4. **Live Updates** - progress updates instantly as you work in-game
5. **Completion Alerts** - get notifications when remaining effort reaches 0

### Traveler's Tasks Tab
1. **Task Overview** - view all available traveler tasks and their requirements
2. **Progress Tracking** - monitor task completion status
3. **Refresh Timer** - see when new tasks become available
4. **Completion Notifications** - receive alerts when tasks are completed

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

## 🚨 Troubleshooting

### Why aren't my notifications working?

**Problem**: The most common issue is that Windows Focus Assist (Do Not Disturb mode) automatically turns on while playing games, blocking all notifications.

**Solution**:
1. **Open Windows Settings** by pressing `WIN + I` or searching "Settings" from the Start Menu
2. **Navigate to System → Focus assist** (alternatively, press `WIN + R` and run `ms-settings:quiethours`)
3. **Find the "Automatic Rules" section** - you'll see these options are enabled by default:
   - ✅ "When I'm playing a game"
   - ✅ "When I'm using an app in full screen mode"
4. **Disable both options** by clicking the toggle switches to turn them OFF
5. **Restart BitCraft Companion** to ensure changes take effect

**Additional Notification Troubleshooting**:
- Verify Windows notifications are enabled for the application in Windows Settings → Notifications
- Test notifications using the "Test Notification" button in the BitCraft Companion Settings window
- Ensure your Windows sound is not muted (notifications include audio cues)
- Check that BitCraft Companion has notification permissions

### Other Common Issues

#### Windows Security Scanning
- **PyInstaller executables** may trigger Windows Defender scanning on first run
- **This is normal behavior** for compiled Python applications
- **Solutions**: Add BitCraft Companion to Windows Defender exclusions or run from source

#### Performance Notes
- **Large inventories** (1000+ unique items) may take a few seconds to load initially
- **Real-time search** is optimized but may slow slightly with very large datasets
- **Multiple claims** with extensive data may impact switching speed

#### Connection Issues
- **VPN interference**: Some VPNs may block WebSocket connections to BitCraft servers
- **Firewall blocks**: Ensure BitCraft Companion can access the internet
- **Server maintenance**: BitCraft server downtime will prevent data loading

## 📝 License
This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.