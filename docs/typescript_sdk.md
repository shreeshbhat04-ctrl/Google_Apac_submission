# TypeScript SDK

The TypeScript SDK lives under [ts/src](c:\Users\shree\google_submission\p1\ts\src).

It is intentionally thinner than the Python SDK.

## What It Does

- exposes request and response types
- wraps a transport abstraction
- mirrors the shared proto contract
- keeps parity with the generalized row-based upsert and search model

## Current Status

- handwritten TS client and types exist
- proto generation works locally
- TypeScript build passes
- transport is still abstract rather than bound to a live generated RPC transport

## Main Files

- [ts/src/client.ts](c:\Users\shree\google_submission\p1\ts\src\client.ts)
- [ts/src/types.ts](c:\Users\shree\google_submission\p1\ts\src\types.ts)
- [ts/proto/alloynative.proto](c:\Users\shree\google_submission\p1\ts\proto\alloynative.proto)
