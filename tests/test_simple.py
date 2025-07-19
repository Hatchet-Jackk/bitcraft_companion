"""
Simple unit tests for the modular architecture.
Run with: poetry run python tests/test_simple.py
"""

# pyright: reportMissingImports=false

import sys
import os
import unittest
from unittest.mock import Mock

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


class TestModularStructure(unittest.TestCase):
    """Test the modular structure is working correctly."""

    def test_can_import_all_modules(self):
        """Test that all modules can be imported without errors."""
        modules_to_test = [
            "client",
            "claim",
            "base_window",
            "inventory_service",
            "inventory_window",
        ]

        for module_name in modules_to_test:
            try:
                __import__(module_name)
                print(f"✓ Successfully imported {module_name}")
            except ImportError as e:
                self.fail(f"Failed to import {module_name}: {e}")

    def test_no_duplicate_classes(self):
        """Test that ClaimInventoryWindow is not duplicated."""
        # Should be able to import from inventory_window
        try:
            from inventory_window import ClaimInventoryWindow

            inventory_window_has_class = True
        except ImportError:
            inventory_window_has_class = False

        # Should NOT be importable from main
        try:
            from main import ClaimInventoryWindow

            main_has_duplicate = True
        except ImportError:
            main_has_duplicate = False

        # Should NOT be importable from overlay
        try:
            from overlay import ClaimInventoryWindow

            overlay_has_duplicate = True
        except ImportError:
            overlay_has_duplicate = False

        self.assertTrue(
            inventory_window_has_class,
            "ClaimInventoryWindow should be in inventory_window module",
        )
        self.assertFalse(
            main_has_duplicate, "ClaimInventoryWindow should NOT be in main module"
        )
        self.assertFalse(
            overlay_has_duplicate,
            "ClaimInventoryWindow should NOT be in overlay module",
        )

        print("✓ No duplicate ClaimInventoryWindow classes found")

    def test_inheritance_structure(self):
        """Test that inheritance is working correctly."""
        from main import BitCraftMainWindow
        from overlay import BitCraftOverlay
        from base_window import BaseWindow

        self.assertTrue(issubclass(BitCraftMainWindow, BaseWindow))
        self.assertTrue(issubclass(BitCraftOverlay, BaseWindow))

        print("✓ Inheritance structure is correct")

    def test_client_basic_functionality(self):
        """Test basic client operations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
        from client import BitCraft

        client = BitCraft()
        original_region = client.region
        try:
            # Test setting region
            client.region = "bitcraft-2"
            self.assertEqual(client.region, "bitcraft-2")
        finally:
            # Restore original region
            client.region = original_region

    def test_claim_basic_functionality(self):
        """Test basic Claim functionality."""
        from claim import Claim

        claim = Claim()

        # Test initial state
        self.assertIsNone(claim.get_claim_id())
        self.assertIsNone(claim.get_claim_name())

        # Test setting values
        claim.set_claim_id("test-123")
        claim.set_claim_name("Test Claim")
        claim.set_owner_id("owner-456")

        self.assertEqual(claim.get_claim_id(), "test-123")
        self.assertEqual(claim.get_claim_name(), "Test Claim")
        self.assertEqual(claim.get_owner_id(), "owner-456")

        print("✓ Claim basic functionality works")

    def test_inventory_service_initialization(self):
        """Test InventoryService can be initialized."""
        from inventory_service import InventoryService
        from client import BitCraft
        from claim import Claim

        client = BitCraft()
        claim = Claim()
        service = InventoryService(client, claim)

        self.assertEqual(service.bitcraft_client, client)
        self.assertEqual(service.claim_instance, claim)
        self.assertIsNone(service.cached_inventory_data)
        self.assertIsNone(service.last_inventory_fetch_time)

        print("✓ InventoryService initialization works")


def run_tests():
    """Run the tests and print results."""
    print("🧪 Running modular architecture tests...\n")

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestModularStructure)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w"))
    result = runner.run(suite)

    print(f"\n📊 Test Results:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")

    if result.failures:
        print(f"\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback}")

    if result.errors:
        print(f"\n💥 Errors:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback}")

    if result.wasSuccessful():
        print("\n🎉 All tests passed! Modular architecture is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Please check the issues above.")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
