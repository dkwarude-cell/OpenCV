"""
Unit tests for the cache module.
"""

import sys
import time
from pathlib import Path
import tempfile
import shutil

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cache import ProductCache, MockDataCache


class TestProductCache:
    """Tests for ProductCache class."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache fixture with temp directory."""
        return ProductCache(cache_dir=temp_cache_dir, ttl=3600)
    
    def test_cache_initialization(self, cache):
        """Test cache initializes correctly."""
        assert cache.db_path.exists()
        assert cache.ttl == 3600
    
    def test_set_and_get(self, cache):
        """Test setting and getting a product."""
        test_data = {"name": "Test Product", "brand": "Test Brand"}
        
        result = cache.set("1234567890123", test_data)
        assert result is True
        
        retrieved = cache.get("1234567890123")
        assert retrieved == test_data
    
    def test_get_nonexistent(self, cache):
        """Test getting a non-existent product."""
        result = cache.get("9999999999999")
        assert result is None
    
    def test_get_invalid_barcode(self, cache):
        """Test getting with invalid barcode."""
        result = cache.get("")
        assert result is None
    
    def test_set_invalid_barcode(self, cache):
        """Test setting with invalid barcode."""
        result = cache.set("", {"test": "data"})
        assert result is False
    
    def test_delete(self, cache):
        """Test deleting a product."""
        cache.set("1234567890123", {"test": "data"})
        
        result = cache.delete("1234567890123")
        assert result is True
        
        retrieved = cache.get("1234567890123")
        assert retrieved is None
    
    def test_delete_nonexistent(self, cache):
        """Test deleting non-existent product."""
        result = cache.delete("9999999999999")
        assert result is False
    
    def test_update_existing(self, cache):
        """Test updating an existing product."""
        cache.set("1234567890123", {"name": "Original"})
        cache.set("1234567890123", {"name": "Updated"})
        
        retrieved = cache.get("1234567890123")
        assert retrieved["name"] == "Updated"
    
    def test_get_stats(self, cache):
        """Test getting cache statistics."""
        cache.set("1234567890123", {"test": "data"})
        cache.set("9876543210987", {"test": "data2"})
        
        stats = cache.get_stats()
        
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0
        assert stats["ttl_seconds"] == 3600
    
    def test_clear_all(self, cache):
        """Test clearing all entries."""
        cache.set("1234567890123", {"test": "data"})
        cache.set("9876543210987", {"test": "data2"})
        
        count = cache.clear_all()
        
        assert count == 2
        assert cache.get("1234567890123") is None


class TestCacheTTL:
    """Tests for cache TTL functionality."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_expired_entry_not_returned(self, temp_cache_dir):
        """Test that expired entries are not returned."""
        # Create cache with very short TTL
        cache = ProductCache(cache_dir=temp_cache_dir, ttl=1)
        
        cache.set("1234567890123", {"test": "data"})
        
        # Wait for expiry
        time.sleep(1.5)
        
        result = cache.get("1234567890123")
        assert result is None
    
    def test_clear_expired(self, temp_cache_dir):
        """Test clearing expired entries."""
        cache = ProductCache(cache_dir=temp_cache_dir, ttl=1)
        
        cache.set("1234567890123", {"test": "data"})
        time.sleep(1.5)
        
        count = cache.clear_expired()
        
        assert count == 1


class TestLookupHistory:
    """Tests for lookup history functionality."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache fixture."""
        return ProductCache(cache_dir=temp_cache_dir)
    
    def test_log_lookup(self, cache):
        """Test logging a lookup."""
        cache.log_lookup("1234567890123", True, "api")
        
        history = cache.get_lookup_history(limit=1)
        
        assert len(history) == 1
        assert history[0]["barcode"] == "1234567890123"
        assert history[0]["success"] == 1
        assert history[0]["source"] == "api"
    
    def test_get_lookup_history_order(self, cache):
        """Test that history is returned in reverse order."""
        cache.log_lookup("111", True, "cache")
        cache.log_lookup("222", True, "api")
        cache.log_lookup("333", False, None)
        
        history = cache.get_lookup_history(limit=10)
        
        assert len(history) == 3
        # Most recent should be first
        assert history[0]["barcode"] == "333"


class TestMockDataCache:
    """Tests for MockDataCache class."""
    
    @pytest.fixture
    def temp_data_file(self):
        """Create a temporary data file."""
        temp_dir = Path(tempfile.mkdtemp())
        data_file = temp_dir / "mock_products.json"
        yield data_file
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_mock_cache_empty(self, temp_data_file):
        """Test mock cache with non-existent file."""
        cache = MockDataCache(temp_data_file)
        result = cache.get("1234567890123")
        assert result is None
    
    def test_mock_cache_set_and_get(self, temp_data_file):
        """Test setting and getting from mock cache."""
        cache = MockDataCache(temp_data_file)
        
        test_data = {"name": "Test Product"}
        cache.set("1234567890123", test_data)
        
        retrieved = cache.get("1234567890123")
        assert retrieved == test_data
    
    def test_mock_cache_persistence(self, temp_data_file):
        """Test that mock cache persists to file."""
        cache1 = MockDataCache(temp_data_file)
        cache1.set("1234567890123", {"name": "Test"})
        
        # Create new cache instance
        cache2 = MockDataCache(temp_data_file)
        
        retrieved = cache2.get("1234567890123")
        assert retrieved["name"] == "Test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
