/**
 * Provider type schema fetched from /api/providers/schema at boot.
 *
 * Single source of truth lives in tinyagentos/providers/types.py. The
 * frontend reads it via this module — do NOT add new hardcoded provider
 * type arrays anywhere in desktop/src; consume the schema instead.
 */
import { useEffect, useState } from "react";

export interface ProviderTypeSpec {
  id: string;
  category: "cloud" | "local";
  label: string;
  description: string;
  default_url: string;
  key_placeholder: string;
  litellm_prefix: string;
}

let cache: ProviderTypeSpec[] | null = null;
let inFlight: Promise<ProviderTypeSpec[]> | null = null;

export async function fetchProviderSchema(): Promise<ProviderTypeSpec[]> {
  if (cache) return cache;
  if (inFlight) return inFlight;
  inFlight = (async () => {
    try {
      const r = await fetch("/api/providers/schema", { credentials: "include" });
      if (!r.ok) throw new Error(`schema fetch failed: ${r.status}`);
      const json = await r.json();
      cache = (json.providers ?? []) as ProviderTypeSpec[];
      return cache;
    } catch (err) {
      console.warn("[provider-schema] fetch failed, falling back to empty list:", err);
      cache = [];
      return cache;
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

export function getCachedSchema(): ProviderTypeSpec[] | null {
  return cache;
}

export function resetSchemaCache(): void {
  cache = null;
  inFlight = null;
}

export function useProviderSchema(): { providers: ProviderTypeSpec[]; loaded: boolean } {
  const [providers, setProviders] = useState<ProviderTypeSpec[]>(() => getCachedSchema() ?? []);
  const [loaded, setLoaded] = useState<boolean>(getCachedSchema() !== null);
  useEffect(() => {
    if (loaded) return;
    let cancelled = false;
    fetchProviderSchema().then((p) => {
      if (cancelled) return;
      setProviders(p);
      setLoaded(true);
    });
    return () => { cancelled = true; };
  }, [loaded]);
  return { providers, loaded };
}
