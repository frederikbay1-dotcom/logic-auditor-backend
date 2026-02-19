import os
import json
import anthropic
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from api.services.data_connectors import DataConnectors

# Initialize tools
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
connectors = DataConnectors()

SYSTEM_PROMPT = """
You are the "Logic Auditor." Deconstruct the provided text and return ONLY a valid JSON object.

CATEGORIES for data_anchors:
- 'ECON_INFLATION': US CPI (Annual Rate)
- 'ECON_UNEMPLOYMENT': US Unemployment rate
- 'ENERGY_OIL': Crude oil spot prices
- 'GLOBAL_GDP': Global GDP growth percentage
- 'MARKET_INDEX': Stocks/Indices (e.g., SPY, QQQ)
- 'CLIMATE_METRIC': Global temperature or CO2
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
    """Cleanly extract the first number from a string, handling symbols."""
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
        
        raw_output = response.content[0].text
        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if not json_match:
            return {"error": "AI failed to produce valid JSON."}
            
        audit_data = json.loads(json_match.group(0))

        # SPECIALIST DATA ENRICHMENT — fetch live data in parallel
        anchors = [a for a in audit_data.get("data_anchors", []) if isinstance(a, dict)]

        def fetch_live_data(anchor):
            cat = anchor.get("category", "").upper()
            if cat == "ENERGY_OIL":
                return connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            elif cat == "ECON_INFLATION":
                return connectors.get_fred_data("CPIAUCSL", units="pc1")
            elif cat == "ECON_UNEMPLOYMENT":
                return connectors.get_fred_data("UNRATE")
            elif cat == "GLOBAL_GDP":
                return connectors.get_world_bank_data("NY.GDP.MKTP.KD.ZG")
            elif cat == "MARKET_INDEX":
                symbol = "SPY"
                if "nasdaq" in anchor.get("claim", "").lower() or "qqq" in anchor.get("claim", "").lower():
                    symbol = "QQQ"
                return connectors.get_market_data(symbol)
            elif cat == "CLIMATE_METRIC":
                return connectors.get_climate_data()
            elif cat == "GLOBAL_STATS":
                return connectors.get_world_bank_data("SP.DYN.LE00.IN")
            return None

        with ThreadPoolExecutor(max_workers=len(anchors) or 1) as pool:
            futures = {pool.submit(fetch_live_data, a): a for a in anchors}
            for future in as_completed(futures):
                anchor = futures[future]
                live_data = future.result()

                if live_data:
                    val = live_data.get('value')
                    # Safety: Handle reporting lags for demographic data
                    if val is None:
                        anchor["official_value"] = "Data Pending (Reporting Lag)"
                        anchor["variance"] = "N/A"
                    else:
                        off_val_str = str(val)
                        anchor["official_value"] = off_val_str
                        anchor["source"] = f"{live_data.get('source')} ({live_data.get('date')})"

                        # Calculate Variance Delta
                        c_num = extract_number(anchor.get("claim", ""))
                        o_num = extract_number(off_val_str)

                        if c_num is not None and o_num is not None and o_num != 0:
                            diff = ((c_num - o_num) / o_num) * 100
                            if abs(diff) < 0.1:
                                anchor["variance"] = "Match"
                            else:
                                prefix = "+" if diff > 0 else ""
                                anchor["variance"] = f"{prefix}{round(diff, 1)}%"

        # UI Sanitization
        conflicts = audit_data.get("unresolved_conflicts", [])
        audit_data["unresolved_conflicts"] = [str(c.get("conflict", c) if isinstance(c, dict) else c) for c in conflicts]

        return audit_data
        
    except Exception as e:
        return {"error": f"Audit Logic Error: {str(e)}"}

def scrape_text_from_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        return res.text if res.status_code == 200 else ""
    except Exception: return ""