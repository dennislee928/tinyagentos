# Concept: Permissions

taOS uses a two-layer permission model for agents:

1. **User-mirroring ceiling.** Every agent is associated with a user. The
   agent can never do anything the user themselves can't do. This is the hard
   security boundary — enforced at the data layer, not at the API layer.
2. **Tool-set scoping.** Within the user's ceiling, an agent's bearer token
   carries a `scope` — a list of glob patterns matching the `noun.verb`
   action structure. Out-of-scope calls return a canonical 403
   `scope_denied`.

## Scope syntax

| Pattern | Matches | Examples |
|---|---|---|
| `*` | Everything | `agents.list`, `ui.notify`, `agents.token.issue`, … |
| `agents.*` | Any verb in the `agents` namespace | `agents.list`, `agents.create`, `agents.delete`, … |
| `agents.token.*` | Both token verbs | `agents.token.issue`, `agents.token.revoke` |
| `agents.list` | Exact match — list only | `agents.list` |

Matching is `fnmatch`-style: `*` is a wildcard, exact strings are exact.
Combine multiple patterns in the list; any match grants access.

## Action slug taxonomy (Pass 1)

The AgentsApp routes are gated by these action slugs. The full mapping lives
on each endpoint decorator in `tinyagentos/routes/agents.py`.

| Slug | Covers |
|---|---|
| `agents.list` | `GET /api/agents`, `GET /api/agents/containers`, `GET /api/agents/archived` |
| `agents.read` | `GET /api/agents/{name}`, `GET /api/agents/{name}/deploy-status` |
| `agents.logs` | `GET /api/agents/{name}/logs` |
| `agents.create` | `POST /api/agents` (register a new agent config row) |
| `agents.update` | `PUT /api/agents/{name}`, `PUT /api/agents/{name}/permissions`, `POST /api/agents/{name}/dismiss-migration-banner` |
| `agents.delete` | `DELETE /api/agents/{name}` (archives by default), plus archived-agent purge endpoints |
| `agents.deploy` | `POST /api/agents/deploy` (the real container deploy) |
| `agents.lifecycle` | `POST /api/agents/{name}/start|stop|pause|restart`, plus `POST /api/agents/bulk/*` |
| `agents.token.issue` | `POST /api/agents/{name}/token/issue` |
| `agents.token.revoke` | `DELETE /api/agents/{name}/token` |
| `ui.notify` | `POST /api/ui/notify` (the agent-to-UI primitive) |

## Default scope

Every newly issued token gets `scope = ["*"]` — full user-mirroring. This is
the "no compromise" default: an agent can do anything its user can do, no
setup needed. Operators narrow scope explicitly when an agent should be
constrained.

## Narrowing scope

Today, scope is supplied at token-issue time. Reissuing a token replaces the
previous one atomically (the old plaintext stops authenticating immediately).
A future `PUT /api/agents/{name}/permissions` will accept a `scope` field
and apply it to the next issued token; for now, pass it via the issue call.

When a call exceeds the token's scope, the response is:

```json
{
  "error": "scope_denied",
  "detail": "Token scope does not cover 'agents.deploy'.",
  "fix": "Reissue the token with a wider scope (e.g. ['*'] for full access) via POST /api/agents/{name}/token/issue, or have the operator widen the agent's permissions.",
  "doc_url": "/docs/agents/concepts/permissions"
}
```

## Session cookies vs bearer tokens

Scope only applies to **bearer tokens**. A logged-in human using the desktop
UI authenticates via the `taos_session` cookie and is not scope-gated — they
have the full ceiling of their user account. Scope is the *delegated-access*
mechanism for the agents acting on their behalf.

## Why this shape

- **Default is permissive** because the typical case is a user wanting their
  agent to act as them. Friction here pushes users toward overly broad
  workarounds.
- **Narrowing is opt-in** because some agents have specific jobs (a
  code-review agent doesn't need `agents.deploy`).
- **User-mirroring is the ceiling** because security is enforced at the user
  boundary, not at the agent boundary — same principle as the existing
  multi-user isolation in taOS.

## See also

- [`../getting-started.md`](../getting-started.md) for token issuance.
- [`../recipes/managing-agents.md`](../recipes/managing-agents.md) for the
  issue/revoke flow.
