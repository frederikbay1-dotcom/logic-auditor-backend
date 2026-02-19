import os
import json
import anthropic
import requests
import re
from bs4 import BeautifulSoup
from api.services.data_connectors import DataConnectors

# Initialize specialists
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
connectors = DataConnectors()

SYSTEM_PROMPT = """
You are the "Logic Auditor." Deconstruct the provided text.
Return ONLY a valid JSON object. For 'data_anchors', categorize each claim.

CATEGORIES:
- 'ECON_INFLATION': US CPI
- 'ECON_UNEMPLOYMENT': US Jobs
- 'ENERGY_OIL': Crude prices
- 'GLOBAL_GDP': Growth %

STRICT JSON SCHEMA:
{
  "theses": ["string"],
  "logical_flaws": [{"flaw_type": "string", "lawyers_note": "string", "quote": "string", "severity": "High"}],
  "data_anchors": [
    {
      "claim": "string",
      "category": "ECON_INFLATION | ECON_UNEMPLOYMENT | ENERGY_OIL | GLOBAL_GDP | NONE",
      "source": "string",
      "official_value": "TBD",
      "variance": "N/A"
    }
  ],
  "unresolved_conflicts": ["string"],
  "next_steps": ["string"]
}
"""

def extract_number(text: str):
    """Helper to pull the first number out of a string (e.g., '$82.50' -> 82.5)."""
    if not text: return None
    # Remove commas and find digits/decimals
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

        # ENRICHMENT & VARIANCE CALCULATION
        for anchor in audit_data.get("data_anchors", []):
            if not isinstance(anchor, dict): continue
            
            category = anchor.get("category", "").upper()
            live_data = None
            
            # 1. Fetch official data
            if category == "ENERGY_OIL":
                live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            elif category == "ECON_INFLATION":
                live_data = connectors.get_fred_data("CPIAUCSL")
            elif category == "ECON_UNEMPLOYMENT":
                live_data = connectors.get_fred_data("UNRATE")
            elif category == "GLOBAL_GDP":
                live_data = connectors.get_world_bank_data("NY.GDP.MKTP.KD.ZG")

            # 2. Compare and Calculate
            if live_data:
                official_val_str = str(live_data.get('value', 'TBD'))
                anchor["official_value"] = official_val_str
                anchor["source"] = f"{live_data.get('source', 'Unknown')} ({live_data.get('date', 'N/A')})"
                
                # Math: (Claim - Official) / Official
                claimed_num = extract_number(anchor.get("claim", ""))
                official_num = extract_number(official_val_str)
                
                if claimed_num is not None and official_num is not None and official_num != 0:
                    diff_pct = ((claimed_num - official_num) / official_num) * 100
                    # If the difference is tiny, call it 'Accurate'
                    if abs(diff_pct) < 0.1:
                        anchor["variance"] = "Match"
                    else:
                        prefix = "+" if diff_pct > 0 else ""
                        anchor["variance"] = f"{prefix}{round(diff_pct, 1)}%"

        # Cleanup for React
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
        if res.status_code == 200: return res.text
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            return " ".join([p.text for p in soup.find_all('p')])
        return ""
    except Exception: return ""