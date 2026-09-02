from fastapi import FastAPI

from app import config
from app.models import Greeting

# A small FastAPI application. The Swagger UI is served at /docs, which gives
# the non-technical participants a working product to look at.

app = FastAPI(
    title="DEDIH 2.0 CI/CD demo",
    description="Demo application for the CI/CD and DevSecOps course.",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    # Health check endpoint. Used by the CI smoke test, by the container
    # HEALTHCHECK and by anyone opening the app in a browser.
    return {"status": "ok"}


@app.post("/greet")
def greet(payload: Greeting) -> dict[str, str]:
    # The Greeting model gets its validation from Pydantic. Invalid input is
    # rejected by FastAPI with HTTP 422 before this function is reached.
    return {"message": f"Szia, {payload.name}!"}


@app.get("/config")
def read_config() -> dict[str, bool]:
    # Reports whether the API key is configured, without returning the value.
    # This is what makes the secret load bearing: with no secret the endpoint
    # answers false, and after the workflow injects one it answers true.
    return {"api_key_configured": config.api_key_configured()}
