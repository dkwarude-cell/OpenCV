"""
Additives analysis module for the Food Barcode Scanner.

This module handles identification and concern-level mapping of food additives
(E-numbers) found in product ingredients.
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from utils import logger, extract_e_numbers


class ConcernLevel(Enum):
    """Concern level classification for additives."""
    HIGH = "High"
    MODERATE = "Moderate"
    MINIMAL = "Minimal"
    LOW_VALUE = "Low Value"  # Unknown or insufficient data
    
    @property
    def color(self) -> str:
        """Get the display color for this concern level."""
        colors = {
            ConcernLevel.HIGH: "#f44336",  # Red
            ConcernLevel.MODERATE: "#ff9800",  # Orange
            ConcernLevel.MINIMAL: "#8bc34a",  # Green
            ConcernLevel.LOW_VALUE: "#9e9e9e",  # Grey
        }
        return colors.get(self, "#9e9e9e")
    
    @property
    def badge_class(self) -> str:
        """Get the CSS class for this concern level badge."""
        classes = {
            ConcernLevel.HIGH: "badge-high",
            ConcernLevel.MODERATE: "badge-moderate",
            ConcernLevel.MINIMAL: "badge-minimal",
            ConcernLevel.LOW_VALUE: "badge-low",
        }
        return classes.get(self, "badge-low")


@dataclass
class AdditiveInfo:
    """
    Information about a food additive.
    
    Attributes:
        code: The E-number code (e.g., "E150d").
        name: Human-readable name of the additive.
        concern: Concern level classification.
        category: Category of the additive (color, preservative, etc.).
        description: Detailed description of the additive.
    """
    code: str
    name: str
    concern: ConcernLevel
    category: str = ""
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "code": self.code,
            "name": self.name,
            "concern": self.concern.value,
            "concern_color": self.concern.color,
            "category": self.category,
            "description": self.description,
        }


class AdditivesAnalyzer:
    """
    Analyzes food additives and provides concern-level mappings.
    
    This class loads additive data from a JSON mapping file and provides
    methods to look up individual additives or analyze a list of additives.
    """
    
    def __init__(self, mapping_file: Optional[Path] = None):
        """
        Initialize the additives analyzer.
        
        Args:
            mapping_file: Path to the additives mapping JSON file.
                         Defaults to data/additives_mapping.json.
        """
        if mapping_file is None:
            mapping_file = Path(__file__).parent.parent / "data" / "additives_mapping.json"
        
        self.mapping_file = Path(mapping_file)
        self._mapping: Dict[str, Dict[str, Any]] = {}
        self._load_mapping()
    
    def _load_mapping(self) -> None:
        """Load the additives mapping from JSON file."""
        if not self.mapping_file.exists():
            logger.warning(f"Additives mapping file not found: {self.mapping_file}")
            return
        
        try:
            with open(self.mapping_file, "r", encoding="utf-8") as f:
                self._mapping = json.load(f)
            logger.info(f"Loaded {len(self._mapping)} additive mappings")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load additives mapping: {e}")
    
    def _normalize_code(self, code: str) -> str:
        """
        Normalize an additive code for lookup.
        
        Args:
            code: Raw additive code (e.g., "en:e150d", "E150d", "150d").
            
        Returns:
            Normalized code (e.g., "E150d").
        """
        # Remove OpenFoodFacts prefix
        if code.startswith("en:"):
            code = code[3:]
        
        # Ensure uppercase E prefix
        code = code.strip().upper()
        
        if not code.startswith("E"):
            code = "E" + code
        
        # Handle letter suffixes (e.g., E150D -> E150d)
        match = re.match(r"(E\d+)([A-Z])?$", code)
        if match:
            base = match.group(1)
            suffix = match.group(2)
            if suffix:
                return base + suffix.lower()
            return base
        
        return code
    
    def get_additive(self, code: str) -> AdditiveInfo:
        """
        Look up information for a single additive.
        
        Args:
            code: Additive code (E-number).
            
        Returns:
            AdditiveInfo object with additive details.
        """
        normalized = self._normalize_code(code)
        
        # Try exact match first
        if normalized in self._mapping:
            data = self._mapping[normalized]
            return AdditiveInfo(
                code=normalized,
                name=data.get("name", normalized),
                concern=ConcernLevel(data.get("concern", "Low Value")),
                category=data.get("category", ""),
                description=data.get("description", ""),
            )
        
        # Try without letter suffix (e.g., E150d -> E150)
        base_code = re.match(r"(E\d+)", normalized)
        if base_code:
            base = base_code.group(1)
            if base in self._mapping:
                data = self._mapping[base]
                return AdditiveInfo(
                    code=normalized,
                    name=f"{data.get('name', base)} (variant)",
                    concern=ConcernLevel(data.get("concern", "Low Value")),
                    category=data.get("category", ""),
                    description=data.get("description", ""),
                )
        
        # Unknown additive
        logger.debug(f"Unknown additive: {normalized}")
        return AdditiveInfo(
            code=normalized,
            name=normalized,
            concern=ConcernLevel.LOW_VALUE,
            category="Unknown",
            description="This additive is not in our database.",
        )
    
    def analyze(
        self,
        additives_tags: Optional[List[str]] = None,
        ingredients_text: str = ""
    ) -> List[AdditiveInfo]:
        """
        Analyze a list of additives from a product.
        
        Args:
            additives_tags: List of additive tags from OpenFoodFacts.
            ingredients_text: Raw ingredients text to parse for E-numbers.
            
        Returns:
            List of AdditiveInfo objects for all identified additives.
        """
        additives = []
        seen_codes = set()
        
        # Process additives_tags from OpenFoodFacts
        if additives_tags:
            for tag in additives_tags:
                code = self._normalize_code(tag)
                if code not in seen_codes:
                    seen_codes.add(code)
                    additives.append(self.get_additive(code))
        
        # Extract additional E-numbers from ingredients text
        if ingredients_text:
            extracted = extract_e_numbers(ingredients_text)
            for code in extracted:
                normalized = self._normalize_code(code)
                if normalized not in seen_codes:
                    seen_codes.add(normalized)
                    additives.append(self.get_additive(normalized))
        
        # Sort by concern level (high first)
        concern_order = {
            ConcernLevel.HIGH: 0,
            ConcernLevel.MODERATE: 1,
            ConcernLevel.MINIMAL: 2,
            ConcernLevel.LOW_VALUE: 3,
        }
        additives.sort(key=lambda a: concern_order.get(a.concern, 4))
        
        return additives
    
    def get_summary(self, additives: List[AdditiveInfo]) -> Dict[str, Any]:
        """
        Get a summary of additives by concern level.
        
        Args:
            additives: List of AdditiveInfo objects.
            
        Returns:
            Summary dictionary with counts and lists by concern level.
        """
        summary = {
            "total": len(additives),
            "high_concern": [],
            "moderate_concern": [],
            "minimal_concern": [],
            "low_value": [],
            "categories": {},
        }
        
        for additive in additives:
            if additive.concern == ConcernLevel.HIGH:
                summary["high_concern"].append(additive.to_dict())
            elif additive.concern == ConcernLevel.MODERATE:
                summary["moderate_concern"].append(additive.to_dict())
            elif additive.concern == ConcernLevel.MINIMAL:
                summary["minimal_concern"].append(additive.to_dict())
            else:
                summary["low_value"].append(additive.to_dict())
            
            # Count by category
            category = additive.category or "Unknown"
            summary["categories"][category] = summary["categories"].get(category, 0) + 1
        
        return summary
    
    def format_for_display(
        self,
        additives: List[AdditiveInfo],
        include_description: bool = False
    ) -> str:
        """
        Format additives list for text display.
        
        Args:
            additives: List of AdditiveInfo objects.
            include_description: Whether to include descriptions.
            
        Returns:
            Formatted string for display.
        """
        if not additives:
            return "No additives detected"
        
        lines = []
        for additive in additives:
            concern_icon = {
                ConcernLevel.HIGH: "🔴",
                ConcernLevel.MODERATE: "🟠",
                ConcernLevel.MINIMAL: "🟢",
                ConcernLevel.LOW_VALUE: "⚪",
            }.get(additive.concern, "⚪")
            
            line = f"{concern_icon} {additive.code}: {additive.name}"
            if additive.category:
                line += f" ({additive.category})"
            
            lines.append(line)
            
            if include_description and additive.description:
                lines.append(f"   → {additive.description}")
        
        return "\n".join(lines)
    
    def add_mapping(
        self,
        code: str,
        name: str,
        concern: str,
        category: str = "",
        description: str = "",
        save: bool = True
    ) -> None:
        """
        Add or update an additive mapping.
        
        Args:
            code: E-number code.
            name: Human-readable name.
            concern: Concern level (High, Moderate, Minimal, Low Value).
            category: Category of the additive.
            description: Description of the additive.
            save: Whether to save to file immediately.
        """
        normalized = self._normalize_code(code)
        
        self._mapping[normalized] = {
            "name": name,
            "concern": concern,
            "category": category,
            "description": description,
        }
        
        if save:
            self._save_mapping()
        
        logger.info(f"Added additive mapping: {normalized}")
    
    def _save_mapping(self) -> None:
        """Save the current mapping to file."""
        try:
            with open(self.mapping_file, "w", encoding="utf-8") as f:
                json.dump(self._mapping, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save additives mapping: {e}")
    
    def get_all_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all additive mappings.
        
        Returns:
            Dictionary of all additive mappings.
        """
        return self._mapping.copy()
    
    def search(self, query: str) -> List[AdditiveInfo]:
        """
        Search for additives by name or code.
        
        Args:
            query: Search query string.
            
        Returns:
            List of matching AdditiveInfo objects.
        """
        query = query.lower()
        results = []
        
        for code, data in self._mapping.items():
            if (query in code.lower() or 
                query in data.get("name", "").lower() or
                query in data.get("category", "").lower()):
                results.append(self.get_additive(code))
        
        return results


def get_common_additives_info() -> List[Dict[str, str]]:
    """
    Get information about commonly found additives.
    
    Returns:
        List of dictionaries with common additive information.
    """
    common = [
        {"code": "E150d", "name": "Caramel color (Class IV)", "found_in": "Cola, sauces, bread"},
        {"code": "E950", "name": "Acesulfame K", "found_in": "Diet drinks, sugar-free foods"},
        {"code": "E951", "name": "Aspartame", "found_in": "Diet drinks, sugar-free gum"},
        {"code": "E955", "name": "Sucralose", "found_in": "Diet drinks, protein shakes"},
        {"code": "E338", "name": "Phosphoric acid", "found_in": "Cola drinks"},
        {"code": "E211", "name": "Sodium benzoate", "found_in": "Soft drinks, fruit juices"},
        {"code": "E330", "name": "Citric acid", "found_in": "Most processed foods"},
        {"code": "E322", "name": "Lecithin", "found_in": "Chocolate, margarine"},
        {"code": "E621", "name": "MSG", "found_in": "Savory snacks, soups"},
        {"code": "E471", "name": "Mono/diglycerides", "found_in": "Baked goods, ice cream"},
    ]
    return common


if __name__ == "__main__":
    # Test the additives analyzer
    print("Testing AdditivesAnalyzer...")
    
    analyzer = AdditivesAnalyzer()
    
    # Test single additive lookup
    print("\nLooking up E150d:")
    additive = analyzer.get_additive("E150d")
    print(f"  Name: {additive.name}")
    print(f"  Concern: {additive.concern.value}")
    print(f"  Category: {additive.category}")
    
    # Test analysis of multiple additives
    print("\nAnalyzing additives from a product:")
    additives_tags = ["en:e150d", "en:e338", "en:e950", "en:e955"]
    ingredients = "Contains E211 and natural flavors"
    
    results = analyzer.analyze(additives_tags, ingredients)
    print(analyzer.format_for_display(results, include_description=True))
    
    # Test summary
    print("\nSummary:")
    summary = analyzer.get_summary(results)
    print(f"  Total: {summary['total']}")
    print(f"  High concern: {len(summary['high_concern'])}")
    print(f"  Moderate: {len(summary['moderate_concern'])}")
    print(f"  Minimal: {len(summary['minimal_concern'])}")
