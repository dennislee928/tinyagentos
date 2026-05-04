import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserApp } from "./BrowserApp";
import { useBrowserStore } from "@/stores/browser-store";

const TEST_WINDOW_ID = "win-test";

beforeEach(() => {
  useBrowserStore.setState({ windows: {} });
});

describe("BrowserApp — composition", () => {
  it("auto-creates the window in browser-store on mount", () => {
    render(<BrowserApp windowId={TEST_WINDOW_ID} />);
    const win = useBrowserStore.getState().getWindow(TEST_WINDOW_ID);
    expect(win).toBeDefined();
    expect(win?.profileId).toBe("personal");
    expect(win?.tabs.length).toBe(1);
  });

  it("renders Chrome (back/forward/refresh + profile chip)", () => {
    render(<BrowserApp windowId={TEST_WINDOW_ID} />);
    expect(screen.getByRole("button", { name: /back/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /forward/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /refresh|reload/i })).toBeTruthy();
    expect(screen.getByLabelText(/profile/i)).toBeTruthy();
  });

  it("renders TabStrip with at least one tab", () => {
    render(<BrowserApp windowId={TEST_WINDOW_ID} />);
    expect(screen.getAllByRole("tab").length).toBeGreaterThanOrEqual(1);
  });

  it("renders TabRenderer with one iframe (the default new-tab)", () => {
    const { container } = render(<BrowserApp windowId={TEST_WINDOW_ID} />);
    expect(container.querySelectorAll("iframe").length).toBe(1);
  });

  it("renders AddressBar input", () => {
    render(<BrowserApp windowId={TEST_WINDOW_ID} />);
    expect(screen.getByLabelText("Address")).toBeTruthy();
  });

  it("does not duplicate window if already in store (idempotent on mount)", () => {
    useBrowserStore.getState().createWindow(TEST_WINDOW_ID, "work");
    render(<BrowserApp windowId={TEST_WINDOW_ID} />);
    const win = useBrowserStore.getState().getWindow(TEST_WINDOW_ID);
    expect(win?.profileId).toBe("work"); // Existing window preserved, NOT overwritten with "personal"
  });
});
