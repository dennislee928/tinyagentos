#!/usr/bin/env python3
"""A-tier conformance smoke — live-LLM run against a deployed taOS instance.

Pass 1 ships the scaffold. The B + C tier suites in tests/conformance/
already cover the canonical contract per-commit; this script is the
nightly check that a real LLM agent — using only the public docs +
CLI + REST surface — can actually accomplish things end-to-end.

For each task, an agent is given a goal in plain English; the agent
navigates the documented surface to complete it; this script verifies
the side effect on the server. Outcomes:

  - succeeded:   side effect was created as the goal described
  - wrong_path:  agent finished without the expected side effect
  - gave_up:     agent errored / timed out / refused

Run manually:

    python3 scripts/conformance-smoke.py \\
      --controller http://localhost:6969 \\
      --token taos_agent_<wide-scope-token> \\
      --report-json /tmp/smoke.json

Wiring the actual agent runtime is the operator's responsibility — see
`run_agent_task` below. The plan calls for the `kilo-auto/free` provider
(see the throwaway-agent policy in memory) but any agent runtime that
honours `TAOS_URL` + `TAOS_TOKEN` env vars + can navigate the docs at
`/docs/agents/` would work.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

import httpx


@dataclass
class SmokeResult:
    task: str
    outcome: str  # succeeded | wrong_path | gave_up
    detail: str


SMOKE_TASKS: list[dict[str, Any]] = [
    {
        "name": "create-agent",
        "prompt": (
            "Create a new taOS agent named 'smoke-1' with host '192.0.2.250' "
            "and qmd_index 'smoke-test'. Use the documented REST API or the "
            "`taosctl agents create` CLI. The agent does not need to be deployed "
            "or started — registering the config row is enough."
        ),
        "verify": "agent_exists",
        "verify_args": {"name": "smoke-1"},
    },
    {
        "name": "send-notification",
        "prompt": (
            "Send a notification to the user with title 'A-tier smoke' and body "
            "'reachable'. Use POST /api/ui/notify or `taosctl ui notify`."
        ),
        "verify": "notification_exists",
        "verify_args": {"title": "A-tier smoke"},
    },
    {
        "name": "issue-and-use-token",
        "prompt": (
            "Issue a fresh API token for the agent named 'smoke-1', then use "
            "that token to authenticate a `GET /api/agents` call and confirm "
            "smoke-1 appears in the list."
        ),
        "verify": "agent_has_token",
        "verify_args": {"name": "smoke-1"},
    },
]


async def run_agent_task(prompt: str, controller_url: str, token: str) -> dict:
    """Invoke the operator-supplied agent runtime.

    The agent should:
      1. Receive `prompt` and the env vars TAOS_URL=controller_url +
         TAOS_TOKEN=token.
      2. Have read-only access to `/docs/agents/` (markdown files in this
         repo) plus the live `/openapi.json`.
      3. Use whatever interface it prefers (HTTP, taosctl CLI) to attempt
         the goal.
      4. Return a structured outcome (anything JSON-serialisable).

    The implementation here is intentionally a hook: integrating with the
    Anthropic/OpenAI/kilocode SDK (or a local agent harness) is the
    operator's call, and the choice is environment-specific (CI runner,
    nightly box, etc.). When wired, the operator implements this function
    or monkey-patches it before running the script.
    """
    raise NotImplementedError(
        "run_agent_task is the integration hook — wire your agent runtime "
        "here. See the docstring for the contract."
    )


async def verify_outcome(
    verify_kind: str,
    verify_args: dict[str, Any],
    controller_url: str,
    token: str,
) -> tuple[bool, str]:
    """Check whether the agent's task produced the documented side effect."""
    async with httpx.AsyncClient(
        base_url=controller_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    ) as client:
        if verify_kind == "agent_exists":
            r = await client.get(f"/api/agents/{verify_args['name']}")
            return r.status_code == 200, f"GET /api/agents/{verify_args['name']} -> {r.status_code}"
        if verify_kind == "agent_has_token":
            r = await client.get(f"/api/agents/{verify_args['name']}")
            if r.status_code != 200:
                return False, f"agent missing: {r.status_code}"
            body = r.json()
            return bool(body.get("has_token")), f"has_token={body.get('has_token')}"
        if verify_kind == "notification_exists":
            r = await client.get("/api/notifications?limit=20")
            if r.status_code != 200:
                return False, f"GET /api/notifications -> {r.status_code}"
            items = r.json()
            found = any(n.get("title") == verify_args["title"] for n in items)
            return found, f"matching notification {'found' if found else 'absent'}"
    return False, f"unknown verify kind: {verify_kind}"


async def run_smoke(controller_url: str, token: str) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    for task in SMOKE_TASKS:
        try:
            outcome = await run_agent_task(task["prompt"], controller_url, token)
            verified, detail = await verify_outcome(
                task["verify"], task["verify_args"], controller_url, token
            )
            if verified:
                results.append(
                    SmokeResult(task=task["name"], outcome="succeeded", detail=detail)
                )
            else:
                results.append(
                    SmokeResult(
                        task=task["name"],
                        outcome="wrong_path",
                        detail=f"agent: {str(outcome)[:120]}; verify: {detail}",
                    )
                )
        except NotImplementedError as exc:
            results.append(
                SmokeResult(
                    task=task["name"],
                    outcome="gave_up",
                    detail=str(exc),
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                SmokeResult(
                    task=task["name"],
                    outcome="gave_up",
                    detail=f"{type(exc).__name__}: {str(exc)[:150]}",
                )
            )
    return results


def format_summary(results: list[SmokeResult]) -> dict[str, Any]:
    return {
        "totals": {
            "succeeded": sum(1 for r in results if r.outcome == "succeeded"),
            "wrong_path": sum(1 for r in results if r.outcome == "wrong_path"),
            "gave_up": sum(1 for r in results if r.outcome == "gave_up"),
        },
        "results": [asdict(r) for r in results],
    }


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--controller", required=True, help="Controller base URL.")
    parser.add_argument("--token", required=True, help="Wide-scope agent bearer.")
    parser.add_argument(
        "--report-json",
        default="-",
        help="Output path for JSON summary ('-' for stdout).",
    )
    args = parser.parse_args()

    results = await run_smoke(args.controller, args.token)
    summary = format_summary(results)
    rendered = json.dumps(summary, indent=2)
    if args.report_json == "-":
        sys.stdout.write(rendered + "\n")
    else:
        with open(args.report_json, "w", encoding="utf-8") as fh:
            fh.write(rendered + "\n")

    # Exit non-zero if anything didn't succeed — lets CI / nightly cron
    # mark the run red.
    return 0 if summary["totals"]["gave_up"] == 0 and summary["totals"]["wrong_path"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
