"""Test script for barcode detection."""
import cv2
import numpy as np
from PIL import Image
from pyzbar import pyzbar

print("=" * 50)
print("BARCODE DETECTION TEST")
print("=" * 50)

# Test 1: Check pyzbar is working
print("\n1. Testing pyzbar import...")
try:
    from pyzbar.pyzbar import ZBarSymbol
    print("   ✓ pyzbar imported successfully")
    print(f"   Available types: {[s.name for s in ZBarSymbol][:5]}...")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 2: Generate a simple barcode image programmatically
print("\n2. Testing with generated barcode pattern...")

# Create a simple EAN-13 style barcode image
def create_test_barcode():
    """Create a simple barcode-like image for testing."""
    width, height = 200, 100
    img = np.ones((height, width), dtype=np.uint8) * 255
    
    # Draw some vertical bars (simplified barcode pattern)
    bar_positions = [10, 12, 16, 18, 22, 30, 32, 40, 42, 44, 50, 52, 58, 60, 
                     70, 72, 76, 80, 82, 90, 92, 94, 100, 102, 110, 112, 116, 
                     120, 122, 130, 132, 134, 140, 142, 150, 152, 156, 160, 162, 170, 172, 174, 180, 182]
    
    for pos in bar_positions:
        if pos < width:
            img[10:90, pos:pos+2] = 0
    
    return img

test_img = create_test_barcode()
results = pyzbar.decode(test_img)
print(f"   Generated pattern: {len(results)} barcodes detected")

# Test 3: Try to download and test with a real barcode
print("\n3. Testing with online barcode image...")
try:
    import urllib.request
    import io
    
    # Use a simple barcode generator API
    url = "https://barcodeapi.org/api/ean13/9781234567897"
    print(f"   Downloading from: {url[:50]}...")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        img_data = response.read()
    
    # Convert to numpy array
    img_array = np.frombuffer(img_data, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
    
    if img is not None:
        print(f"   Image size: {img.shape}")
        
        # Try to decode
        results = pyzbar.decode(img)
        print(f"   Barcodes detected: {len(results)}")
        
        for r in results:
            print(f"   → Data: {r.data.decode()}, Type: {r.type}")
    else:
        print("   ✗ Could not decode image")
        
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 4: Test with a local file if exists
print("\n4. Testing barcode decoder class...")
import sys
sys.path.insert(0, 'd:/OpenCV/food_scanner/src')

try:
    from barcode_decoder import BarcodeDecoder
    decoder = BarcodeDecoder()
    print("   ✓ BarcodeDecoder initialized")
    
    # Test with generated image
    test_img_color = cv2.cvtColor(create_test_barcode(), cv2.COLOR_GRAY2BGR)
    results = decoder.decode_image(test_img_color)
    print(f"   Decoder found: {len(results)} barcodes")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("TEST COMPLETE")
print("=" * 50)
