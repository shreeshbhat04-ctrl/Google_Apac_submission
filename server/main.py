"""Server entrypoint for the REST-first AlloyNative runtime."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from server.action_registry import ActionRegistry
from server.dependencies import ServerSettings, build_client
from server.rest_routes import create_rest_app


def create_app():
    """Create the FastAPI app with a managed AlloyNative client lifespan."""

    settings = ServerSettings.from_env()
    action_registry = ActionRegistry()

    @asynccontextmanager
    async def lifespan(_app):
        client = await build_client(settings)
        _app.state.client = client
        _app.state.action_registry = action_registry
        try:
            yield
        finally:
            await client.close()

    app = create_rest_app()
    app.state.settings = settings
    app.router.lifespan_context = lifespan
    return app


app = create_app()


async def serve_rest() -> None:
    """Run the REST server via uvicorn."""

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depends on local env
        raise RuntimeError(
            "uvicorn is not installed. Install server dependencies before running the app."
        ) from exc

    settings = ServerSettings.from_env()
    config = uvicorn.Config(app, host=settings.host, port=settings.port)
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Run the REST server entrypoint."""

    asyncio.run(serve_rest())


if __name__ == "__main__":
    main()
