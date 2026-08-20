from fastapi import FastAPI

from argumenta import __version__
from argumenta.presentation.fastapi.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Argumenta API", version=__version__)
    app.include_router(health_router)
    return app


app = create_app()
