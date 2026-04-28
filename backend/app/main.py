"""Axiom FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="Axiom",
    description="Intelligent A/B testing and experimentation platform",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
