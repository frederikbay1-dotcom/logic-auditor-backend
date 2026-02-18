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
    """
    Uses Jina AI to bypass bot-blockers (like Cloudflare) and extract 
    clean, readable text from news articles.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'text/plain'
        }
        # We prepend 'https://r.jina.ai/' to the URL to use their proxy scraper
        jina_url = f"https://r.jina.ai/{url}"
        res = requests.get(jina_url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            # Jina returns beautiful, clean text ready for the LLM
            return res.text
        else:
            print(f"Scraper Failed with status: {res.status_code}")
            return ""
    except Exception as e:
        print(f"Scraper Error: {str(e)}")
        return ""