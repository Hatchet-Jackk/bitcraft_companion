# BitCraft Companion

A comprehensive desktop application for managing and monitoring your BitCraft game data in real time. BitCraft Companion provides live access to your claim information, inventory management, crafting monitoring, task tracking, and completion notifications through an intuitive tabbed interface.

## 🎮 What It Does

BitCraft Companion connects directly to BitCraft game servers via WebSocket to provide real-time monitoring of your gameplay data. The application serves as your external command center, helping you manage multiple claims, track crafting progress, monitor inventory, and receive notifications when items are ready—all while you play the game.

### Core Features

#### 🔐 **Secure Authentication**
- **Email-Based Login**: Uses your BitCraft account email for authentication. Nothing is shared externally.
- **Token Management**: Securely stores authentication tokens using Windows Credential Manager.
- **Persistent Sessions**: Remembers your login details between sessions.

#### 🏠 **Multi-Claim Management**
- **Claim Switching**: Seamlessly switch between multiple claims via a dropdown selector.
- **Real-Time Claim Data**: Live connection to your active BitCraft claim.
- **Claim Information Header**: Shows current claim name, member count, and connection status.

#### 📊 **Data Presentation**
- **Advanced Search & Filtering**: Instantly search and filter across item names, tags, containers, building types, and crafting status.
- **Column Filtering**: Right-click any column header to access advanced filtering options.
- **Column Sorting**: Click any column header to sort data logically in ascending or descending order.
- **Combined Filters & Sorting**: Use filters and sorting together to drill down into large datasets, such as finding all Tier 3 building materials currently being crafted.
- **Live Updates**: All search, filter, and sort operations reflect real-time changes as your in-game data updates, ensuring you always see the most current information.
- **Contextual Actions**: Right-click rows for context menus with quick actions, such as exporting filtered data, viewing item details, or jumping to related crafting operations.
- **Clear & Reset Controls**: Easily reset all filters and sorting with dedicated clear buttons, returning your view to the default state for broad overviews.

#### ⚙️ **Settings**
- **Data Export**: Easily export your claim inventory data to CSV or JSON formats for external analysis or sharing.
- **Theme Selection** *(work in progress)*: Switch between Light and Dark themes to match your personal preference or system settings.
- **Force Refresh**: Instantly reload all claim and inventory data from the server. Use this option if you suspect data is out of sync or want to ensure you have the latest updates.
- **Notification Controls**: Enable or disable Windows toast notifications for craft completions.
- **About & Version Info**: View application version, update status, and links to documentation or support.

#### 🔢 **Available Data**
- **Claim Inventory**: View all items stored across your claim, with live updates and instant search/filtering.
- **Passive Crafting**: Track ongoing passive crafting operations, see timers, progress, and who started each craft.
- **Active Crafting**: Monitor active crafting projects in real time, including remaining effort and help status.
- **Traveler's Tasks**: See available traveler tasks, requirements, progress, and refresh timers at a glance.

## 🚀 Getting Started

### Prerequisites

- Windows 10/11 (for Windows Credential Manager support)
- BitCraft game account with valid credentials
- Python 3.10+ (if running from source)

### Installation Options

#### Option 1: Executable (Recommended)
1. **Download the latest release** from the releases page.
2. **Extract** the executable to your preferred location.
3. **Run** `BitCraft_Companion-v{version}.exe`.

#### Option 2: Run from Source
1. **Clone the repository** or download the source code.
2. **Install Poetry** if you haven't already: `pip install poetry`.
3. **Install dependencies**: `poetry install`.
4. **Run the application**: `poetry run python app/main.py`.

### First-Time Setup

1. **Launch the application**—you'll see the login overlay.
2. **Enter your BitCraft email**—the same email used for your game account.
3. **Check your email** for the access code from BitCraft.
4. **Enter the access code** in the application.
5. **Select your player name**.
6. **Choose your region** (e.g., bitcraft-1) from the dropdown.
7. **Start using the features**—your credentials are securely saved for future use.

## 📱 How to Use

### Getting Started
1. **Launch the application** and complete the login process.
2. **Select your claim** from the dropdown in the header (if you have multiple).
3. **Navigate between tabs**—Claim Inventory, Passive Crafting, Active Crafting, Traveler's Tasks.
4. **Use the search bar** for instant filtering across any tab's data.
5. **Enable notifications** in the Settings window for craft completion alerts.

## ⚙️ Configuration

### User Data

The application automatically creates a `player_data.json` file to store:
- Last used player name
- Preferred region selection
- Theme settings (Light/Dark)
- Activity log

On Windows, these files are stored in `%APPDATA%/BitCraftCompanion`.

### Secure Storage

Sensitive data is stored in Windows Credential Manager:
- Authentication tokens
- Email addresses
- Access credentials

### ❓ Frequently Asked Questions
#### 📋 Why are my tables not loading?

This issue is still under investigation. Current findings suggest that slow or unstable internet connections can interrupt the WebSocket connection while the application loads reference data. If your tables are not loading, try waiting a few minutes—data may eventually appear once the connection stabilizes.

**Tips:**
- Check your internet connection speed and stability.
- Restart BitCraft Companion if the issue persists.
- Avoid heavy network usage during application startup.
- If problems continue, report the issue with details about your network environment.

#### 💬 Why aren't my notifications working?

**Problem:**  
Windows Focus Assist (Do Not Disturb mode) may automatically enable during gaming, blocking notifications.

**Solution:**  
1. Open **Windows Settings** (`WIN + I` or search "Settings" in the Start Menu).
2. Go to **System → Focus assist** (or `WIN + R`, run `ms-settings:quiethours`).
3. In **Automatic Rules**, locate:
  - "When I'm playing a game"
  - "When I'm using an app in full screen mode"
4. **Disable** both options by toggling them OFF.
5. **Restart BitCraft Companion** for changes to apply.

**Additional Tips:**
- Ensure Windows notifications are enabled for BitCraft Companion (**Settings → Notifications**).
- Use the "Test Notification" button in the app's Settings window.
- Confirm your Windows sound is not muted.
- Check notification permissions for BitCraft Companion.

---

#### 🔄 Why aren't my Traveler's Tasks updating?

BitCraft Companion syncs Traveler's Tasks in real time via the game servers. If the game isn't running or you're logged in with a different account, updates won't appear.

**Checklist:**
- BitCraft game is open and running.
- Logged in with the same account in both BitCraft and BitCraft Companion.
- After switching claims/accounts, wait a few seconds for sync.

**Still not updating?**  
Use "Force Refresh" in the Settings menu to reload claim and task data.

---

#### 🌗 Why doesn't the Light theme look right?

The Light theme is a work in progress. Some UI elements and colors may not display correctly. Improvements are planned for future releases.

---

#### ⚠️ Other Common Issues

**Windows Security Scanning**
- PyInstaller executables may trigger Windows Defender scans on first run.
- This is normal for compiled Python apps.
- To resolve: Add BitCraft Companion to Defender exclusions or run from source.

**Performance Notes**
- Large inventories (1000+ items) may take a few seconds to load.
- Real-time search is optimized but may slow with very large datasets.
- Switching between multiple claims with extensive data may be slower.

**Connection Issues**
- VPNs may block WebSocket connections to BitCraft servers.
- Firewalls may prevent BitCraft Companion from accessing the internet.
- BitCraft server maintenance can temporarily prevent data loading.

## 📝 License
This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
