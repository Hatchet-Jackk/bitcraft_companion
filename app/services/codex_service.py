"""
CodexService - Minimal Implementation

A lightweight service for codex material requirements tracking.
Based on lessons learned - focuses on simplicity and avoids background processing complexity.

Key principles:
- Lazy initialization (no expensive operations in __init__)
- Template-based calculations (no recursive recipe resolution) 
- Direct inventory lookups (no large data copying)
- Simple caching with automatic invalidation
"""

import logging
import pickle
import threading
import time
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from .cascading_inventory_service import CascadingInventoryCalculator, extract_dependency_trees_from_templates


class CodexService:
    """
    Minimal codex service for material requirements tracking.
    
    Uses pre-calculated binary templates for fast material requirement lookups.
    Avoids all the problematic patterns that caused previous implementation failures.
    """
    
    def __init__(self, data_service):
        """
        Initialize CodexService with lazy loading.
        
        CRITICAL: No expensive operations here - this was the key lesson learned.
        """
        self.data_service = data_service
        
        # Template system
        self._templates_loaded = False
        self._static_templates = {}  # Will store pre-calculated material requirements
        self._template_lock = threading.RLock()
        
        # Simple supply cache (avoid complex background processing)
        self._supply_cache = {}
        self._cache_timestamp = 0
        self._cache_ttl = 30  # 30 second cache
        
        # Advanced caching system for requirements and inventory
        self._requirements_cache = {}  # (tier_key, inventory_hash) -> requirements
        self._inventory_cache = {}     # timestamp -> consolidated_inventory  
        self._inventory_hash_cache = None  # current inventory hash
        self._last_inventory_check = 0
        self._requirements_cache_ttl = 300  # 5 minutes for requirements cache
        
        # Cascading inventory calculator
        self._cascading_calculator = CascadingInventoryCalculator()
        self._dependency_trees = {}  # Will be loaded when templates are loaded
        
        logging.info("CodexService initialized (lazy mode - no expensive operations)")
    
    def are_templates_loaded(self) -> bool:
        """Check if templates are loaded and ready."""
        with self._template_lock:
            return self._templates_loaded
    
    def load_templates_sync(self) -> bool:
        """
        Load templates synchronously when needed.
        
        This is called when templates are actually needed, not during startup.
        """
        with self._template_lock:
            if self._templates_loaded:
                return True
            
            try:
                template_dir = Path(__file__).parent.parent / "data" / "codex_templates"
                
                if not template_dir.exists():
                    logging.warning(f"Template directory not found: {template_dir}")
                    return False
                
                # Load manifest first
                manifest_file = template_dir / "manifest.bin"
                if manifest_file.exists():
                    with open(manifest_file, 'rb') as f:
                        manifest = pickle.load(f)
                    logging.info(f"Loading templates for {len(manifest['professions'])} professions")
                
                # Load individual profession templates
                templates_loaded = 0
                for profession in ["cloth", "metal", "wood", "stone", "leather", "scholar"]:
                    template_file = template_dir / f"{profession}_templates.bin"
                    if template_file.exists():
                        with open(template_file, 'rb') as f:
                            self._static_templates[profession] = pickle.load(f)
                        templates_loaded += 1
                        logging.debug(f"Loaded {profession} template successfully")
                    else:
                        logging.warning(f"Template file not found: {template_file}")
                        # Create empty template for missing professions
                        self._static_templates[profession] = {}
                
                self._templates_loaded = templates_loaded > 0
                
                # Extract dependency trees for cascading calculator
                if self._templates_loaded:
                    self._dependency_trees = extract_dependency_trees_from_templates(self._static_templates)
                    logging.info(f"Templates loaded successfully: {templates_loaded} professions, {len(self._dependency_trees)} dependency trees")
                else:
                    logging.info(f"Templates loaded successfully: {templates_loaded} professions")
                
                return self._templates_loaded
                
            except Exception as e:
                logging.error(f"Failed to load templates: {e}")
                return False
    
    def get_template_for_profession(self, profession: str, tier: int) -> Optional[Dict[str, float]]:
        """
        Get template data for a specific profession and tier.
        
        Returns the pre-calculated material requirements.
        """
        if not self._templates_loaded:
            if not self.load_templates_sync():
                return None
        
        with self._template_lock:
            profession_data = self._static_templates.get(profession, {})
            return profession_data.get(tier, {})
    
    def get_current_supply(self, material_name: str) -> int:
        """
        Get current supply of a material from processed inventory data.
        
        Uses the same consolidated inventory data as the main inventory tab
        to ensure consistency across the application.
        """
        current_time = time.time()
        
        # Check cache validity
        if current_time - self._cache_timestamp > self._cache_ttl:
            self._supply_cache.clear()
            self._cache_timestamp = current_time
        
        # Return cached value if available
        if material_name in self._supply_cache:
            return self._supply_cache[material_name]
        
        # Get supply from processed inventory data (same as main inventory tab)
        supply = 0
        try:
            consolidated_inventory = self.data_service.get_consolidated_inventory()
            
            if isinstance(consolidated_inventory, dict):
                item_data = consolidated_inventory.get(material_name)
                if item_data and isinstance(item_data, dict):
                    supply = item_data.get('total_quantity', 0)
                    logging.debug(f"Found {supply} {material_name} in consolidated inventory")
                else:
                    logging.debug(f"Material '{material_name}' not found in consolidated inventory")
            else:
                logging.debug(f"No consolidated inventory available (type: {type(consolidated_inventory)})")
                
        except Exception as e:
            logging.debug(f"Error getting supply for {material_name}: {e}")
        
        # Cache the result
        self._supply_cache[material_name] = supply
        return supply
    
    def _get_inventory_hash(self) -> str:
        """
        Generate a hash of current inventory state for cache invalidation.
        
        Returns:
            Hash string representing current inventory state
        """
        current_time = time.time()
        
        # Check if we need to refresh the hash (every 30 seconds)
        if current_time - self._last_inventory_check > 30:
            try:
                consolidated_inventory = self.data_service.get_consolidated_inventory()
                
                if isinstance(consolidated_inventory, dict):
                    # Create a simplified version for hashing (item_name -> quantity)
                    inventory_for_hash = {}
                    for item_name, item_data in consolidated_inventory.items():
                        if isinstance(item_data, dict):
                            inventory_for_hash[item_name] = item_data.get('total_quantity', 0)
                    
                    # Generate hash from sorted inventory data
                    inventory_json = json.dumps(inventory_for_hash, sort_keys=True)
                    self._inventory_hash_cache = hashlib.md5(inventory_json.encode()).hexdigest()
                else:
                    self._inventory_hash_cache = "empty"
                    
                self._last_inventory_check = current_time
                logging.debug(f"Updated inventory hash: {self._inventory_hash_cache}")
                
            except Exception as e:
                logging.debug(f"Error generating inventory hash: {e}")
                self._inventory_hash_cache = "error"
                
        return self._inventory_hash_cache or "unknown"
    
    def _get_tier_cache_key(self, current_tier: int, target_tier: int) -> str:
        """
        Generate cache key for tier requirements.
        
        Args:
            current_tier: Current claim tier
            target_tier: Target claim tier
            
        Returns:
            Cache key string
        """
        return f"{current_tier}->{target_tier}"
    
    def _get_cached_requirements(self, tier_key: str, inventory_hash: str) -> Optional[Dict]:
        """
        Get cached requirements if available and valid.
        
        Args:
            tier_key: Tier transition key (e.g., "4->5")
            inventory_hash: Current inventory hash
            
        Returns:
            Cached requirements or None if not available/invalid
        """
        current_time = time.time()
        cache_key = (tier_key, inventory_hash)
        
        if cache_key in self._requirements_cache:
            cached_data, timestamp = self._requirements_cache[cache_key]
            
            # Check if cache is still valid
            if current_time - timestamp < self._requirements_cache_ttl:
                logging.info(f"Using cached requirements for {tier_key} (inventory: {inventory_hash[:8]}...)")
                return cached_data
            else:
                # Cache expired, remove it
                del self._requirements_cache[cache_key]
                logging.debug(f"Cache expired for {tier_key}")
                
        return None
    
    def _cache_requirements(self, tier_key: str, inventory_hash: str, requirements: Dict):
        """
        Cache calculated requirements.
        
        Args:
            tier_key: Tier transition key
            inventory_hash: Current inventory hash
            requirements: Calculated requirements to cache
        """
        current_time = time.time()
        cache_key = (tier_key, inventory_hash)
        
        self._requirements_cache[cache_key] = (requirements, current_time)
        
        # Clean old cache entries (keep only last 10)
        if len(self._requirements_cache) > 10:
            oldest_key = min(self._requirements_cache.keys(), 
                           key=lambda k: self._requirements_cache[k][1])
            del self._requirements_cache[oldest_key]
            
        logging.info(f"Cached requirements for {tier_key} (inventory: {inventory_hash[:8]}...)")
    
    def get_current_claim_tier(self) -> int:
        """
        Get the current tier of the player's claim from claim tech data.
        
        Uses subscription data via ClaimsProcessor and ClaimTechState methods for proper tier parsing.
        """
        try:
            # Get current claim ID
            if not hasattr(self.data_service, 'claim') or not self.data_service.claim:
                logging.debug("No claim available for tier lookup")
                return 4
                
            claim_id = self.data_service.claim.claim_id
            if not claim_id:
                logging.debug("No claim ID available for tier lookup")
                return 4
            
            # Find ClaimsProcessor from processors list
            claims_processor = None
            if hasattr(self.data_service, 'processors') and self.data_service.processors:
                for processor in self.data_service.processors:
                    if hasattr(processor, 'get_claim_tech_state'):
                        claims_processor = processor
                        break
            
            if not claims_processor:
                logging.debug("ClaimsProcessor not found")
                return 4
            
            # Get claim tech state for current claim
            logging.debug(f"Looking up claim tech state for claim {claim_id}")
            claim_tech = claims_processor.get_claim_tech_state(int(claim_id))
            if claim_tech:
                current_tier = claim_tech.get_current_tier()
                logging.info(f"Found claim tier: T{current_tier} for claim {claim_id}")
                return current_tier
            else:
                logging.warning(f"No claim tech data found for claim {claim_id}")
                return 4
            
        except Exception as e:
            logging.debug(f"Error getting claim tier from subscription data: {e}")
            return 4
    
    def get_target_tier(self) -> int:
        """
        Get the target tier (current + 1) for codex calculations.
        """
        return self.get_current_claim_tier() + 1
    
    def get_codex_requirements_for_tier(self, tier: int) -> Dict:
        """
        Get codex requirements for a specific tier from reference data.
        
        Uses cached reference data from the reference processor.
        """
        try:
            reference_processor = None
            if hasattr(self.data_service, 'processors'):
                for processor in self.data_service.processors:
                    if type(processor).__name__ == 'ReferenceDataProcessor':
                        reference_processor = processor
                        break
            
            if reference_processor:
                # Get claim_tech_desc items from the processor cache
                tech_items = reference_processor.get_reference_items('claim_tech_desc')
                
                for tech_item in tech_items:
                    if hasattr(tech_item, 'tier') and tech_item.tier == tier:
                        return {
                            'tier': tier,
                            'supplies_cost': tech_item.supplies_cost,
                            'requirements': tech_item.requirements,
                            'input': tech_item.input
                        }
                
                # Also check the backward compatibility dict format
                if hasattr(reference_processor, 'reference_data') and reference_processor.reference_data:
                    reference_data = reference_processor.reference_data
                    if 'claim_tech_desc' in reference_data:
                        for tech_desc in reference_data['claim_tech_desc']:
                            if isinstance(tech_desc, dict) and tech_desc.get('tier') == tier:
                                return {
                                    'tier': tier,
                                    'supplies_cost': tech_desc.get('supplies_cost', 0),
                                    'requirements': tech_desc.get('requirements', []),
                                    'input': tech_desc.get('input', [])
                                }
                
            else:
                logging.error(f"No ReferenceDataProcessor found in processors list")
            
            logging.error(f"Could not find tier {tier} data - returning error")
            return {'tier': tier, 'supplies_cost': 0, 'requirements': [], 'input': [], 'error': 'no_data'}
            
        except Exception as e:
            logging.error(f"Error getting codex requirements for tier {tier}: {e}")
            return {'tier': tier, 'supplies_cost': 0, 'requirements': [], 'input': [], 'error': str(e)}
    
    def calculate_tier_requirements(self, current_tier: int = None, target_tier: int = None, codex_window=None) -> Dict[str, Dict[str, float]]:
        """
        Calculate material requirements for tier advancement with smart caching.
        
        Uses templates for fast calculation and caches results based on inventory state.
        Returns simple need vs supply data.
        
        If no parameters provided, uses real claim tech data.
        """
        # Use real claim data if no parameters provided
        if current_tier is None:
            current_tier = self.get_current_claim_tier()
        if target_tier is None:
            target_tier = self.get_target_tier()
        
        tier_key = self._get_tier_cache_key(current_tier, target_tier)
        inventory_hash = self._get_inventory_hash()
        
        # Try to get cached results first
        cached_results = self._get_cached_requirements(tier_key, inventory_hash)
        if cached_results is not None:
            return cached_results
        
        logging.info(f"Calculating codex requirements: T{current_tier} -> T{target_tier} (no cache)")
        
        if target_tier <= current_tier:
            logging.warning(f"Target tier {target_tier} <= current tier {current_tier}, no requirements")
            return {}
        
        if not self._templates_loaded:
            if not self.load_templates_sync():
                return {}
        
        # Perform the calculation
        results = self._calculate_requirements_internal(target_tier, codex_window)
        
        # Cache the results
        self._cache_requirements(tier_key, inventory_hash, results)
        
        return results
    
    def _calculate_requirements_internal(self, target_tier: int, codex_window=None) -> Dict[str, Dict[str, float]]:
        """
        Internal method for calculating requirements with optimized batch inventory queries.
        
        Args:
            target_tier: Target tier to calculate requirements for
            
        Returns:
            Dictionary of profession requirements
        """
        results = {}
        
        # Get codex requirements to determine total needed
        codex_required = 30  # Default
        if codex_window:
            try:
                codex_requirements = self.get_codex_requirements_for_tier(target_tier)
                codex_required = codex_window._extract_codex_quantity_from_requirements(codex_requirements, target_tier)
            except:
                pass
        
        # First pass: collect all required materials across all professions
        all_required_materials = set()
        profession_templates = {}
        profession_adjustments = {}  
        
        for profession in ["cloth", "metal", "wood", "stone", "leather", "scholar"]:
            template = self.get_template_for_profession(profession, target_tier)
            if not template:
                continue
                
            profession_templates[profession] = template
            
            # Calculate adjustment factor based on existing refined products
            refined_count = 0
            if codex_window:
                refined_count = codex_window._get_refined_product_count(profession, target_tier)
            
            # Calculate how many we still need to make
            remaining_needed = max(0, codex_required - refined_count)
            adjustment_factor = remaining_needed / codex_required if codex_required > 0 else 0
            profession_adjustments[profession] = adjustment_factor
            
            logging.debug(f"{profession}: {refined_count}/{codex_required} refined, need {remaining_needed} more (factor: {adjustment_factor:.2f})")
            
            # Collect material names for batch lookup
            for material_name, material_data in template.items():
                # Handle both old format (just quantity) and new format (dict with quantity and tier)
                if isinstance(material_data, dict):
                    tier = material_data.get('tier', 1)
                else:
                    tier = 1
                
                # Tier filtering: Only include materials with tier <= target_tier
                if tier <= target_tier:
                    all_required_materials.add(material_name)
        
        # Batch inventory lookup: get all supplies at once
        batch_supplies = self._get_batch_supply(list(all_required_materials))
        
        # Prepare base requirements for cascading calculator
        base_requirements = {}
        for profession, template in profession_templates.items():
            adjustment_factor = profession_adjustments.get(profession, 1.0)
            
            for material_name, material_data in template.items():
                # Handle both old format (just quantity) and new format (dict with quantity and tier)
                if isinstance(material_data, dict):
                    base_quantity = material_data.get('quantity', 0)
                    tier = material_data.get('tier', 1)
                else:
                    base_quantity = material_data
                    tier = 1
                
                # Tier filtering: Only include materials with tier <= target_tier
                if tier <= target_tier:
                    # Apply adjustment factor for refined products
                    quantity_needed = int(base_quantity * adjustment_factor)
                    
                    # Accumulate requirements across professions (some materials appear in multiple)
                    if material_name in base_requirements:
                        base_requirements[material_name] += quantity_needed
                    else:
                        base_requirements[material_name] = quantity_needed
        
        # Apply cascading inventory reductions
        cascaded_requirements = {}
        if self._dependency_trees and base_requirements:
            # Debug: check what inventory we have
            inventory_with_items = {k: v for k, v in batch_supplies.items() if v > 0}
            logging.debug(f"Batch supplies with inventory: {len(inventory_with_items)} items: {list(inventory_with_items.keys())[:5]}...")
            
            cascaded_results = self._cascading_calculator.apply_cascading_reductions(
                base_requirements, batch_supplies, self._dependency_trees
            )
            
            # Convert cascaded results to simple requirement dict
            for material_name, info in cascaded_results.items():
                cascaded_requirements[material_name] = info['final_need']
                
            logging.debug(f"Applied cascading reductions: {len([m for m, info in cascaded_results.items() if info['inventory_reduction'] > 0])} materials reduced")
        else:
            # No cascading - use original requirements
            cascaded_requirements = base_requirements
        
        # Second pass: build results using cascaded requirements
        for profession, template in profession_templates.items():
            profession_materials = {}
            
            for material_name, material_data in template.items():
                # Handle both old format (just quantity) and new format (dict with quantity and tier)
                if isinstance(material_data, dict):
                    tier = material_data.get('tier', 1)
                else:
                    tier = 1
                
                # Tier filtering: Only include materials with tier <= target_tier
                if tier > target_tier:
                    logging.debug(f"Filtering out {material_name} (tier {tier} > target {target_tier})")
                    continue
                
                # Use cascaded requirement (already adjusted for refined products and cascading reductions)
                quantity_needed = cascaded_requirements.get(material_name, 0)
                
                # Use batch-fetched supply data
                current_supply = batch_supplies.get(material_name, 0)
                
                profession_materials[material_name] = {
                    'need': quantity_needed,
                    'supply': current_supply,
                    'progress': min(1.0, current_supply / quantity_needed) if quantity_needed > 0 else 1.0,
                    'tier': tier
                }
            
            if profession_materials:
                results[profession] = profession_materials
        
        return results
    
    def _get_batch_supply(self, material_names: list) -> Dict[str, int]:
        """
        Get supply data for multiple materials in a single batch operation.
        
        Args:
            material_names: List of material names to get supplies for
            
        Returns:
            Dictionary mapping material names to their supply quantities
        """
        batch_supplies = {}
        current_time = time.time()
        
        # Check if we need to refresh the consolidated inventory cache
        if current_time - self._cache_timestamp > self._cache_ttl:
            self._supply_cache.clear()  # Clear individual cache
            
        try:
            # Get consolidated inventory once
            consolidated_inventory = self.data_service.get_consolidated_inventory()
            
            if isinstance(consolidated_inventory, dict):
                # Process all requested materials at once
                for material_name in material_names:
                    supply = 0
                    
                    # Check individual cache first
                    if material_name in self._supply_cache and current_time - self._cache_timestamp <= self._cache_ttl:
                        supply = self._supply_cache[material_name]
                    else:
                        # Look up in consolidated inventory
                        item_data = consolidated_inventory.get(material_name)
                        if item_data and isinstance(item_data, dict):
                            supply = item_data.get('total_quantity', 0)
                        
                        # Cache the result
                        self._supply_cache[material_name] = supply
                    
                    batch_supplies[material_name] = supply
                
                # Update cache timestamp
                self._cache_timestamp = current_time
                
                logging.debug(f"Batch fetched supplies for {len(material_names)} materials")
            else:
                logging.debug(f"No consolidated inventory available for batch fetch")
                # Fallback: all materials have 0 supply
                batch_supplies = {name: 0 for name in material_names}
                
        except Exception as e:
            logging.debug(f"Error in batch supply fetch: {e}")
            # Fallback: all materials have 0 supply
            batch_supplies = {name: 0 for name in material_names}
        
        return batch_supplies
    
    def invalidate_cache(self):
        """Invalidate all caches when inventory changes."""
        self._supply_cache.clear()
        self._cache_timestamp = 0
        
        # Invalidate advanced caches
        self._requirements_cache.clear()
        self._inventory_cache.clear()
        self._inventory_hash_cache = None
        self._last_inventory_check = 0
        
        logging.info("All codex caches invalidated")
    
    def cleanup(self):
        """Clean up resources."""
        with self._template_lock:
            self._static_templates.clear()
            self._supply_cache.clear()
            self._templates_loaded = False
        
        logging.info("CodexService cleanup completed")