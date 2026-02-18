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
            model="claude-sonnet-4-6",
            max_tokens=8192, # <--- INCREASE THIS TO 8192
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Domain: {domain}\n\nArticle Text:\n{text}\n\nReturn strictly valid JSON."}
            ],
            temperature=0.2
        )
        
        raw_text = response.content[0].text
        print(f"RAW AI TEXT: {raw_text}") # <--- ADD THIS SO VERCEL LOGS IT
        
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match:
            return {"error": "Failed to extract valid JSON. Regex missed."}
            
        clean_json = json_match.group(0)
        
        try:
            return json.loads(clean_json)
        except json.JSONDecodeError as decode_error:
            # This captures the exact parsing error and returns it to Lovable
            return {"error": f"JSON Parse Failed: {str(decode_error)}. Text was: {clean_json[:100]}..."}
        
    except Exception as e:
        return {"error": str(e)}

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