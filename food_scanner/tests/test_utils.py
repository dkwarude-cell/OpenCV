"""
Unit tests for the utils module.
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import (
    sanitize_barcode,
    validate_ean_checksum,
    extract_e_numbers,
    detect_liquid_product,
    calculate_rda_percent,
    format_nutrient_value,
    determine_processing_level,
    convert_to_milligrams,
    convert_to_grams,
)


class TestSanitizeBarcode:
    """Tests for barcode sanitization."""
    
    def test_sanitize_digits_only(self):
        """Test sanitizing a valid barcode."""
        result = sanitize_barcode("1234567890123")
        assert result == "1234567890123"
    
    def test_sanitize_with_spaces(self):
        """Test sanitizing barcode with spaces."""
        result = sanitize_barcode("  1234567890123  ")
        assert result == "1234567890123"
    
    def test_sanitize_with_dashes(self):
        """Test sanitizing barcode with dashes."""
        result = sanitize_barcode("1234-5678-9012-3")
        assert result == "1234567890123"
    
    def test_sanitize_with_letters(self):
        """Test sanitizing barcode with letters."""
        result = sanitize_barcode("ABC1234567890123XYZ")
        assert result == "1234567890123"
    
    def test_sanitize_empty_raises(self):
        """Test that empty barcode raises ValueError."""
        with pytest.raises(ValueError):
            sanitize_barcode("")
    
    def test_sanitize_no_digits_raises(self):
        """Test that barcode with no digits raises ValueError."""
        with pytest.raises(ValueError):
            sanitize_barcode("ABCDEF")


class TestValidateEanChecksum:
    """Tests for EAN/UPC checksum validation."""
    
    def test_valid_ean13(self):
        """Test valid EAN-13 checksum."""
        assert validate_ean_checksum("5449000000996") is True  # Coca-Cola
        assert validate_ean_checksum("3017620422003") is True  # Nutella
    
    def test_invalid_ean13(self):
        """Test invalid EAN-13 checksum."""
        assert validate_ean_checksum("5449000000997") is False
        assert validate_ean_checksum("1234567890123") is False
    
    def test_valid_ean8(self):
        """Test valid EAN-8 checksum."""
        assert validate_ean_checksum("96385074") is True
    
    def test_invalid_ean8(self):
        """Test invalid EAN-8 checksum."""
        assert validate_ean_checksum("96385075") is False
    
    def test_non_standard_length(self):
        """Test non-standard length barcodes."""
        # Should return True for unknown formats (don't reject)
        assert validate_ean_checksum("12345") is True
        assert validate_ean_checksum("123456789012345678") is True


class TestExtractENumbers:
    """Tests for E-number extraction."""
    
    def test_extract_with_prefix(self):
        """Test extracting E-numbers with E prefix."""
        text = "Contains E150d, E338, and E950"
        result = extract_e_numbers(text)
        
        assert "E150D" in result or "E150d" in result
        assert "E338" in result
        assert "E950" in result
    
    def test_extract_without_prefix(self):
        """Test extracting E-numbers without E prefix."""
        text = "Contains 150d, 338"
        result = extract_e_numbers(text)
        
        # Should still find them
        assert len(result) >= 1
    
    def test_extract_with_hyphen(self):
        """Test extracting E-numbers with hyphen."""
        text = "Contains E-150d"
        result = extract_e_numbers(text)
        
        assert len(result) >= 1
    
    def test_extract_empty_string(self):
        """Test extracting from empty string."""
        result = extract_e_numbers("")
        assert result == []
    
    def test_extract_no_e_numbers(self):
        """Test extracting when no E-numbers present."""
        text = "Water, sugar, salt"
        result = extract_e_numbers(text)
        assert result == []
    
    def test_no_false_positives(self):
        """Test that non-E-numbers are not extracted."""
        text = "Contains 50g of sugar and E200"
        result = extract_e_numbers(text)
        
        # 50 should not be extracted (not in E-number range)
        assert "E50" not in result
        assert "E200" in result


class TestDetectLiquidProduct:
    """Tests for liquid product detection."""
    
    def test_detect_by_quantity_ml(self):
        """Test detecting liquid by ml in quantity."""
        data = {"quantity": "330 ml"}
        assert detect_liquid_product(data) is True
    
    def test_detect_by_quantity_liter(self):
        """Test detecting liquid by liter in quantity."""
        data = {"quantity": "1.5 litre"}
        assert detect_liquid_product(data) is True
    
    def test_detect_by_categories(self):
        """Test detecting liquid by categories."""
        data = {"categories": "Beverages, Carbonated drinks"}
        assert detect_liquid_product(data) is True
    
    def test_detect_by_packaging(self):
        """Test detecting liquid by packaging."""
        data = {"packaging": "Bottle, Plastic"}
        assert detect_liquid_product(data) is True
    
    def test_solid_product(self):
        """Test non-liquid product."""
        data = {"quantity": "100g", "categories": "Snacks, Chips"}
        assert detect_liquid_product(data) is False


class TestCalculateRdaPercent:
    """Tests for RDA percentage calculation."""
    
    def test_calculate_energy(self):
        """Test calculating RDA for energy."""
        result = calculate_rda_percent("energy_kcal", 400, "kcal")
        assert result == 20.0  # 400/2000 * 100 = 20%
    
    def test_calculate_fat(self):
        """Test calculating RDA for fat."""
        result = calculate_rda_percent("fat", 14, "g")
        assert result == 20.0  # 14/70 * 100 = 20%
    
    def test_unknown_nutrient(self):
        """Test calculating RDA for unknown nutrient."""
        result = calculate_rda_percent("unknown_nutrient", 10, "g")
        assert result is None
    
    def test_unit_conversion(self):
        """Test calculating RDA with unit conversion."""
        result = calculate_rda_percent("sodium", 1.2, "g")
        # Should convert g to mg: 1.2g = 1200mg, 1200/2400 = 50%
        assert result == 50.0


class TestFormatNutrientValue:
    """Tests for nutrient value formatting."""
    
    def test_format_none(self):
        """Test formatting None value."""
        result = format_nutrient_value(None)
        assert result == "—"
    
    def test_format_zero(self):
        """Test formatting zero value."""
        result = format_nutrient_value(0)
        assert result == "0.0 g"
    
    def test_format_small_value(self):
        """Test formatting small value."""
        result = format_nutrient_value(0.05)
        assert result == "<0.1 g"
    
    def test_format_medium_value(self):
        """Test formatting medium value."""
        result = format_nutrient_value(0.5)
        assert "0.50" in result
    
    def test_format_large_value(self):
        """Test formatting large value."""
        result = format_nutrient_value(42)
        assert "42" in result
    
    def test_format_with_unit(self):
        """Test formatting with custom unit."""
        result = format_nutrient_value(100, "mg")
        assert "mg" in result


class TestDetermineProcessingLevel:
    """Tests for processing level determination."""
    
    def test_nova_group_1(self):
        """Test NOVA group 1."""
        result = determine_processing_level(1, 0)
        assert "minimally processed" in result.lower() or "unprocessed" in result.lower()
    
    def test_nova_group_4(self):
        """Test NOVA group 4."""
        result = determine_processing_level(4, 0)
        assert "ultra-processed" in result.lower()
    
    def test_many_additives(self):
        """Test with many additives and no NOVA group."""
        result = determine_processing_level(None, 6)
        assert "ultra" in result.lower()
    
    def test_few_additives(self):
        """Test with few additives."""
        result = determine_processing_level(None, 1)
        assert "processed" in result.lower()
    
    def test_no_additives(self):
        """Test with no additives."""
        result = determine_processing_level(None, 0)
        assert "minimal" in result.lower() or "unprocessed" in result.lower()


class TestUnitConversions:
    """Tests for unit conversion functions."""
    
    def test_convert_g_to_mg(self):
        """Test converting grams to milligrams."""
        result = convert_to_milligrams(1, "g")
        assert result == 1000
    
    def test_convert_mg_to_mg(self):
        """Test converting mg to mg (no change)."""
        result = convert_to_milligrams(100, "mg")
        assert result == 100
    
    def test_convert_ug_to_mg(self):
        """Test converting micrograms to milligrams."""
        result = convert_to_milligrams(1000, "μg")
        assert result == 1
    
    def test_convert_to_grams(self):
        """Test converting to grams."""
        result = convert_to_grams(1000, "mg")
        assert result == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
