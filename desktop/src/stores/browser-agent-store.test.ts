import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  useBrowserAgentStore,
  MIN_PANEL_WIDTH,
  MAX_PANEL_WIDTH,
  DEFAULT_PANEL_WIDTH,
  WATCHING_DECAY_MS,
  MAX_RECENT_EVENTS,
} from "./browser-agent-store";

beforeEach(() => {
  useBrowserAgentStore.setState({
    panels: {},
    lastEventAt: {},
    messages: {},
    recentEvents: {},
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("browser-agent-store: openPanel", () => {
  it("creates a new panel entry with default width when none exists", () => {
    const s = useBrowserAgentStore.getState();
    s.openPanel("win-1", "tab-1", "agent-a");

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel).toBeDefined();
    expect(panel.isOpen).toBe(true);
    expect(panel.activeAgentId).toBe("agent-a");
    expect(panel.width).toBe(DEFAULT_PANEL_WIDTH);
  });

  it("preserves existing width when re-opening", () => {
    const s = useBrowserAgentStore.getState();
    s.openPanel("win-1", "tab-1", "agent-a");
    s.setPanelWidth("win-1", "tab-1", 350);
    s.closePanel("win-1", "tab-1");
    s.openPanel("win-1", "tab-1", "agent-b");

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel.width).toBe(350);
    expect(panel.isOpen).toBe(true);
    expect(panel.activeAgentId).toBe("agent-b");
  });
});

describe("browser-agent-store: closePanel", () => {
  it("sets isOpen to false without removing the entry", () => {
    const s = useBrowserAgentStore.getState();
    s.openPanel("win-1", "tab-1", "agent-a");
    s.closePanel("win-1", "tab-1");

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel).toBeDefined();
    expect(panel.isOpen).toBe(false);
  });

  it("is a no-op if panel doesn't exist", () => {
    const s = useBrowserAgentStore.getState();
    s.closePanel("win-1", "tab-missing");
    expect(useBrowserAgentStore.getState().panels["win-1:tab-missing"]).toBeUndefined();
  });
});

describe("browser-agent-store: setPanelWidth", () => {
  it("clamps width below min to 240", () => {
    const s = useBrowserAgentStore.getState();
    s.openPanel("win-1", "tab-1", "agent-a");
    s.setPanelWidth("win-1", "tab-1", 100);

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel.width).toBe(MIN_PANEL_WIDTH);
  });

  it("clamps width above max to 480", () => {
    const s = useBrowserAgentStore.getState();
    s.openPanel("win-1", "tab-1", "agent-a");
    s.setPanelWidth("win-1", "tab-1", 999);

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel.width).toBe(MAX_PANEL_WIDTH);
  });

  it("accepts width within range", () => {
    const s = useBrowserAgentStore.getState();
    s.openPanel("win-1", "tab-1", "agent-a");
    s.setPanelWidth("win-1", "tab-1", 320);

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel.width).toBe(320);
  });

  it("is a no-op if panel doesn't exist (must be opened first)", () => {
    const s = useBrowserAgentStore.getState();
    s.setPanelWidth("win-1", "tab-missing", 300);
    expect(useBrowserAgentStore.getState().panels["win-1:tab-missing"]).toBeUndefined();
  });
});

describe("browser-agent-store: togglePanel", () => {
  it("opens when closed", () => {
    const s = useBrowserAgentStore.getState();
    // Panel doesn't exist yet (treated as closed)
    s.togglePanel("win-1", "tab-1", "agent-a");

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel.isOpen).toBe(true);
  });

  it("closes when open", () => {
    const s = useBrowserAgentStore.getState();
    s.openPanel("win-1", "tab-1", "agent-a");
    s.togglePanel("win-1", "tab-1", "agent-a");

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel.isOpen).toBe(false);
  });
});

describe("browser-agent-store: setActiveAgent", () => {
  it("updates active agent when panel exists", () => {
    const s = useBrowserAgentStore.getState();
    s.openPanel("win-1", "tab-1", "agent-a");
    s.setActiveAgent("win-1", "tab-1", "agent-b");

    const panel = useBrowserAgentStore.getState().panels["win-1:tab-1"];
    expect(panel.activeAgentId).toBe("agent-b");
  });

  it("is a no-op if panel doesn't exist", () => {
    const s = useBrowserAgentStore.getState();
    s.setActiveAgent("win-1", "tab-missing", "agent-a");
    expect(useBrowserAgentStore.getState().panels["win-1:tab-missing"]).toBeUndefined();
  });
});

describe("browser-agent-store: bumpEventAt + isWatching", () => {
  it("isWatching returns true within WATCHING_DECAY_MS of bumpEventAt", () => {
    vi.useFakeTimers();
    const now = Date.now();
    vi.setSystemTime(now);

    const s = useBrowserAgentStore.getState();
    s.bumpEventAt("win-1", "tab-1", "agent-a");

    expect(useBrowserAgentStore.getState().isWatching("win-1", "tab-1", "agent-a")).toBe(true);
  });

  it("isWatching returns false after WATCHING_DECAY_MS expires (use vi.useFakeTimers)", () => {
    vi.useFakeTimers();
    const now = Date.now();
    vi.setSystemTime(now);

    const s = useBrowserAgentStore.getState();
    s.bumpEventAt("win-1", "tab-1", "agent-a");

    vi.setSystemTime(now + WATCHING_DECAY_MS + 1);
    expect(useBrowserAgentStore.getState().isWatching("win-1", "tab-1", "agent-a")).toBe(false);
  });

  it("isWatching returns false when no event has been bumped", () => {
    const s = useBrowserAgentStore.getState();
    expect(s.isWatching("win-1", "tab-1", "agent-nobody")).toBe(false);
  });

  it("bumpEventAt accepts an explicit timestamp", () => {
    vi.useFakeTimers();
    const explicitTs = Date.now() - 1000; // 1 second ago

    const s = useBrowserAgentStore.getState();
    s.bumpEventAt("win-1", "tab-1", "agent-a", explicitTs);

    const stored = useBrowserAgentStore.getState().lastEventAt["win-1:tab-1:agent-a"];
    expect(stored).toBe(explicitTs);
    // Should still be watching (1s < WATCHING_DECAY_MS=3s)
    expect(useBrowserAgentStore.getState().isWatching("win-1", "tab-1", "agent-a")).toBe(true);
  });
});

describe("browser-agent-store: appendMessage", () => {
  it("appends a message to an empty thread", () => {
    const s = useBrowserAgentStore.getState();
    s.appendMessage("win-1", "tab-1", "agent-a", {
      id: "msg-1",
      author: "user",
      content: "Hello",
      timestamp: 1000,
    });

    const msgs = useBrowserAgentStore.getState().messages["win-1:tab-1:agent-a"];
    expect(msgs).toHaveLength(1);
    expect(msgs[0].content).toBe("Hello");
    expect(msgs[0].author).toBe("user");
  });

  it("appends multiple messages in order", () => {
    const s = useBrowserAgentStore.getState();
    s.appendMessage("win-1", "tab-1", "agent-a", { id: "1", author: "user", content: "First", timestamp: 1000 });
    s.appendMessage("win-1", "tab-1", "agent-a", { id: "2", author: "agent", content: "Second", timestamp: 2000 });

    const msgs = useBrowserAgentStore.getState().messages["win-1:tab-1:agent-a"];
    expect(msgs).toHaveLength(2);
    expect(msgs[0].content).toBe("First");
    expect(msgs[1].content).toBe("Second");
  });

  it("keeps threads for different (tab, agent) pairs separate", () => {
    const s = useBrowserAgentStore.getState();
    s.appendMessage("win-1", "tab-1", "agent-a", { id: "1", author: "user", content: "Tab1 A", timestamp: 1000 });
    s.appendMessage("win-1", "tab-1", "agent-b", { id: "2", author: "user", content: "Tab1 B", timestamp: 1000 });

    const msgsA = useBrowserAgentStore.getState().messages["win-1:tab-1:agent-a"];
    const msgsB = useBrowserAgentStore.getState().messages["win-1:tab-1:agent-b"];
    expect(msgsA).toHaveLength(1);
    expect(msgsB).toHaveLength(1);
    expect(msgsA[0].content).toBe("Tab1 A");
    expect(msgsB[0].content).toBe("Tab1 B");
  });
});

describe("browser-agent-store: appendEvent", () => {
  it("appends an event to an empty list", () => {
    const s = useBrowserAgentStore.getState();
    s.appendEvent("win-1", "tab-1", "agent-a", {
      kind: "page-changed",
      title: "Example",
      url: "https://example.com",
      timestamp: 1000,
    });

    const events = useBrowserAgentStore.getState().recentEvents["win-1:tab-1:agent-a"];
    expect(events).toHaveLength(1);
    expect(events[0].kind).toBe("page-changed");
    expect(events[0].title).toBe("Example");
  });

  it(`caps events at MAX_RECENT_EVENTS (${MAX_RECENT_EVENTS})`, () => {
    const s = useBrowserAgentStore.getState();
    for (let i = 0; i < MAX_RECENT_EVENTS + 2; i++) {
      s.appendEvent("win-1", "tab-1", "agent-a", {
        kind: "url-changed",
        url: `https://example.com/${i}`,
        timestamp: 1000 + i,
      });
    }

    const events = useBrowserAgentStore.getState().recentEvents["win-1:tab-1:agent-a"];
    expect(events).toHaveLength(MAX_RECENT_EVENTS);
    // Should keep the most recent events (last MAX_RECENT_EVENTS)
    expect(events[events.length - 1].url).toBe(`https://example.com/${MAX_RECENT_EVENTS + 1}`);
  });

  it("keeps events for different (tab, agent) pairs separate", () => {
    const s = useBrowserAgentStore.getState();
    s.appendEvent("win-1", "tab-1", "agent-a", { kind: "scroll", timestamp: 1000 });
    s.appendEvent("win-1", "tab-1", "agent-b", { kind: "page-changed", title: "B", timestamp: 1000 });

    const eventsA = useBrowserAgentStore.getState().recentEvents["win-1:tab-1:agent-a"];
    const eventsB = useBrowserAgentStore.getState().recentEvents["win-1:tab-1:agent-b"];
    expect(eventsA).toHaveLength(1);
    expect(eventsB).toHaveLength(1);
    expect(eventsA[0].kind).toBe("scroll");
    expect(eventsB[0].kind).toBe("page-changed");
  });
});
