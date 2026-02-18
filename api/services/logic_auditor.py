import os
import json
import anthropic
import requests
import re
from bs4 import BeautifulSoup

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
You are the "Logic Auditor," an LSAT-style analytical reader. 
Deconstruct the provided text in the domains of Economics or Climate.
Respond strictly with a JSON object matching the requested schema.
Include these specific flaw types if present:
- Causal Flaw
- Conditional Error
- Sampling Flaw
- Omission Flaw
- Comparison Flaw

Map the article's claims to required data anchors (e.g., FRED 'INDPRO', CPI).
"""

def perform_audit(text: str, domain: str) -> dict:
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6", # (Or whatever model string you are currently using)
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Domain: {domain}\n\nArticle Text:\n{text}\n\nReturn strictly valid JSON."}
            ],
            temperature=0.2
        )
        
        raw_text = response.content[0].text
        
        # Use Regex to isolate only the JSON block
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match:
            return {"error": "Failed to extract valid JSON from the AI response."}
            
        clean_json = json_match.group(0)
        return json.loads(clean_json)
        
    except Exception as e:
        return {"error": str(e)}

def scrape_text_from_url(url: str) -> str:
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    paragraphs = soup.find_all('p')
    return " ".join([p.text for p in paragraphs])