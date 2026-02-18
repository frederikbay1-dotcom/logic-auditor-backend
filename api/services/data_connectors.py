import os
import requests

class DataConnectors:
    def __init__(self):
        # These are your 'Labs' credentials
        self.fred_key = os.getenv("FRED_API_KEY")
        self.eia_key = os.getenv("EIA_API_KEY")

    def get_fred_data(self, series_id: str):
        """Fetch latest US Econ data from FRED."""
        if not self.fred_key:
            return None
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.fred_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1
        }
        try:
            res = requests.get(url, params=params, timeout=5)
            if res.status_code == 200:
                obs = res.json().get("observations", [])
                if obs:
                    return {"value": obs[0]["value"], "date": obs[0]["date"], "source": "FRED"}
        except Exception:
            pass
        return None

    def get_eia_data(self, route: str, series: str):
        """Fetch Energy data from EIA."""
        if not self.eia_key:
            return None
        url = f"https://api.eia.gov/v2/{route}/data/"
        params = {
            "api_key": self.eia_key,
            "frequency": "monthly",
            "data[0]": "value",
            "facets[series][]": series,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 1
        }
        try:
            res = requests.get(url, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()["response"]["data"][0]
                return {"value": data["value"], "date": data["period"], "source": "EIA"}
        except Exception:
            pass
        return None

    def get_world_bank_data(self, indicator: str):
        """Fetch Global metrics from World Bank."""
        url = f"https://api.worldbank.org/v2/country/WLD/indicator/{indicator}"
        try:
            res = requests.get(url, params={"format": "json", "per_page": 1}, timeout=5)
            data = res.json()
            if len(data) > 1 and data[1]:
                latest = data[1][0]
                return {"value": latest["value"], "date": latest["date"], "source": "World Bank"}
        except Exception:
            pass
        return None