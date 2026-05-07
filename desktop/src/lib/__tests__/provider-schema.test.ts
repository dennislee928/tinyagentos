/**
 * Drift guard: hardcoded provider type arrays should not exist outside
 * provider-schema.ts. Catches the frontend equivalent of the duplication
 * bug that motivated #351.
 *
 * Plus tests for the schema fetch behaviour.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { fetchProviderSchema, resetSchemaCache } from "../provider-schema";

const SRC_ROOT = resolve(__dirname, "..", "..");
const ALLOWLIST = new Set([
  resolve(__dirname, "..", "provider-schema.ts"),
  resolve(__dirname, "provider-schema.test.ts"),
]);

const FORBIDDEN_PATTERNS = [
  /CLOUD_TYPES\s*=\s*\[/,
  /LOCAL_TYPES\s*=\s*\[/,
  /CLOUD_PROVIDER_META\s*=\s*\{/,
];

function* walkTs(dir: string): Generator<string> {
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return;
  }
  for (const entry of entries) {
    if (entry === "node_modules" || entry === "dist" || entry === ".git") continue;
    const full = join(dir, entry);
    let stat;
    try {
      stat = statSync(full);
    } catch {
      continue;
    }
    if (stat.isDirectory()) {
      yield* walkTs(full);
    } else if (full.endsWith(".ts") || full.endsWith(".tsx")) {
      if (!full.endsWith(".spec.ts") && !full.endsWith(".spec.tsx")) {
        yield full;
      }
    }
  }
}

describe("provider schema drift guard", () => {
  afterEach(() => {
    resetSchemaCache();
    vi.restoreAllMocks();
  });

  it("no other file hardcodes provider type lists", () => {
    const offenders: string[] = [];
    for (const file of walkTs(SRC_ROOT)) {
      if (ALLOWLIST.has(file)) continue;
      let text: string;
      try {
        text = readFileSync(file, "utf8");
      } catch {
        continue;
      }
      for (const pat of FORBIDDEN_PATTERNS) {
        const m = text.match(pat);
        if (m) offenders.push(`${file}: ${m[0]}`);
      }
    }
    expect(offenders, `Hardcoded provider lists found:\n${offenders.join("\n")}`).toEqual([]);
  });

  it("fetches and caches schema", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          providers: [
            {
              id: "openai",
              category: "cloud",
              label: "OpenAI",
              description: "...",
              default_url: "x",
              key_placeholder: "y",
              litellm_prefix: "openai",
            },
          ],
        }),
        { status: 200 }
      )
    );
    vi.stubGlobal("fetch", fetchMock);
    const r1 = await fetchProviderSchema();
    expect(r1.length).toBe(1);
    const r2 = await fetchProviderSchema();
    expect(r2).toBe(r1); // same reference, cached
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to empty list on fetch failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    const r = await fetchProviderSchema();
    expect(r).toEqual([]);
  });

  it("falls back to empty list on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Unauthorized", { status: 401 }))
    );
    const r = await fetchProviderSchema();
    expect(r).toEqual([]);
  });
});
