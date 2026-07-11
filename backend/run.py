from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the DataAgent FastAPI backend.")
    parser.add_argument("--host", default=os.getenv("BACKEND_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BACKEND_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload for local development.")
    return parser.parse_args()


def main() -> None:
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    load_env_file(project_root / ".env")

    args = parse_args()
    uvicorn.run(
        "app.main:app",
        app_dir=str(backend_dir),
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
