"""
SQLite caching module for the Food Barcode Scanner.

This module provides persistent caching for product data to reduce API calls
and enable offline mode functionality.
"""

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager

from utils import logger, sanitize_barcode


# Default cache configuration
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "cache"
DEFAULT_CACHE_TTL = int(os.environ.get("FOOD_SCANNER_CACHE_TTL", 604800))  # 7 days


class ProductCache:
    """
    SQLite-based cache for product data.
    
    Provides persistent storage for product information to reduce API calls
    and enable offline functionality.
    
    Attributes:
        db_path: Path to the SQLite database file.
        ttl: Time-to-live for cache entries in seconds.
    """
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl: int = DEFAULT_CACHE_TTL
    ):
        """
        Initialize the product cache.
        
        Args:
            cache_dir: Directory for the cache database. Defaults to ./cache/
            ttl: Time-to-live for cache entries in seconds.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.cache_dir / "products.db"
        self.ttl = ttl
        
        self._init_database()
        logger.debug(f"Cache initialized at {self.db_path}")
    
    def _init_database(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create products table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    barcode TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    source TEXT DEFAULT 'openfoodfacts'
                )
            """)
            
            # Create index on updated_at for TTL queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_updated_at
                ON products(updated_at)
            """)
            
            # Create lookup history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lookup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT NOT NULL,
                    lookup_time INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    source TEXT
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections.
        
        Yields:
            sqlite3.Connection: Database connection.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a product from the cache.
        
        Args:
            barcode: Product barcode to look up.
            
        Returns:
            Product data dictionary if found and not expired, None otherwise.
        """
        try:
            barcode = sanitize_barcode(barcode)
        except ValueError as e:
            logger.warning(f"Invalid barcode for cache lookup: {e}")
            return None
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get product data
            cursor.execute(
                "SELECT data, updated_at FROM products WHERE barcode = ?",
                (barcode,)
            )
            row = cursor.fetchone()
            
            if row is None:
                logger.debug(f"Cache miss for barcode: {barcode}")
                return None
            
            # Check TTL
            if time.time() - row["updated_at"] > self.ttl:
                logger.debug(f"Cache expired for barcode: {barcode}")
                return None
            
            logger.debug(f"Cache hit for barcode: {barcode}")
            return json.loads(row["data"])
    
    def set(
        self,
        barcode: str,
        data: Dict[str, Any],
        source: str = "openfoodfacts"
    ) -> bool:
        """
        Store a product in the cache.
        
        Args:
            barcode: Product barcode.
            data: Product data dictionary.
            source: Data source identifier.
            
        Returns:
            True if stored successfully, False otherwise.
        """
        try:
            barcode = sanitize_barcode(barcode)
        except ValueError as e:
            logger.warning(f"Invalid barcode for cache storage: {e}")
            return False
        
        current_time = int(time.time())
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Upsert product data
            cursor.execute("""
                INSERT INTO products (barcode, data, created_at, updated_at, source)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(barcode) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at,
                    source = excluded.source
            """, (barcode, json.dumps(data), current_time, current_time, source))
            
            conn.commit()
            logger.debug(f"Cached product: {barcode}")
            return True
    
    def delete(self, barcode: str) -> bool:
        """
        Remove a product from the cache.
        
        Args:
            barcode: Product barcode to remove.
            
        Returns:
            True if deleted, False if not found.
        """
        try:
            barcode = sanitize_barcode(barcode)
        except ValueError:
            return False
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE barcode = ?", (barcode,))
            conn.commit()
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug(f"Deleted cached product: {barcode}")
            return deleted
    
    def clear_expired(self) -> int:
        """
        Remove all expired entries from the cache.
        
        Returns:
            Number of entries removed.
        """
        # Use <= to ensure entries exactly at the TTL boundary are purged.
        expiry_time = int(time.time()) - self.ttl
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM products WHERE updated_at <= ?",
                (expiry_time,)
            )
            conn.commit()
            
            count = cursor.rowcount
            if count > 0:
                logger.info(f"Cleared {count} expired cache entries")
            return count
    
    def clear_all(self) -> int:
        """
        Remove all entries from the cache.
        
        Returns:
            Number of entries removed.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products")
            conn.commit()
            
            count = cursor.rowcount
            logger.info(f"Cleared all {count} cache entries")
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total entries
            cursor.execute("SELECT COUNT(*) as count FROM products")
            total_count = cursor.fetchone()["count"]
            
            # Valid entries (not expired)
            expiry_time = int(time.time()) - self.ttl
            cursor.execute(
                "SELECT COUNT(*) as count FROM products WHERE updated_at >= ?",
                (expiry_time,)
            )
            valid_count = cursor.fetchone()["count"]
            
            # Oldest entry
            cursor.execute("SELECT MIN(created_at) as oldest FROM products")
            oldest_row = cursor.fetchone()
            oldest = oldest_row["oldest"] if oldest_row else None
            
            # Database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            return {
                "total_entries": total_count,
                "valid_entries": valid_count,
                "expired_entries": total_count - valid_count,
                "oldest_entry": oldest,
                "database_size_bytes": db_size,
                "ttl_seconds": self.ttl,
            }
    
    def log_lookup(
        self,
        barcode: str,
        success: bool,
        source: Optional[str] = None
    ) -> None:
        """
        Log a product lookup for analytics.
        
        Args:
            barcode: Product barcode looked up.
            success: Whether the lookup was successful.
            source: Source of the data (cache, api, etc.).
        """
        try:
            barcode = sanitize_barcode(barcode)
        except ValueError:
            barcode = "invalid"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lookup_history (barcode, lookup_time, success, source)
                VALUES (?, ?, ?, ?)
            """, (barcode, int(time.time()), int(success), source))
            conn.commit()
    
    def get_lookup_history(self, limit: int = 50) -> list:
        """
        Get recent lookup history.
        
        Args:
            limit: Maximum number of entries to return.
            
        Returns:
            List of lookup history entries.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT barcode, lookup_time, success, source
                FROM lookup_history
                ORDER BY lookup_time DESC, id DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]


class MockDataCache:
    """
    Fallback cache using local JSON file for mock/test data.
    
    Used when SQLite is not available or for testing purposes.
    """
    
    def __init__(self, data_file: Optional[Path] = None):
        """
        Initialize the mock data cache.
        
        Args:
            data_file: Path to the JSON data file.
        """
        default_file = Path(__file__).parent.parent / "data" / "mock_products.json"
        self.data_file = Path(data_file) if data_file else default_file
        self._data: Dict[str, Any] = {}
        self._load_data()
    
    def _load_data(self) -> None:
        """Load data from JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.debug(f"Loaded {len(self._data)} mock products")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load mock data: {e}")
                self._data = {}
    
    def get(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Get a product from mock data."""
        try:
            barcode = sanitize_barcode(barcode)
        except ValueError:
            return None
        
        return self._data.get(barcode)
    
    def set(self, barcode: str, data: Dict[str, Any]) -> bool:
        """Add or update a mock product."""
        try:
            barcode = sanitize_barcode(barcode)
        except ValueError:
            return False
        
        self._data[barcode] = data
        self._save_data()
        return True
    
    def _save_data(self) -> None:
        """Save data to JSON file."""
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.warning(f"Failed to save mock data: {e}")


# Create default mock products file if it doesn't exist
def create_default_mock_data():
    """Create default mock products file with example data."""
    mock_file = Path(__file__).parent.parent / "data" / "mock_products.json"
    
    if not mock_file.exists():
        mock_data = {
            "0123456789012": {
                "product_name": "Example Cola Zero",
                "brands": "Example Brand",
                "code": "0123456789012",
                "quantity": "330 ml",
                "categories": "Beverages, Carbonated drinks, Sodas, Diet sodas",
                "image_url": None,
                "ingredients_text": "Carbonated Water, Caramel Color (E150d), Phosphoric Acid (E338), Sweeteners (Aspartame, Acesulfame K), Natural Flavors, Caffeine",
                "nutriments": {
                    "energy-kcal_100g": 0.4,
                    "fat_100g": 0,
                    "saturated-fat_100g": 0,
                    "carbohydrates_100g": 0,
                    "sugars_100g": 0,
                    "proteins_100g": 0,
                    "salt_100g": 0.02,
                    "sodium_100g": 0.008,
                    "fiber_100g": 0
                },
                "additives_tags": [
                    "en:e150d",
                    "en:e338",
                    "en:e951",
                    "en:e950"
                ],
                "nova_group": 4,
                "packaging": "Bottle, Plastic",
                "status": 1
            }
        }
        
        mock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(mock_file, "w", encoding="utf-8") as f:
            json.dump(mock_data, f, indent=2, ensure_ascii=False)
        
        logger.info("Created default mock products file")


# Create mock data file on module import
create_default_mock_data()


if __name__ == "__main__":
    # Test cache functionality
    print("Testing ProductCache...")
    
    cache = ProductCache()
    
    # Test set
    test_data = {"name": "Test Product", "brand": "Test Brand"}
    cache.set("1234567890123", test_data)
    
    # Test get
    result = cache.get("1234567890123")
    print(f"Retrieved: {result}")
    
    # Test stats
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")
    
    # Test lookup logging
    cache.log_lookup("1234567890123", True, "cache")
    history = cache.get_lookup_history(limit=5)
    print(f"Lookup history: {history}")
