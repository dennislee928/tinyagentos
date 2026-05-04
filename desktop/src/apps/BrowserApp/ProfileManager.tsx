/**
 * Modal for full profile CRUD: rename + delete + create.
 *
 * Opened from ProfileSwitcher's "Manage profiles…" footer.
 *
 * - Active profile: delete button disabled (with tooltip)
 * - Last profile delete: backend rejects with 400; UI surfaces an error
 * - Delete confirmation includes explicit cookie-cascade warning
 * - Create form has 8 preset color swatches matching the chrome palette
 */
import { useEffect, useState } from "react";
import { Trash2, Edit2, Plus, X, Check } from "lucide-react";
import {
  listProfiles,
  createProfile,
  renameProfile,
  deleteProfile,
  type Profile,
} from "@/lib/browser-profile-api";

const COLOR_SWATCHES = [
  "#6c8df0",
  "#f5b86b",
  "#88aa44",
  "#cc6644",
  "#9966cc",
  "#44aabb",
  "#cc44aa",
  "#888888",
];

interface ProfileManagerProps {
  activeProfileId: string;
  onClose: () => void;
}

export function ProfileManager({ activeProfileId, onClose }: ProfileManagerProps) {
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState(COLOR_SWATCHES[0]);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    const fresh = await listProfiles();
    setProfiles(fresh);
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleRename(id: string) {
    if (!editName.trim()) {
      setEditingId(null);
      return;
    }
    const updated = await renameProfile(id, { name: editName.trim() });
    if (updated) {
      await reload();
    } else {
      setError("Rename failed");
    }
    setEditingId(null);
  }

  async function handleDelete(id: string) {
    const ok = await deleteProfile(id);
    if (ok) {
      await reload();
    } else {
      setError("Delete failed (cannot delete last profile)");
    }
    setConfirmDeleteId(null);
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    const created = await createProfile({ name: newName.trim(), color: newColor });
    if (created) {
      setNewName("");
      setNewColor(COLOR_SWATCHES[0]);
      setAdding(false);
      await reload();
    } else {
      setError("Create failed");
    }
  }

  return (
    <div
      role="dialog"
      aria-label="Manage profiles"
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="bg-shell-surface rounded-md shadow-xl border border-shell-border w-[420px] max-w-full max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-4 py-3 border-b border-shell-border-subtle">
          <h2 className="text-sm font-medium">Manage profiles</h2>
          <button
            type="button"
            aria-label="Close manager"
            onClick={onClose}
            className="p-1 rounded hover:bg-shell-hover"
          >
            <X size={16} />
          </button>
        </header>

        {error && (
          <div className="mx-4 mt-3 px-3 py-2 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
            {error}
          </div>
        )}

        <ul role="list" className="flex-1 overflow-y-auto py-2 px-2">
          {profiles === null ? (
            <li className="px-2 py-2 text-xs opacity-60 italic">Loading…</li>
          ) : profiles.length === 0 ? (
            <li className="px-2 py-2 text-xs opacity-60 italic">No profiles</li>
          ) : (
            profiles.map((p) => {
              const isActive = p.profile_id === activeProfileId;
              return (
                <li
                  key={p.profile_id}
                  role="listitem"
                  className="flex items-center gap-2 px-2 py-2 hover:bg-shell-hover rounded"
                >
                  <span
                    className="inline-block w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: p.color ?? "#8b92a3" }}
                    aria-hidden="true"
                  />
                  {editingId === p.profile_id ? (
                    <input
                      type="text"
                      autoFocus
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onBlur={() => handleRename(p.profile_id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRename(p.profile_id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="flex-1 bg-shell-bg-deep border border-shell-border-subtle rounded px-1.5 py-0.5 text-xs outline-none focus:border-accent"
                    />
                  ) : (
                    <span className="flex-1 text-sm">{p.name}</span>
                  )}
                  <button
                    type="button"
                    aria-label={`Rename ${p.name}`}
                    onClick={() => {
                      setEditingId(p.profile_id);
                      setEditName(p.name);
                    }}
                    className="p-1 rounded hover:bg-shell-hover"
                  >
                    <Edit2 size={12} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete profile ${p.name}`}
                    disabled={isActive}
                    title={isActive ? "Cannot delete the active profile" : "Delete"}
                    onClick={() => setConfirmDeleteId(p.profile_id)}
                    className="p-1 rounded hover:bg-shell-hover disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <Trash2 size={12} />
                  </button>
                </li>
              );
            })
          )}
        </ul>

        {/* Add profile section */}
        <div className="border-t border-shell-border-subtle p-2">
          {adding ? (
            <div className="space-y-2 px-2 py-1">
              <input
                type="text"
                aria-label="Profile name"
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Profile name"
                className="w-full bg-shell-bg-deep border border-shell-border-subtle rounded px-2 py-1 text-xs outline-none focus:border-accent"
              />
              <div className="flex gap-1.5 items-center" role="radiogroup" aria-label="Profile color">
                {COLOR_SWATCHES.map((c) => (
                  <button
                    key={c}
                    type="button"
                    role="radio"
                    aria-label={`Color ${c}`}
                    aria-checked={newColor === c}
                    onClick={() => setNewColor(c)}
                    className={[
                      "w-5 h-5 rounded-full border-2",
                      newColor === c ? "border-accent" : "border-transparent",
                    ].join(" ")}
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
              <div className="flex gap-1 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setAdding(false);
                    setNewName("");
                    setNewColor(COLOR_SWATCHES[0]);
                  }}
                  className="px-2 py-1 rounded hover:bg-shell-hover text-xs"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  aria-label="Create"
                  onClick={handleCreate}
                  className="px-2 py-1 rounded bg-accent text-shell-bg text-xs"
                >
                  Create
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              aria-label="Add profile"
              onClick={() => setAdding(true)}
              className="w-full text-left px-2 py-1.5 hover:bg-shell-hover flex items-center gap-1.5 text-xs"
            >
              <Plus size={12} />
              Add profile
            </button>
          )}
        </div>

        {/* Delete confirmation */}
        {confirmDeleteId && (
          <div
            role="alertdialog"
            aria-label="Delete profile confirmation"
            className="absolute inset-0 z-10 flex items-center justify-center bg-black/30 rounded-md"
          >
            <div className="bg-shell-surface border border-shell-border rounded shadow-xl p-4 max-w-[320px] w-full mx-3">
              <p className="text-sm mb-1">
                Delete profile{" "}
                <strong>
                  {profiles?.find((p) => p.profile_id === confirmDeleteId)?.name ?? confirmDeleteId}
                </strong>?
              </p>
              <p className="text-xs text-shell-text-secondary mb-3">
                This also clears all saved cookies for this profile.
              </p>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setConfirmDeleteId(null)}
                  className="px-3 py-1 rounded hover:bg-shell-hover text-xs"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  aria-label="Confirm delete"
                  onClick={() => handleDelete(confirmDeleteId)}
                  className="px-3 py-1 rounded bg-red-500 text-white text-xs flex items-center gap-1"
                >
                  <Check size={12} />
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
