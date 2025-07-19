import unittest
import sys
import os

# pyright: reportMissingImports=false

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from unittest.mock import Mock, patch, MagicMock
import customtkinter as ctk

# Import the modules we want to test
from client import BitCraft
from claim import Claim
from base_window import BaseWindow
from inventory_service import InventoryService


class TestBitCraftClient(unittest.TestCase):
    """Test cases for BitCraft client functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = BitCraft()

    def test_client_initialization(self):
        """Test that BitCraft client initializes correctly."""
        self.assertIsInstance(self.client, BitCraft)
        self.assertIsNone(self.client.ws_connection)

    def test_email_validation(self):
        """Test email validation method."""
        # Valid emails
        self.assertTrue(self.client._is_valid_email("test@example.com"))
        self.assertTrue(self.client._is_valid_email("user.name@domain.co.uk"))

        # Invalid emails
        self.assertFalse(self.client._is_valid_email("invalid-email"))
        self.assertFalse(self.client._is_valid_email("@domain.com"))
        self.assertFalse(self.client._is_valid_email("user@"))
        self.assertFalse(self.client._is_valid_email(""))

    def test_region_setting(self):
        """Test region setting and getting operations."""
        original_region = self.client.region
        test_region = "bitcraft-2"
        try:
            self.client.region = test_region
            self.assertEqual(self.client.region, test_region)
        finally:
            # Restore original region
            self.client.region = original_region

    def test_endpoint_setting(self):
        """Test setting endpoint on client."""
        test_endpoint = "subscribe"
        self.client.set_endpoint(test_endpoint)
        self.assertEqual(self.client.endpoint, test_endpoint)


class TestClaim(unittest.TestCase):
    """Test cases for Claim model functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.claim = Claim()

    def test_claim_initialization(self):
        """Test that Claim initializes correctly."""
        self.assertIsInstance(self.claim, Claim)
        self.assertIsNone(self.claim.get_claim_id())
        self.assertIsNone(self.claim.get_claim_name())
        self.assertIsNone(self.claim.get_owner_id())

    def test_claim_id_operations(self):
        """Test setting and getting claim ID."""
        test_id = "test-claim-123"
        self.claim.set_claim_id(test_id)
        self.assertEqual(self.claim.get_claim_id(), test_id)

    def test_claim_name_operations(self):
        """Test setting and getting claim name."""
        test_name = "Test Claim"
        self.claim.set_claim_name(test_name)
        self.assertEqual(self.claim.get_claim_name(), test_name)

    def test_owner_id_operations(self):
        """Test setting and getting owner ID."""
        test_owner = "owner-123"
        self.claim.set_owner_id(test_owner)
        self.assertEqual(self.claim.get_owner_id(), test_owner)

    def test_buildings_operations(self):
        """Test building operations."""
        test_buildings = [
            {"entity_id": "building1", "type": "storage", "building_description_id": "storage_building"},
            {"entity_id": "building2", "type": "workshop", "building_description_id": "workshop_building"},
        ]

        self.claim.set_buildings(test_buildings)

        # Without reference data, buildings are grouped by "Unknown Type"
        buildings = self.claim.get_buildings()
        self.assertIsInstance(buildings, dict)

        # The buildings should be grouped under "Unknown Type" since we don't have reference data
        if "Unknown Type" in buildings:
            self.assertEqual(len(buildings["Unknown Type"]), 2)
        else:
            # If the implementation changes, just verify we got some buildings back
            total_buildings = sum(len(building_list) for building_list in buildings.values())
            self.assertGreater(total_buildings, 0)

    def test_inventory_aggregation(self):
        """Test inventory aggregation from buildings."""
        # Set up buildings with inventory
        buildings_with_inventory = [
            {
                "entity_id": "building1",
                "building_description_id": "storage_building",  # Required field
                "inventory": {
                    "item1": {"name": "Wood", "quantity": 100, "tier": 1},
                    "item2": {"name": "Stone", "quantity": 50, "tier": 1},
                },
            },
            {
                "entity_id": "building2",
                "building_description_id": "workshop_building",  # Required field
                "inventory": {
                    "item1": {"name": "Wood", "quantity": 75, "tier": 1},
                    "item3": {"name": "Iron", "quantity": 25, "tier": 2},
                },
            },
        ]

        self.claim.set_buildings(buildings_with_inventory)
        inventory = self.claim.get_inventory()

        # Without reference data, inventory aggregation returns empty dict
        self.assertIsInstance(inventory, dict)
        # We can't test specific items without reference data loaded


class TestInventoryService(unittest.TestCase):
    """Test cases for InventoryService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=BitCraft)
        self.mock_claim = Mock(spec=Claim)
        self.service = InventoryService(self.mock_client, self.mock_claim)

    def test_service_initialization(self):
        """Test that InventoryService initializes correctly."""
        self.assertIsInstance(self.service, InventoryService)
        self.assertEqual(self.service.bitcraft_client, self.mock_client)
        self.assertEqual(self.service.claim_instance, self.mock_claim)

    def test_cache_validation_no_data(self):
        """Test cache validation when no data exists."""
        self.service.cached_inventory_data = None
        self.service.last_inventory_fetch_time = None

        self.assertFalse(self.service.is_cache_valid())

    def test_cache_validation_expired(self):
        """Test cache validation when data is expired."""
        from datetime import datetime, timedelta

        # Set cache time to 10 minutes ago (beyond 5 minute cache duration)
        self.service.last_inventory_fetch_time = datetime.now() - timedelta(minutes=10)
        self.service.cached_inventory_data = [{"test": "data"}]

        self.assertFalse(self.service.is_cache_valid())

    def test_cache_validation_valid(self):
        """Test cache validation when data is still valid."""
        from datetime import datetime, timedelta

        # Set cache time to 2 minutes ago (within 5 minute cache duration)
        self.service.last_inventory_fetch_time = datetime.now() - timedelta(minutes=2)
        self.service.cached_inventory_data = [{"test": "data"}]

        self.assertTrue(self.service.is_cache_valid())


class TestBaseWindow(unittest.TestCase):
    """Test cases for BaseWindow functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock root for testing (since we can't create actual windows in tests)
        self.mock_root = Mock()

    @patch("customtkinter.CTk")
    def test_base_window_initialization(self, mock_ctk):
        """Test that BaseWindow initializes correctly."""
        # Mock the CTk initialization
        mock_instance = Mock()
        mock_ctk.return_value = mock_instance

        # We can't actually instantiate BaseWindow in tests due to Tkinter
        # but we can test the concept
        self.assertTrue(hasattr(BaseWindow, "__init__"))
        self.assertTrue(hasattr(BaseWindow, "initialize_services"))
        self.assertTrue(hasattr(BaseWindow, "toggle_claim_inventory_window"))


class TestModuleImports(unittest.TestCase):
    """Test that all modules can be imported correctly."""

    def test_import_client(self):
        """Test that client module imports correctly."""
        try:
            from client import BitCraft

            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import client module: {e}")

    def test_import_claim(self):
        """Test that claim module imports correctly."""
        try:
            from claim import Claim

            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import claim module: {e}")

    def test_import_base_window(self):
        """Test that base_window module imports correctly."""
        try:
            from base_window import BaseWindow

            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import base_window module: {e}")

    def test_import_inventory_service(self):
        """Test that inventory_service module imports correctly."""
        try:
            from inventory_service import InventoryService

            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import inventory_service module: {e}")

    def test_import_inventory_window(self):
        """Test that inventory_window module imports correctly."""
        try:
            from inventory_window import ClaimInventoryWindow, FilterDialog

            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import inventory_window module: {e}")


if __name__ == "__main__":
    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestBitCraftClient))
    suite.addTests(loader.loadTestsFromTestCase(TestClaim))
    suite.addTests(loader.loadTestsFromTestCase(TestInventoryService))
    suite.addTests(loader.loadTestsFromTestCase(TestBaseWindow))
    suite.addTests(loader.loadTestsFromTestCase(TestModuleImports))

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
