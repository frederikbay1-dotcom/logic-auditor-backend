import os
import requests

class DataConnectors:
    def __init__(self):
        # Credentials set in Vercel Environment Variables
        self.fred_key = os.getenv("FRED_API_KEY")
        self.eia_key = os.getenv("EIA_API_KEY")
        self.alpha_key = os.getenv("ALPHA_VANTAGE_KEY")

    def get_fred_data(self, series_id: str):
        if not self.fred_key: return None
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {"series_id": series_id, "api_key": self.fred_key, "file_type": "json", "sort_order": "desc", "limit": 1}
        try:
            res = requests.get(url, params=params, timeout=5)
            if res.status_code == 200:
                obs = res.json().get("observations", [])
                if obs: return {"value": obs[0]["value"], "date": obs[0]["date"], "source": "FRED"}
        except Exception: pass
        return None

    def get_eia_data(self, route: str, series: str):
        if not self.eia_key: return None
        url = f"https://api.eia.gov/v2/{route}/data/"
        params = {"api_key": self.eia_key, "frequency": "monthly", "data[0]": "value", "facets[series][]": series, "sort[0][column]": "period", "sort[0][direction]": "desc", "length": 1}
        try:
            res = requests.get(url, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()["response"]["data"][0]
                return {"value": data["value"], "date": data["period"], "source": "EIA"}
        except Exception: pass
        return None

    def get_market_data(self, symbol: str):
        """Fetch Market Index data from Alpha Vantage."""
        if not self.alpha_key: return None
        url = "https://www.alphavantage.co/query"
        params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": self.alpha_key}
        try:
            res = requests.get(url, params=params, timeout=5)
            data = res.json().get("Global Quote", {})
            if data and "05. price" in data:
                return {"value": data.get("05. price"), "date": data.get("07. latest trading day"), "source": f"Alpha Vantage ({symbol})"}
        except Exception: pass
        return None

    def get_climate_data(self):
        """Fetch Global Temperature Anomaly (NASA GISS)."""
        url = "https://global-warming.org/api/temperature-api"
        try:
            res = requests.get(url, timeout=5)
            latest = res.json().get("result", [])[-1]
            return {"value": f"+{latest['station']}°C", "date": latest['time'], "source": "NASA GISS"}
        except Exception: pass
        return None

    def get_world_bank_data(self, indicator: str):
        url = f"https://api.worldbank.org/v2/country/WLD/indicator/{indicator}"
        try:
            res = requests.get(url, params={"format": "json", "per_page": 1}, timeout=5)
            data = res.json()
            if len(data) > 1 and data[1]:
                latest = data[1][0]
                val = latest["value"]
                if val is not None and "ZG" in indicator: val = f"{round(val, 2)}%"
                return {"value": val, "date": latest["date"], "source": "World Bank"}
        except Exception: pass
        return None