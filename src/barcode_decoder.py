"""
Barcode decoding module for the Food Barcode Scanner.

This module provides barcode decoding functionality using pyzbar as the primary
decoder with fallback strategies for difficult-to-read barcodes.
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

try:
    from pyzbar import pyzbar
    from pyzbar.pyzbar import Decoded
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    Decoded = None

from utils import logger, sanitize_barcode, validate_ean_checksum


class BarcodeType(Enum):
    """Supported barcode types."""
    EAN13 = "EAN13"
    EAN8 = "EAN8"
    UPCA = "UPCA"
    UPCE = "UPCE"
    QR = "QRCODE"
    CODE128 = "CODE128"
    CODE39 = "CODE39"
    UNKNOWN = "UNKNOWN"


@dataclass
class BarcodeResult:
    """
    Result from barcode decoding.
    
    Attributes:
        data: The decoded barcode data (digits/text).
        type: The type of barcode detected.
        rect: Bounding rectangle (x, y, width, height).
        polygon: List of polygon points for the barcode boundary.
        valid_checksum: Whether the checksum validation passed.
        confidence: Confidence score if available.
    """
    data: str
    type: BarcodeType
    rect: Tuple[int, int, int, int]
    polygon: List[Tuple[int, int]]
    valid_checksum: bool = True
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "data": self.data,
            "type": self.type.value,
            "rect": self.rect,
            "polygon": self.polygon,
            "valid_checksum": self.valid_checksum,
            "confidence": self.confidence,
        }


class BarcodeDecoder:
    """
    Barcode decoder with preprocessing and fallback strategies.
    
    Uses pyzbar as the primary decoder with image preprocessing
    and rotation-based fallback for difficult barcodes.
    """
    
    # Barcode type mapping from pyzbar
    TYPE_MAPPING = {
        "EAN13": BarcodeType.EAN13,
        "EAN8": BarcodeType.EAN8,
        "UPCA": BarcodeType.UPCA,
        "UPCE": BarcodeType.UPCE,
        "QRCODE": BarcodeType.QR,
        "CODE128": BarcodeType.CODE128,
        "CODE39": BarcodeType.CODE39,
    }
    
    def __init__(
        self,
        validate_checksum: bool = True,
        use_preprocessing: bool = True,
        try_rotations: bool = True
    ):
        """
        Initialize the barcode decoder.
        
        Args:
            validate_checksum: Whether to validate EAN/UPC checksums.
            use_preprocessing: Whether to apply image preprocessing.
            try_rotations: Whether to try different image rotations.
        """
        if not PYZBAR_AVAILABLE:
            raise ImportError(
                "pyzbar is not installed. Install it with: pip install pyzbar"
            )
        
        self.validate_checksum = validate_checksum
        self.use_preprocessing = use_preprocessing
        self.try_rotations = try_rotations
        
        logger.debug("BarcodeDecoder initialized")
    
    def decode_image(
        self,
        image: Union[str, Path, np.ndarray, Image.Image]
    ) -> List[BarcodeResult]:
        """
        Decode barcodes from an image.
        
        Args:
            image: Image as file path, numpy array, or PIL Image.
            
        Returns:
            List of BarcodeResult objects for detected barcodes.
        """
        # Load image if path provided
        if isinstance(image, (str, Path)):
            image = self._load_image(image)
        elif isinstance(image, Image.Image):
            image = np.array(image)
        
        if image is None or image.size == 0:
            logger.warning("Empty or invalid image provided")
            return []
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Try decoding with different preprocessing strategies
        results = []
        
        # Strategy 1: Direct decode
        results.extend(self._decode_frame(gray))
        
        if not results:
            # Strategy 2: Upscale small images (important for low-res barcodes)
            h, w = gray.shape[:2]
            if w < 500 or h < 500:
                scale = max(500 / w, 500 / h, 2.0)
                upscaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                results.extend(self._decode_frame(upscaled))
        
        if not results:
            # Strategy 3: Simple threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            results.extend(self._decode_frame(binary))
        
        if not results:
            # Strategy 4: Upscaled + threshold
            h, w = gray.shape[:2]
            scale = max(2.0, 600 / min(w, h))
            upscaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            _, binary = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            results.extend(self._decode_frame(binary))
        
        if not results and self.use_preprocessing:
            # Strategy 5: Full preprocessed image
            preprocessed = self._preprocess_image(gray)
            results.extend(self._decode_frame(preprocessed))
        
        if not results and self.use_preprocessing:
            # Strategy 6: Upscaled + preprocessed
            h, w = gray.shape[:2]
            scale = max(2.0, 600 / min(w, h))
            upscaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            preprocessed = self._preprocess_image(upscaled)
            results.extend(self._decode_frame(preprocessed))
        
        if not results and self.try_rotations:
            # Strategy 7: Try rotations
            for angle in [90, 180, 270]:
                rotated = self._rotate_image(gray, angle)
                results.extend(self._decode_frame(rotated))
                if results:
                    break
        
        if not results and self.use_preprocessing and self.try_rotations:
            # Strategy 8: Preprocessed with rotations
            preprocessed = self._preprocess_image(gray)
            for angle in [90, 180, 270]:
                rotated = self._rotate_image(preprocessed, angle)
                results.extend(self._decode_frame(rotated))
                if results:
                    break
        
        # Validate and deduplicate results
        results = self._validate_results(results)
        results = self._deduplicate_results(results)
        
        logger.debug(f"Decoded {len(results)} barcodes")
        return results
    
    def decode_frame(self, frame: np.ndarray) -> List[BarcodeResult]:
        """
        Decode barcodes from a video frame (optimized for real-time).
        
        Args:
            frame: OpenCV frame (BGR or grayscale).
            
        Returns:
            List of BarcodeResult objects.
        """
        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # For real-time, use minimal preprocessing
        results = self._decode_frame(gray)
        
        if not results and self.use_preprocessing:
            # Quick preprocessing
            processed = cv2.GaussianBlur(gray, (3, 3), 0)
            processed = cv2.adaptiveThreshold(
                processed, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )
            results = self._decode_frame(processed)
        
        return self._validate_results(results)
    
    def _load_image(self, path: Union[str, Path]) -> Optional[np.ndarray]:
        """Load an image from file."""
        path = str(path)
        image = cv2.imread(path)
        
        if image is None:
            logger.error(f"Failed to load image: {path}")
            return None
        
        return image
    
    def _decode_frame(self, image: np.ndarray) -> List[BarcodeResult]:
        """Decode barcodes using pyzbar."""
        try:
            decoded = pyzbar.decode(image)
        except Exception as e:
            logger.error(f"pyzbar decode error: {e}")
            return []
        
        results = []
        for barcode in decoded:
            try:
                data = barcode.data.decode("utf-8")
                
                # Get barcode type
                barcode_type = self.TYPE_MAPPING.get(
                    barcode.type, BarcodeType.UNKNOWN
                )
                
                # Get bounding rect
                rect = (
                    barcode.rect.left,
                    barcode.rect.top,
                    barcode.rect.width,
                    barcode.rect.height
                )
                
                # Get polygon points
                polygon = [(point.x, point.y) for point in barcode.polygon]
                
                results.append(BarcodeResult(
                    data=data,
                    type=barcode_type,
                    rect=rect,
                    polygon=polygon,
                ))
                
            except Exception as e:
                logger.debug(f"Error processing barcode: {e}")
                continue
        
        return results
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Apply preprocessing to improve barcode detection.
        
        Uses:
        - Bilateral filter for noise reduction
        - CLAHE for adaptive histogram equalization
        - Adaptive thresholding
        - Morphological operations
        """
        # Bilateral filter (preserves edges while reducing noise)
        filtered = cv2.bilateralFilter(image, 9, 75, 75)
        
        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        equalized = clahe.apply(filtered)
        
        # Adaptive threshold
        thresh = cv2.adaptiveThreshold(
            equalized, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Morphological opening to remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Morphological closing to fill gaps
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
        
        return closed
    
    def _rotate_image(self, image: np.ndarray, angle: int) -> np.ndarray:
        """Rotate image by specified angle (90, 180, 270 degrees)."""
        if angle == 90:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(image, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return image
    
    def _validate_results(
        self,
        results: List[BarcodeResult]
    ) -> List[BarcodeResult]:
        """Validate barcode results and check checksums."""
        validated = []
        
        for result in results:
            # Skip empty data
            if not result.data:
                continue
            
            # Skip very short or long barcodes (likely false positives)
            if len(result.data) < 6 or len(result.data) > 20:
                logger.debug(f"Skipping barcode with unusual length: {result.data}")
                continue
            
            # Validate checksum for EAN/UPC
            if self.validate_checksum:
                if result.type in (
                    BarcodeType.EAN13, BarcodeType.EAN8,
                    BarcodeType.UPCA, BarcodeType.UPCE
                ):
                    valid = validate_ean_checksum(result.data)
                    result.valid_checksum = valid
                    
                    if not valid:
                        logger.debug(f"Invalid checksum for barcode: {result.data}")
                        # Still include but mark as invalid
            
            validated.append(result)
        
        return validated
    
    def _deduplicate_results(
        self,
        results: List[BarcodeResult]
    ) -> List[BarcodeResult]:
        """Remove duplicate barcode detections."""
        seen = set()
        unique = []
        
        for result in results:
            if result.data not in seen:
                seen.add(result.data)
                unique.append(result)
        
        return unique
    
    def draw_results(
        self,
        image: np.ndarray,
        results: List[BarcodeResult],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw barcode detection results on an image.
        
        Args:
            image: Image to draw on (will be modified).
            results: List of BarcodeResult objects.
            color: BGR color for the bounding box.
            thickness: Line thickness.
            
        Returns:
            Image with drawn results.
        """
        output = image.copy()
        
        for result in results:
            # Draw polygon
            if result.polygon:
                pts = np.array(result.polygon, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(output, [pts], True, color, thickness)
            else:
                # Fall back to rectangle
                x, y, w, h = result.rect
                cv2.rectangle(output, (x, y), (x + w, y + h), color, thickness)
            
            # Draw barcode data
            x, y = result.rect[0], result.rect[1]
            
            # Background for text
            text = f"{result.data} ({result.type.value})"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, 1)
            
            cv2.rectangle(
                output,
                (x, y - text_h - 10),
                (x + text_w + 10, y),
                color,
                -1
            )
            
            # Draw text
            cv2.putText(
                output,
                text,
                (x + 5, y - 5),
                font,
                font_scale,
                (0, 0, 0),
                1
            )
        
        return output
    
    @staticmethod
    def extract_roi(
        image: np.ndarray,
        center_ratio: float = 0.6
    ) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        Extract a Region of Interest from the center of an image.
        
        Args:
            image: Input image.
            center_ratio: Size of ROI as ratio of image size.
            
        Returns:
            Tuple of (ROI image, (x, y, width, height)).
        """
        h, w = image.shape[:2]
        
        roi_w = int(w * center_ratio)
        roi_h = int(h * center_ratio)
        x = (w - roi_w) // 2
        y = (h - roi_h) // 2
        
        roi = image[y:y + roi_h, x:x + roi_w]
        return roi, (x, y, roi_w, roi_h)


class DuplicateFilter:
    """
    Filter to prevent reporting the same barcode multiple times.
    
    Used in continuous scanning to debounce repeated detections.
    """
    
    def __init__(self, timeout_seconds: float = 3.0):
        """
        Initialize the duplicate filter.
        
        Args:
            timeout_seconds: Time before a barcode can be reported again.
        """
        self.timeout = timeout_seconds
        self._last_seen: dict = {}
    
    def is_duplicate(self, barcode: str) -> bool:
        """
        Check if a barcode was recently seen.
        
        Args:
            barcode: Barcode data string.
            
        Returns:
            True if duplicate (recently seen), False otherwise.
        """
        import time
        
        current_time = time.time()
        
        if barcode in self._last_seen:
            if current_time - self._last_seen[barcode] < self.timeout:
                return True
        
        self._last_seen[barcode] = current_time
        return False
    
    def reset(self) -> None:
        """Clear the filter history."""
        self._last_seen.clear()
    
    def cleanup(self) -> None:
        """Remove expired entries from history."""
        import time
        
        current_time = time.time()
        expired = [
            k for k, v in self._last_seen.items()
            if current_time - v >= self.timeout
        ]
        
        for k in expired:
            del self._last_seen[k]


if __name__ == "__main__":
    # Test the barcode decoder
    print("Testing BarcodeDecoder...")
    
    decoder = BarcodeDecoder()
    
    # Test with a sample image (if available)
    sample_path = Path(__file__).parent.parent / "tests" / "sample_images"
    
    if sample_path.exists():
        for img_file in sample_path.glob("*.png"):
            print(f"\nDecoding: {img_file.name}")
            results = decoder.decode_image(img_file)
            
            for result in results:
                print(f"  Barcode: {result.data}")
                print(f"  Type: {result.type.value}")
                print(f"  Valid checksum: {result.valid_checksum}")
    else:
        print("No sample images found. Create test images in tests/sample_images/")
    
    # Test duplicate filter
    print("\nTesting DuplicateFilter...")
    dup_filter = DuplicateFilter(timeout_seconds=1.0)
    
    print(f"First check '12345': {dup_filter.is_duplicate('12345')}")  # False
    print(f"Second check '12345': {dup_filter.is_duplicate('12345')}")  # True
    print(f"Check '67890': {dup_filter.is_duplicate('67890')}")  # False
