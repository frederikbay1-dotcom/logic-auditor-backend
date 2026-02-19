from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from api.models import AuditRequest
from api.services.logic_auditor import perform_audit, scrape_text_from_url

app = FastAPI()

# Enable CORS to allow the Lovable frontend to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    """Simple health check endpoint for deployment verification."""
    return {"status": "ok"}

@app.post("/api/audit")
async def audit(request: AuditRequest):
    """
    Primary endpoint for logical audits. 
    Prioritizes manually pasted text over URL scraping to bypass bot blockers.
    """
    try:
        audit_content = ""
        
        # Priority 1: Use manually pasted text if it meets minimum length
        if request.text and len(request.text.strip()) > 10:
            audit_content = request.text
        # Priority 2: Attempt to scrape content if a URL is provided
        elif request.url:
            audit_content = scrape_text_from_url(request.url)
        else:
            raise ValueError("Validation Error: Please paste article text or provide a valid URL.")

        # Final validation to ensure sufficient content was received
        if not audit_content or len(audit_content.strip()) < 10:
            raise ValueError("Content Error: The provided text or scraped content is too short to audit.")

        # Execute the logical audit via the logic_auditor service
        audit_result = perform_audit(audit_content, request.domain)
        
        # Catch and surface any internal service errors (e.g., AI or API failures)
        if isinstance(audit_result, dict) and "error" in audit_result:
            raise ValueError(audit_result["error"])
            
        return audit_result

    except Exception as e:
        # Log the detailed error to the console and return a 400 status to the frontend
        print(f"Audit Exception: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))