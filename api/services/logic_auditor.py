import os
import json
import anthropic
import requests
import re
from bs4 import BeautifulSoup # <--- FIXED: Added the missing import
from api.services.data_connectors import DataConnectors

# Initialize Anthropic and Data Connectors
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
connectors = DataConnectors()

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
- Return NO conversational text. Just the raw JSON.
"""

def perform_audit(text: str, domain: str) -> dict:
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022", # Using a stable, high-performance model
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Domain: {domain}\n\nArticle Text:\n{text}"}
            ],
            temperature=0.1
        )
        
        raw_text = response.content[0].text
        
        # Robustly extract JSON even if Claude adds conversational filler
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match:
            return {"error": "AI failed to produce a valid JSON block."}
            
        audit_data = json.loads(json_match.group(0))

        # ENRICHMENT: Automatically check FRED, EIA, and World Bank for data anchors
        for anchor in audit_data.get("data_anchors", []):
            claim = anchor.get("claim", "").lower()
            live_data = None
            
            if "oil" in claim or "energy" in claim or "brent" in claim:
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
    """
    Safely extracts text from a URL. 
    If the input is already raw text (not a URL), it returns it as-is.
    """
    if not url.strip().startswith("http"):
        return url # It's already text, don't try to scrape it!

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        # Try Jina AI first for clean, bot-resistant scraping
        res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        if res.status_code == 200:
            return res.text
            
        # Fallback to direct scrape if Jina fails
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            paragraphs = soup.find_all('p')
            return " ".join([p.text for p in paragraphs])
            
        return ""
    except Exception as e:
        raise Exception(f"Scraper Error: {str(e)}")