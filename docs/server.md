# Server

The server is REST-first today and uses the Python SDK as the single source of business logic.

## Main Pieces

- [server/main.py](c:\Users\shree\google_submission\p1\server\main.py)
- [server/rest_routes.py](c:\Users\shree\google_submission\p1\server\rest_routes.py)
- [server/mcp_tools.py](c:\Users\shree\google_submission\p1\server\mcp_tools.py)
- [server/grpc_servicer.py](c:\Users\shree\google_submission\p1\server\grpc_servicer.py)
- [server/action_registry.py](c:\Users\shree\google_submission\p1\server\action_registry.py)

## Runtime Modes

- real AlloyDB mode
- mock dev mode via `ALLOYNATIVE_DEV_MODE=true`

Mock mode is useful for:
- local endpoint testing
- Postman demos
- frontend and integration work before infrastructure is live

## Current Shape

- FastAPI app is implemented
- gRPC adapter exists as a transport translation layer
- MCP wrappers are implemented
- action registration and execution flow is available
