from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for environments not yet synced with requirements.txt
    load_dotenv = None

env_path = Path(__file__).resolve().parents[2] / ".env"
if load_dotenv:
    load_dotenv(env_path)

from app.api.v1.agent import router as agent_router
from app.api.v1.chat import router as chat_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.reports import router as reports_router


app = FastAPI(
    title="DataAgent API",
    version="0.1.0",
    description="W1 data upload and preview service.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(datasets_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")

artifacts_dir = Path(__file__).resolve().parents[2] / "data" / "artifacts"
artifacts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=artifacts_dir), name="artifacts")
