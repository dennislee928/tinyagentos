/**
 * Fetch wrappers for /api/desktop/browser/site-permissions.
 * All functions are silent on errors (return empty/false).
 *
 * Backend: tinyagentos/routes/desktop_browser/site_permission_routes.py
 *
 * Response shapes:
 *  GET  /api/desktop/browser/site-permissions?profile_id=…
 *       → { grants: SitePermissionGrant[] }
 *  DELETE /api/desktop/browser/site-permissions?profile_id=…&host_pattern=…&permission=…
 *       → 204 No Content
 */

export interface SitePermissionGrant {
  host_pattern: string;
  permission: string;
  state: string; // 'allow' | 'deny'
}

export async function listSitePermissions(profileId: string): Promise<SitePermissionGrant[]> {
  const params = new URLSearchParams({ profile_id: profileId });
  try {
    const resp = await fetch(`/api/desktop/browser/site-permissions?${params}`, {
      credentials: "include",
    });
    if (!resp.ok) return [];
    const body = await resp.json();
    return Array.isArray(body?.grants) ? body.grants : [];
  } catch {
    return [];
  }
}

export async function revokeSitePermission(
  profileId: string,
  hostPattern: string,
  permission: string,
): Promise<boolean> {
  const params = new URLSearchParams({
    profile_id: profileId,
    host_pattern: hostPattern,
    permission,
  });
  try {
    const resp = await fetch(`/api/desktop/browser/site-permissions?${params}`, {
      method: "DELETE",
      credentials: "include",
    });
    return resp.ok;
  } catch {
    return false;
  }
}
