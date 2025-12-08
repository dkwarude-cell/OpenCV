"""
Food Barcode Scanner - Streamlit Web Application

A web-based interface for scanning food barcodes and displaying
nutrition and additive information.

Usage:
    streamlit run src/app.py
"""

import io
import time
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image

# Import our modules
from barcode_decoder import BarcodeDecoder, BarcodeResult
from product_lookup import ProductLookup, format_product_json
from additives import AdditivesAnalyzer, ConcernLevel
from cache import ProductCache
from dish_detector import DishDetector
from utils import ProductInfo, format_nutrient_value, generate_html_report


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


def handle_api_request():
    """Handle API requests via URL query parameters."""
    try:
        query_params = st.query_params
        
        # Check if this is an API request
        if "api" in query_params:
            api_endpoint = query_params.get("api", "")
            
            # Initialize lookup if needed
            if "lookup" not in st.session_state:
                st.session_state.lookup = ProductLookup()
            
            if api_endpoint == "health":
                st.json({"status": "healthy", "version": "1.0.0", "message": "Food Scanner API is running"})
                st.stop()
                
            elif api_endpoint == "product":
                barcode = query_params.get("barcode", "")
                if barcode:
                    product = st.session_state.lookup.get_product(barcode)
                    if product and product.name != "Product Not Found":
                        result = {
                            "status": "success",
                            "barcode": barcode,
                            "name": product.name,
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
                        st.json({"status": "error", "message": "Product not found", "barcode": barcode})
                else:
                    st.json({"status": "error", "message": "Barcode parameter required. Use: ?api=product&barcode=XXX"})
                st.stop()
                
            elif api_endpoint == "search":
                query = query_params.get("q", "")
                if query:
                    results = st.session_state.lookup.search_products(query, page_size=10)
                    st.json({
                        "status": "success",
                        "query": query,
                        "count": len(results),
                        "results": [{"barcode": r.get("code"), "name": r.get("product_name"), "brand": r.get("brands")} for r in results]
                    })
                else:
                    st.json({"status": "error", "message": "Query parameter 'q' required. Use: ?api=search&q=product+name"})
                st.stop()
            
            else:
                st.json({
                    "status": "error",
                    "message": "Unknown API endpoint",
                    "available_endpoints": {
                        "health": "?api=health",
                        "product": "?api=product&barcode=XXX",
                        "search": "?api=search&q=product+name"
                    }
                })
                st.stop()
    except Exception as e:
        st.json({"status": "error", "message": str(e)})
        st.stop()


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


def render_sidebar():
    """Render the sidebar with settings and history."""
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # Unit toggle
        st.session_state.per_unit = st.radio(
            "Display nutrients per:",
            options=["100g", "100ml", "Serving"],
            index=["100g", "100ml", "Serving"].index(st.session_state.per_unit),
            horizontal=True
        )
        
        st.divider()
        
        # Offline mode toggle
        offline = st.checkbox(
            "Offline Mode",
            value=False,
            help="Use only cached data, no API calls"
        )
        if offline != st.session_state.lookup.offline_mode:
            st.session_state.lookup.offline_mode = offline
        
        st.divider()
        
        # Scan history
        st.subheader("📜 Recent Scans")
        if st.session_state.scan_history:
            for idx, item in enumerate(reversed(st.session_state.scan_history[-5:])):
                if st.button(f"{item['name'][:25]}...", key=f"hist_{idx}_{item['barcode']}"):
                    lookup_barcode(item['barcode'])
        else:
            st.caption("No recent scans")
        
        st.divider()
        
        # Cache stats
        st.subheader("💾 Cache")
        cache = st.session_state.lookup.cache
        stats = cache.get_stats()
        st.metric("Cached Products", stats["valid_entries"])
        
        if st.button("Clear Cache"):
            cache.clear_all()
            st.success("Cache cleared!")


def lookup_barcode(barcode: str):
    """Look up a barcode and update session state."""
    with st.spinner("Looking up product..."):
        product = st.session_state.lookup.get_product(barcode)
        st.session_state.last_barcode = barcode
        st.session_state.last_product = product
        
        # Add to history
        if product.name != "Product Not Found":
            st.session_state.scan_history.append({
                "barcode": barcode,
                "name": product.name,
                "time": time.time()
            })


def render_barcode_input():
    """Render barcode input methods."""
    st.header("🔍 Scan or Enter Barcode")
    
    tab1, tab2, tab3 = st.tabs(["📷 Camera", "📁 Upload Image", "⌨️ Manual Entry"])
    
    with tab1:
        render_camera_tab()
    
    with tab2:
        render_upload_tab()
    
    with tab3:
        render_manual_tab()


def render_camera_tab():
    """Render camera scanning tab."""
    st.info("📷 Click 'Capture' to take a photo and scan for barcodes.")
    
    # Camera input
    camera_image = st.camera_input("Take a picture of the barcode")
    
    if camera_image is not None:
        # Process the captured image
        image = Image.open(camera_image)
        image_np = np.array(image)
        
        # Convert RGB to BGR for OpenCV
        if len(image_np.shape) == 3:
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
        
        # Decode barcode
        results = st.session_state.decoder.decode_image(image_np)
        
        if results:
            barcode = results[0].data
            st.success(f"✅ Barcode detected: **{barcode}**")
            lookup_barcode(barcode)
        else:
            st.warning("⚠️ No barcode detected. Try adjusting the angle or lighting.")


def render_upload_tab():
    """Render image upload tab."""
    uploaded_file = st.file_uploader(
        "Upload an image with a barcode",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        help="Upload a clear image of the product barcode (at least 200x100 pixels recommended)"
    )
    
    if uploaded_file is not None:
        # Load and display image
        image = Image.open(uploaded_file)
        
        # Convert to RGB if needed (handles RGBA, P mode, etc.)
        if image.mode == 'RGBA':
            # Create white background for transparent images
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.image(image, caption="Uploaded Image", use_container_width=True)
            # Show image info
            st.caption(f"Size: {image.size[0]}x{image.size[1]}px")
        
        with col2:
            # Convert to numpy array
            image_np = np.array(image)
            
            # Show diagnostic info
            st.caption(f"Processing image: {image_np.shape}")
            
            # Convert RGB to BGR for OpenCV
            if len(image_np.shape) == 3:
                image_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
            else:
                image_bgr = image_np
            
            # Decode barcode
            with st.spinner("Scanning for barcodes..."):
                results = st.session_state.decoder.decode_image(image_bgr)
            
            if results:
                for result in results:
                    st.success(f"✅ Found: **{result.data}** ({result.type.value})")
                
                # Look up the first barcode
                lookup_barcode(results[0].data)
            else:
                st.warning("⚠️ No barcode detected.")
                
                # Show tips
                st.info("""
                **Tips for better detection:**
                - Use a larger, clearer image (at least 300px wide)
                - Ensure good contrast between bars and background
                - Avoid blurry or distorted images
                - Try the **Manual Entry** tab to type the barcode number directly
                """)
                
                # Show preprocessing options
                with st.expander("🔧 Advanced Options"):
                    if st.button("Try with enhanced preprocessing"):
                        # Apply more aggressive preprocessing
                        if len(image_bgr.shape) == 3:
                            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
                        else:
                            gray = image_bgr
                        
                        # Upscale if small
                        h, w = gray.shape[:2]
                        if w < 400:
                            scale = 400 / w
                            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                            st.caption(f"Upscaled to: {gray.shape[1]}x{gray.shape[0]}px")
                        
                        enhanced = cv2.equalizeHist(gray)
                        results = st.session_state.decoder.decode_image(enhanced)
                        
                        if results:
                            st.success(f"✅ Found with preprocessing: **{results[0].data}**")
                            lookup_barcode(results[0].data)
                        else:
                            st.error("Still no barcode detected. Try using Manual Entry.")


def render_manual_tab():
    """Render manual barcode entry tab."""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        barcode = st.text_input(
            "Enter barcode number:",
            placeholder="e.g., 5449000000996",
            help="Enter the barcode number printed on the product"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        search_btn = st.button("🔍 Look Up", type="primary", use_container_width=True)
    
    if search_btn and barcode:
        lookup_barcode(barcode)
    
    # Product name search
    st.divider()
    st.subheader("Search by Product Name")
    
    search_query = st.text_input(
        "Search for a product:",
        placeholder="e.g., Coca-Cola, Nutella, etc."
    )
    
    if search_query:
        with st.spinner("Searching..."):
            results = st.session_state.lookup.search_products(search_query, page_size=5)
        
        if results:
            st.write(f"Found {len(results)} results:")
            for product in results:
                col1, col2 = st.columns([4, 1])
                with col1:
                    name = product.get("product_name", "Unknown")
                    brand = product.get("brands", "")
                    display = f"**{name}**" + (f" - {brand}" if brand else "")
                    st.markdown(display)
                with col2:
                    if st.button("Select", key=f"select_{product.get('code')}"):
                        lookup_barcode(product.get("code"))
        else:
            st.info("No products found. Try a different search term.")


def render_product_info():
    """Render product information display."""
    product = st.session_state.last_product
    
    if product is None:
        st.info("👆 Scan or enter a barcode to see product information")
        return
    
    st.header("📦 Product Information")
    
    # Product header
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if product.image_url:
            st.image(product.image_url, width=150)
        else:
            st.image("https://via.placeholder.com/150?text=No+Image", width=150)
    
    with col2:
        st.subheader(product.name)
        if product.brand:
            st.markdown(f"**Brand:** {product.brand}")
        st.markdown(f"**Barcode:** `{product.barcode}`")
        if product.quantity:
            st.markdown(f"**Quantity:** {product.quantity}")
        
        # Processing level badge
        if product.processing_level:
            level_class = "minimal"
            if "Ultra" in product.processing_level:
                level_class = "ultra"
            elif "Highly" in product.processing_level:
                level_class = "high"
            elif "Processed" in product.processing_level:
                level_class = "moderate"
            
            st.markdown(
                f'<span class="processing-badge processing-{level_class}">'
                f'🏭 {product.processing_level}</span>',
                unsafe_allow_html=True
            )
    
    st.divider()
    
    # Health Rating Section
    render_health_rating(product)
    
    # Not rated message - but still show tabs
    if not product.is_rated:
        st.warning(f"⚠️ {product.status_message}")
    
    st.divider()
    
    # Tabs for different info sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Nutrients",
        "🧪 Additives",
        "📝 Ingredients",
        "🍽 Dish Insight",
        "📄 Raw Data"
    ])
    
    with tab1:
        render_nutrients_tab(product)
    
    with tab2:
        render_additives_tab(product)
    
    with tab3:
        render_ingredients_tab(product)
    
    with tab4:
        render_dish_insight_tab(product)
    
    with tab5:
        render_raw_data_tab(product)


def render_health_rating(product: ProductInfo):
    """Render health rating section with Nutri-Score, NOVA, and overall rating."""
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Nutri-Score
    with col1:
        st.markdown("**Nutri-Score**")
        if product.nutriscore_grade:
            grade = product.nutriscore_grade.upper()
            colors = {'A': '#038141', 'B': '#85BB2F', 'C': '#FECB02', 'D': '#EE8100', 'E': '#E63E11'}
            color = colors.get(grade, '#9e9e9e')
            st.markdown(
                f'<div style="background-color:{color}; color:white; padding:15px; '
                f'border-radius:10px; text-align:center; font-size:28px; font-weight:bold;">'
                f'{grade}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div style="background-color:#9e9e9e; color:white; padding:15px; '
                'border-radius:10px; text-align:center; font-size:18px;">N/A</div>',
                unsafe_allow_html=True
            )
    
    # NOVA Group
    with col2:
        st.markdown("**NOVA Group**")
        if product.nova_group:
            nova_colors = {1: '#038141', 2: '#85BB2F', 3: '#FECB02', 4: '#E63E11'}
            nova_labels = {1: 'Unprocessed', 2: 'Processed ingredients', 3: 'Processed', 4: 'Ultra-processed'}
            color = nova_colors.get(product.nova_group, '#9e9e9e')
            st.markdown(
                f'<div style="background-color:{color}; color:white; padding:15px; '
                f'border-radius:10px; text-align:center; font-size:28px; font-weight:bold;">'
                f'{product.nova_group}</div>',
                unsafe_allow_html=True
            )
            st.caption(nova_labels.get(product.nova_group, ''))
        else:
            st.markdown(
                '<div style="background-color:#9e9e9e; color:white; padding:15px; '
                'border-radius:10px; text-align:center; font-size:18px;">N/A</div>',
                unsafe_allow_html=True
            )
    
    # Additives Count
    with col3:
        st.markdown("**Additives**")
        count = len(product.additives_tags) if product.additives_tags else 0
        if count == 0:
            color = '#038141'
            emoji = '✓'
        elif count <= 3:
            color = '#FECB02'
            emoji = '⚠'
        else:
            color = '#E63E11'
            emoji = '⚠'
        st.markdown(
            f'<div style="background-color:{color}; color:white; padding:15px; '
            f'border-radius:10px; text-align:center; font-size:28px; font-weight:bold;">'
            f'{emoji} {count}</div>',
            unsafe_allow_html=True
        )
    
    # Overall Health Rating
    with col4:
        st.markdown("**Health Rating**")
        score, label, color, factors = product.get_health_rating()
        st.markdown(
            f'<div style="background-color:{color}; color:white; padding:15px; '
            f'border-radius:10px; text-align:center;">'
            f'<div style="font-size:28px; font-weight:bold;">{score}</div>'
            f'<div style="font-size:12px;">{label}</div></div>',
            unsafe_allow_html=True
        )
        if factors:
            st.caption(f"Based on: {', '.join(factors)}")


def render_fatty_acid_profile(nutrients: dict):
    """Render fatty acid profile with percentages (SFA, MUFA, PUFA, Omega-3, Omega-6)."""
    
    # Get fat values
    total_fat = nutrients.get("fat")
    saturated = nutrients.get("saturated_fat")
    monounsaturated = nutrients.get("monounsaturated_fat")
    polyunsaturated = nutrients.get("polyunsaturated_fat")
    omega3 = nutrients.get("omega3")
    omega6 = nutrients.get("omega6")
    trans = nutrients.get("trans_fat")
    
    # Check if we have enough data for fatty acid profile
    has_fatty_acids = any([saturated, monounsaturated, polyunsaturated, omega3, omega6])
    
    if not has_fatty_acids or not total_fat:
        return
    
    st.markdown("#### 🧈 Fatty Acid Profile")
    
    total_fat_value = total_fat.value if total_fat else 0
    
    if total_fat_value <= 0:
        st.caption("No fat content data available")
        return
    
    # Calculate percentages
    fatty_acids = []
    
    if saturated:
        sfa_pct = (saturated.value / total_fat_value) * 100
        fatty_acids.append(("SFA (Saturated)", saturated.value, sfa_pct, "#E63E11"))
    
    if monounsaturated:
        mufa_pct = (monounsaturated.value / total_fat_value) * 100
        fatty_acids.append(("MUFA (Monounsaturated)", monounsaturated.value, mufa_pct, "#85BB2F"))
    
    if polyunsaturated:
        pufa_pct = (polyunsaturated.value / total_fat_value) * 100
        fatty_acids.append(("PUFA (Polyunsaturated)", polyunsaturated.value, pufa_pct, "#038141"))
    
    if omega3:
        omega3_pct = (omega3.value / total_fat_value) * 100
        fatty_acids.append(("Omega-3", omega3.value, omega3_pct, "#2196F3"))
    
    if omega6:
        omega6_pct = (omega6.value / total_fat_value) * 100
        fatty_acids.append(("Omega-6", omega6.value, omega6_pct, "#9C27B0"))
    
    if trans:
        trans_pct = (trans.value / total_fat_value) * 100
        fatty_acids.append(("Trans Fat", trans.value, trans_pct, "#424242"))
    
    if not fatty_acids:
        return
    
    # Display as columns
    cols = st.columns(len(fatty_acids))
    
    for i, (name, value, pct, color) in enumerate(fatty_acids):
        with cols[i]:
            st.markdown(
                f'<div style="text-align:center; padding:10px; background:#1e1e1e; border-radius:8px; border-left:4px solid {color};">'
                f'<div style="font-size:11px; color:#888;">{name}</div>'
                f'<div style="font-size:20px; font-weight:bold; color:{color};">{pct:.1f}%</div>'
                f'<div style="font-size:12px; color:#ccc;">{value:.2f}g</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    
    # Display Omega-6:Omega-3 ratio if both available
    if omega3 and omega6 and omega3.value > 0:
        ratio = omega6.value / omega3.value
        st.caption(f"**Omega-6:Omega-3 Ratio:** {ratio:.1f}:1 " + 
                   ("✅ Good (<4:1)" if ratio < 4 else "⚠️ High (aim for <4:1)"))
    
    # Fat quality assessment
    if saturated and total_fat_value > 0:
        sfa_ratio = saturated.value / total_fat_value
        if sfa_ratio < 0.3:
            st.success("✅ Low saturated fat content - heart healthy choice!")
        elif sfa_ratio > 0.5:
            st.warning("⚠️ High saturated fat content - consume in moderation")


def render_nutrients_tab(product: ProductInfo):
    """Render the nutrients tab."""
    # Unit selector
    unit = st.session_state.per_unit.lower()
    
    if unit == "serving":
        nutrients = product.nutrients_per_serving
        if not nutrients:
            st.info("Per-serving data not available. Showing per 100g.")
            nutrients = product.nutrients_per_100
            unit = "100ml" if product.is_liquid else "100g"
    else:
        nutrients = product.nutrients_per_100
        if product.is_liquid and unit == "100g":
            unit = "100ml"
    
    if not nutrients:
        st.warning("No nutrition data available for this product.")
        return
    
    st.subheader(f"Nutrition Facts (per {unit})")
    
    # Fatty Acid Profile Section
    render_fatty_acid_profile(nutrients)
    
    st.divider()
    
    # Create nutrient table
    table_html = """
    <table class="nutrient-table">
        <tr>
            <th>Nutrient</th>
            <th>Value</th>
            <th>% Daily Value</th>
        </tr>
    """
    
    # Define display order (main nutrients)
    display_order = [
        "energy_kcal", "fat", "saturated_fat", "monounsaturated_fat", 
        "polyunsaturated_fat", "omega3", "omega6", "trans_fat", "cholesterol",
        "carbohydrates", "sugars", "sugars_added", "fiber",
        "proteins", "sodium", "salt",
        "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_e",
        "calcium", "iron", "potassium"
    ]
    
    for key in display_order:
        if key in nutrients:
            nutrient = nutrients[key]
            value_str = format_nutrient_value(nutrient.value, nutrient.unit)
            rda_str = f"{nutrient.rda_percent}%" if nutrient.rda_percent else "—"
            
            # Highlight high sodium
            row_style = ""
            if key == "sodium" and nutrient.value > 500:
                row_style = "background-color: #ffebee;"
            
            table_html += f"""
            <tr style="{row_style}">
                <td>{nutrient.name}</td>
                <td>{value_str}</td>
                <td>{rda_str}</td>
            </tr>
            """
    
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)
    
    # Serving size note
    if product.serving_size:
        st.caption(f"Serving size: {product.serving_size}")


def render_additives_tab(product: ProductInfo):
    """Render the additives tab."""
    analyzer = st.session_state.additives_analyzer
    
    # Analyze additives
    additives = analyzer.analyze(
        product.additives_tags,
        product.ingredients_text
    )
    
    if not additives:
        st.success("✅ No additives detected in this product.")
        return
    
    st.subheader(f"Additives Found ({len(additives)})")
    
    # Summary
    summary = analyzer.get_summary(additives)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔴 High Concern", len(summary["high_concern"]))
    with col2:
        st.metric("🟠 Moderate", len(summary["moderate_concern"]))
    with col3:
        st.metric("🟢 Minimal", len(summary["minimal_concern"]))
    with col4:
        st.metric("⚪ Unknown", len(summary["low_value"]))
    
    st.divider()
    
    # Display additives
    for additive in additives:
        badge_class = {
            ConcernLevel.HIGH: "badge-high",
            ConcernLevel.MODERATE: "badge-moderate",
            ConcernLevel.MINIMAL: "badge-minimal",
            ConcernLevel.LOW_VALUE: "badge-low",
        }.get(additive.concern, "badge-low")
        
        concern_emoji = {
            ConcernLevel.HIGH: "🔴",
            ConcernLevel.MODERATE: "🟠",
            ConcernLevel.MINIMAL: "🟢",
            ConcernLevel.LOW_VALUE: "⚪",
        }.get(additive.concern, "⚪")
        
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**{additive.code}**: {additive.name}")
                if additive.category:
                    st.caption(f"Category: {additive.category}")
            
            with col2:
                st.markdown(
                    f'<span class="badge {badge_class}">'
                    f'{concern_emoji} {additive.concern.value}</span>',
                    unsafe_allow_html=True
                )
            
            if additive.description:
                with st.expander("More info"):
                    st.write(additive.description)
        
        st.divider()


def render_ingredients_tab(product: ProductInfo):
    """Render the ingredients tab."""
    st.subheader("Ingredients")
    
    if not product.ingredients_text:
        st.info("No ingredients information available.")
        return
    
    # Display ingredients
    st.markdown(product.ingredients_text)
    
    st.divider()
    
    # Analyze ingredients for oils and fats
    render_oil_fat_analysis(product.ingredients_text)
    
    st.divider()
    
    # Highlight allergens if present
    allergens = [
        "milk", "wheat", "soy", "peanut", "tree nut", "egg",
        "fish", "shellfish", "sesame", "gluten"
    ]
    
    ingredients_lower = product.ingredients_text.lower()
    found_allergens = [a for a in allergens if a in ingredients_lower]
    
    if found_allergens:
        st.warning(f"⚠️ Potential allergens: {', '.join(found_allergens)}")


def render_oil_fat_analysis(ingredients_text: str):
    """Analyze ingredients for oils and fats with fatty acid profiles."""
    
    # Oil/fat database with typical fatty acid profiles
    oil_profiles = {
        "palm oil": {"SFA": 49, "MUFA": 37, "PUFA": 9, "omega6": 9, "omega3": 0.2, "concern": "high"},
        "palm": {"SFA": 49, "MUFA": 37, "PUFA": 9, "omega6": 9, "omega3": 0.2, "concern": "high"},
        "coconut oil": {"SFA": 82, "MUFA": 6, "PUFA": 2, "omega6": 1.8, "omega3": 0, "concern": "high"},
        "coconut": {"SFA": 82, "MUFA": 6, "PUFA": 2, "omega6": 1.8, "omega3": 0, "concern": "high"},
        "olive oil": {"SFA": 14, "MUFA": 73, "PUFA": 11, "omega6": 9.7, "omega3": 0.8, "concern": "low"},
        "extra virgin olive": {"SFA": 14, "MUFA": 73, "PUFA": 11, "omega6": 9.7, "omega3": 0.8, "concern": "low"},
        "sunflower oil": {"SFA": 10, "MUFA": 20, "PUFA": 66, "omega6": 65, "omega3": 0.5, "concern": "moderate"},
        "sunflower": {"SFA": 10, "MUFA": 20, "PUFA": 66, "omega6": 65, "omega3": 0.5, "concern": "moderate"},
        "canola oil": {"SFA": 7, "MUFA": 63, "PUFA": 28, "omega6": 19, "omega3": 9, "concern": "low"},
        "rapeseed oil": {"SFA": 7, "MUFA": 63, "PUFA": 28, "omega6": 19, "omega3": 9, "concern": "low"},
        "rapeseed": {"SFA": 7, "MUFA": 63, "PUFA": 28, "omega6": 19, "omega3": 9, "concern": "low"},
        "soybean oil": {"SFA": 16, "MUFA": 23, "PUFA": 58, "omega6": 51, "omega3": 7, "concern": "moderate"},
        "soy oil": {"SFA": 16, "MUFA": 23, "PUFA": 58, "omega6": 51, "omega3": 7, "concern": "moderate"},
        "corn oil": {"SFA": 13, "MUFA": 28, "PUFA": 55, "omega6": 54, "omega3": 1, "concern": "moderate"},
        "peanut oil": {"SFA": 17, "MUFA": 46, "PUFA": 32, "omega6": 32, "omega3": 0, "concern": "moderate"},
        "groundnut oil": {"SFA": 17, "MUFA": 46, "PUFA": 32, "omega6": 32, "omega3": 0, "concern": "moderate"},
        "sesame oil": {"SFA": 14, "MUFA": 40, "PUFA": 42, "omega6": 41, "omega3": 0.3, "concern": "moderate"},
        "flaxseed oil": {"SFA": 9, "MUFA": 18, "PUFA": 68, "omega6": 13, "omega3": 53, "concern": "low"},
        "linseed oil": {"SFA": 9, "MUFA": 18, "PUFA": 68, "omega6": 13, "omega3": 53, "concern": "low"},
        "fish oil": {"SFA": 20, "MUFA": 30, "PUFA": 40, "omega6": 2, "omega3": 35, "concern": "low"},
        "butter": {"SFA": 63, "MUFA": 26, "PUFA": 4, "omega6": 2.7, "omega3": 0.3, "concern": "high"},
        "ghee": {"SFA": 62, "MUFA": 29, "PUFA": 4, "omega6": 2.5, "omega3": 0.5, "concern": "high"},
        "lard": {"SFA": 39, "MUFA": 45, "PUFA": 11, "omega6": 10, "omega3": 1, "concern": "high"},
        "vegetable oil": {"SFA": 15, "MUFA": 30, "PUFA": 50, "omega6": 45, "omega3": 5, "concern": "moderate"},
        "hydrogenated": {"SFA": 25, "MUFA": 50, "PUFA": 20, "omega6": 18, "omega3": 2, "concern": "high", "trans": True},
        "partially hydrogenated": {"SFA": 25, "MUFA": 45, "PUFA": 25, "omega6": 22, "omega3": 3, "concern": "high", "trans": True},
        "margarine": {"SFA": 20, "MUFA": 40, "PUFA": 35, "omega6": 30, "omega3": 5, "concern": "moderate"},
        "shortening": {"SFA": 25, "MUFA": 45, "PUFA": 25, "omega6": 22, "omega3": 3, "concern": "high"},
        "avocado oil": {"SFA": 12, "MUFA": 70, "PUFA": 13, "omega6": 12, "omega3": 1, "concern": "low"},
        "rice bran oil": {"SFA": 20, "MUFA": 39, "PUFA": 35, "omega6": 34, "omega3": 1.6, "concern": "moderate"},
        "cottonseed oil": {"SFA": 26, "MUFA": 18, "PUFA": 52, "omega6": 52, "omega3": 0.2, "concern": "moderate"},
        "walnut oil": {"SFA": 9, "MUFA": 23, "PUFA": 63, "omega6": 53, "omega3": 10, "concern": "low"},
    }
    
    ingredients_lower = ingredients_text.lower()
    found_oils = []
    
    for oil_name, profile in oil_profiles.items():
        if oil_name in ingredients_lower:
            found_oils.append((oil_name, profile))
    
    if not found_oils:
        st.caption("No specific oils/fats identified in ingredients.")
        return
    
    st.markdown("#### 🛢️ Oils & Fats Analysis")
    
    for oil_name, profile in found_oils:
        concern = profile.get("concern", "moderate")
        concern_colors = {"low": "#038141", "moderate": "#FECB02", "high": "#E63E11"}
        concern_labels = {"low": "✅ Heart Healthy", "moderate": "⚠️ Use Moderately", "high": "🔴 Limit Intake"}
        color = concern_colors.get(concern, "#FECB02")
        
        with st.container():
            st.markdown(
                f'<div style="background:#1e1e1e; padding:15px; border-radius:8px; margin-bottom:10px; border-left:4px solid {color};">'
                f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                f'<span style="font-weight:bold; font-size:16px; text-transform:capitalize;">{oil_name}</span>'
                f'<span style="background:{color}; color:white; padding:3px 8px; border-radius:4px; font-size:12px;">'
                f'{concern_labels.get(concern, "")}</span>'
                f'</div>'
                f'<div style="display:flex; gap:20px; margin-top:10px; font-size:13px;">'
                f'<span><b>SFA:</b> {profile["SFA"]}%</span>'
                f'<span><b>MUFA:</b> {profile["MUFA"]}%</span>'
                f'<span><b>PUFA:</b> {profile["PUFA"]}%</span>'
                f'<span><b>Ω-6:</b> {profile["omega6"]}%</span>'
                f'<span><b>Ω-3:</b> {profile["omega3"]}%</span>'
                f'</div>'
                + (f'<div style="color:#E63E11; margin-top:5px; font-size:12px;">⚠️ May contain trans fats</div>' if profile.get("trans") else '')
                + f'</div>',
                unsafe_allow_html=True
            )


def render_dish_insight_tab(product: ProductInfo):
    """Render dish detection insights based on ingredients and categories."""
    detector = st.session_state.get("dish_detector")
    if detector is None:
        st.info("Dish detector is not initialized yet.")
        return

    result = detector.detect(product)
    render_dish_detection_result(
        result,
        empty_message="No confident dish match yet. Include detailed ingredients for better results."
    )


def render_dish_detection_result(result, empty_message: str):
    """Shared renderer for dish detection results across the app."""
    if not result:
        st.info(empty_message)
        st.caption("Matches are derived from the curated dataset in `data/dish_profiles.json`.")
        return

    confidence_pct = int(result.confidence * 100)

    st.markdown(f"### 🍽 {result.profile.name}")
    st.caption(f"{result.profile.cuisine} • Confidence {confidence_pct}%")

    if result.profile.description:
        st.write(result.profile.description)

    col1, col2 = st.columns(2)
    with col1:
        if result.profile.hero_ingredients:
            heroes = ", ".join(ing.title() for ing in result.profile.hero_ingredients)
            st.markdown(f"**Signature ingredients:** {heroes}")
        if result.matched_keywords:
            matched = ", ".join(sorted({kw.title() for kw in result.matched_keywords}))
            st.caption(f"Matched terms: {matched}")
    with col2:
        if result.profile.serving_style:
            st.markdown(f"**Serving style:** {result.profile.serving_style}")
        if result.profile.recipe_url:
            st.markdown(f"[View reference recipe]({result.profile.recipe_url})")

    if result.matched_categories:
        categories = ", ".join(sorted({cat.title() for cat in result.matched_categories}))
        st.caption(f"Category context: {categories}")

    st.caption("Insights powered by the curated recipe dataset in `data/dish_profiles.json`.")


def render_raw_data_tab(product: ProductInfo):
    """Render raw data tab for debugging."""
    st.subheader("Raw Data (JSON)")
    
    st.json(product.to_dict())
    
    # Download buttons
    col1, col2 = st.columns(2)
    
    with col1:
        json_data = format_product_json(product)
        st.download_button(
            "📥 Download JSON",
            json_data,
            f"product_{product.barcode}.json",
            "application/json"
        )
    
    with col2:
        html_data = generate_html_report(product)
        st.download_button(
            "📥 Download HTML Report",
            html_data,
            f"product_{product.barcode}.html",
            "text/html"
        )


def render_footer():
    """Render the footer with attribution."""
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption("Data source: [OpenFoodFacts](https://world.openfoodfacts.org/)")
    
    with col2:
        # Feedback buttons
        if st.session_state.last_product:
            st.caption("Was this helpful?")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("👍"):
                    st.toast("Thanks for the feedback!")
            with col_b:
                if st.button("👎"):
                    st.toast("We'll try to improve!")
    
    with col3:
        st.empty()


def main():
    """Main application entry point."""
    # Handle API requests first (before any UI rendering)
    handle_api_request()
    
    # Initialize session state
    init_session_state()
    
    # Professional Header
    st.markdown("""
    <div style='text-align: center; padding: 2rem 0; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
            🔍 Food Scanner Pro
        </h1>
        <p style='font-size: 1.2rem; color: #666; margin-top: 0;'>
            Smart Nutrition Analysis & Barcode Intelligence
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # API Info Box
    with st.expander("🔗 API Integration - Click to expand"):
        st.markdown("""
        ### REST API Built-In!
        
        This app now includes API endpoints accessible via URL parameters. Perfect for integrating with other apps, mobile devices, or automation tools.
        
        **Available Endpoints:**
        
        1. **Health Check**
           ```
           http://localhost:8502/?api=health
           ```
        
        2. **Get Product Info**
           ```
           http://localhost:8502/?api=product&barcode=8902080104581
           ```
        
        3. **Search Products**
           ```
           http://localhost:8502/?api=search&q=coca+cola
           ```
        
        **Usage Examples:**
        
        **Python:**
        ```python
        import requests
        
        # Get product
        response = requests.get('http://localhost:8502/?api=product&barcode=8902080104581')
        data = response.json()
        print(data['name'])
        ```
        
        **JavaScript:**
        ```javascript
        fetch('http://localhost:8502/?api=search&q=nutella')
            .then(r => r.json())
            .then(data => console.log(data.results));
        ```
        
        **cURL:**
        ```bash
        curl "http://localhost:8502/?api=product&barcode=8902080104581"
        ```
        
        **Mobile Apps:** Use the same URLs in Android/iOS HTTP clients!
        """)
    
    # Render sidebar
    render_sidebar()
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_barcode_input()
    
    with col2:
        render_product_info()

    
    # Footer
    render_footer()


if __name__ == "__main__":
    main()
