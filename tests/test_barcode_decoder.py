"""
Unit tests for the barcode decoder module.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from barcode_decoder import (
    BarcodeDecoder,
    BarcodeResult,
    BarcodeType,
    DuplicateFilter,
)


class TestBarcodeDecoder:
    """Tests for BarcodeDecoder class."""
    
    def test_decoder_initialization(self):
        """Test decoder initializes correctly."""
        decoder = BarcodeDecoder()
        assert decoder.validate_checksum is True
        assert decoder.use_preprocessing is True
        assert decoder.try_rotations is True
    
    def test_decoder_custom_settings(self):
        """Test decoder with custom settings."""
        decoder = BarcodeDecoder(
            validate_checksum=False,
            use_preprocessing=False,
            try_rotations=False
        )
        assert decoder.validate_checksum is False
        assert decoder.use_preprocessing is False
        assert decoder.try_rotations is False
    
    def test_decode_empty_image(self):
        """Test decoding an empty image returns empty list."""
        decoder = BarcodeDecoder()
        empty_image = np.zeros((100, 100), dtype=np.uint8)
        results = decoder.decode_image(empty_image)
        assert results == []
    
    def test_decode_none_image(self):
        """Test decoding None returns empty list."""
        decoder = BarcodeDecoder()
        results = decoder.decode_image(None)
        assert results == []
    
    @patch("barcode_decoder.pyzbar.decode")
    def test_decode_with_mocked_pyzbar(self, mock_decode):
        """Test decoding with mocked pyzbar response."""
        # Create mock barcode result
        mock_barcode = MagicMock()
        mock_barcode.data = b"5449000000996"
        mock_barcode.type = "EAN13"
        mock_barcode.rect = MagicMock(left=10, top=20, width=100, height=50)
        mock_barcode.polygon = [
            MagicMock(x=10, y=20),
            MagicMock(x=110, y=20),
            MagicMock(x=110, y=70),
            MagicMock(x=10, y=70),
        ]
        mock_decode.return_value = [mock_barcode]
        
        decoder = BarcodeDecoder()
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        results = decoder.decode_image(image)
        
        assert len(results) == 1
        assert results[0].data == "5449000000996"
        assert results[0].type == BarcodeType.EAN13
    
    def test_result_to_dict(self):
        """Test BarcodeResult to_dict method."""
        result = BarcodeResult(
            data="1234567890123",
            type=BarcodeType.EAN13,
            rect=(10, 20, 100, 50),
            polygon=[(10, 20), (110, 20), (110, 70), (10, 70)],
            valid_checksum=True,
            confidence=0.95
        )
        
        d = result.to_dict()
        
        assert d["data"] == "1234567890123"
        assert d["type"] == "EAN13"
        assert d["rect"] == (10, 20, 100, 50)
        assert d["valid_checksum"] is True
        assert d["confidence"] == 0.95


class TestDuplicateFilter:
    """Tests for DuplicateFilter class."""
    
    def test_filter_initialization(self):
        """Test filter initializes with correct timeout."""
        filter = DuplicateFilter(timeout_seconds=5.0)
        assert filter.timeout == 5.0
    
    def test_first_barcode_not_duplicate(self):
        """Test first occurrence of a barcode is not a duplicate."""
        filter = DuplicateFilter(timeout_seconds=1.0)
        assert filter.is_duplicate("12345") is False
    
    def test_immediate_rescan_is_duplicate(self):
        """Test immediate rescan of same barcode is a duplicate."""
        filter = DuplicateFilter(timeout_seconds=1.0)
        filter.is_duplicate("12345")
        assert filter.is_duplicate("12345") is True
    
    def test_different_barcode_not_duplicate(self):
        """Test different barcode is not a duplicate."""
        filter = DuplicateFilter(timeout_seconds=1.0)
        filter.is_duplicate("12345")
        assert filter.is_duplicate("67890") is False
    
    def test_reset_clears_history(self):
        """Test reset clears all history."""
        filter = DuplicateFilter(timeout_seconds=1.0)
        filter.is_duplicate("12345")
        filter.is_duplicate("67890")
        
        filter.reset()
        
        assert filter.is_duplicate("12345") is False
        assert filter.is_duplicate("67890") is False


class TestBarcodeType:
    """Tests for BarcodeType enum."""
    
    def test_all_types_exist(self):
        """Test all expected barcode types exist."""
        expected_types = ["EAN13", "EAN8", "UPCA", "UPCE", "QR", "CODE128", "CODE39", "UNKNOWN"]
        for type_name in expected_types:
            assert hasattr(BarcodeType, type_name)
    
    def test_type_values(self):
        """Test barcode type values."""
        assert BarcodeType.EAN13.value == "EAN13"
        assert BarcodeType.QR.value == "QRCODE"


class TestROIExtraction:
    """Tests for ROI extraction functionality."""
    
    def test_extract_roi(self):
        """Test ROI extraction with different ratios."""
        decoder = BarcodeDecoder()
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        
        roi, rect = decoder.extract_roi(image, center_ratio=0.5)
        
        # ROI should be 50% of original size, centered
        assert roi.shape[0] == 50  # height
        assert roi.shape[1] == 100  # width
        assert rect[0] == 50  # x offset
        assert rect[1] == 25  # y offset
    
    def test_extract_roi_full_image(self):
        """Test ROI extraction with ratio 1.0."""
        decoder = BarcodeDecoder()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        roi, rect = decoder.extract_roi(image, center_ratio=1.0)
        
        assert roi.shape == image.shape
        assert rect == (0, 0, 100, 100)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
