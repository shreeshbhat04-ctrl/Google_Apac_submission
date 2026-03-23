# AlloyNative Build Order

This document defines the shortest safe path from scaffold to working SDK.

The key idea is simple: build the Python core first, because every later layer
depends on it.

If we get the Python connection and SQL generation right, the server, proto,
TypeScript client, and demo story all become wrappers around a stable core.

## Guiding Rule

Build in this order:
1. Lowest-level correctness first.
2. Public Python API second.
3. Tests immediately after each core layer.
4. Shared transport contract after the Python behavior is real.
5. Server and TypeScript wrappers last.

## The First 7 Files To Implement

### 1. `py/alloynative/errors.py`

Why first:
- Error names define how the rest of the SDK communicates failure.
- They give us a clean vocabulary before connection and validation code exists.
- They are low-risk and help every later file stay consistent.

What this file must do:
- Define the base SDK exception.
- Define auth, connection, extension, model, and index exceptions.
- Keep error names aligned with `LEARNINGS.md`.

Done means:
- Every expected failure mode has a named exception.
- Other files can import these exceptions without redesign later.

### 2. `py/alloynative/config.py`

Why second:
- The client, connection layer, validation layer, and server all need the same config shape.
- A stable config object prevents argument drift across files.

What this file must do:
- Define the core connection settings.
- Hold project, region, cluster, instance, database, and IP mode.
- Be simple enough that Python client construction is obvious.

Done means:
- There is one canonical config representation for the Python SDK.
- No other file invents its own connection arguments.

### 3. `py/alloynative/auth.py`

Why third:
- IAM principal resolution is one of the hardest “real AlloyDB” pieces.
- It is isolated enough to build early without needing full client logic.

What this file must do:
- Resolve default Google credentials.
- Extract or derive the IAM principal email used for DB auth.
- Hide GCP auth details from the public SDK surface.

Done means:
- Given a real environment, this layer can answer “which DB user should connect?”
- Failures map cleanly to auth-specific SDK exceptions.

### 4. `py/alloynative/connection.py`

Why fourth:
- This is the actual bridge to AlloyDB.
- Nothing meaningful can run until this layer can create and close a connection safely.

What this file must do:
- Create the AlloyDB connector.
- Use asyncpg as the database driver.
- Build the instance URI from config.
- Enable IAM authentication.
- Provide a minimal execute/fetch capability for higher layers.

Done means:
- We can establish a real connection and run `SELECT 1`.
- Connector lifecycle is explicit and not leaked into the public API.

### 5. `py/alloynative/validation.py`

Why fifth:
- Once we can connect, the next biggest source of confusion is bad environment setup.
- Failing fast is part of the SDK value proposition.

What this file must do:
- Check for `google_ml_integration`.
- Check the DB flag for model support.
- Check that the default embedding model is registered.
- Later, optionally check index presence where useful.

Done means:
- `connect()` can tell the user what is wrong before they try search or upsert.
- Setup failures are actionable, not mysterious.

### 6. `py/alloynative/client.py`

Why sixth:
- This is the public Python face of AlloyNative.
- It should be thin once the lower layers are already real.

What this file must do in the first pass:
- Accept config inputs.
- Create the connection layer.
- Run startup validation.
- Expose a raw `execute()` escape hatch.

What this file must do in the second pass:
- Add `upsert_raw_text()`.
- Add `search_hybrid()`.
- Add optional rerank flow.

Done means:
- The user can call `connect()` and then `execute("SELECT 1")`.
- The client is real, not just a shell around unimplemented helpers.

### 7. `py/tests/test_client.py`

Why seventh:
- This is the first proof that the public surface is coherent.
- It keeps the connection milestone honest.

What this file must test first:
- Client construction.
- Required argument validation.
- Connection flow with mocked dependencies.
- Raw execute happy path and error mapping.

What it should test next:
- Validation failure propagation.
- Cleanup behavior on shutdown.

Done means:
- Phase 1 has an executable definition of success.
- Refactors in connection code won’t silently break the API.

## Files That Should Come Immediately After

After the first 7, implement these next:

### `py/alloynative/sql.py`

Why next:
- This is the moat.
- It translates the AlloyNative API into in-database ML SQL.

What success looks like:
- Upsert SQL is parameterized and safe.
- Hybrid search SQL supports filters and RRF.
- Rerank SQL is modeled as a second-stage query path.

### `py/tests/test_sql.py`

Why next:
- SQL generation is too important to leave untested.
- This file should lock in the actual query shapes.

What success looks like:
- Tests assert the presence of `google_ml.embedding(...)`.
- Tests assert hybrid search structure and filter operator mapping.
- Tests assert rerank path uses the intended query strategy.

### `py/alloynative/results.py`

Why next:
- Once search exists, result objects need to stabilize.
- This file helps avoid ad hoc dictionaries everywhere.

### `py/alloynative/sync.py`

Why next:
- Add this only after the async core works.
- Sync wrappers are useful, but not worth blocking Phase 1.

## Why Not Start With Proto, gRPC, or TypeScript

Do not start there.

Reasons:
- The transport layer is not the product.
- The Python core defines the real behavior.
- If you write proto or TS too early, you risk encoding guesses instead of truths.
- “One proto, two languages, zero drift” only works after the Python contract is real.

## Recommended Phase Sequence

### Phase 1: Connection Milestone

Implement:
- `errors.py`
- `config.py`
- `auth.py`
- `connection.py`
- `validation.py`
- `client.py`
- `test_client.py`

Success bar:
- `AlloyDBClient.connect(...)` works.
- `await client.execute("SELECT 1")` works.
- Misconfigured environments fail with good messages.

### Phase 2: SQL Generation Milestone

Implement:
- `sql.py`
- `results.py`
- `test_sql.py`
- expand `test_client.py`

Success bar:
- `upsert_raw_text()` generates in-database embedding SQL.
- `search_hybrid()` generates true hybrid SQL with filters and RRF.
- reranking path is represented clearly.

### Phase 3: Shared Contract Milestone

Implement:
- `ts/proto/alloynative.proto`
- `server/grpc_servicer.py`
- `server/tests/test_grpc_servicer.py`

Success bar:
- The transport contract matches the Python client behavior.
- Search and upsert messages are stable enough to generate clients from.

### Phase 4: TypeScript Client Milestone

Implement:
- `ts/src/client.ts`
- `ts/src/types.ts`
- generated code flow

Success bar:
- TS consumers can call the same conceptual API as Python users.

### Phase 5: Server and Demo Milestone

Implement:
- `server/rest_routes.py`
- `server/mcp_tools.py`
- `server/action_registry.py`
- demo scripts
- deployment files

Success bar:
- The SDK can be used directly and also exposed to agents.

## A Practical Rule For Every New File

Before implementing a file, answer:
1. Does this file define core behavior, or is it just wrapping another layer?
2. If it is just a wrapper, can it wait?

For AlloyNative, wrappers should usually wait.
Core behavior should come first.
