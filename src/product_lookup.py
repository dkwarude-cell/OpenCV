"""
Product lookup module for the Food Barcode Scanner.

This module handles fetching product data from the OpenFoodFacts API
with caching, rate limiting, and fallback strategies.
"""

import os
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from urllib.parse import quote

import requests

from cache import ProductCache, MockDataCache
from utils import (
    logger,
    sanitize_barcode,
    ProductInfo,
    NutrientValue,
    detect_liquid_product,
    calculate_rda_percent,
    determine_processing_level,
)


# API Configuration
OPENFOODFACTS_API_URL = "https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
OPENFOODFACTS_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

# Rate limiting
MIN_REQUEST_INTERVAL = 0.5  # seconds between API requests

# Offline mode from environment
OFFLINE_MODE = os.environ.get("FOOD_SCANNER_OFFLINE", "false").lower() == "true"


@dataclass
class ApiResponse:
    """
    API response wrapper.
    
    Attributes:
        success: Whether the request was successful.
        data: Response data if successful.
        error: Error message if failed.
        source: Data source (api, cache, mock).
    """
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    source: str = "unknown"


class RateLimiter:
    """Simple rate limiter for API requests."""
    
    def __init__(self, min_interval: float = MIN_REQUEST_INTERVAL):
        """Initialize rate limiter with minimum interval between requests."""
        self.min_interval = min_interval
        self._last_request = 0.0
    
    def wait(self) -> None:
        """Wait if needed to respect rate limit."""
        elapsed = time.time() - self._last_request
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self._last_request = time.time()


class ProductLookup:
    """
    Product lookup service using OpenFoodFacts API.
    
    Features:
    - Automatic caching with SQLite
    - Rate limiting to respect API limits
    - Offline mode using local cache
    - Fallback to mock data
    - Comprehensive data parsing
    """
    
    # Nutrient field mapping from OpenFoodFacts to our format
    NUTRIENT_MAPPING = {
        "energy-kcal_100g": ("energy_kcal", "kcal", "Energy"),
        "energy_100g": ("energy_kj", "kJ", "Energy (kJ)"),
        "fat_100g": ("fat", "g", "Total Fat"),
        "saturated-fat_100g": ("saturated_fat", "g", "Saturated Fat (SFA)"),
        "monounsaturated-fat_100g": ("monounsaturated_fat", "g", "Monounsaturated Fat (MUFA)"),
        "polyunsaturated-fat_100g": ("polyunsaturated_fat", "g", "Polyunsaturated Fat (PUFA)"),
        "omega-3-fat_100g": ("omega3", "g", "Omega-3"),
        "omega-6-fat_100g": ("omega6", "g", "Omega-6"),
        "trans-fat_100g": ("trans_fat", "g", "Trans Fat"),
        "cholesterol_100g": ("cholesterol", "mg", "Cholesterol"),
        "carbohydrates_100g": ("carbohydrates", "g", "Carbohydrates"),
        "sugars_100g": ("sugars", "g", "Total Sugars"),
        "sugars_added_100g": ("sugars_added", "g", "Added Sugars"),
        "fiber_100g": ("fiber", "g", "Fiber"),
        "proteins_100g": ("proteins", "g", "Proteins"),
        "salt_100g": ("salt", "g", "Salt"),
        "sodium_100g": ("sodium", "g", "Sodium"),
        # Vitamins
        "vitamin-a_100g": ("vitamin_a", "µg", "Vitamin A"),
        "vitamin-c_100g": ("vitamin_c", "mg", "Vitamin C"),
        "vitamin-d_100g": ("vitamin_d", "µg", "Vitamin D"),
        "vitamin-e_100g": ("vitamin_e", "mg", "Vitamin E"),
        # Minerals
        "calcium_100g": ("calcium", "mg", "Calcium"),
        "iron_100g": ("iron", "mg", "Iron"),
        "potassium_100g": ("potassium", "mg", "Potassium"),
    }
    
    NUTRIENT_MAPPING_SERVING = {
        "energy-kcal_serving": ("energy_kcal", "kcal", "Energy"),
        "fat_serving": ("fat", "g", "Total Fat"),
        "saturated-fat_serving": ("saturated_fat", "g", "Saturated Fat"),
        "trans-fat_serving": ("trans_fat", "g", "Trans Fat"),
        "carbohydrates_serving": ("carbohydrates", "g", "Carbohydrates"),
        "sugars_serving": ("sugars", "g", "Total Sugars"),
        "fiber_serving": ("fiber", "g", "Fiber"),
        "proteins_serving": ("proteins", "g", "Proteins"),
        "salt_serving": ("salt", "g", "Salt"),
        "sodium_serving": ("sodium", "g", "Sodium"),
    }
    
    def __init__(
        self,
        cache: Optional[ProductCache] = None,
        use_cache: bool = True,
        offline_mode: bool = False,
        timeout: float = 10.0
    ):
        """
        Initialize product lookup service.
        
        Args:
            cache: ProductCache instance. Creates new one if not provided.
            use_cache: Whether to use caching.
            offline_mode: Only use local cache, no API calls.
            timeout: Request timeout in seconds.
        """
        self.cache = cache if cache else ProductCache()
        self.mock_cache = MockDataCache()
        self.use_cache = use_cache
        self.offline_mode = offline_mode or OFFLINE_MODE
        self.timeout = timeout
        self._rate_limiter = RateLimiter()
        
        # Session for connection pooling
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "FoodBarcodeScanner/1.0 (Python)",
            "Accept": "application/json",
        })
        
        logger.debug(f"ProductLookup initialized (offline={self.offline_mode})")
    
    def get_product(self, barcode: str) -> ProductInfo:
        """
        Get product information by barcode.
        
        Args:
            barcode: Product barcode (EAN/UPC).
            
        Returns:
            ProductInfo object with product data.
        """
        try:
            barcode = sanitize_barcode(barcode)
        except ValueError as e:
            return self._create_error_product(str(barcode), str(e))
        
        logger.info(f"Looking up product: {barcode}")
        
        # Try cache first
        if self.use_cache:
            cached = self.cache.get(barcode)
            if cached:
                logger.debug(f"Cache hit for {barcode}")
                self.cache.log_lookup(barcode, True, "cache")
                return self._parse_product_data(barcode, cached)
        
        # If offline mode, try mock data
        if self.offline_mode:
            mock = self.mock_cache.get(barcode)
            if mock:
                logger.debug(f"Using mock data for {barcode}")
                return self._parse_product_data(barcode, mock)
            
            return self._create_not_found_product(barcode, "Offline mode - product not in cache")
        
        # Fetch from API
        response = self._fetch_from_api(barcode)
        
        if response.success and response.data:
            # Cache the result
            if self.use_cache:
                self.cache.set(barcode, response.data, "openfoodfacts")
            
            self.cache.log_lookup(barcode, True, "api")
            return self._parse_product_data(barcode, response.data)
        
        # Try mock data as fallback
        mock = self.mock_cache.get(barcode)
        if mock:
            logger.debug(f"Using mock data fallback for {barcode}")
            self.cache.log_lookup(barcode, True, "mock")
            return self._parse_product_data(barcode, mock)
        
        # No data found
        self.cache.log_lookup(barcode, False, None)
        return self._create_not_found_product(
            barcode,
            response.error or "Product not found"
        )
    
    def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for products by name.
        
        Args:
            query: Search query string.
            page: Page number (1-indexed).
            page_size: Number of results per page.
            
        Returns:
            List of product data dictionaries.
        """
        if self.offline_mode:
            logger.warning("Search not available in offline mode")
            return []
        
        try:
            self._rate_limiter.wait()
            
            params = {
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page": page,
                "page_size": page_size,
            }
            
            response = self._session.get(
                OPENFOODFACTS_SEARCH_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            products = data.get("products", [])
            
            logger.debug(f"Search returned {len(products)} results")
            return products
            
        except requests.RequestException as e:
            logger.error(f"Search request failed: {e}")
            return []
    
    def _fetch_from_api(self, barcode: str) -> ApiResponse:
        """Fetch product data from OpenFoodFacts API."""
        try:
            self._rate_limiter.wait()
            
            url = OPENFOODFACTS_API_URL.format(barcode=quote(barcode))
            logger.debug(f"Fetching from API: {url}")
            
            response = self._session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Check API response status
            if data.get("status") == 0:
                return ApiResponse(
                    success=False,
                    error="Product not found in OpenFoodFacts",
                    source="api"
                )
            
            product_data = data.get("product", {})
            
            if not product_data:
                return ApiResponse(
                    success=False,
                    error="Empty product data received",
                    source="api"
                )
            
            return ApiResponse(
                success=True,
                data=product_data,
                source="api"
            )
            
        except requests.Timeout:
            logger.warning(f"API timeout for barcode {barcode}")
            return ApiResponse(
                success=False,
                error="Request timed out. Please try again.",
                source="api"
            )
            
        except requests.ConnectionError:
            logger.warning("Network connection error")
            return ApiResponse(
                success=False,
                error="Network connection error. Check your internet connection.",
                source="api"
            )
            
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return ApiResponse(
                success=False,
                error=f"API request failed: {str(e)}",
                source="api"
            )
    
    def _parse_product_data(
        self,
        barcode: str,
        data: Dict[str, Any]
    ) -> ProductInfo:
        """Parse raw API data into ProductInfo object."""
        # Basic info
        product = ProductInfo(barcode=barcode)
        product.name = data.get("product_name", "Unknown Product")
        product.brand = data.get("brands", "")
        product.image_url = data.get("image_url") or data.get("image_front_url")
        product.ingredients_text = data.get("ingredients_text", "")
        product.quantity = data.get("quantity", "")
        product.categories = data.get("categories", "")
        
        # Detect if liquid
        product.is_liquid = detect_liquid_product(data)
        
        # Parse nutrients per 100g/100ml
        nutriments = data.get("nutriments", {})
        product.nutrients_per_100 = self._parse_nutrients(
            nutriments, self.NUTRIENT_MAPPING
        )
        
        # Parse nutrients per serving
        product.nutrients_per_serving = self._parse_nutrients(
            nutriments, self.NUTRIENT_MAPPING_SERVING
        )
        product.serving_size = data.get("serving_size", "")
        
        # Convert sodium to mg if in g
        if "sodium" in product.nutrients_per_100:
            sodium = product.nutrients_per_100["sodium"]
            if sodium.unit == "g":
                # Convert g to mg
                product.nutrients_per_100["sodium"] = NutrientValue(
                    value=sodium.value * 1000,
                    unit="mg",
                    name="Sodium",
                    rda_percent=calculate_rda_percent("sodium", sodium.value * 1000, "mg")
                )
        
        # Additives
        product.additives_tags = data.get("additives_tags", [])
        
        # NOVA group and processing level
        product.nova_group = data.get("nova_group")
        product.processing_level = determine_processing_level(
            product.nova_group,
            len(product.additives_tags),
            product.ingredients_text
        )
        
        # Nutri-Score and Eco-Score
        product.nutriscore_grade = data.get("nutriscore_grade", "") or data.get("nutrition_grades", "")
        product.nutriscore_score = data.get("nutriscore_score")
        product.ecoscore_grade = data.get("ecoscore_grade", "")
        
        # Determine if product can be rated - now more lenient
        # We can rate if we have ANY useful data
        has_nutrition = bool(product.nutrients_per_100)
        has_nutriscore = bool(product.nutriscore_grade)
        has_nova = product.nova_group is not None
        has_additives_info = product.additives_tags is not None  # Even empty list is info
        has_ingredients = bool(product.ingredients_text)
        
        if has_nutrition or has_nutriscore or has_nova or has_ingredients:
            product.is_rated = True
        else:
            product.is_rated = False
            product.status_message = "Limited data available for this product."
        
        # Store raw data for debugging
        product.raw_data = data
        
        return product
    
    def _parse_nutrients(
        self,
        nutriments: Dict[str, Any],
        mapping: Dict[str, tuple]
    ) -> Dict[str, NutrientValue]:
        """Parse nutrients from raw data using the provided mapping."""
        nutrients = {}
        
        for source_key, (target_key, unit, display_name) in mapping.items():
            value = nutriments.get(source_key)
            
            if value is not None:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    continue
                
                rda_percent = calculate_rda_percent(target_key, value, unit)
                
                nutrients[target_key] = NutrientValue(
                    value=value,
                    unit=unit,
                    name=display_name,
                    rda_percent=rda_percent
                )
        
        return nutrients
    
    def _create_error_product(self, barcode: str, error: str) -> ProductInfo:
        """Create a ProductInfo for error cases."""
        product = ProductInfo(barcode=barcode)
        product.is_rated = False
        product.status_message = f"Error: {error}"
        return product
    
    def _create_not_found_product(self, barcode: str, message: str) -> ProductInfo:
        """Create a ProductInfo for not found cases."""
        product = ProductInfo(barcode=barcode)
        product.name = "Product Not Found"
        product.is_rated = False
        product.status_message = message
        return product
    
    def get_product_image(self, barcode: str) -> Optional[bytes]:
        """
        Get product image as bytes.
        
        Args:
            barcode: Product barcode.
            
        Returns:
            Image bytes or None if not available.
        """
        product = self.get_product(barcode)
        
        if not product.image_url:
            return None
        
        try:
            response = self._session.get(product.image_url, timeout=self.timeout)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch product image: {e}")
            return None


def format_product_json(product: ProductInfo) -> str:
    """
    Format product info as JSON string.
    
    Args:
        product: ProductInfo object.
        
    Returns:
        Pretty-printed JSON string.
    """
    import json
    return json.dumps(product.to_dict(), indent=2, ensure_ascii=False)


def format_product_text(product: ProductInfo, per_unit: str = "100g") -> str:
    """
    Format product info as text.
    
    Args:
        product: ProductInfo object.
        per_unit: Display unit ("100g", "100ml", or "serving").
        
    Returns:
        Formatted text string.
    """
    lines = []
    
    # Header
    lines.append("=" * 50)
    lines.append(f"Product: {product.name}")
    if product.brand:
        lines.append(f"Brand: {product.brand}")
    lines.append(f"Barcode: {product.barcode}")
    lines.append("=" * 50)
    
    if not product.is_rated:
        lines.append(f"\n⚠️ {product.status_message}")
        return "\n".join(lines)
    
    # Processing level
    lines.append(f"\n🏭 Processing Level: {product.processing_level}")
    
    # Nutrients
    lines.append(f"\n📊 Nutrition Facts (per {per_unit}):")
    lines.append("-" * 30)
    
    nutrients = (
        product.nutrients_per_100
        if per_unit in ("100g", "100ml")
        else product.nutrients_per_serving
    )
    
    if not nutrients:
        lines.append("No nutrition data available")
    else:
        for key, nutrient in nutrients.items():
            rda = f" ({nutrient.rda_percent}% DV)" if nutrient.rda_percent else ""
            lines.append(f"  {nutrient.name}: {nutrient.value:.1f} {nutrient.unit}{rda}")
    
    # Additives
    if product.additives_tags:
        lines.append(f"\n🧪 Additives ({len(product.additives_tags)}):")
        lines.append("-" * 30)
        for additive in product.additives_tags[:10]:  # Limit to 10
            lines.append(f"  • {additive}")
        if len(product.additives_tags) > 10:
            lines.append(f"  ... and {len(product.additives_tags) - 10} more")
    
    # Ingredients (truncated)
    if product.ingredients_text:
        lines.append("\n📝 Ingredients:")
        lines.append("-" * 30)
        ingredients = product.ingredients_text[:300]
        if len(product.ingredients_text) > 300:
            ingredients += "..."
        lines.append(f"  {ingredients}")
    
    lines.append("\n" + "=" * 50)
    lines.append("Source: OpenFoodFacts")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Test product lookup
    print("Testing ProductLookup...")
    
    lookup = ProductLookup()
    
    # Test with a known barcode (Coca-Cola)
    test_barcodes = [
        "5449000000996",  # Coca-Cola
        "3017620422003",  # Nutella
        "0123456789012",  # Mock barcode
    ]
    
    for barcode in test_barcodes:
        print(f"\n{'=' * 60}")
        print(f"Looking up: {barcode}")
        print("=" * 60)
        
        product = lookup.get_product(barcode)
        print(format_product_text(product))
