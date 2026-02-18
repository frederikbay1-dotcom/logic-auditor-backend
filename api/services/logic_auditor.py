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

# RE-INTRODUCED: Strict Schema for the AI Brain
SYSTEM_PROMPT = """
You are the "Logic Auditor." Deconstruct the provided text.
Return ONLY a valid JSON object with this EXACT structure:

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

        # Define keyword lists for specialist routing
        energy_keywords = ["oil", "brent", "wti", "petroleum", "gasoline", "fuel", "energy", "crude", "barrel"]
        econ_keywords = ["inflation", "cpi", "consumer price", "unemployment", "jobs", "yield", "interest rate"]
        global_keywords = ["gdp", "poverty", "growth", "population", "emissions", "carbon"]

        # ENRICHMENT: Precise Specialist Routing
        for anchor in audit_data.get("data_anchors", []):
            if not isinstance(anchor, dict): continue
                
            claim = anchor.get("claim", "").lower()
            live_data = None
            
            # 1. EIA (Crude Oil)
            if any(k in claim for k in ["oil", "brent", "wti", "crude"]):
                live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            
            # 2. FRED (Inflation/Unemployment)
            elif any(k in claim for k in ["inflation", "cpi"]):
                live_data = connectors.get_fred_data("CPIAUCSL")
            elif "unemployment" in claim:
                live_data = connectors.get_fred_data("UNRATE")
            
            # 3. World Bank (Growth Percentage)
            elif any(k in claim for k in ["gdp", "growth"]):
                live_data = connectors.get_world_bank_growth_data() # <--- Use the new % method

            if live_data:
                anchor["official_value"] = live_data['value']
                anchor["source"] = f"{live_data['source']} ({live_data['date']})"

        # SANITIZATION: Force 'unresolved_conflicts' to be a list of strings for React
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