import os
import json
import anthropic
import requests
import re
from bs4 import BeautifulSoup # <--- THIS IS THE MISSING LINK
from api.services.data_connectors import DataConnectors

# Initialize the AI and Data Labs
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
connectors = DataConnectors()

SYSTEM_PROMPT = """
You are the "Logic Auditor." Deconstruct the provided text.
Return ONLY a JSON object with keys: theses, logical_flaws, data_anchors, unresolved_conflicts, next_steps.
"""

def perform_audit(text: str, domain: str) -> dict:
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-latest", 
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

        # Cross-reference identified anchors with FRED/EIA/World Bank
        for anchor in audit_data.get("data_anchors", []):
            claim = anchor.get("claim", "").lower()
            live_data = None
            
            # Use your new DataConnectors specialists
            if "oil" in claim or "energy" in claim:
                live_data = connectors.get_eia_data("petroleum/pri/spt", "RWTC")
            elif "inflation" in claim or "cpi" in claim:
                live_data = connectors.get_fred_data("CPIAUCSL")
            elif "unemployment" in claim:
                live_data = connectors.get_fred_data("UNRATE")
            elif "gdp" in claim:
                live_data = connectors.get_world_bank_data("NY.GDP.MKTP.CD")

            if live_data:
                anchor["official_value"] = f"{live_data['value']}"
                anchor["source"] = f"{live_data['source']} ({live_data['date']})"
        
        return audit_data
        
    except Exception as e:
        return {"error": f"Audit Logic Error: {str(e)}"}

def scrape_text_from_url(url: str) -> str:
    # If input isn't a URL, return it as text
    if not url.strip().startswith("http"):
        return url

    

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        # Try Jina AI first for clean content
        res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        if res.status_code == 200:
            return res.text
            
        # Fallback to BeautifulSoup if Jina fails
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            return " ".join([p.text for p in soup.find_all('p')])
            
        raise Exception(f"Access denied by publisher (Status {res.status_code})")
    except Exception as e:
        raise Exception(f"Scraper Error: {str(e)}")