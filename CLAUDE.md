# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BitCraft Companion is a desktop application built with CustomTkinter that connects to the BitCraft game servers via WebSocket to provide real-time data about claims, inventory, passive crafting operations, and active crafting operations. The application uses a modular processor-based architecture to handle different types of game data.

## Development Commands

### Dependencies
- **Install dependencies**: `poetry install`
- **Run application**: `poetry run python app/main.py`

### Testing
- **Run tests**: `poetry run pytest`
- **Run specific test**: `poetry run pytest tests/test_specific.py`
- **Run with verbose output**: `poetry run pytest -v`

### Build
- **Build executable**: Run `build_exe.bat` (Windows batch script that uses PyInstaller)
- **Generate version**: `python generate_version.py`

## Execution Guidelines

### Testing Protocol
- **I will perform all tests. do not ask me to run the application**
- I will run tests personally do not try to run any. just ask

## Architecture Overview

### Core Architecture
The application follows a layered architecture with clear separation of concerns:

1. **UI Layer** (`app/ui/`): CustomTkinter-based GUI components
2. **Service Layer** (`app/services/`): Business logic and data management
3. **Core Layer** (`app/core/`): Message routing and data processing
4. **Client Layer** (`app/client/`): BitCraft API communication
5. **Models** (`app/models/`): Data structures and entities

[... rest of the file remains unchanged ...]