"""
Shared test fixtures and configuration for pytest.
"""

import pytest
import sys
import os
from unittest.mock import Mock

# Ensure the app directory is in the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


@pytest.fixture
def mock_bitcraft_client():
    """Create a mock BitCraft client for testing."""
    from client import BitCraft
    mock_client = Mock(spec=BitCraft)
    mock_client.auth = "test-auth-token"
    mock_client.email = "test@example.com"
    mock_client.player_name = "TestPlayer"
    mock_client.region = "bitcraft-1"
    mock_client.ws_connection = None
    mock_client._is_valid_email.return_value = True
    return mock_client


@pytest.fixture
def mock_claim():
    """Create a mock Claim instance for testing."""
    from claim import Claim
    mock_claim = Mock(spec=Claim)
    mock_claim.get_claim_id.return_value = "test-claim-123"
    mock_claim.get_claim_name.return_value = "Test Claim"
    mock_claim.get_owner_id.return_value = "test-owner-456"
    mock_claim.get_buildings.return_value = []
    mock_claim.get_inventory.return_value = {}
    return mock_claim


@pytest.fixture
def sample_inventory_data():
    """Sample inventory data for testing."""
    return [
        {"id": "item1", "Name": "Wood", "Quantity": 100, "Tier": 1, "Tag": "Materials"},
        {"id": "item2", "Name": "Stone", "Quantity": 50, "Tier": 1, "Tag": "Materials"},
        {"id": "item3", "Name": "Iron", "Quantity": 25, "Tier": 2, "Tag": "Metals"},
    ]


@pytest.fixture
def sample_buildings_data():
    """Sample buildings data for testing."""
    return [
        {
            "entity_id": "building1",
            "type": "storage",
            "inventory": {
                "item1": {"name": "Wood", "quantity": 100, "tier": 1, "tag": "Materials"},
                "item2": {"name": "Stone", "quantity": 50, "tier": 1, "tag": "Materials"}
            }
        },
        {
            "entity_id": "building2", 
            "type": "workshop",
            "inventory": {
                "item1": {"name": "Wood", "quantity": 75, "tier": 1, "tag": "Materials"},
                "item3": {"name": "Iron", "quantity": 25, "tier": 2, "tag": "Metals"}
            }
        }
    ]
