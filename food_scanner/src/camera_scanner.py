"""
Camera scanner module for the Food Barcode Scanner.

This module provides real-time camera capture and barcode scanning
using OpenCV for video capture and processing.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generator, List, Optional, Tuple

import cv2
import numpy as np

from barcode_decoder import BarcodeDecoder, BarcodeResult, DuplicateFilter
from utils import logger


class CameraState(Enum):
    """Camera state enumeration."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class CameraConfig:
    """
    Configuration for the camera scanner.
    
    Attributes:
        camera_id: Camera device ID (0 for default).
        width: Frame width in pixels.
        height: Frame height in pixels.
        fps: Target frames per second.
        use_roi: Whether to use Region of Interest for scanning.
        roi_ratio: ROI size as ratio of frame size.
        show_roi_box: Whether to display ROI box overlay.
        duplicate_timeout: Seconds before same barcode can be scanned again.
        debug_mode: Enable debug visualizations.
    """
    camera_id: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    use_roi: bool = True
    roi_ratio: float = 0.7
    show_roi_box: bool = True
    duplicate_timeout: float = 3.0
    debug_mode: bool = False


class CameraScanner:
    """
    Real-time camera barcode scanner.
    
    Provides continuous video capture and barcode scanning with
    preprocessing, ROI detection, and duplicate filtering.
    """
    
    def __init__(
        self,
        config: Optional[CameraConfig] = None,
        on_barcode_detected: Optional[Callable[[BarcodeResult], None]] = None
    ):
        """
        Initialize the camera scanner.
        
        Args:
            config: Camera configuration. Uses defaults if not provided.
            on_barcode_detected: Callback function when barcode is detected.
        """
        self.config = config or CameraConfig()
        self.on_barcode_detected = on_barcode_detected
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._state = CameraState.STOPPED
        self._decoder = BarcodeDecoder(
            validate_checksum=True,
            use_preprocessing=False,  # We do our own preprocessing
            try_rotations=False  # Too slow for real-time
        )
        self._dup_filter = DuplicateFilter(self.config.duplicate_timeout)
        
        # Performance tracking
        self._frame_count = 0
        self._last_fps_time = time.time()
        self._current_fps = 0.0
        
        logger.debug(f"CameraScanner initialized with config: {self.config}")
    
    @property
    def state(self) -> CameraState:
        """Get the current camera state."""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """Check if camera is running."""
        return self._state == CameraState.RUNNING
    
    @property
    def current_fps(self) -> float:
        """Get the current frames per second."""
        return self._current_fps
    
    def start(self) -> bool:
        """
        Start the camera.
        
        Returns:
            True if camera started successfully, False otherwise.
        """
        if self._state == CameraState.RUNNING:
            logger.warning("Camera is already running")
            return True
        
        try:
            # Open camera
            self._cap = cv2.VideoCapture(self.config.camera_id)
            
            if not self._cap.isOpened():
                logger.error(f"Failed to open camera {self.config.camera_id}")
                self._state = CameraState.ERROR
                return False
            
            # Set camera properties
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            
            # Verify settings
            actual_width = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(
                f"Camera started: {actual_width}x{actual_height} @ {actual_fps}fps"
            )
            
            self._state = CameraState.RUNNING
            self._frame_count = 0
            self._last_fps_time = time.time()
            self._dup_filter.reset()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting camera: {e}")
            self._state = CameraState.ERROR
            return False
    
    def stop(self) -> None:
        """Stop the camera."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        
        self._state = CameraState.STOPPED
        logger.info("Camera stopped")
    
    def pause(self) -> None:
        """Pause camera scanning (keeps camera open)."""
        if self._state == CameraState.RUNNING:
            self._state = CameraState.PAUSED
            logger.debug("Camera paused")
    
    def resume(self) -> None:
        """Resume camera scanning."""
        if self._state == CameraState.PAUSED:
            self._state = CameraState.RUNNING
            logger.debug("Camera resumed")
    
    def read_frame(self) -> Optional[np.ndarray]:
        """
        Read a single frame from the camera.
        
        Returns:
            Frame as numpy array, or None if read failed.
        """
        if self._cap is None or not self._cap.isOpened():
            return None
        
        ret, frame = self._cap.read()
        
        if not ret:
            logger.warning("Failed to read frame from camera")
            return None
        
        return frame
    
    def scan_frame(
        self,
        frame: np.ndarray,
        draw_results: bool = True
    ) -> Tuple[np.ndarray, List[BarcodeResult]]:
        """
        Scan a frame for barcodes.
        
        Args:
            frame: Input frame (BGR format).
            draw_results: Whether to draw results on the frame.
            
        Returns:
            Tuple of (processed frame, list of barcode results).
        """
        output_frame = frame.copy()
        results = []
        
        # Extract ROI if configured
        if self.config.use_roi:
            scan_area, roi_rect = self._extract_roi(frame)
            
            # Draw ROI box
            if self.config.show_roi_box:
                self._draw_roi_box(output_frame, roi_rect)
        else:
            scan_area = frame
            roi_rect = (0, 0, frame.shape[1], frame.shape[0])
        
        # Decode barcodes
        raw_results = self._decoder.decode_frame(scan_area)
        
        # Adjust coordinates for ROI offset and filter duplicates
        for result in raw_results:
            # Skip duplicates
            if self._dup_filter.is_duplicate(result.data):
                continue
            
            # Adjust coordinates
            if self.config.use_roi:
                result = self._adjust_coordinates(result, roi_rect)
            
            results.append(result)
            
            # Trigger callback
            if self.on_barcode_detected:
                self.on_barcode_detected(result)
        
        # Draw results
        if draw_results and results:
            output_frame = self._decoder.draw_results(output_frame, results)
        
        # Draw FPS if debug mode
        if self.config.debug_mode:
            self._draw_debug_info(output_frame)
        
        # Update FPS counter
        self._update_fps()
        
        return output_frame, results
    
    def scan_continuous(
        self
    ) -> Generator[Tuple[np.ndarray, List[BarcodeResult]], None, None]:
        """
        Generator for continuous scanning.
        
        Yields:
            Tuples of (frame, barcode results).
        """
        if not self.start():
            return
        
        try:
            while self._state in (CameraState.RUNNING, CameraState.PAUSED):
                frame = self.read_frame()
                
                if frame is None:
                    continue
                
                if self._state == CameraState.PAUSED:
                    yield frame, []
                    continue
                
                processed, results = self.scan_frame(frame)
                yield processed, results
                
        finally:
            self.stop()
    
    def capture_image(self) -> Optional[np.ndarray]:
        """
        Capture a single high-quality image.
        
        Returns:
            Captured image or None if failed.
        """
        was_running = self.is_running
        
        if not was_running:
            if not self.start():
                return None
        
        # Wait for auto-exposure to stabilize
        for _ in range(10):
            frame = self.read_frame()
        
        if not was_running:
            self.stop()
        
        return frame
    
    def _extract_roi(
        self,
        frame: np.ndarray
    ) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """Extract Region of Interest from frame."""
        h, w = frame.shape[:2]
        
        roi_w = int(w * self.config.roi_ratio)
        roi_h = int(h * self.config.roi_ratio)
        x = (w - roi_w) // 2
        y = (h - roi_h) // 2
        
        roi = frame[y:y + roi_h, x:x + roi_w]
        return roi, (x, y, roi_w, roi_h)
    
    def _adjust_coordinates(
        self,
        result: BarcodeResult,
        roi_rect: Tuple[int, int, int, int]
    ) -> BarcodeResult:
        """Adjust barcode coordinates for ROI offset."""
        rx, ry, _, _ = roi_rect
        
        # Adjust rectangle
        x, y, w, h = result.rect
        new_rect = (x + rx, y + ry, w, h)
        
        # Adjust polygon
        new_polygon = [(px + rx, py + ry) for px, py in result.polygon]
        
        return BarcodeResult(
            data=result.data,
            type=result.type,
            rect=new_rect,
            polygon=new_polygon,
            valid_checksum=result.valid_checksum,
            confidence=result.confidence
        )
    
    def _draw_roi_box(
        self,
        frame: np.ndarray,
        roi_rect: Tuple[int, int, int, int]
    ) -> None:
        """Draw ROI box overlay on frame."""
        x, y, w, h = roi_rect
        
        # Draw semi-transparent overlay outside ROI
        overlay = frame.copy()
        
        # Top region
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], y), (0, 0, 0), -1)
        # Bottom region
        cv2.rectangle(
            overlay,
            (0, y + h),
            (frame.shape[1], frame.shape[0]),
            (0, 0, 0),
            -1
        )
        # Left region
        cv2.rectangle(overlay, (0, y), (x, y + h), (0, 0, 0), -1)
        # Right region
        cv2.rectangle(
            overlay,
            (x + w, y),
            (frame.shape[1], y + h),
            (0, 0, 0),
            -1
        )
        
        # Blend overlay
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        
        # Draw ROI border
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Draw corner markers
        corner_len = 30
        corner_color = (0, 255, 0)
        corner_thickness = 3
        
        # Top-left
        cv2.line(frame, (x, y), (x + corner_len, y), corner_color, corner_thickness)
        cv2.line(frame, (x, y), (x, y + corner_len), corner_color, corner_thickness)
        
        # Top-right
        cv2.line(
            frame,
            (x + w, y),
            (x + w - corner_len, y),
            corner_color,
            corner_thickness
        )
        cv2.line(
            frame,
            (x + w, y),
            (x + w, y + corner_len),
            corner_color,
            corner_thickness
        )
        
        # Bottom-left
        cv2.line(
            frame,
            (x, y + h),
            (x + corner_len, y + h),
            corner_color,
            corner_thickness
        )
        cv2.line(
            frame,
            (x, y + h),
            (x, y + h - corner_len),
            corner_color,
            corner_thickness
        )
        
        # Bottom-right
        cv2.line(
            frame,
            (x + w, y + h),
            (x + w - corner_len, y + h),
            corner_color,
            corner_thickness
        )
        cv2.line(
            frame,
            (x + w, y + h),
            (x + w, y + h - corner_len),
            corner_color,
            corner_thickness
        )
        
        # Draw instruction text
        text = "Position barcode within frame"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        
        (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        text_x = (frame.shape[1] - text_w) // 2
        text_y = y - 15
        
        cv2.putText(
            frame,
            text,
            (text_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness
        )
    
    def _draw_debug_info(self, frame: np.ndarray) -> None:
        """Draw debug information on frame."""
        info_lines = [
            f"FPS: {self._current_fps:.1f}",
            f"Frame: {self._frame_count}",
            f"State: {self._state.value}",
        ]
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        color = (0, 255, 255)
        thickness = 1
        
        y_offset = 20
        for i, line in enumerate(info_lines):
            y = y_offset + i * 20
            cv2.putText(frame, line, (10, y), font, font_scale, color, thickness)
    
    def _update_fps(self) -> None:
        """Update FPS counter."""
        self._frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._last_fps_time
        
        if elapsed >= 1.0:
            self._current_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._last_fps_time = current_time


def list_cameras() -> List[dict]:
    """
    List available cameras.
    
    Returns:
        List of camera info dictionaries.
    """
    cameras = []
    
    for i in range(10):  # Check first 10 camera indices
        cap = cv2.VideoCapture(i)
        
        if cap.isOpened():
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            cameras.append({
                "id": i,
                "width": int(width),
                "height": int(height),
                "fps": fps,
            })
            
            cap.release()
    
    return cameras


def run_scanner_window(
    config: Optional[CameraConfig] = None,
    window_name: str = "Barcode Scanner"
) -> None:
    """
    Run the barcode scanner in an OpenCV window.
    
    Args:
        config: Camera configuration.
        window_name: Name of the display window.
    """
    config = config or CameraConfig(debug_mode=True)
    
    def on_barcode(result: BarcodeResult):
        print(f"\n✓ Barcode detected: {result.data}")
        print(f"  Type: {result.type.value}")
        print(f"  Valid checksum: {result.valid_checksum}")
    
    scanner = CameraScanner(config, on_barcode_detected=on_barcode)
    
    print("Starting camera scanner...")
    print("Press 'q' to quit, 'p' to pause/resume, 'r' to reset filter")
    
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    for frame, results in scanner.scan_continuous():
        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('p'):
            if scanner.state == CameraState.RUNNING:
                scanner.pause()
                print("Paused")
            else:
                scanner.resume()
                print("Resumed")
        elif key == ord('r'):
            scanner._dup_filter.reset()
            print("Filter reset")
    
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # List available cameras
    print("Available cameras:")
    for cam in list_cameras():
        print(f"  Camera {cam['id']}: {cam['width']}x{cam['height']} @ {cam['fps']}fps")
    
    # Run the scanner
    print("\nStarting scanner...")
    run_scanner_window()
