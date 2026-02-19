import os
import json
import anthropic
import requests
import re
from api.services.data_connectors import DataConnectors

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
  "executive_abstract": {
    "headline": "A concise, authoritative headline summarizing the primary audit finding.",
    "key_findings": ["3-5 clear, simplified bullet points deconstructing the core logical and data gaps."]
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
            model="claude-3-5-sonnet-20240620", 
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Domain: {domain}\n\nText:\n{text}"}],
            temperature=0.1
        )
        
        raw_output = response.content[0].text
        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if not json_match: return {"error": "AI failed to produce valid JSON."}
        audit_data = json.loads(json_match.group(0))

        # Specialist Data Enrichment
        for anchor in audit_data.get("data_anchors", []):
            if not isinstance(anchor, dict): continue
            cat = anchor.get("category", "").upper()
            live_data = None
            
            if cat == "ENERGY_OIL": live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            elif cat == "ECON_INFLATION": live_data = connectors.get_fred_data("CPIAUCSL", units="pc1")
            elif cat == "ECON_UNEMPLOYMENT": live_data = connectors.get_fred_data("UNRATE")
            elif cat == "GLOBAL_GDP": live_data = connectors.get_world_bank_data("NY.GDP.MKTP.KD.ZG")
            elif cat == "MARKET_INDEX": 
                symbol = "SPY"
                if "nasdaq" in anchor.get("claim", "").lower(): symbol = "QQQ"
                live_data = connectors.get_market_data(symbol)
            elif cat == "CLIMATE_METRIC": live_data = connectors.get_climate_data()
            elif cat == "GLOBAL_STATS": live_data = connectors.get_world_bank_data("SP.DYN.LE00.IN")

            if live_data:
                val = live_data.get('value')
                if val is None:
                    anchor["official_value"], anchor["variance"] = "Data Pending", "N/A"
                else:
                    anchor["official_value"] = str(val)
                    anchor["source"] = f"{live_data.get('source')} ({live_data.get('date')})"
                    c_num, o_num = extract_number(anchor.get("claim")), extract_number(str(val))
                    if c_num is not None and o_num is not None and o_num != 0:
                        diff = ((c_num - o_num) / o_num) * 100
                        anchor["variance"] = "Match" if abs(diff) < 0.1 else f"{'+' if diff > 0 else ''}{round(diff, 1)}%"

        audit_data["unresolved_conflicts"] = [str(c.get("conflict", c) if isinstance(c, dict) else c) for c in audit_data.get("unresolved_conflicts", [])]
        return audit_data
    except Exception as e:
        return {"error": f"Audit Logic Error: {str(e)}"}

def scrape_text_from_url(url: str) -> str:
    url = url.strip()
    if " " in url or len(url) > 255: return url
    if not url.startswith("http"): url = f"https://{url}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        return res.text if res.status_code == 200 else ""
    except Exception: return url