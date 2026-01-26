from fastapi import FastAPI
from app.api.session_routes import router as session_router
from app.api.scenario_routes import router as scenario_router

app = FastAPI(
    title="VR Nursing Education System Backend",
    version="Week-9"
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(session_router)
app.include_router(scenario_router)
