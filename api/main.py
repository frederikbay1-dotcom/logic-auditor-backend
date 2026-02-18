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

@app.post("/api/audit")
async def audit(request: AuditRequest):
    try:
        if request.url:
            text = scrape_text_from_url(request.url)
        else:
            text = request.text
            
        if not text or len(text.strip()) < 10:
            raise HTTPException(status_code=400, detail="No readable text found. Please paste it manually.")
            
        return perform_audit(text, request.domain)
    except Exception as e:
        # This sends the actual error message back to Lovable
        raise HTTPException(status_code=400, detail=str(e))