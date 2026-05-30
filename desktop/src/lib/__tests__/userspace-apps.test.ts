import { describe, it, expect, vi } from "vitest";
import { fetchUserspaceApps, toAppManifest } from "../userspace-apps";

describe("userspace apps", () => {
  it("maps a userspace app row to an AppManifest in the 'userspace' category", () => {
    const m = toAppManifest({ app_id: "todo", name: "Todo", icon: "", app_type: "web", version: "1", enabled: 1, permissions_requested: [], permissions_granted: [] });
    expect(m.id).toBe("todo");
    expect(m.name).toBe("Todo");
    expect(m.category).toBe("userspace");
    expect(typeof m.component).toBe("function");
  });

  it("fetchUserspaceApps returns only enabled apps as manifests", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [
      { app_id: "a", name: "A", icon: "", app_type: "web", version: "1", enabled: 1, permissions_requested: [], permissions_granted: [] },
      { app_id: "b", name: "B", icon: "", app_type: "web", version: "1", enabled: 0, permissions_requested: [], permissions_granted: [] },
    ]}));
    const apps = await fetchUserspaceApps();
    expect(apps.map(a => a.id)).toEqual(["a"]);
    vi.unstubAllGlobals();
  });

  it("fetchUserspaceApps returns [] on fetch failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    expect(await fetchUserspaceApps()).toEqual([]);
    vi.unstubAllGlobals();
  });
});
