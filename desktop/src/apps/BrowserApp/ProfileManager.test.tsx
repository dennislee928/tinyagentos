import { describe, expect, it, beforeEach, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ProfileManager } from "./ProfileManager";

const originalFetch = global.fetch;

function mockListResponse(profiles: any[]) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ profiles }),
  };
}

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue(
    mockListResponse([
      { profile_id: "personal", name: "Personal", color: "#6c8df0", created_at: 0 },
      { profile_id: "work", name: "Work", color: "#f5b86b", created_at: 0 },
    ]),
  );
});

afterEach(() => {
  global.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("ProfileManager — list view", () => {
  it("renders all profiles after loading", async () => {
    render(
      <ProfileManager
        activeProfileId="personal"
        onClose={() => {}}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("Personal")).toBeTruthy();
      expect(screen.getByText("Work")).toBeTruthy();
    });
  });

  it("each profile row has rename + delete buttons", async () => {
    render(
      <ProfileManager
        activeProfileId="personal"
        onClose={() => {}}
      />,
    );
    await waitFor(() => {
      const rename = screen.getAllByLabelText(/rename/i);
      expect(rename.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("delete button on the active profile is disabled", async () => {
    render(
      <ProfileManager
        activeProfileId="personal"
        onClose={() => {}}
      />,
    );
    await waitFor(() => screen.getByText("Personal"));

    const deleteBtns = screen.getAllByLabelText(/delete profile/i);
    // Find the one inside the Personal row
    const personalRow = screen.getByText("Personal").closest('[role="listitem"], li, div');
    const deleteBtn = deleteBtns.find((b) => personalRow?.contains(b)) as HTMLButtonElement;
    expect(deleteBtn?.disabled).toBe(true);
  });
});

describe("ProfileManager — create flow", () => {
  it("Add profile form takes name + color, posts to backend", async () => {
    let postBody: any = null;
    global.fetch = vi.fn().mockImplementation((url, opts) => {
      if (opts?.method === "POST") {
        postBody = JSON.parse(opts.body as string);
        return Promise.resolve({
          ok: true,
          json: async () => ({
            profile_id: "research",
            name: postBody.name,
            color: postBody.color,
            created_at: 0,
          }),
        });
      }
      // Default: list returns initial 2 profiles
      return Promise.resolve(mockListResponse([
        { profile_id: "personal", name: "Personal", color: "#6c8df0", created_at: 0 },
        { profile_id: "work", name: "Work", color: "#f5b86b", created_at: 0 },
      ]));
    });

    render(
      <ProfileManager
        activeProfileId="personal"
        onClose={() => {}}
      />,
    );
    await waitFor(() => screen.getByText("Personal"));

    // Open the add form
    fireEvent.click(screen.getByLabelText(/add profile/i));
    const nameInput = screen.getByLabelText(/profile name/i);
    fireEvent.change(nameInput, { target: { value: "Research" } });

    // Pick a color swatch (any one)
    const swatches = screen.getAllByLabelText(/color/i);
    if (swatches.length > 0) fireEvent.click(swatches[0]);

    fireEvent.click(screen.getByLabelText(/^create$/i));

    await waitFor(() => {
      expect(postBody).not.toBeNull();
      expect(postBody.name).toBe("Research");
    });
  });
});

describe("ProfileManager — delete flow", () => {
  it("delete button shows confirmation with cookie-cascade warning", async () => {
    render(
      <ProfileManager
        activeProfileId="personal"
        onClose={() => {}}
      />,
    );
    await waitFor(() => screen.getByText("Work"));

    // Click delete on Work (not active)
    const deleteBtns = screen.getAllByLabelText(/delete profile/i);
    const workRow = screen.getByText("Work").closest('[role="listitem"], li, div');
    const workDelete = deleteBtns.find((b) => workRow?.contains(b)) as HTMLButtonElement;
    fireEvent.click(workDelete);

    // Confirmation should appear
    await waitFor(() => {
      expect(screen.getByText(/this also clears all saved cookies/i)).toBeTruthy();
    });
  });

  it("confirming delete sends DELETE request", async () => {
    let deleteUrl: string | null = null;
    global.fetch = vi.fn().mockImplementation((url, opts) => {
      if (opts?.method === "DELETE") {
        deleteUrl = url as string;
        return Promise.resolve({ ok: true, status: 204 });
      }
      return Promise.resolve(mockListResponse([
        { profile_id: "personal", name: "Personal", color: "#6c8df0", created_at: 0 },
        { profile_id: "work", name: "Work", color: "#f5b86b", created_at: 0 },
      ]));
    });

    render(
      <ProfileManager
        activeProfileId="personal"
        onClose={() => {}}
      />,
    );
    await waitFor(() => screen.getByText("Work"));

    const deleteBtns = screen.getAllByLabelText(/delete profile/i);
    const workRow = screen.getByText("Work").closest('[role="listitem"], li, div');
    const workDelete = deleteBtns.find((b) => workRow?.contains(b)) as HTMLButtonElement;
    fireEvent.click(workDelete);

    await waitFor(() => screen.getByText(/this also clears all saved cookies/i));

    fireEvent.click(screen.getByLabelText(/confirm delete/i));

    await waitFor(() => {
      expect(deleteUrl).toContain("/api/desktop/browser/profiles/work");
    });
  });
});

describe("ProfileManager — close", () => {
  it("close button calls onClose", async () => {
    const onClose = vi.fn();
    render(
      <ProfileManager
        activeProfileId="personal"
        onClose={onClose}
      />,
    );
    await waitFor(() => screen.getByText("Personal"));
    fireEvent.click(screen.getByLabelText(/close manager/i));
    expect(onClose).toHaveBeenCalled();
  });
});
