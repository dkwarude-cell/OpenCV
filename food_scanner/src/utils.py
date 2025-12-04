"""
Utility functions for the Food Barcode Scanner.

This module provides common utility functions used across the application,
including logging configuration, input sanitization, and unit conversions.
"""

import logging
import os
import re
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum


# Configure logging based on environment variable
DEBUG_MODE = os.environ.get("FOOD_SCANNER_DEBUG", "false").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("food_scanner")


class UnitType(Enum):
    """Enum for unit types."""
    GRAM = "g"
    MILLIGRAM = "mg"
    KILOCALORIE = "kcal"
    KILOJOULE = "kJ"
    MILLILITER = "ml"
    LITER = "l"
    PERCENT = "%"


@dataclass
class NutrientValue:
    """Represents a nutrient value with its unit."""
    value: float
    unit: str
    name: str
    rda_percent: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "value": self.value,
            "unit": self.unit,
            "name": self.name,
            "rda_percent": self.rda_percent,
        }


@dataclass
class ProductInfo:
    """Represents complete product information."""
    barcode: str
    name: str = "Unknown Product"
    brand: str = ""
    image_url: Optional[str] = None
    ingredients_text: str = ""
    quantity: str = ""
    categories: str = ""
    
    # Nutrient data per 100g/100ml
    nutrients_per_100: Dict[str, NutrientValue] = field(default_factory=dict)
    
    # Nutrient data per serving
    nutrients_per_serving: Dict[str, NutrientValue] = field(default_factory=dict)
    serving_size: str = ""
    
    # Additives
    additives_tags: list = field(default_factory=list)
    
    # Processing level
    nova_group: Optional[int] = None
    processing_level: str = ""
    
    # Scores
    nutriscore_grade: str = ""  # A, B, C, D, E
    nutriscore_score: Optional[int] = None
    ecoscore_grade: str = ""
    
    # Flags
    is_liquid: bool = False
    is_rated: bool = True
    status_message: str = ""
    
    # Raw data for debugging
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def get_health_rating(self) -> tuple:
        """
        Calculate an overall health rating based on available data.
        Returns (score 0-100, rating label, color).
        """
        score = 50  # Start neutral
        factors = []
        
        # Nutriscore contribution (major factor)
        if self.nutriscore_grade:
            nutri_scores = {'a': 90, 'b': 75, 'c': 50, 'd': 30, 'e': 10}
            score = nutri_scores.get(self.nutriscore_grade.lower(), 50)
            factors.append(f"Nutri-Score {self.nutriscore_grade.upper()}")
        
        # NOVA group contribution
        if self.nova_group:
            nova_adjust = {1: 15, 2: 5, 3: -5, 4: -20}
            score += nova_adjust.get(self.nova_group, 0)
            factors.append(f"NOVA {self.nova_group}")
        
        # Additives penalty
        if self.additives_tags:
            additive_count = len(self.additives_tags)
            if additive_count > 5:
                score -= 15
            elif additive_count > 2:
                score -= 8
            elif additive_count > 0:
                score -= 3
            factors.append(f"{additive_count} additives")
        
        # Clamp score
        score = max(0, min(100, score))
        
        # Determine rating
        if score >= 80:
            return (score, "Excellent", "#4CAF50", factors)
        elif score >= 60:
            return (score, "Good", "#8BC34A", factors)
        elif score >= 40:
            return (score, "Moderate", "#FFC107", factors)
        elif score >= 20:
            return (score, "Poor", "#FF9800", factors)
        else:
            return (score, "Avoid", "#F44336", factors)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "barcode": self.barcode,
            "name": self.name,
            "brand": self.brand,
            "image_url": self.image_url,
            "ingredients_text": self.ingredients_text,
            "quantity": self.quantity,
            "categories": self.categories,
            "nutrients_per_100": {
                k: v.to_dict() for k, v in self.nutrients_per_100.items()
            },
            "nutrients_per_serving": {
                k: v.to_dict() for k, v in self.nutrients_per_serving.items()
            },
            "serving_size": self.serving_size,
            "additives_tags": self.additives_tags,
            "nova_group": self.nova_group,
            "processing_level": self.processing_level,
            "nutriscore_grade": self.nutriscore_grade,
            "nutriscore_score": self.nutriscore_score,
            "ecoscore_grade": self.ecoscore_grade,
            "is_liquid": self.is_liquid,
            "is_rated": self.is_rated,
            "status_message": self.status_message,
        }


# Reference Daily Allowance (RDA) values for adults
RDA_VALUES: Dict[str, Dict[str, Union[float, str]]] = {
    "energy_kcal": {"value": 2000, "unit": "kcal"},
    "fat": {"value": 70, "unit": "g"},
    "saturated_fat": {"value": 20, "unit": "g"},
    "carbohydrates": {"value": 260, "unit": "g"},
    "sugars": {"value": 90, "unit": "g"},
    "fiber": {"value": 25, "unit": "g"},
    "proteins": {"value": 50, "unit": "g"},
    "salt": {"value": 6, "unit": "g"},
    "sodium": {"value": 2400, "unit": "mg"},
}


def sanitize_barcode(barcode: str) -> str:
    """
    Sanitize barcode string to prevent injection attacks.
    
    Args:
        barcode: Raw barcode string from scanner or user input.
        
    Returns:
        Sanitized barcode string containing only digits.
        
    Raises:
        ValueError: If barcode is empty or contains no valid digits.
    """
    if not barcode:
        raise ValueError("Barcode cannot be empty")
    
    # Remove all non-digit characters
    sanitized = re.sub(r"[^\d]", "", barcode)
    
    if not sanitized:
        raise ValueError("Barcode must contain at least one digit")
    
    return sanitized


def validate_ean_checksum(barcode: str) -> bool:
    """
    Validate EAN/UPC barcode checksum.
    
    Supports EAN-13, EAN-8, UPC-A (12 digits), and UPC-E (8 digits).
    
    Args:
        barcode: Barcode string to validate.
        
    Returns:
        True if checksum is valid, False otherwise.
    """
    barcode = sanitize_barcode(barcode)
    
    if len(barcode) not in (8, 12, 13, 14):
        logger.debug(f"Barcode length {len(barcode)} not standard EAN/UPC")
        return True  # Unknown format, don't reject
    
    try:
        # Calculate checksum for EAN-13/UPC-A
        if len(barcode) in (12, 13):
            if len(barcode) == 12:
                barcode = "0" + barcode  # Pad to 13 digits
            
            total = 0
            for i, digit in enumerate(barcode[:-1]):
                if i % 2 == 0:
                    total += int(digit)
                else:
                    total += int(digit) * 3
            
            check_digit = (10 - (total % 10)) % 10
            return check_digit == int(barcode[-1])
        
        # EAN-8
        elif len(barcode) == 8:
            total = 0
            for i, digit in enumerate(barcode[:-1]):
                if i % 2 == 0:
                    total += int(digit) * 3
                else:
                    total += int(digit)
            
            check_digit = (10 - (total % 10)) % 10
            return check_digit == int(barcode[-1])
        
        # EAN-14/GTIN-14
        elif len(barcode) == 14:
            total = 0
            for i, digit in enumerate(barcode[:-1]):
                if i % 2 == 0:
                    total += int(digit) * 3
                else:
                    total += int(digit)
            
            check_digit = (10 - (total % 10)) % 10
            return check_digit == int(barcode[-1])
            
    except (ValueError, IndexError) as e:
        logger.debug(f"Checksum validation error: {e}")
        return False
    
    return True


def convert_to_milligrams(value: float, unit: str) -> float:
    """
    Convert a value to milligrams.
    
    Args:
        value: The numeric value to convert.
        unit: The source unit (g, mg, μg, etc.).
        
    Returns:
        Value in milligrams.
    """
    unit = unit.lower().strip()
    
    conversions = {
        "g": 1000,
        "gram": 1000,
        "grams": 1000,
        "mg": 1,
        "milligram": 1,
        "milligrams": 1,
        "μg": 0.001,
        "ug": 0.001,
        "microgram": 0.001,
        "micrograms": 0.001,
        "kg": 1000000,
        "kilogram": 1000000,
    }
    
    multiplier = conversions.get(unit, 1)
    return value * multiplier


def convert_to_grams(value: float, unit: str) -> float:
    """
    Convert a value to grams.
    
    Args:
        value: The numeric value to convert.
        unit: The source unit (g, mg, kg, etc.).
        
    Returns:
        Value in grams.
    """
    return convert_to_milligrams(value, unit) / 1000


def calculate_rda_percent(
    nutrient_name: str, value: float, unit: str
) -> Optional[float]:
    """
    Calculate the percentage of Reference Daily Allowance.
    
    Args:
        nutrient_name: Name of the nutrient.
        value: The nutrient value.
        unit: The unit of the value.
        
    Returns:
        Percentage of RDA, or None if RDA not defined for this nutrient.
    """
    if nutrient_name not in RDA_VALUES:
        return None
    
    rda = RDA_VALUES[nutrient_name]
    rda_value = rda["value"]
    rda_unit = rda["unit"]
    
    # Normalize units
    if rda_unit == "mg" and unit == "g":
        value = value * 1000
    elif rda_unit == "g" and unit == "mg":
        value = value / 1000
    
    if rda_value == 0:
        return None
    
    percent = (value / rda_value) * 100
    return round(percent, 1)


def detect_liquid_product(product_data: Dict[str, Any]) -> bool:
    """
    Detect if a product is a liquid based on its data.
    
    Args:
        product_data: Product data from OpenFoodFacts.
        
    Returns:
        True if product appears to be a liquid, False otherwise.
    """
    # Check quantity field for ml/l
    quantity = product_data.get("quantity", "").lower()
    if re.search(r"\d+\s*(ml|l|litre|liter|cl|dl)", quantity):
        return True
    
    # Check categories
    categories = product_data.get("categories", "").lower()
    liquid_categories = [
        "beverage", "drink", "juice", "soda", "water", "milk",
        "coffee", "tea", "beer", "wine", "spirit", "cocktail",
        "smoothie", "shake", "boisson", "getränk", "bebida"
    ]
    
    for cat in liquid_categories:
        if cat in categories:
            return True
    
    # Check packaging
    packaging = product_data.get("packaging", "").lower()
    liquid_packaging = ["bottle", "can", "tetra", "carton", "bouteille"]
    
    for pack in liquid_packaging:
        if pack in packaging:
            return True
    
    return False


def format_nutrient_value(value: Optional[float], unit: str = "g") -> str:
    """
    Format a nutrient value for display.
    
    Args:
        value: The nutrient value.
        unit: The unit to display.
        
    Returns:
        Formatted string representation.
    """
    if value is None:
        return "—"
    
    if value == 0:
        return f"0.0 {unit}"
    
    if value < 0.1:
        return f"<0.1 {unit}"
    
    if value < 1:
        return f"{value:.2f} {unit}"
    
    if value < 10:
        return f"{value:.1f} {unit}"
    
    return f"{value:.0f} {unit}"


def extract_e_numbers(text: str) -> list:
    """
    Extract E-numbers from ingredient text.
    
    Args:
        text: Ingredient text to parse.
        
    Returns:
        List of E-numbers found (e.g., ["E150d", "E950"]).
    """
    if not text:
        return []
    
    # Match patterns like: E150d, E-150d, E 150d, 150d, e150d
    pattern = r"\b[Ee][-\s]?(\d{3,4}[a-zA-Z]?)\b|\b(\d{3,4}[a-zA-Z]?)\b"
    
    matches = re.findall(pattern, text)
    e_numbers = []
    
    for match in matches:
        # Take the first non-empty group
        num = match[0] if match[0] else match[1]
        
        # Only consider valid E-number ranges (100-1999)
        try:
            base_num = int(re.match(r"(\d+)", num).group(1))
            if 100 <= base_num <= 1999:
                e_number = f"E{num.upper()}"
                if e_number not in e_numbers:
                    e_numbers.append(e_number)
        except (ValueError, AttributeError):
            continue
    
    return e_numbers


def determine_processing_level(
    nova_group: Optional[int],
    additives_count: int,
    ingredients_text: str = ""
) -> str:
    """
    Determine the processing level of a food product.
    
    Args:
        nova_group: NOVA classification (1-4) from OpenFoodFacts.
        additives_count: Number of additives detected.
        ingredients_text: Raw ingredients text.
        
    Returns:
        Human-readable processing level description.
    """
    # Use NOVA group if available
    if nova_group is not None:
        nova_descriptions = {
            1: "Unprocessed or minimally processed",
            2: "Processed culinary ingredients",
            3: "Processed foods",
            4: "Ultra-processed foods",
        }
        return nova_descriptions.get(nova_group, "Unknown processing level")
    
    # Heuristic based on additives
    if additives_count >= 5:
        return "Ultra-processed (5+ additives detected)"
    elif additives_count >= 3:
        return "Highly processed (3-4 additives detected)"
    elif additives_count >= 1:
        return "Processed (1-2 additives detected)"
    
    # Check for ultra-processed markers in ingredients
    ultra_processed_markers = [
        "high fructose corn syrup", "hydrogenated",
        "maltodextrin", "dextrose", "isolate",
        "protein concentrate", "modified starch",
        "artificial flavor", "artificial colour"
    ]
    
    ingredients_lower = ingredients_text.lower()
    marker_count = sum(1 for m in ultra_processed_markers if m in ingredients_lower)
    
    if marker_count >= 2:
        return "Ultra-processed (contains processed ingredients)"
    elif marker_count >= 1:
        return "Processed"
    
    return "Minimally processed or unprocessed"


def generate_html_report(product: ProductInfo) -> str:
    """
    Generate an HTML report for a product.
    
    Args:
        product: ProductInfo object with all product data.
        
    Returns:
        HTML string for the report.
    """
    nutrients_html = ""
    for name, nutrient in product.nutrients_per_100.items():
        rda_str = f"{nutrient.rda_percent}%" if nutrient.rda_percent else "—"
        nutrients_html += f"""
        <tr>
            <td>{nutrient.name}</td>
            <td>{format_nutrient_value(nutrient.value, nutrient.unit)}</td>
            <td>{rda_str}</td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Product Report - {product.name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; }}
            .header {{ background: #f0f0f0; padding: 20px; border-radius: 8px; }}
            .product-image {{ max-width: 200px; float: right; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #4CAF50; color: white; }}
            .badge {{ padding: 4px 8px; border-radius: 4px; margin: 2px; display: inline-block; }}
            .badge-high {{ background: #f44336; color: white; }}
            .badge-moderate {{ background: #ff9800; color: white; }}
            .badge-minimal {{ background: #8bc34a; color: white; }}
            .badge-low {{ background: #9e9e9e; color: white; }}
        </style>
    </head>
    <body>
        <div class="header">
            {"<img src='" + product.image_url + "' class='product-image' />" if product.image_url else ""}
            <h1>{product.name}</h1>
            <p><strong>Brand:</strong> {product.brand or "Unknown"}</p>
            <p><strong>Barcode:</strong> {product.barcode}</p>
            <p><strong>Processing Level:</strong> {product.processing_level}</p>
        </div>
        
        <h2>Nutrition Facts (per 100{"ml" if product.is_liquid else "g"})</h2>
        <table>
            <tr>
                <th>Nutrient</th>
                <th>Value</th>
                <th>% Daily Value</th>
            </tr>
            {nutrients_html}
        </table>
        
        <h2>Additives</h2>
        <p>{", ".join(product.additives_tags) if product.additives_tags else "No additives detected"}</p>
        
        <h2>Ingredients</h2>
        <p>{product.ingredients_text or "Not available"}</p>
        
        <footer>
            <p><small>Data source: OpenFoodFacts</small></p>
        </footer>
    </body>
    </html>
    """
    
    return html


if __name__ == "__main__":
    # Test utilities
    print("Testing barcode sanitization...")
    print(sanitize_barcode("  1234567890128  "))
    print(sanitize_barcode("1234-5678-9012-8"))
    
    print("\nTesting checksum validation...")
    print(f"5449000000996: {validate_ean_checksum('5449000000996')}")  # Valid Coca-Cola
    print(f"5449000000997: {validate_ean_checksum('5449000000997')}")  # Invalid
    
    print("\nTesting E-number extraction...")
    text = "Contains: water, sugar, E150d, caramel color (E150d), E950, acesulfame-k"
    print(extract_e_numbers(text))
