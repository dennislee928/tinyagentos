import type { AppManifest } from "@/registry/app-registry";

export interface UserspaceAppRow {
  app_id: string;
  name: string;
  icon: string;
  app_type: "web" | "container";
  version: string;
  enabled: number;
  permissions_requested: string[];
  permissions_granted: string[];
}

export function toAppManifest(row: UserspaceAppRow): AppManifest {
  return {
    id: row.app_id,
    name: row.name,
    icon: "layout-grid",
    category: "userspace",
    component: () =>
      import("@/apps/SandboxedAppWindow").then((m) => ({
        default: (props: { windowId: string }) =>
          m.SandboxedAppWindow({ ...props, appId: row.app_id }),
      })),
    defaultSize: { w: 900, h: 600 },
    minSize: { w: 360, h: 280 },
    singleton: true,
    pinned: false,
    launchpadOrder: 100,
  };
}

export async function fetchUserspaceApps(): Promise<AppManifest[]> {
  let rows: UserspaceAppRow[];
  try {
    const res = await fetch("/api/userspace-apps");
    if (!res.ok) return [];
    rows = (await res.json()) as UserspaceAppRow[];
  } catch {
    return [];
  }
  return rows.filter((r) => r.enabled).map(toAppManifest);
}
