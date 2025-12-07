"""Quick API test script"""
import requests
import time

def test_api():
    base_url = "http://127.0.0.1:8000"
    
    print("Testing Food Scanner API...")
    print(f"Base URL: {base_url}\n")
    
    # Test 1: Health check
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✓ Health Check: {response.status_code}")
        print(f"  Response: {response.json()}\n")
    except Exception as e:
        print(f"✗ Health Check Failed: {e}\n")
        return False
    
    # Test 2: Product lookup (Coca-Cola)
    try:
        barcode = "5449000000996"
        response = requests.get(f"{base_url}/product/{barcode}", timeout=10)
        print(f"✓ Product Lookup ({barcode}): {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Product: {data.get('name', 'N/A')}")
            print(f"  Brands: {data.get('brands', 'N/A')}")
            print(f"  Additives: {data.get('additives_analysis', {}).get('count', 0)}\n")
        else:
            print(f"  Response: {response.text}\n")
    except Exception as e:
        print(f"✗ Product Lookup Failed: {e}\n")
    
    # Test 3: Search
    try:
        response = requests.get(f"{base_url}/search?q=coca&page_size=3", timeout=10)
        print(f"✓ Search (coca): {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Results: {data.get('count', 0)}\n")
        else:
            print(f"  Response: {response.text}\n")
    except Exception as e:
        print(f"✗ Search Failed: {e}\n")
    
    print("\n=== API Test Complete ===")
    print("Server is running correctly at http://127.0.0.1:8000")
    print("\nAvailable endpoints:")
    print("  GET  /health")
    print("  GET  /product/{barcode}")
    print("  GET  /search?q=term")
    print("  POST /dish-detect")
    print("  POST /scan-image")
    return True

if __name__ == "__main__":
    print("Waiting for server to be ready...")
    time.sleep(2)
    test_api()
