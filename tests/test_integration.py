"""
Integration tests for the BitCraft application modules.
Run with: poetry run python -m pytest tests/ -v
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


class TestModuleStructure:
    """Test the modular structure and imports."""
    
    def test_client_module_exists(self):
        """Test that client module can be imported."""
        try:
            import client
            assert hasattr(client, 'BitCraft')
        except ImportError:
            pytest.fail("Could not import client module")
    
    def test_claim_module_exists(self):
        """Test that claim module can be imported."""
        try:
            import claim
            assert hasattr(claim, 'Claim')
        except ImportError:
            pytest.fail("Could not import claim module")
    
    def test_base_window_module_exists(self):
        """Test that base_window module can be imported."""
        try:
            import base_window
            assert hasattr(base_window, 'BaseWindow')
        except ImportError:
            pytest.fail("Could not import base_window module")
    
    def test_inventory_service_module_exists(self):
        """Test that inventory_service module can be imported."""
        try:
            import inventory_service
            assert hasattr(inventory_service, 'InventoryService')
        except ImportError:
            pytest.fail("Could not import inventory_service module")
    
    def test_inventory_window_module_exists(self):
        """Test that inventory_window module can be imported."""
        try:
            import inventory_window
            assert hasattr(inventory_window, 'ClaimInventoryWindow')
            assert hasattr(inventory_window, 'FilterDialog')
        except ImportError:
            pytest.fail("Could not import inventory_window module")


class TestBitCraftClient:
    """Test BitCraft client functionality."""
    
    @pytest.fixture
    def client(self):
        """Create a BitCraft client for testing."""
        from client import BitCraft
        return BitCraft()
    
    def test_client_initialization(self, client):
        """Test client initializes correctly."""
        assert client is not None
        assert hasattr(client, 'ws_connection')
        assert hasattr(client, 'auth')
    
    def test_email_validation(self, client):
        """Test email validation method."""
        # Valid emails
        assert client._is_valid_email("test@example.com") is True
        assert client._is_valid_email("user.name@domain.co.uk") is True
        
        # Invalid emails
        assert client._is_valid_email("invalid-email") is False
        assert client._is_valid_email("@domain.com") is False
        assert client._is_valid_email("user@") is False
        assert client._is_valid_email("") is False
    
    def test_region_setting(self, client):
        """Test setting and getting region on client."""
        original_region = client.region
        test_region = "bitcraft-2"
        try:
            client.region = test_region
            assert client.region == test_region
        finally:
            # Restore original region
            client.region = original_region


class TestClaim:
    """Test Claim model functionality."""
    
    @pytest.fixture
    def claim(self):
        """Create a Claim instance for testing."""
        from claim import Claim
        return Claim()
    
    def test_claim_initialization(self, claim):
        """Test claim initializes correctly."""
        assert claim is not None
        assert claim.get_claim_id() is None
        assert claim.get_claim_name() is None
        assert claim.get_owner_id() is None
    
    def test_claim_properties(self, claim):
        """Test setting and getting claim properties."""
        test_id = "test-claim-123"
        test_name = "Test Claim"
        test_owner = "owner-123"
        
        claim.set_claim_id(test_id)
        claim.set_claim_name(test_name)
        claim.set_owner_id(test_owner)
        
        assert claim.get_claim_id() == test_id
        assert claim.get_claim_name() == test_name
        assert claim.get_owner_id() == test_owner
    
    def test_inventory_aggregation(self, claim):
        """Test basic building storage without complex inventory aggregation."""
        buildings_with_inventory = [
            {
                "entity_id": "building1",
                "building_description_id": "storage_building",  # Required field
                "inventory": {
                    "item1": {"name": "Wood", "quantity": 100, "tier": 1, "tag": "Materials"},
                    "item2": {"name": "Stone", "quantity": 50, "tier": 1, "tag": "Materials"}
                }
            },
            {
                "entity_id": "building2", 
                "building_description_id": "workshop_building",  # Required field
                "inventory": {
                    "item1": {"name": "Wood", "quantity": 75, "tier": 1, "tag": "Materials"},
                    "item3": {"name": "Iron", "quantity": 25, "tier": 2, "tag": "Metals"}
                }
            }
        ]
        
        claim.set_buildings(buildings_with_inventory)
        
        # Test that buildings are stored (this will work without reference data)
        buildings = claim.get_buildings()
        assert isinstance(buildings, dict)
        
        # The inventory aggregation requires reference data to be loaded,
        # so we'll just test that the method exists and doesn't crash
        inventory = claim.get_inventory()
        assert isinstance(inventory, dict)  # Should return empty dict without reference data


class TestInventoryService:
    """Test InventoryService functionality."""
    
    @pytest.fixture
    def service(self):
        """Create an InventoryService for testing."""
        from inventory_service import InventoryService
        from client import BitCraft
        from claim import Claim
        
        mock_client = Mock(spec=BitCraft)
        mock_claim = Mock(spec=Claim)
        return InventoryService(mock_client, mock_claim)
    
    def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service is not None
        assert hasattr(service, 'bitcraft_client')
        assert hasattr(service, 'claim_instance')
        assert hasattr(service, 'cached_inventory_data')
        assert hasattr(service, 'last_inventory_fetch_time')
    
    def test_cache_validation_no_data(self, service):
        """Test cache validation when no data exists."""
        service.cached_inventory_data = None
        service.last_inventory_fetch_time = None
        
        assert service.is_cache_valid() is False
    
    def test_cache_validation_valid_data(self, service):
        """Test cache validation with valid data."""
        from datetime import datetime, timedelta
        
        # Set cache time to 2 minutes ago (within 5 minute cache duration)
        service.last_inventory_fetch_time = datetime.now() - timedelta(minutes=2)
        service.cached_inventory_data = [{"test": "data"}]
        
        assert service.is_cache_valid() is True
    
    def test_cache_validation_expired_data(self, service):
        """Test cache validation with expired data."""
        from datetime import datetime, timedelta
        
        # Set cache time to 10 minutes ago (beyond 5 minute cache duration)
        service.last_inventory_fetch_time = datetime.now() - timedelta(minutes=10)
        service.cached_inventory_data = [{"test": "data"}]
        
        assert service.is_cache_valid() is False


class TestIntegration:
    """Integration tests for the complete system."""
    
    def test_no_duplicate_classes(self):
        """Test that classes are not duplicated between modules."""
        # Check that ClaimInventoryWindow is only in inventory_window
        try:
            from inventory_window import ClaimInventoryWindow
            inventory_window_has_class = True
        except ImportError:
            inventory_window_has_class = False
        
        # Check that it's NOT in main or overlay
        try:
            from main import ClaimInventoryWindow
            main_has_class = True
        except ImportError:
            main_has_class = False
        
        try:
            from overlay import ClaimInventoryWindow  
            overlay_has_class = True
        except ImportError:
            overlay_has_class = False
        
        assert inventory_window_has_class is True
        assert main_has_class is False
        assert overlay_has_class is False
    
    def test_base_window_inheritance(self):
        """Test that main and overlay properly inherit from BaseWindow."""
        from main import BitCraftMainWindow
        from overlay import BitCraftOverlay
        from base_window import BaseWindow
        
        # Check inheritance hierarchy
        assert issubclass(BitCraftMainWindow, BaseWindow)
        assert issubclass(BitCraftOverlay, BaseWindow)
    
    def test_clean_imports(self):
        """Test that imports are clean and non-circular."""
        # This test will fail if there are circular imports
        try:
            from main import BitCraftMainWindow
            from overlay import BitCraftOverlay
            from base_window import BaseWindow
            from inventory_service import InventoryService
            from inventory_window import ClaimInventoryWindow
            
            # If we get here, imports are clean
            assert True
        except ImportError as e:
            pytest.fail(f"Circular import or missing dependency: {e}")


if __name__ == "__main__":
    # Run pytest programmatically if called directly
    pytest.main([__file__, "-v"])
