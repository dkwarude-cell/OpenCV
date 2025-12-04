"""Download a test barcode image for testing."""
import urllib.request
import os

# Create test images directory
os.makedirs("d:/OpenCV/food_scanner/tests/sample_images", exist_ok=True)

# Download a real barcode
url = "https://barcodeapi.org/api/ean13/9781234567897"
output_path = "d:/OpenCV/food_scanner/tests/sample_images/test_ean13.png"

print(f"Downloading barcode from {url}...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

with urllib.request.urlopen(req, timeout=10) as response:
    img_data = response.read()
    
with open(output_path, 'wb') as f:
    f.write(img_data)

print(f"Saved to: {output_path}")

# Test decoding it
import cv2
from pyzbar import pyzbar

img = cv2.imread(output_path)
print(f"Image size: {img.shape}")

results = pyzbar.decode(img)
print(f"Detected {len(results)} barcodes:")
for r in results:
    print(f"  - {r.data.decode()} ({r.type})")
