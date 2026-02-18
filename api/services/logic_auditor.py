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

# 1. THE BRAIN: Strict Intent-Based Prompting
SYSTEM_PROMPT = """
You are the "Logic Auditor," a high-precision analytical tool. 
Deconstruct the provided text and return ONLY a valid JSON object.

For the 'data_anchors', you must assign one of these categories if applicable:
- 'ECON_INFLATION': US CPI data
- 'ECON_UNEMPLOYMENT': US Unemployment rate
- 'ENERGY_OIL': Crude oil spot prices
- 'GLOBAL_GDP': Global GDP growth percentage

STRICT JSON SCHEMA:
{
  "theses": ["string"],
  "logical_flaws": [
    {
      "flaw_type": "string",
      "lawyers_note": "string",
      "quote": "string",
      "severity": "High/Medium/Low"
    }
  ],
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

        # 2. THE SPECIALISTS: Intent-Based Execution
        # We rely on the AI's categorization to call the correct Data Lab
        for anchor in audit_data.get("data_anchors", []):
            if not isinstance(anchor, dict):
                continue
                
            category = anchor.get("category", "").upper()
            live_data = None
            
            if category == "ENERGY_OIL":
                # Specifically targeting WTI Crude Spot Price
                live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            elif category == "ECON_INFLATION":
                live_data = connectors.get_fred_data("CPIAUCSL")
            elif category == "ECON_UNEMPLOYMENT":
                live_data = connectors.get_fred_data("UNRATE")
            elif category == "GLOBAL_GDP":
                # Specifically targeting the Growth Percentage indicator
                live_data = connectors.get_world_bank_data("NY.GDP.MKTP.KD.ZG")

            if live_data:
                anchor["official_value"] = str(live_data.get('value', 'TBD'))
                anchor["source"] = f"{live_data.get('source', 'Unknown')} ({live_data.get('date', 'N/A')})"

        # 3. THE SAFETY FILTER: Frontend Compatibility
        # Prevents "React Error #31" by ensuring all items in the list are strings
        conflicts = audit_data.get("unresolved_conflicts", [])
        clean_conflicts = []
        for item in conflicts:
            if isinstance(item, dict):
                # Flatten any objects Claude might have accidentally nested
                c_text = item.get("conflict", "") or item.get("claim", "Logical Conflict")
                d_text = item.get("detail", "") or item.get("note", "")
                clean_conflicts.append(f"{c_text}: {d_text}")
            else:
                clean_conflicts.append(str(item))
        
        audit_data["unresolved_conflicts"] = clean_conflicts

        return audit_data
        
    except Exception as e:
        # Surfaces the exact error in the Lovable Audit UI for easier debugging
        return {"error": f"Audit Logic Error: {str(e)}"}

def scrape_text_from_url(url: str) -> str:
    """Robust scraper with anti-bot fallbacks."""
    if not url.strip().startswith("http"):
        return url

    

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        # Priority 1: Clean text extraction via Jina AI
        res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        if res.status_code == 200:
            return res.text
            
        # Priority 2: Standard BeautifulSoup fallback
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Extract text only from paragraphs to reduce noise
            return " ".join([p.get_text() for p in soup.find_all('p')])
            
        return ""
    except Exception:
        return ""