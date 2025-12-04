# Food Barcode Scanner

A Python application that scans barcodes on food packages using OpenCV and returns nutrition and additive information from OpenFoodFacts.

## Features

- 📷 **Live Camera Scanning**: Real-time barcode detection using OpenCV
- 🔍 **Image Scanning**: Scan barcodes from image files
- 🥗 **Nutrition Information**: Detailed nutrient breakdown per 100g/100ml and per serving
- ⚠️ **Additive Analysis**: E-number identification with concern level mapping
- 🍽 **Dish Insights**: Ingredient mapping to likely dishes with quick recipe references
- 🏭 **Processing Level**: Ultra-processed food detection
- 💾 **Smart Caching**: SQLite-based caching to reduce API calls
- 🌐 **Streamlit Web UI**: Modern, responsive web interface
- 🔒 **Privacy-Focused**: Optional offline mode with local cache only

## Installation

### Prerequisites

- Python 3.10 or higher
- Webcam (for live scanning)
- Windows/Linux/macOS

### Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd food_scanner
```

2. Create a virtual environment (recommended):

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install ZBar library (required for pyzbar):

**Windows:**
Download and install from: https://sourceforge.net/projects/zbar/files/zbar/0.10/zbar-0.10-setup.exe/download

**Linux (Ubuntu/Debian):**

```bash
sudo apt-get install libzbar0
```

**macOS:**

```bash
brew install zbar
```

## Usage

### Streamlit Web App (Recommended)

```bash
streamlit run src/app.py
```

The web interface will open at http://localhost:8501

Features:

- Click "Start Camera" to begin live scanning
- Upload an image file to scan
- Manual barcode entry for testing
- Toggle between per-100g and per-100ml view
- Expand additives and ingredients sections

### Command Line Interface

Scan a barcode image:

```bash
python src/scan_image.py --image path/to/barcode.jpg
```

Options:

```bash
python src/scan_image.py --image sample.jpg --per 100ml --output json
python src/scan_image.py --image sample.jpg --html preview.html
python src/scan_image.py --barcode 5449000000996 --per serving
```

### Python API

```python
from src.barcode_decoder import BarcodeDecoder
from src.product_lookup import ProductLookup
from src.additives import AdditivesAnalyzer

# Decode barcode from image
decoder = BarcodeDecoder()
barcodes = decoder.decode_image("barcode.jpg")

# Look up product
lookup = ProductLookup()
product = lookup.get_product(barcodes[0].data)

# Analyze additives
analyzer = AdditivesAnalyzer()
additives = analyzer.analyze(product.additives_tags)
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_barcode_decoder.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## Project Structure

```
food_scanner/
├── README.md
├── LICENSE
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── app.py              # Streamlit web application
│   ├── scan_image.py       # CLI scanner
│   ├── camera_scanner.py   # OpenCV camera handling
│   ├── barcode_decoder.py  # Barcode decoding logic
│   ├── product_lookup.py   # OpenFoodFacts API client
│   ├── additives.py        # Additive analysis
│   ├── dish_detector.py    # Ingredient-to-dish inference
│   ├── cache.py            # SQLite caching
│   └── utils.py            # Utility functions
├── data/
│   ├── additives_mapping.json  # E-number to concern mapping
│   └── dish_profiles.json      # Curated dish/recipe signatures
├── tests/
│   ├── __init__.py
│   ├── test_barcode_decoder.py
│   ├── test_product_lookup.py
│   ├── test_additives.py
│   ├── test_cache.py
│   └── sample_images/
│       └── README.md
└── cache/
    └── .gitkeep
```

## Extending Additives Mapping

The additives mapping is stored in `data/additives_mapping.json`. To add new additives:

1. Open `data/additives_mapping.json`
2. Add new entries in the format:

```json
{
  "E123": {
    "name": "Amaranth",
    "concern": "High",
    "category": "Color",
    "description": "Red food coloring, banned in some countries"
  }
}
```

Concern levels:

- **High**: Avoid if possible, potential health concerns
- **Moderate**: Use with caution, some concerns
- **Minimal**: Generally safe
- **Low Value**: Insufficient data or unknown

## Dish Insight Dataset

The recipe detection feature is powered by `data/dish_profiles.json`. Each entry describes a dish signature through:

- `name`, `cuisine`, and `description`
- `ingredient_keywords`: tokens that should match the ingredient list
- Optional `required_terms`, `category_keywords`, `aliases`, `hero_ingredients`, and `recipe_url`

To add a new dish, append an object in the dataset following this template:

```json
{
  "name": "Falafel Wrap",
  "cuisine": "Middle Eastern",
  "aliases": ["falafel sandwich"],
  "ingredient_keywords": ["chickpea", "herb", "pita", "tahini"],
  "required_terms": ["chickpea", "falafel"],
  "category_keywords": ["wrap", "sandwich"],
  "hero_ingredients": ["chickpea", "tahini"],
  "description": "Crispy falafel tucked into pita with tahini sauce and vegetables.",
  "recipe_url": "https://example.com/falafel-wrap"
}
```

Provide descriptive keywords so the detector can reach the 35% confidence threshold when matching against ingredient labels.

## Configuration

### Environment Variables

| Variable                 | Default  | Description                   |
| ------------------------ | -------- | ----------------------------- |
| `FOOD_SCANNER_DEBUG`     | `false`  | Enable debug logging          |
| `FOOD_SCANNER_CACHE_TTL` | `604800` | Cache TTL in seconds (7 days) |
| `FOOD_SCANNER_OFFLINE`   | `false`  | Enable offline mode           |

### Camera Settings

Configure in `src/camera_scanner.py`:

- Frame resolution
- Preprocessing parameters
- ROI (Region of Interest) box size
- De-duplication timeout

## API Reference

### OpenFoodFacts API

This project uses the free OpenFoodFacts API:

- Endpoint: `https://world.openfoodfacts.org/api/v0/product/{barcode}.json`
- No API key required
- Rate limit: Be respectful, cache results

### Fallback Data Sources

1. Local SQLite cache
2. Mock data file (`data/mock_products.json`)
3. "Non-rated Category" message

## Troubleshooting

### Camera Not Working

- Check webcam permissions
- Try a different camera index: `--camera 1`
- Ensure no other application is using the camera

### Barcode Not Detected

- Ensure adequate lighting
- Hold barcode steady and centered
- Try uploading a clear image instead

### ZBar Library Error

- Reinstall the ZBar library for your platform
- On Windows, ensure DLL is in PATH

## License

MIT License - see LICENSE file for details.

## Attribution

- Product data from [OpenFoodFacts](https://world.openfoodfacts.org/)
- Barcode decoding by [pyzbar](https://github.com/NaturalHistoryMuseum/pyzbar)
- Image processing by [OpenCV](https://opencv.org/)

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md for guidelines.
