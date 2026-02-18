import os
import json
import anthropic
import requests
import re
from api.services.data_connectors import DataConnectors # <--- Add this import

# Initialize the connectors
connectors = DataConnectors()
# THE DICTATOR PROMPT: Enforces the exact schema your Pydantic model needs
SYSTEM_PROMPT = """
You are the "Logic Auditor," an LSAT-style analytical reader. 
Deconstruct the provided text in the domains of Economics or Climate.

STRICT JSON SCHEMA REQUIREMENT:
You must return ONLY a JSON object with this exact structure:
{
  "theses": ["string", "string"],
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
      "source": "string",
      "official_value": "TBD - Verify via FRED",
      "variance": "N/A"
    }
  ],
  "unresolved_conflicts": ["string"],
  "next_steps": ["string"]
}

Rules:
- 'theses': Extract the primary core arguments.
- 'logical_flaws': Identify Causal Flaws, Conditional Errors, or Omissions.
- 'data_anchors': Isolate claims that need hard data verification. 
- Return NO conversational text. No markdown blocks. Just the raw JSON.
"""

def perform_audit(text: str, domain: str) -> dict:
    try:
        # 1. Get the Logical Audit from Claude
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

        # 2. Enrich "Data Anchors" with Live Data
        for anchor in audit_data.get("data_anchors", []):
            claim = anchor.get("claim", "").lower()
            
            # Simple keyword routing to the correct Lab
            live_data = None
            if "oil" in claim or "energy" in claim:
                live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC") # WTI Crude
            elif "inflation" in claim or "cpi" in claim:
                live_data = connectors.get_fred_data("CPIAUCSL")
            elif "unemployment" in claim:
                live_data = connectors.get_fred_data("UNRATE")
            elif "gdp" in claim:
                live_data = connectors.get_world_bank_data("NY.GDP.MKTP.CD")

            # If we found a match, overwrite the TBD
            if live_data:
                anchor["official_value"] = f"{live_data['value']}"
                anchor["source"] = f"{live_data['source']} ({live_data['date']})"
        
        return audit_data
        
    except Exception as e:
        return {"error": str(e)}

# ... (Keep your scrape_text_from_url function as is)
def scrape_text_from_url(url: str) -> str:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        # Try Jina AI first (Best for bypassing blocks)
        res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        if res.status_code == 200:
            return res.text
            
        # Fallback to direct scrape
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            return " ".join([p.text for p in soup.find_all('p')])
            
        # If we reach here, tell the user WHY it failed
        raise Exception(f"Publisher Blocked Access (Status {res.status_code}). Please paste text manually.")
    except Exception as e:
        raise Exception(f"Scraper Error: {str(e)}")