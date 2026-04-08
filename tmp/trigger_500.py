import requests
import json

def trigger():
    print("🚀 Triggering Backend 500 Error for Debugging...")
    url = "http://localhost:8000/api/v1/generate"
    payload = {
        "plot_size_sqft": 1200,
        "floors": 1,
        "rooms": [{"type": "Bedroom", "count": 3}, {"type": "Living", "count": 1}],
        "building_type": "independent_house",
        "floor_number": 1,
        "entry_direction": "E",
        "prompt": "Generate 30x40 east facing 3BHK plan G+3 high-fidelity v6"
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        print(f"📡 Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ Error Detail: {response.text}")
        else:
            print("✅ Generation SUCCESS (Unexpectedly!)")
    except Exception as e:
        print(f"💥 Failed to reach backend: {e}")

if __name__ == "__main__":
    trigger()
