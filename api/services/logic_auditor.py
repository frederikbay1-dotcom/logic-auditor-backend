import os
import json
import anthropic
import requests
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
            model="claude-3-5-sonnet-20240620",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Domain: {domain}\n\nArticle Text:\n{text}\n\nReturn strictly valid JSON."}
            ],
            temperature=0.2
        )
        return json.loads(response.content[0].text)
    except Exception as e:
        return {"error": str(e)}

def scrape_text_from_url(url: str) -> str:
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    paragraphs = soup.find_all('p')
    return " ".join([p.text for p in paragraphs])