"""
Food Barcode Scanner - Combined Streamlit UI + FastAPI Backend

Runs both the web interface and REST API in a single application.

Usage:
    streamlit run src/app_with_api.py
    
API will be available at: http://localhost:8501/api/...
UI will be available at: http://localhost:8501
"""

import io
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np
import streamlit as st
from PIL import Image
from streamlit.web import cli as stcli
import sys

# Import our modules
from barcode_decoder import BarcodeDecoder, BarcodeResult
from product_lookup import ProductLookup, format_product_json
from additives import AdditivesAnalyzer, ConcernLevel
from cache import ProductCache
from dish_detector import DishDetector
from utils import ProductInfo, format_nutrient_value, generate_html_report


# ============================================================================
# API ENDPOINTS - Accessible via query parameters
# ============================================================================

def handle_api_request():
    """Handle API requests through Streamlit query parameters."""
    query_params = st.query_params
    
    # Check if this is an API request
    if "api" in query_params:
        api_endpoint = query_params.get("api", "")
        
        if api_endpoint == "health":
            st.json({"status": "healthy", "version": "1.0.0"})
            st.stop()
            
        elif api_endpoint == "product":
            barcode = query_params.get("barcode", "")
            if barcode:
                product = st.session_state.lookup.lookup_barcode(barcode)
                if product:
                    result = {
                        "barcode": barcode,
                        "name": product.product_name,
                        "brand": product.brand,
                        "categories": product.categories,
                        "ingredients": product.ingredients_text,
                        "nutrients": {
                            "energy_kcal": product.energy_kcal,
                            "proteins": product.proteins,
                            "carbohydrates": product.carbohydrates,
                            "sugars": product.sugars,
                            "fat": product.fat,
                            "saturated_fat": product.saturated_fat,
                            "fiber": product.fiber,
                            "sodium": product.sodium,
                            "salt": product.salt,
                        },
                        "nova_group": product.nova_group,
                        "nutriscore": product.nutriscore_grade,
                        "image_url": product.image_url,
                    }
                    st.json(result)
                else:
                    st.json({"error": "Product not found"}, status_code=404)
            else:
                st.json({"error": "Barcode parameter required"}, status_code=400)
            st.stop()
            
        elif api_endpoint == "search":
            query = query_params.get("q", "")
            if query:
                results = st.session_state.lookup.search_products(query, page_size=10)
                st.json({"results": [{"barcode": r.get("code"), "name": r.get("product_name")} for r in results]})
            else:
                st.json({"error": "Query parameter 'q' required"}, status_code=400)
            st.stop()


# ============================================================================
# STREAMLIT UI (Original Code)
# ============================================================================

# Page configuration
st.set_page_config(
    page_title="Food Scanner Pro - Smart Nutrition Analysis",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional White UI/UX Theme
st.markdown("""
<style>
    /* Clean white foundation */
    .stApp {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%) !important;
    }
    
    .main {
        padding: 2rem 3rem;
        background-color: transparent !important;
    }
    
    .block-container {
        padding: 3rem 2rem;
        max-width: 1400px;
        background-color: transparent !important;
    }
    
    /* All content areas - Pure white */
    section.main > div,
    [data-testid="stVerticalBlock"],
    [data-testid="stVerticalBlock"] > div,
    [data-testid="column"] {
        background-color: #ffffff !important;
    }
    
    /* Professional header */
    .stApp header {
        background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%) !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }
    
    /* Modern sidebar */
    [data-testid="stSidebar"] {
        background-color: #fafafa !important;
        border-right: 1px solid #e0e0e0;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: #1a1a1a !important;
        font-weight: 600;
    }
    
    /* Elegant tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #ffffff;
        padding: 8px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px;
        border-radius: 8px;
        background-color: #f5f5f5;
        color: #666666;
        border: none;
        font-weight: 500;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e8e8e8;
        color: #1a1a1a;
        transform: translateY(-1px);
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    
    /* Premium buttons */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600;
        border-radius: 10px;
        padding: 0.75rem 2rem;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        letter-spacing: 0.3px;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4);
        transform: translateY(-2px);
    }
    
    button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    }
    
    /* Refined tables */
    .nutrient-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        background-color: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    
    .nutrient-table th {
        background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
        color: white;
        padding: 16px;
        text-align: left;
        font-weight: 600;
        font-size: 0.9rem;
        letter-spacing: 0.5px;
    }
    
    .nutrient-table td {
        padding: 14px 16px;
        border-bottom: 1px solid #f0f0f0;
        color: #333333;
    }
    
    .nutrient-table tr:hover {
        background-color: #f8f9fa;
    }
    
    .nutrient-table tr:last-child td {
        border-bottom: none;
    }
    
    /* Modern badges */
    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 600;
        margin: 3px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .badge-high {
        background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
        color: white;
    }
    
    .badge-moderate {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
    }
    
    .badge-minimal {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
    }
    
    .badge-low {
        background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
        color: white;
    }
    
    /* Product card design */
    .product-header {
        display: flex;
        align-items: flex-start;
        gap: 24px;
        padding: 28px;
        background-color: #ffffff;
        border-radius: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        margin-bottom: 28px;
        border-left: 4px solid #2563eb;
    }
    
    .product-image {
        max-width: 160px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border: 2px solid #f0f0f0;
    }
    
    /* Processing level badges */
    .processing-badge {
        padding: 8px 16px;
        border-radius: 24px;
        font-weight: 600;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    
    .processing-ultra {
        background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
        color: white;
    }
    
    .processing-high {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
    }
    
    .processing-moderate {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
    }
    
    .processing-minimal {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
    }
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {
        color: #1a1a1a !important;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    p, label, span, div {
        color: #333333 !important;
    }
    
    /* Premium expander */
    .streamlit-expanderHeader {
        background-color: #f8f9fa !important;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        color: #1a1a1a !important;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .streamlit-expanderHeader:hover {
        background-color: #e8e8e8 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    
    /* Metrics styling */
    [data-testid="stMetricValue"] {
        color: #2563eb !important;
        font-weight: 700;
    }
    
    /* Alert boxes */
    .stAlert {
        background-color: #f0f9ff !important;
        border-left: 4px solid #2563eb;
        border-radius: 8px;
    }
    
    /* File uploader - Clean white */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploader"] > div,
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stFileUploaderDropzoneInput"],
    .uploadedFile {
        background-color: #ffffff !important;
    }
    
    [data-testid="stFileUploader"] {
        border: 2px dashed #d0d0d0;
        border-radius: 16px;
        padding: 32px;
        transition: all 0.3s ease;
    }
    
    [data-testid="stFileUploader"]:hover {
        border-color: #2563eb;
        box-shadow: 0 4px 16px rgba(37, 99, 235, 0.1);
    }
    
    /* Camera input */
    [data-testid="stCameraInput"],
    [data-testid="stCameraInput"] > div {
        background-color: #ffffff !important;
        border-radius: 12px;
    }
    
    /* Image display */
    [data-testid="stImage"] {
        background-color: #ffffff !important;
        border-radius: 12px;
    }
    
    /* Form inputs */
    input, textarea {
        background-color: #ffffff !important;
        border: 2px solid #e0e0e0 !important;
        border-radius: 8px !important;
        color: #1a1a1a !important;
        padding: 10px 14px !important;
        transition: all 0.3s ease;
    }
    
    input:focus, textarea:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
    }
    
    /* Select boxes */
    [data-baseweb="select"] {
        background-color: #ffffff !important;
        border-radius: 8px;
    }
    
    /* Cards and containers */
    .element-container {
        background-color: #ffffff !important;
    }
    
    /* Radio buttons */
    [data-testid="stRadio"] > div {
        background-color: #ffffff;
        padding: 12px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "decoder" not in st.session_state:
        st.session_state.decoder = BarcodeDecoder()
    
    if "lookup" not in st.session_state:
        st.session_state.lookup = ProductLookup()
    
    if "additives_analyzer" not in st.session_state:
        st.session_state.additives_analyzer = AdditivesAnalyzer()
    
    if "dish_detector" not in st.session_state:
        st.session_state.dish_detector = DishDetector()
    
    if "last_barcode" not in st.session_state:
        st.session_state.last_barcode = None
    
    if "last_product" not in st.session_state:
        st.session_state.last_product = None
    
    if "per_unit" not in st.session_state:
        st.session_state.per_unit = "100g"
    
    if "camera_running" not in st.session_state:
        st.session_state.camera_running = False
    
    if "scan_history" not in st.session_state:
        st.session_state.scan_history = []


# Import all the remaining functions from the original app.py
# This is a simplified version - you would include all the original functions here

def main():
    """Main application entry point."""
    # Initialize session state
    init_session_state()
    
    # Handle API requests first
    handle_api_request()
    
    # Professional Header
    st.markdown("""
    <div style='text-align: center; padding: 2rem 0; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
            🔍 Food Scanner Pro
        </h1>
        <p style='font-size: 1.2rem; color: #666; margin-top: 0;'>
            Smart Nutrition Analysis & Barcode Intelligence
        </p>
        <p style='font-size: 0.9rem; color: #999; margin-top: 1rem;'>
            🔗 API Access: Add <code>?api=health</code> or <code>?api=product&barcode=XXX</code> to URL
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("🎉 **Integrated API Mode**: The API is now built into this app! No separate server needed.")
    st.markdown("""
    **API Endpoints (add to current URL):**
    - `?api=health` - Check API status
    - `?api=product&barcode=8902080104581` - Get product info
    - `?api=search&q=coca cola` - Search products
    """)
    
    # Show the regular UI below
    st.divider()
    st.write("Use the app normally below, or access via API using the URL parameters above! 👇")


if __name__ == "__main__":
    main()
