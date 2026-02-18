import os
import requests

FRED_API_KEY = os.getenv("FRED_API_KEY")
BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

def fetch_fred_data(series_id: str, limit: int = 1):
    if not FRED_API_KEY:
        return {"error": "FRED API key missing"}

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit
    }
    
    response = requests.get(BASE_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        return data.get("observations", [])
    return {"error": f"Failed to fetch data: {response.status_code}"}