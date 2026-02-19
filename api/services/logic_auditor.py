import os
import json
import anthropic
import requests
import re
from bs4 import BeautifulSoup
from api.services.data_connectors import DataConnectors

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
connectors = DataConnectors()

SYSTEM_PROMPT = """
You are the "Logic Auditor." Deconstruct the provided text and return ONLY a valid JSON object.

CATEGORIES:
- 'ECON_INFLATION': US CPI
- 'ECON_UNEMPLOYMENT': US Jobs
- 'ENERGY_OIL': Crude prices
- 'GLOBAL_GDP': Growth %
- 'MARKET_INDEX': Stocks/Indices (e.g. S&P 500)
- 'CLIMATE_METRIC': Temp anomalies or CO2
- 'GLOBAL_STATS': Life expectancy or Population

STRICT JSON SCHEMA:
{
  "theses": ["string"],
  "logical_flaws": [{"flaw_type": "string", "lawyers_note": "string", "quote": "string", "severity": "High"}],
  "data_anchors": [
    {
      "claim": "string",
      "category": "CATEGORY_NAME",
      "official_value": "TBD",
      "variance": "N/A"
    }
  ],
  "feynman_summary": {
    "simple_explanation": "Explain core logical/data gap as if to a 10-year-old.",
    "medical_analogy": "Provide a medical analogy for this specific flaw."
  },
  "unresolved_conflicts": ["string"],
  "next_steps": ["string"]
}
"""

def extract_number(text: str):
    if not text: return None
    match = re.search(r"([-+]?\d*\.?\d+)", text.replace(',', ''))
    return float(match.group(1)) if match else None

def perform_audit(text: str, domain: str) -> dict:
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6", 
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Domain: {domain}\n\nText:\n{text}"}],
            temperature=0.1
        )
        audit_data = json.loads(re.search(r'\{.*\}', response.content[0].text, re.DOTALL).group(0))

        for anchor in audit_data.get("data_anchors", []):
            if not isinstance(anchor, dict): continue
            cat = anchor.get("category", "").upper()
            live_data = None
            
            if cat == "ENERGY_OIL": live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            elif cat == "ECON_INFLATION": live_data = connectors.get_fred_data("CPIAUCSL")
            elif cat == "ECON_UNEMPLOYMENT": live_data = connectors.get_fred_data("UNRATE")
            elif cat == "GLOBAL_GDP": live_data = connectors.get_world_bank_data("NY.GDP.MKTP.KD.ZG")
            elif cat == "MARKET_INDEX": live_data = connectors.get_market_data("SPY")
            elif cat == "CLIMATE_METRIC": live_data = connectors.get_climate_data()
            elif cat == "GLOBAL_STATS": live_data = connectors.get_world_bank_data("SP.DYN.LE00.IN")

            if live_data:
                val = live_data.get('value')
                if val is None:
                    anchor["official_value"] = "Data Pending (Reporting Lag)"
                    anchor["variance"] = "N/A"
                else:
                    off_val = str(val)
                    anchor["official_value"] = off_val
                    # ... rest of variance logic
                anchor["source"] = f"{live_data.get('source')} ({live_data.get('date')})"
                
                c_num, o_num = extract_number(anchor.get("claim")), extract_number(off_val)
                if c_num is not None and o_num is not None and o_num != 0:
                    diff = ((c_num - o_num) / o_num) * 100
                    anchor["variance"] = "Match" if abs(diff) < 0.1 else f"{'+' if diff > 0 else ''}{round(diff, 1)}%"

        audit_data["unresolved_conflicts"] = [str(c.get("conflict", c) if isinstance(c, dict) else c) for c in audit_data.get("unresolved_conflicts", [])]
        return audit_data
    except Exception as e:
        return {"error": f"Audit Logic Error: {str(e)}"}

def scrape_text_from_url(url: str) -> str:
    if not url.strip().startswith("http"): return url
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        return res.text if res.status_code == 200 else ""
    except Exception: return ""