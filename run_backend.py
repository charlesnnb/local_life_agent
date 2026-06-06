"""Start the FastAPI service and built frontend."""

import uvicorn

from src.config.settings import settings


if __name__ == "__main__":
    print(f"Starting Local Life Agent on http://localhost:{settings.port}")
    uvicorn.run(
        "src.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
