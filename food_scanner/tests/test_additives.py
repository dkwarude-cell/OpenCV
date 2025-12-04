"""
Unit tests for the additives module.
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from additives import AdditivesAnalyzer, AdditiveInfo, ConcernLevel


class TestAdditivesAnalyzer:
    """Tests for AdditivesAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer fixture."""
        return AdditivesAnalyzer()
    
    def test_analyzer_initialization(self, analyzer):
        """Test analyzer initializes and loads mappings."""
        assert analyzer._mapping is not None
        assert len(analyzer._mapping) > 0
    
    def test_normalize_code_with_prefix(self, analyzer):
        """Test E-number normalization with en: prefix."""
        assert analyzer._normalize_code("en:e150d") == "E150d"
    
    def test_normalize_code_lowercase(self, analyzer):
        """Test E-number normalization from lowercase."""
        assert analyzer._normalize_code("e150d") == "E150d"
    
    def test_normalize_code_uppercase(self, analyzer):
        """Test E-number normalization from uppercase."""
        assert analyzer._normalize_code("E150D") == "E150d"
    
    def test_normalize_code_without_e(self, analyzer):
        """Test E-number normalization without E prefix."""
        assert analyzer._normalize_code("150d") == "E150d"
    
    def test_get_known_additive(self, analyzer):
        """Test getting a known additive."""
        additive = analyzer.get_additive("E150d")
        
        assert additive.code == "E150d"
        assert "Caramel" in additive.name
        assert additive.concern in [ConcernLevel.MODERATE, ConcernLevel.HIGH]
        assert additive.category == "Color"
    
    def test_get_unknown_additive(self, analyzer):
        """Test getting an unknown additive."""
        additive = analyzer.get_additive("E9999")
        
        assert additive.code == "E9999"
        assert additive.concern == ConcernLevel.LOW_VALUE
        assert "not in our database" in additive.description.lower() or additive.name == "E9999"
    
    def test_analyze_additives_tags(self, analyzer):
        """Test analyzing additives from tags."""
        tags = ["en:e150d", "en:e338", "en:e950"]
        
        results = analyzer.analyze(tags)
        
        assert len(results) == 3
        codes = [a.code for a in results]
        assert "E150d" in codes
        assert "E338" in codes
        assert "E950" in codes
    
    def test_analyze_ingredients_text(self, analyzer):
        """Test extracting additives from ingredients text."""
        text = "Contains E211, natural flavors, E330"
        
        results = analyzer.analyze(ingredients_text=text)
        
        codes = [a.code for a in results]
        assert "E211" in codes
        assert "E330" in codes
    
    def test_analyze_combined(self, analyzer):
        """Test analyzing with both tags and text."""
        tags = ["en:e150d"]
        text = "Also contains E211"
        
        results = analyzer.analyze(tags, text)
        
        codes = [a.code for a in results]
        assert "E150d" in codes
        assert "E211" in codes
    
    def test_analyze_deduplication(self, analyzer):
        """Test that duplicate additives are removed."""
        tags = ["en:e150d", "en:e150d"]
        text = "Contains E150d"
        
        results = analyzer.analyze(tags, text)
        
        codes = [a.code for a in results]
        assert codes.count("E150d") == 1
    
    def test_analyze_sorted_by_concern(self, analyzer):
        """Test that results are sorted by concern level."""
        # Mix of different concern levels
        tags = ["en:e300", "en:e150d", "en:e171"]  # Minimal, Moderate, High
        
        results = analyzer.analyze(tags)
        
        # High concern should be first
        if len(results) >= 2:
            # The first additive should have equal or higher concern than subsequent ones
            concern_order = {
                ConcernLevel.HIGH: 0,
                ConcernLevel.MODERATE: 1,
                ConcernLevel.MINIMAL: 2,
                ConcernLevel.LOW_VALUE: 3,
            }
            
            for i in range(len(results) - 1):
                assert concern_order[results[i].concern] <= concern_order[results[i + 1].concern]


class TestAdditiveInfo:
    """Tests for AdditiveInfo dataclass."""
    
    def test_additive_info_creation(self):
        """Test AdditiveInfo creation."""
        additive = AdditiveInfo(
            code="E150d",
            name="Sulphite Ammonia Caramel",
            concern=ConcernLevel.MODERATE,
            category="Color",
            description="Caramel color"
        )
        
        assert additive.code == "E150d"
        assert additive.name == "Sulphite Ammonia Caramel"
        assert additive.concern == ConcernLevel.MODERATE
    
    def test_additive_info_to_dict(self):
        """Test AdditiveInfo to_dict conversion."""
        additive = AdditiveInfo(
            code="E150d",
            name="Test",
            concern=ConcernLevel.HIGH,
            category="Color",
            description="Test description"
        )
        
        d = additive.to_dict()
        
        assert d["code"] == "E150d"
        assert d["concern"] == "High"
        assert d["concern_color"] == "#f44336"


class TestConcernLevel:
    """Tests for ConcernLevel enum."""
    
    def test_concern_level_values(self):
        """Test concern level string values."""
        assert ConcernLevel.HIGH.value == "High"
        assert ConcernLevel.MODERATE.value == "Moderate"
        assert ConcernLevel.MINIMAL.value == "Minimal"
        assert ConcernLevel.LOW_VALUE.value == "Low Value"
    
    def test_concern_level_colors(self):
        """Test concern level colors."""
        assert ConcernLevel.HIGH.color == "#f44336"
        assert ConcernLevel.MODERATE.color == "#ff9800"
        assert ConcernLevel.MINIMAL.color == "#8bc34a"
        assert ConcernLevel.LOW_VALUE.color == "#9e9e9e"
    
    def test_concern_level_badge_classes(self):
        """Test concern level badge classes."""
        assert ConcernLevel.HIGH.badge_class == "badge-high"
        assert ConcernLevel.MODERATE.badge_class == "badge-moderate"


class TestSummary:
    """Tests for summary functionality."""
    
    def test_get_summary(self):
        """Test getting additive summary."""
        analyzer = AdditivesAnalyzer()
        
        additives = [
            AdditiveInfo("E171", "Titanium dioxide", ConcernLevel.HIGH, "Color"),
            AdditiveInfo("E150d", "Caramel", ConcernLevel.MODERATE, "Color"),
            AdditiveInfo("E330", "Citric acid", ConcernLevel.MINIMAL, "Acidity"),
        ]
        
        summary = analyzer.get_summary(additives)
        
        assert summary["total"] == 3
        assert len(summary["high_concern"]) == 1
        assert len(summary["moderate_concern"]) == 1
        assert len(summary["minimal_concern"]) == 1
        assert "Color" in summary["categories"]


class TestFormatting:
    """Tests for formatting functionality."""
    
    def test_format_for_display(self):
        """Test formatting additives for display."""
        analyzer = AdditivesAnalyzer()
        
        additives = [
            AdditiveInfo("E150d", "Caramel color", ConcernLevel.MODERATE, "Color"),
        ]
        
        text = analyzer.format_for_display(additives)
        
        assert "E150d" in text
        assert "Caramel" in text
    
    def test_format_empty_list(self):
        """Test formatting empty additive list."""
        analyzer = AdditivesAnalyzer()
        
        text = analyzer.format_for_display([])
        
        assert "No additives" in text


class TestSearch:
    """Tests for search functionality."""
    
    def test_search_by_code(self):
        """Test searching additives by code."""
        analyzer = AdditivesAnalyzer()
        
        results = analyzer.search("150")
        
        codes = [a.code for a in results]
        # Should find E150a, E150b, E150c, E150d
        assert any("150" in code for code in codes)
    
    def test_search_by_name(self):
        """Test searching additives by name."""
        analyzer = AdditivesAnalyzer()
        
        results = analyzer.search("caramel")
        
        assert len(results) > 0
        assert any("Caramel" in a.name for a in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
