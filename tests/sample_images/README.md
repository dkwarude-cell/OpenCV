# Sample Test Images

This directory should contain sample barcode images for testing.

## Suggested Test Images

To properly test the barcode scanner, add the following types of images:

1. **EAN-13 Barcodes** (most common for food products)

   - `ean13_cocacola.png` - Clear EAN-13 barcode
   - `ean13_nutella.png` - Another EAN-13 sample

2. **Different Quality Levels**

   - `barcode_high_quality.png` - Sharp, well-lit barcode
   - `barcode_low_quality.png` - Blurry or poorly lit
   - `barcode_rotated.png` - Barcode at an angle

3. **Edge Cases**
   - `barcode_partial.png` - Partially visible barcode
   - `barcode_damaged.png` - Barcode with scratches
   - `no_barcode.png` - Image without a barcode

## Creating Test Images

You can create test barcode images using:

1. **Online generators:**

   - https://barcode.tec-it.com/
   - https://www.barcodesinc.com/generator/

2. **Python code:**

```python
import barcode
from barcode.writer import ImageWriter

# Generate EAN-13 barcode
ean = barcode.get('ean13', '5449000000996', writer=ImageWriter())
ean.save('ean13_sample')
```

3. **Take photos of actual products:**
   - Use well-lit environment
   - Ensure barcode is in focus
   - Include some margin around barcode

## Test Barcodes to Use

Here are some real product barcodes you can use for testing:

| Barcode       | Product       |
| ------------- | ------------- |
| 5449000000996 | Coca-Cola     |
| 3017620422003 | Nutella       |
| 5000159407236 | Heinz Ketchup |
| 7622210449283 | Oreo Cookies  |
| 8076809513753 | Barilla Pasta |

## Running Tests with Sample Images

```bash
# Test single image
python src/scan_image.py --image tests/sample_images/ean13_sample.png

# Run automated tests
python -m pytest tests/ -v
```
