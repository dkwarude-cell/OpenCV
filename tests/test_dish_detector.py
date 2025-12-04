"""Unit tests for the rule-based dish detector."""

from dish_detector import DishDetector
from utils import ProductInfo


def test_detects_margherita_pizza():
    detector = DishDetector()
    product = ProductInfo(
        barcode="1234567890123",
        name="Stone Baked Margherita Pizza",
        ingredients_text="Wheat flour, tomato sauce (tomato, basil), mozzarella cheese, olive oil, salt",
        categories="Prepared foods, pizza, italian dishes",
    )

    result = detector.detect(product)

    assert result is not None
    assert result.profile.name == "Margherita Pizza"
    assert result.confidence >= 0.35


def test_returns_none_without_ingredients():
    detector = DishDetector()
    product = ProductInfo(barcode="9999999999999")

    assert detector.detect(product) is None
