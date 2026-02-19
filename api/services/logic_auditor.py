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

STRICT JSON SCHEMA:
{
  "theses": ["string"],
  "logical_flaws": [{"flaw_type": "string", "lawyers_note": "string", "quote": "string", "severity": "High"}],
  "data_anchors": [
    {
      "claim": "string",
      "category": "ECON_INFLATION | ECON_UNEMPLOYMENT | ENERGY_OIL | GLOBAL_GDP | NONE",
      "official_value": "TBD",
      "variance": "N/A"
    }
  ],
  "feynman_summary": {
    "simple_explanation": "Provide a simple, 10-year-old level explanation of the core logical gap.",
    "medical_analogy": "Provide a medical analogy for this specific logical flaw."
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
        
        raw_text = response.content[0].text
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match:
            return {"error": "AI failed to produce a JSON block."}
            
        audit_data = json.loads(json_match.group(0))

        # Enrichment logic for FRED, EIA, and World Bank
        for anchor in audit_data.get("data_anchors", []):
            if not isinstance(anchor, dict): continue
            category = anchor.get("category", "").upper()
            live_data = None
            
            if category == "ENERGY_OIL":
                live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            elif category == "ECON_INFLATION":
                live_data = connectors.get_fred_data("CPIAUCSL")
            elif category == "ECON_UNEMPLOYMENT":
                live_data = connectors.get_fred_data("UNRATE")
            elif category == "GLOBAL_GDP":
                live_data = connectors.get_world_bank_data("NY.GDP.MKTP.KD.ZG")

            if live_data:
                off_val = str(live_data.get('value', 'TBD'))
                anchor["official_value"] = off_val
                anchor["source"] = f"{live_data.get('source', 'Unknown')} ({live_data.get('date', 'N/A')})"
                
                claimed_num = extract_number(anchor.get("claim", ""))
                official_num = extract_number(off_val)
                
                if claimed_num is not None and official_num is not None and official_num != 0:
                    diff_pct = ((claimed_num - official_num) / official_num) * 100
                    anchor["variance"] = "Match" if abs(diff_pct) < 0.1 else f"{'+' if diff_pct > 0 else ''}{round(diff_pct, 1)}%"

        # React Safety Filter
        conflicts = audit_data.get("unresolved_conflicts", [])
        audit_data["unresolved_conflicts"] = [str(c.get("conflict", c) if isinstance(c, dict) else c) for c in conflicts]

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