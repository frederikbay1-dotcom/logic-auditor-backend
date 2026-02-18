from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from api.models import AuditRequest, AuditResponse
from api.services.logic_auditor import perform_audit, scrape_text_from_url

app = FastAPI(title="Logic Auditor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "engine": "LSAT Logic Auditor Active"}

@app.post("/api/audit", response_model=AuditResponse)
def audit_article(request: AuditRequest):
    text_to_audit = request.text
    
    if request.url and not text_to_audit:
        try:
            text_to_audit = scrape_text_from_url(request.url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to scrape URL: {str(e)}")
            
    if not text_to_audit:
        raise HTTPException(status_code=400, detail="Must provide either text or a valid URL.")

    audit_results = perform_audit(text_to_audit, request.domain)
    
    if "error" in audit_results:
         raise HTTPException(status_code=500, detail=audit_results["error"])
    
    return audit_results