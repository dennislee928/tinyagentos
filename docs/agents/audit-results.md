# AgentsApp Endpoint Audit — Pass 1 Results

Per-endpoint pass/fail against the agent-friendliness checklist
(see `docs/superpowers/specs/2026-05-12-agent-friendliness-audit-design.md` §"REST API audit checklist").

**Status as of 2026-05-12:** Pass 1 complete.

| Endpoint | URL shape | HTTP verb | OpenAPI complete | Errors actionable | Bearer auth | Idempotent | List shape | Flat response | Notes |
|---|---|---|---|---|---|---|---|---|---|
| GET /api/agents | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ❌ Pass 2 | ✅ | List endpoint — returns plain JSON array; pagination cursor lands in Pass 2 |
| POST /api/agents | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | Create endpoint — Idempotency-Key supported (Task 12) |
| GET /api/agents/{name} | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | Surfaces has_token (Task 6 ✅) |
| PUT /api/agents/{name} | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | |
| DELETE /api/agents/{name} | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | Cascades token revoke (Task 7 ✅) |
| POST /api/agents/{name}/start | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | Start on a running agent is a no-op — natively idempotent |
| POST /api/agents/{name}/stop | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | Stop on a stopped agent is a no-op — natively idempotent |
| POST /api/agents/{name}/pause | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | Pause on a paused agent is a no-op — natively idempotent |
| POST /api/agents/{name}/restart | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | Restart has side effects each call; idempotency would be an Idempotency-Key add — Pass 2 |
| GET /api/agents/{name}/logs | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ❌ Pass 2 | ✅ | Returns `{lines: [...]}` — pagination via `lines` param; cursor shape Pass 2 |
| PUT /api/agents/{name}/permissions | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | Task 14 ✅ |
| POST /api/agents/deploy | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | ✅ | Idempotency-Key support (Task 12) |
| POST /api/agents/{name}/token/issue | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | Returns plaintext once (Task 6 ✅) |
| DELETE /api/agents/{name}/token | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | Cascade on agent delete (Task 7 ✅) |
| GET /api | ✅ | ✅ | ✅ | N/A | ⚪ Session/bearer-gated by middleware | N/A | ✅ | ✅ | Discovery index — new endpoint (Task 13 ✅). No per-action scope check; auth handled by AuthMiddleware. |
| POST /api/ui/notify | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | First agent-to-UI primitive (Task 15 ✅). Storage backed by single-user NotificationStore; per-user routing lands in Pass 2. |

## Legend

- ✅ — meets the spec.
- ❌ — does not yet meet the spec; reason / Pass tagged.
- N/A — column doesn't apply to this endpoint shape.
- ⚪ — partial / deliberate-by-design (see note).

## Deferred to a later pass

- **Pagination cursor (`{items, next_cursor}`)** on list endpoints (`GET /api/agents`, `GET /api/agents/{name}/logs`) — Pass 2. Pass 1 returns the plain shape current consumers expect; switching to a cursor envelope is a coordinated change across CLI + frontend.
- **`response_model=` for success responses on agent CRUD endpoints** — agent dicts are still loose-typed in Pass 1; locking the schema would either regress existing fields or land an empty/almost-empty pydantic model.
- **Multi-user NotificationStore migration** (`user_id`, `source_type`, `source_id`, `priority`, `action_url`, `app_origin` columns + `list_for_user`/`create` API) — Pass 1 ui.notify uses the existing single-user `add()`; per-user routing lands in Pass 2 along with the `action_url` field on the request schema.
- **Idempotency-Key on `/restart`** — single-shot retries should be safe; adding the cache key would harden against double-fires from CLI shell loops.
- **Per-action scope check on `GET /api` discovery index** — currently relies on the general auth middleware; could gate behind `meta.discover` if we want to hide the surface from narrow-scope agents.

All deferred items are tracked in the Pass 2+ epic: #453.
