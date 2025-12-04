"""
Unit tests for the product lookup module.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import json

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from product_lookup import ProductLookup, format_product_text, format_product_json
from utils import ProductInfo, NutrientValue


# Sample API response for testing
SAMPLE_API_RESPONSE = {
    "status": 1,
    "product": {
        "code": "5449000000996",
        "product_name": "Coca-Cola",
        "brands": "Coca-Cola",
        "quantity": "330 ml",
        "categories": "Beverages, Carbonated drinks, Sodas",
        "ingredients_text": "Carbonated Water, Sugar, Caramel Color (E150d), Phosphoric Acid (E338), Natural Flavors, Caffeine",
        "image_url": "https://example.com/image.jpg",
        "nutriments": {
            "energy-kcal_100g": 42,
            "fat_100g": 0,
            "saturated-fat_100g": 0,
            "carbohydrates_100g": 10.6,
            "sugars_100g": 10.6,
            "proteins_100g": 0,
            "salt_100g": 0,
            "sodium_100g": 0,
        },
        "additives_tags": ["en:e150d", "en:e338"],
        "nova_group": 4,
        "packaging": "Bottle, Plastic",
    }
}


class TestProductLookup:
    """Tests for ProductLookup class."""
    
    def test_lookup_initialization(self):
        """Test lookup initializes correctly."""
        lookup = ProductLookup()
        assert lookup.use_cache is True
        assert lookup.offline_mode is False
        assert lookup.timeout == 10.0
    
    def test_lookup_custom_settings(self):
        """Test lookup with custom settings."""
        lookup = ProductLookup(
            use_cache=False,
            offline_mode=True,
            timeout=5.0
        )
        assert lookup.use_cache is False
        assert lookup.offline_mode is True
        assert lookup.timeout == 5.0
    
    @patch("product_lookup.ProductLookup._fetch_from_api")
    def test_get_product_from_api(self, mock_fetch):
        """Test getting product from API."""
        mock_fetch.return_value = MagicMock(
            success=True,
            data=SAMPLE_API_RESPONSE["product"],
            source="api"
        )
        
        lookup = ProductLookup(use_cache=False)
        product = lookup.get_product("5449000000996")
        
        assert product.barcode == "5449000000996"
        assert product.name == "Coca-Cola"
        assert product.brand == "Coca-Cola"
        assert product.is_rated is True
    
    def test_get_product_invalid_barcode(self):
        """Test getting product with invalid barcode."""
        lookup = ProductLookup(use_cache=False, offline_mode=True)
        product = lookup.get_product("")
        
        assert product.is_rated is False
        assert "Error" in product.status_message
    
    def test_parse_nutrients(self):
        """Test nutrient parsing."""
        lookup = ProductLookup()
        
        nutriments = {
            "energy-kcal_100g": 42,
            "fat_100g": 0,
            "sugars_100g": 10.6,
        }
        
        nutrients = lookup._parse_nutrients(nutriments, lookup.NUTRIENT_MAPPING)
        
        assert "energy_kcal" in nutrients
        assert nutrients["energy_kcal"].value == 42
        assert nutrients["energy_kcal"].unit == "kcal"
        
        assert "fat" in nutrients
        assert nutrients["fat"].value == 0
        
        assert "sugars" in nutrients
        assert nutrients["sugars"].value == 10.6
    
    def test_create_error_product(self):
        """Test error product creation."""
        lookup = ProductLookup()
        product = lookup._create_error_product("12345", "Test error")
        
        assert product.barcode == "12345"
        assert product.is_rated is False
        assert "Test error" in product.status_message
    
    def test_create_not_found_product(self):
        """Test not found product creation."""
        lookup = ProductLookup()
        product = lookup._create_not_found_product("12345", "Not found")
        
        assert product.name == "Product Not Found"
        assert product.is_rated is False


class TestProductInfo:
    """Tests for ProductInfo dataclass."""
    
    def test_product_info_defaults(self):
        """Test ProductInfo default values."""
        product = ProductInfo(barcode="12345")
        
        assert product.barcode == "12345"
        assert product.name == "Unknown Product"
        assert product.brand == ""
        assert product.is_rated is True
        assert product.is_liquid is False
    
    def test_product_info_to_dict(self):
        """Test ProductInfo to_dict conversion."""
        product = ProductInfo(
            barcode="12345",
            name="Test Product",
            brand="Test Brand"
        )
        
        d = product.to_dict()
        
        assert d["barcode"] == "12345"
        assert d["name"] == "Test Product"
        assert d["brand"] == "Test Brand"


class TestNutrientValue:
    """Tests for NutrientValue dataclass."""
    
    def test_nutrient_value_creation(self):
        """Test NutrientValue creation."""
        nutrient = NutrientValue(
            value=10.5,
            unit="g",
            name="Sugars",
            rda_percent=11.7
        )
        
        assert nutrient.value == 10.5
        assert nutrient.unit == "g"
        assert nutrient.name == "Sugars"
        assert nutrient.rda_percent == 11.7
    
    def test_nutrient_value_to_dict(self):
        """Test NutrientValue to_dict conversion."""
        nutrient = NutrientValue(
            value=10.5,
            unit="g",
            name="Sugars",
            rda_percent=11.7
        )
        
        d = nutrient.to_dict()
        
        assert d["value"] == 10.5
        assert d["unit"] == "g"
        assert d["rda_percent"] == 11.7


class TestFormatFunctions:
    """Tests for formatting functions."""
    
    def test_format_product_text(self):
        """Test text formatting."""
        product = ProductInfo(
            barcode="12345",
            name="Test Product",
            brand="Test Brand"
        )
        product.nutrients_per_100 = {
            "energy_kcal": NutrientValue(42, "kcal", "Energy"),
        }
        product.processing_level = "Ultra-processed"
        
        text = format_product_text(product)
        
        assert "Test Product" in text
        assert "Test Brand" in text
        assert "12345" in text
        assert "Ultra-processed" in text
    
    def test_format_product_json(self):
        """Test JSON formatting."""
        product = ProductInfo(
            barcode="12345",
            name="Test Product"
        )
        
        json_str = format_product_json(product)
        data = json.loads(json_str)
        
        assert data["barcode"] == "12345"
        assert data["name"] == "Test Product"


class TestCaching:
    """Tests for caching functionality."""
    
    @patch("product_lookup.ProductCache")
    def test_cache_hit(self, mock_cache_class):
        """Test cache hit scenario."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = SAMPLE_API_RESPONSE["product"]
        mock_cache_class.return_value = mock_cache
        
        lookup = ProductLookup()
        lookup.cache = mock_cache
        
        product = lookup.get_product("5449000000996")
        
        assert product.name == "Coca-Cola"
        mock_cache.get.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
