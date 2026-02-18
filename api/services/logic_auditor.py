import os
import json
import anthropic
import requests
import re
from bs4 import BeautifulSoup

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
        # NOTE: If you are on a Vercel Hobby plan (10s timeout), 
        # consider using a 'haiku' model for speed if this times out.
        response = client.messages.create(
            model="claude-sonnet-4-6", 
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Domain: {domain}\n\nArticle Text:\n{text}"}
            ],
            temperature=0.1
        )
        
        raw_text = response.content[0].text
        
        # Robustly extract JSON even if Claude adds 'Here is the JSON:'
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match:
            return {"error": "AI failed to produce a JSON block."}
            
        clean_json = json_match.group(0)
        return json.loads(clean_json)
        
    except Exception as e:
        return {"error": str(e)}

# ... (Keep your scrape_text_from_url function as is)
def scrape_text_from_url(url: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # Try Jina first (Better formatting)
    try:
        jina_res = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=10)
        if jina_res.status_code == 200:
            return jina_res.text
    except:
        pass

    # Fallback: Direct Scrape if Jina is blocked
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
        soup = BeautifulSoup(res.text, 'html.parser')
        # Standard news article paragraph extraction
        paragraphs = soup.find_all('p')
        return " ".join([p.text for p in paragraphs])
    
    # If all fail, throw a descriptive error
    raise Exception(f"Access Denied by Publisher (Status {res.status_code}). Please copy-paste the article text manually.")