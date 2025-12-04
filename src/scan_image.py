#!/usr/bin/env python3
"""
Food Barcode Scanner - Command Line Interface

Scan barcodes from image files and get nutrition information.

Usage:
    python scan_image.py --image path/to/barcode.jpg
    python scan_image.py --barcode 5449000000996
    python scan_image.py --image sample.jpg --per 100ml --output json
    python scan_image.py --image sample.jpg --html report.html

Examples:
    # Scan an image file
    python scan_image.py --image product.jpg

    # Look up by barcode number
    python scan_image.py --barcode 5449000000996 --per serving

    # Generate HTML report
    python scan_image.py --barcode 3017620422003 --html nutella_report.html

    # Output as JSON
    python scan_image.py --barcode 5449000000996 --output json > product.json
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from barcode_decoder import BarcodeDecoder
from product_lookup import ProductLookup, format_product_text, format_product_json
from additives import AdditivesAnalyzer
from utils import generate_html_report, logger


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scan food barcodes and get nutrition information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--image", "-i",
        type=str,
        help="Path to image file containing barcode"
    )
    input_group.add_argument(
        "--barcode", "-b",
        type=str,
        help="Barcode number to look up directly"
    )
    
    # Display options
    parser.add_argument(
        "--per",
        choices=["100g", "100ml", "serving"],
        default="100g",
        help="Display nutrients per unit (default: 100g)"
    )
    
    # Output options
    parser.add_argument(
        "--output", "-o",
        choices=["text", "json", "brief"],
        default="text",
        help="Output format (default: text)"
    )
    
    parser.add_argument(
        "--html",
        type=str,
        metavar="FILE",
        help="Generate HTML report and save to file"
    )
    
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open HTML report in browser (requires --html)"
    )
    
    # Additional options
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use offline mode (local cache only)"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching"
    )
    
    parser.add_argument(
        "--show-additives",
        action="store_true",
        help="Show detailed additive analysis"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Food Barcode Scanner 1.0.0"
    )
    
    return parser.parse_args()


def scan_image(image_path: str) -> list:
    """
    Scan an image file for barcodes.
    
    Args:
        image_path: Path to the image file.
        
    Returns:
        List of decoded barcode strings.
    """
    path = Path(image_path)
    
    if not path.exists():
        print(f"Error: Image file not found: {image_path}", file=sys.stderr)
        sys.exit(1)
    
    decoder = BarcodeDecoder()
    
    try:
        results = decoder.decode_image(path)
    except Exception as e:
        print(f"Error decoding image: {e}", file=sys.stderr)
        sys.exit(1)
    
    if not results:
        print("No barcodes detected in the image.", file=sys.stderr)
        print("\nTips:", file=sys.stderr)
        print("  - Ensure the barcode is clear and well-lit", file=sys.stderr)
        print("  - Try a higher resolution image", file=sys.stderr)
        print("  - Make sure the barcode is not blurry or damaged", file=sys.stderr)
        sys.exit(1)
    
    return [r.data for r in results]


def format_brief(product) -> str:
    """Format product info in brief one-line format."""
    if not product.is_rated:
        return f"{product.barcode}: {product.status_message}"
    
    energy = product.nutrients_per_100.get("energy_kcal")
    sugar = product.nutrients_per_100.get("sugars")
    fat = product.nutrients_per_100.get("fat")
    
    energy_str = f"{energy.value:.0f}kcal" if energy else "?kcal"
    sugar_str = f"{sugar.value:.1f}g sugar" if sugar else ""
    fat_str = f"{fat.value:.1f}g fat" if fat else ""
    
    additives_str = f"{len(product.additives_tags)} additives" if product.additives_tags else ""
    
    parts = [energy_str]
    if sugar_str:
        parts.append(sugar_str)
    if fat_str:
        parts.append(fat_str)
    if additives_str:
        parts.append(additives_str)
    
    return f"{product.barcode}: {product.name} ({', '.join(parts)})"


def analyze_additives(product) -> str:
    """Analyze and format additive information."""
    analyzer = AdditivesAnalyzer()
    additives = analyzer.analyze(
        product.additives_tags,
        product.ingredients_text
    )
    
    if not additives:
        return "No additives detected."
    
    lines = [f"\n🧪 Additive Analysis ({len(additives)} additives found):"]
    lines.append("-" * 40)
    
    # Group by concern level
    summary = analyzer.get_summary(additives)
    
    if summary["high_concern"]:
        lines.append("\n⚠️ HIGH CONCERN:")
        for a in summary["high_concern"]:
            lines.append(f"  🔴 {a['code']}: {a['name']}")
            if a['description']:
                lines.append(f"     → {a['description']}")
    
    if summary["moderate_concern"]:
        lines.append("\n⚡ MODERATE CONCERN:")
        for a in summary["moderate_concern"]:
            lines.append(f"  🟠 {a['code']}: {a['name']}")
    
    if summary["minimal_concern"]:
        lines.append("\n✅ MINIMAL CONCERN:")
        for a in summary["minimal_concern"]:
            lines.append(f"  🟢 {a['code']}: {a['name']}")
    
    if summary["low_value"]:
        lines.append("\nℹ️ UNKNOWN/LOW DATA:")
        for a in summary["low_value"]:
            lines.append(f"  ⚪ {a['code']}: {a['name']}")
    
    return "\n".join(lines)


def main():
    """Main CLI entry point."""
    args = parse_args()
    
    # Enable debug logging
    if args.debug:
        import logging
        logging.getLogger("food_scanner").setLevel(logging.DEBUG)
    
    # Get barcode
    if args.image:
        barcodes = scan_image(args.image)
        barcode = barcodes[0]  # Use first barcode found
        
        if len(barcodes) > 1:
            print(f"Note: Found {len(barcodes)} barcodes, using first: {barcode}",
                  file=sys.stderr)
    else:
        barcode = args.barcode
    
    # Initialize lookup
    lookup = ProductLookup(
        use_cache=not args.no_cache,
        offline_mode=args.offline
    )
    
    # Look up product
    product = lookup.get_product(barcode)
    
    # Output in requested format
    if args.output == "json":
        print(format_product_json(product))
    
    elif args.output == "brief":
        print(format_brief(product))
    
    else:  # text
        print(format_product_text(product, args.per))
        
        if args.show_additives and product.is_rated:
            print(analyze_additives(product))
    
    # Generate HTML report if requested
    if args.html:
        html_content = generate_html_report(product)
        
        html_path = Path(args.html)
        html_path.write_text(html_content, encoding="utf-8")
        print(f"\n✅ HTML report saved to: {html_path}", file=sys.stderr)
        
        if args.open_browser:
            webbrowser.open(f"file://{html_path.absolute()}")
    
    # Return exit code based on product status
    if not product.is_rated:
        sys.exit(2)  # Product found but not rated
    
    sys.exit(0)


if __name__ == "__main__":
    main()
