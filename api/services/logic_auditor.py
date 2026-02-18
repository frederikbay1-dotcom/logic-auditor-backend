import os
import json
import anthropic
import requests
import re
from bs4 import BeautifulSoup
from api.services.data_connectors import DataConnectors

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
connectors = DataConnectors()

# RE-INTRODUCED: Strict Schema for the AI Brain
SYSTEM_PROMPT = """
You are the "Logic Auditor." Deconstruct the provided text.
Return ONLY a valid JSON object with this exact structure:

{
  "theses": ["string"],
  "logical_flaws": [{"flaw_type": "string", "lawyers_note": "string", "quote": "string", "severity": "High"}],
  "data_anchors": [
    {
      "claim": "string", 
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

        # Specialists Keywords
        energy_keywords = ["oil", "brent", "wti", "petroleum", "gasoline", "fuel", "energy", "crude", "barrel"]
        econ_keywords = ["inflation", "cpi", "consumer price", "unemployment", "jobs", "yield", "interest rate"]
        global_keywords = ["gdp", "poverty", "growth", "population", "emissions", "carbon"]

        # ENRICHMENT: Now with Safety Checks
        for anchor in audit_data.get("data_anchors", []):
            # SAFETY: If anchor is a string (AI lapse), skip it instead of crashing
            if not isinstance(anchor, dict):
                continue
                
            claim = anchor.get("claim", "").lower()
            live_data = None
            
            if any(k in claim for k in energy_keywords):
                live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            elif any(k in claim for k in econ_keywords):
                series_id = "CPIAUCSL" if ("inflation" in claim or "cpi" in claim) else "UNRATE"
                live_data = connectors.get_fred_data(series_id)
            elif any(k in claim for k in global_keywords):
                live_data = connectors.get_world_bank_data("NY.GDP.MKTP.CD")

            if live_data:
                anchor["official_value"] = f"{live_data['value']}"
                anchor["source"] = f"{live_data['source']} ({live_data['date']})"

        # SANITIZATION: Prevent React Error #31
        conflicts = audit_data.get("unresolved_conflicts", [])
        clean_conflicts = []
        for item in conflicts:
            if isinstance(item, dict):
                conflict_text = item.get("conflict", "") or item.get("claim", "")
                detail_text = item.get("detail", "") or item.get("note", "")
                clean_conflicts.append(f"{conflict_text}: {detail_text}")
            else:
                clean_conflicts.append(str(item))
        audit_data["unresolved_conflicts"] = clean_conflicts

        return audit_data
        
    except Exception as e:
        return {"error": f"Audit Logic Error: {str(e)}"}

def scrape_text_from_url(url: str) -> str:
    if not url.strip().startswith("http"):
        return url
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        if res.status_code == 200:
            return res.text
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            return " ".join([p.text for p in soup.find_all('p')])
        return ""
    except Exception:
        return ""