# BitCraft Companion

A comprehensive desktop application for managing and monitoring your BitCraft game data. The BitCraft Companion provides real-time access to your claim information, inventory management, and building data through an intuitive GUI interface.

## 🎮 What it does

BitCraft Companion connects to the BitCraft game servers via WebSocket to provide real-time data about your claim inventory. The application serves as an external tool to help you manage your BitCraft experience more effectively.

### Core Features

#### 🏠 **Claim Management**
- **Real-time Claim Data**: Connects to your BitCraft claim and displays current inventory
- **Live Updates**: Automatically syncs with your in-game changes

#### 📦 **Inventory Management**
- **Comprehensive Inventory View**: Aggregates items from all storage buildings in your claim
- **Tier-based Sorting**: Groups items by tier for easy resource planning
- **Quantity Tracking**: Shows exact quantities of each item across all storage locations
- **Search & Filter**: Find specific items quickly with built-in filtering
- **Auto-refresh**: Keeps inventory data current with configurable refresh intervals

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
- **Popup Windows**: Dedicated inventory windows that can be opened on demand

### Data Sources

The application uses reference data files to interpret game data:
- **Building Descriptions**: Maps building IDs to human-readable names
- **Item Descriptions**: Provides item metadata (names, tiers, tags)
- **Resource Descriptions**: Information about game resources
- **Building Type Mappings**: Categorizes buildings by their function

## 🚀 Getting Started

### Prerequisites

- Windows 10/11 (for Windows Credential Manager support)
- BitCraft game account with valid credentials

### Installation

1. **Download the latest release** from the releases page
2. **Extract** the executable to your preferred location
3. **Run** `BitCraft_Companion-v{version}.exe`

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

1. **Toggle "Claim Inventory Report"** - turns on real-time inventory monitoring
2. **Inventory Window Opens** - shows all items across your storage buildings
3. **Filter & Sort** - use the built-in tools to find specific items
4. **Auto-refresh** - data updates automatically every few minutes
5. **Manual Refresh** - use the refresh button for immediate updates

### Understanding the Data

- **Quantities**: Shows total amounts across all storage buildings
- **Tiers**: Items are organized by their tier level (T1, T2, T3, etc.)

### Managing Settings

- **Region Selection**: Change your server region from the dropdown
- **Data Refresh**: Control when inventory data is updated
- **Window Positioning**: Inventory windows can be moved and resized

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

## 📝 License
This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.