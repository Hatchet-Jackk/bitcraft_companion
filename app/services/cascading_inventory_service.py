"""
Cascading Inventory Service

Provides cascading inventory optimization that reduces material requirements
based on intermediate materials already in inventory.

Example: Having 100 Cloth in inventory reduces requirements for:
- 100 Cloth Strip (direct dependency)
- 100 Wispweave Filament (direct dependency)
- 300 Thread (indirect via Cloth Strip)
- 900 Fiber (indirect via Thread)

This creates a cascading reduction where higher-tier materials automatically
reduce ALL their dependency chains.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class CascadingInventoryCalculator:
    """
    Calculates optimized material requirements using cascading inventory reductions.

    Uses pre-computed dependency trees from templates to efficiently apply
    inventory reductions across complete crafting chains.
    """

    def __init__(self):
        self._cache = {}  # Cache for performance optimization
        self._cache_hits = 0
        self._cache_misses = 0
        self._complexity_scores = {}

    def apply_cascading_reductions(
        self, base_requirements: Dict[str, int], inventory: Dict[str, int], dependency_trees: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """
        Apply cascading inventory reductions to base material requirements.

        Args:
            base_requirements: Dict of {material_name: quantity_needed}
            inventory: Dict of {material_name: quantity_available}
            dependency_trees: Dict of {material_name: {'dependencies': {'all': [(name, qty)]}}}

        Returns:
            Dict of {material_name: {
                'original_need': int,
                'inventory_reduction': int,
                'final_need': int,
                'has_inventory': bool
            }}
        """
        # Create cache key for performance
        cache_key = self._build_cache_key(base_requirements, inventory)
        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]

        self._cache_misses += 1
        logger.debug(f"Cache miss - calculating cascading reductions (hits: {self._cache_hits}, misses: {self._cache_misses})")

        # Start with base requirements
        result = {}
        working_requirements = base_requirements.copy()
        total_reductions = defaultdict(int)  # Track all reductions applied

        # Sort inventory items by complexity (items with more dependencies first)
        # This ensures we get maximum reduction benefit
        inventory_items = self._get_sorted_inventory_items(inventory, dependency_trees)

        # Apply reductions for each inventory item
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Processing {len(inventory_items)} inventory items for cascading")
        for material_name, inventory_quantity in inventory_items:
            if inventory_quantity <= 0:
                continue

            logger.debug(f"Processing inventory: {material_name} x{inventory_quantity}")

            # Get dependency tree for this material
            material_info = dependency_trees.get(material_name, {})
            dependencies = material_info.get("dependencies", {})
            all_deps = dependencies.get("all", [])

            logger.debug(f"  {material_name} has {len(all_deps)} dependencies")

            # Apply reductions to all dependencies
            reductions_applied = 0
            for dep_name, dep_ratio in all_deps:
                if dep_name in working_requirements:
                    # Calculate maximum reduction we can apply
                    max_reduction = min(
                        inventory_quantity * dep_ratio,  # How much this inventory can reduce
                        working_requirements[dep_name],  # How much we actually need
                    )

                    if max_reduction > 0:
                        working_requirements[dep_name] -= max_reduction
                        total_reductions[dep_name] += max_reduction
                        reductions_applied += 1
                        logger.debug(f"    {material_name} x{inventory_quantity} reduces {dep_name} by {max_reduction}")

            logger.debug(f"  Applied {reductions_applied} reductions for {material_name}")

        # Build result with detailed reduction info
        for material_name, original_need in base_requirements.items():
            final_need = max(0, working_requirements.get(material_name, 0))
            inventory_reduction = total_reductions.get(material_name, 0)
            has_inventory = inventory.get(material_name, 0) > 0

            result[material_name] = {
                "original_need": original_need,
                "inventory_reduction": inventory_reduction,
                "final_need": final_need,
                "has_inventory": has_inventory,
            }

        # Cache the result
        self._cache[cache_key] = result

        logger.debug(f"Applied cascading reductions: {len(total_reductions)} materials affected")
        return result

    def _update_complexity_scores(self, dependency_trees: Dict[str, Dict]):
        """Pre-compute complexity scores for all materials to avoid repeated calculations."""
        for material_name, material_info in dependency_trees.items():
            if material_name not in self._complexity_scores:
                dependencies = material_info.get("dependencies", {})
                self._complexity_scores[material_name] = len(dependencies.get("all", []))

    def _get_sorted_inventory_items(self, inventory: Dict[str, int], dependency_trees: Dict[str, Dict]) -> List[Tuple[str, int]]:
        """
        Get inventory items sorted by complexity for optimal reduction.
        Uses pre-computed complexity scores for better performance.
        """
        # Update complexity scores if needed (only for new materials)
        self._update_complexity_scores(dependency_trees)

        # Build list with quantities and complexity scores
        inventory_with_complexity = []
        for material_name, quantity in inventory.items():
            if quantity > 0:
                complexity = self._complexity_scores.get(material_name, 0)
                inventory_with_complexity.append((material_name, quantity, complexity))

        # Sort by complexity (descending) then by quantity (descending)
        inventory_with_complexity.sort(key=lambda x: (x[2], x[1]), reverse=True)

        # Return just name and quantity
        return [(name, qty) for name, qty, _ in inventory_with_complexity]

    def _build_cache_key(self, base_requirements: Dict[str, int], inventory: Dict[str, int]) -> str:
        """Build cache key from requirements and inventory state."""
        # Sort dictionaries for consistent keys
        req_items = sorted(base_requirements.items())
        inv_items = sorted((k, v) for k, v in inventory.items() if v > 0)

        return f"req:{req_items}|inv:{inv_items}"

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics."""
        return {"hits": self._cache_hits, "misses": self._cache_misses, "entries": len(self._cache)}

    def clear_cache(self):
        """Clear the calculation cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.debug("Cleared cascading calculator cache")


def extract_dependency_trees_from_templates(profession_templates: Dict) -> Dict[str, Dict]:
    """
    Extract dependency trees from loaded profession templates.

    Args:
        profession_templates: Loaded template data with dependency information

    Returns:
        Flattened dict of {material_name: dependency_info} for all materials
    """
    dependency_trees = {}

    for profession, tiers in profession_templates.items():
        for tier, materials in tiers.items():
            for material_name, material_info in materials.items():
                if material_name not in dependency_trees:
                    dependency_trees[material_name] = material_info
                # If material appears in multiple places, keep the one with more dependencies
                elif len(material_info.get("dependencies", {}).get("all", [])) > len(
                    dependency_trees[material_name].get("dependencies", {}).get("all", [])
                ):
                    dependency_trees[material_name] = material_info

    return dependency_trees
