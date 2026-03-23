# Server Runtime

This directory contains the REST-first AlloyNative runtime.

It is intentionally thin:
- HTTP routes normalize request payloads
- actions are registered and executed here
- business logic stays inside the Python SDK

Use this layer for:
- local Postman testing
- mock-mode demos
- eventual Cloud Run deployment
