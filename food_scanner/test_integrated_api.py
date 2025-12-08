"""Test the integrated API in Streamlit app"""

import requests

# Base URL
BASE_URL = "http://localhost:8502"

print("🧪 Testing Integrated Food Scanner API\n")
print("=" * 60)

# Test 1: Health Check
print("\n1️⃣ Testing Health Check...")
response = requests.get(f"{BASE_URL}/?api=health")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}\n")

# Test 2: Get Product Info
print("2️⃣ Testing Product Lookup (Maggi Noodles)...")
barcode = "8902080104581"
response = requests.get(f"{BASE_URL}/?api=product&barcode={barcode}")
print(f"Status Code: {response.status_code}")
data = response.json()
if data.get("status") == "success":
    print(f"✅ Product Found: {data['name']}")
    print(f"   Brand: {data['brand']}")
    print(f"   Nutriscore: {data['nutriscore']}")
    print(f"   NOVA Group: {data['nova_group']}")
else:
    print(f"❌ Error: {data.get('message')}\n")

# Test 3: Search Products
print("\n3️⃣ Testing Product Search (Coca Cola)...")
response = requests.get(f"{BASE_URL}/?api=search&q=coca+cola")
print(f"Status Code: {response.status_code}")
data = response.json()
if data.get("status") == "success":
    print(f"✅ Found {data['count']} products:")
    for idx, product in enumerate(data['results'][:3], 1):
        print(f"   {idx}. {product['name']} ({product['barcode']})")
else:
    print(f"❌ Error: {data.get('message')}")

print("\n" + "=" * 60)
print("✨ Integration complete! You can now:")
print("   • Use these URLs from any device/app")
print("   • Access from mobile apps")
print("   • Integrate with automation tools")
print("   • Share the UI at: http://localhost:8502")
print("=" * 60)
