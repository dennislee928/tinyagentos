import { describe, it, expect, beforeEach, vi } from "vitest";
import { openParentWs, type AgentWsBridgeOptions } from "./agent-ws-bridge";

/**
 * In the new architecture (post-Opus whole-branch review), the parent does
 * NOT open its own WebSocket. Instead, copilot.js (running in the iframe)
 * forwards server events to the parent via postMessage as
 *   { type: "taos-copilot:server-event", agentId, message }
 *
 * openParentWs registers a window message listener that filters by source
 * iframe + agentId, normalises message.event → AgentEvent.kind, and calls
 * the supplied onEvent callback.
 */

// ─── Helpers ──────────────────────────────────────────────────────────────────

interface FakeIframe {
  contentWindow: object;
}

function makeIframe(): HTMLIFrameElement {
  const fakeWin = {};
  return { contentWindow: fakeWin } as unknown as HTMLIFrameElement;
}

function makeOpts(overrides?: Partial<AgentWsBridgeOptions>): AgentWsBridgeOptions {
  return {
    windowId: "win-1",
    tabId: "tab-1",
    agentId: "agent-1",
    iframe: makeIframe(),
    onEvent: vi.fn(),
    onOpen: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  };
}

/** Dispatch a message event with a chosen source. JSDOM's MessageEvent
 * constructor doesn't honour the `source` option, so we override via
 * Object.defineProperty before dispatch. */
function dispatchMessageFrom(source: object | null, data: unknown): void {
  const ev = new MessageEvent("message", { data });
  Object.defineProperty(ev, "source", { value: source, configurable: true });
  window.dispatchEvent(ev);
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("openParentWs (postMessage-based)", () => {
  it("isOpen is true after creation (no async ticket round-trip)", () => {
    const opts = makeOpts();
    const handle = openParentWs(opts);
    expect(handle.isOpen).toBe(true);
  });

  it("does NOT open a WebSocket (sanity: no fetch/WS APIs touched)", () => {
    // The whole point of the new design is no WebSocket on the parent.
    // If a WebSocket constructor gets called we'll see it via global mock.
    const ctor = vi.fn();
    (global as unknown as Record<string, unknown>).WebSocket = ctor;
    const opts = makeOpts();
    openParentWs(opts);
    expect(ctor).not.toHaveBeenCalled();
  });

  it("calls onEvent when iframe forwards a page-changed event", () => {
    const opts = makeOpts();
    openParentWs(opts);

    dispatchMessageFrom(opts.iframe.contentWindow, {
      type: "taos-copilot:server-event",
      agentId: "agent-1",
      message: {
        event: "page-changed",
        url: "https://example.com/",
        title: "Example",
        timestamp: 12345,
      },
    });

    expect(opts.onEvent).toHaveBeenCalledOnce();
    const received = vi.mocked(opts.onEvent).mock.calls[0][0];
    expect(received.kind).toBe("page-changed");
    expect(received.url).toBe("https://example.com/");
    expect(received.title).toBe("Example");
    expect(received.timestamp).toBe(12345);
  });

  it("transforms url-changed and scroll kinds", () => {
    const opts = makeOpts();
    openParentWs(opts);

    dispatchMessageFrom(opts.iframe.contentWindow, {
      type: "taos-copilot:server-event",
      agentId: "agent-1",
      message: { event: "url-changed", url: "https://a.com/" },
    });
    dispatchMessageFrom(opts.iframe.contentWindow, {
      type: "taos-copilot:server-event",
      agentId: "agent-1",
      message: { event: "scroll" },
    });

    const calls = vi.mocked(opts.onEvent).mock.calls;
    expect(calls).toHaveLength(2);
    expect(calls[0][0].kind).toBe("url-changed");
    expect(calls[1][0].kind).toBe("scroll");
  });

  it("rejects messages whose source is not the iframe (cross-frame protection)", () => {
    const opts = makeOpts();
    openParentWs(opts);

    // A message from a DIFFERENT window object — must be ignored
    dispatchMessageFrom({}, {
      type: "taos-copilot:server-event",
      agentId: "agent-1",
      message: { event: "page-changed", url: "https://attacker.example/" },
    });

    expect(opts.onEvent).not.toHaveBeenCalled();
  });

  it("rejects messages with mismatched agentId (multi-pin isolation)", () => {
    const opts = makeOpts({ agentId: "agent-1" });
    openParentWs(opts);

    dispatchMessageFrom(opts.iframe.contentWindow, {
      type: "taos-copilot:server-event",
      agentId: "agent-2",
      message: { event: "page-changed", url: "https://example.com/" },
    });

    expect(opts.onEvent).not.toHaveBeenCalled();
  });

  it("ignores messages with unknown event kinds", () => {
    const opts = makeOpts();
    openParentWs(opts);

    dispatchMessageFrom(opts.iframe.contentWindow, {
      type: "taos-copilot:server-event",
      agentId: "agent-1",
      message: { event: "totally-unknown" },
    });

    expect(opts.onEvent).not.toHaveBeenCalled();
  });

  it("ignores messages without the expected type field", () => {
    const opts = makeOpts();
    openParentWs(opts);

    dispatchMessageFrom(opts.iframe.contentWindow, {
      type: "something-else",
      agentId: "agent-1",
      message: { event: "page-changed" },
    });

    expect(opts.onEvent).not.toHaveBeenCalled();
  });

  it("ignores malformed payloads (string data, missing message field)", () => {
    const opts = makeOpts();
    openParentWs(opts);

    dispatchMessageFrom(opts.iframe.contentWindow, "not-an-object");
    dispatchMessageFrom(opts.iframe.contentWindow, { type: "taos-copilot:server-event", agentId: "agent-1" });

    expect(opts.onEvent).not.toHaveBeenCalled();
  });

  it("falls back to Date.now() when server event has no timestamp", () => {
    const beforeTs = Date.now();
    const opts = makeOpts();
    openParentWs(opts);

    dispatchMessageFrom(opts.iframe.contentWindow, {
      type: "taos-copilot:server-event",
      agentId: "agent-1",
      message: { event: "scroll" },
    });

    const afterTs = Date.now();
    const received = vi.mocked(opts.onEvent).mock.calls[0][0];
    expect(received.timestamp).toBeGreaterThanOrEqual(beforeTs);
    expect(received.timestamp).toBeLessThanOrEqual(afterTs);
  });

  it("handle.close() removes the listener and fires onClose", () => {
    const opts = makeOpts();
    const handle = openParentWs(opts);

    handle.close();
    expect(handle.isOpen).toBe(false);
    expect(opts.onClose).toHaveBeenCalledOnce();

    // Subsequent messages should be ignored
    dispatchMessageFrom(opts.iframe.contentWindow, {
      type: "taos-copilot:server-event",
      agentId: "agent-1",
      message: { event: "page-changed" },
    });
    expect(opts.onEvent).not.toHaveBeenCalled();
  });

  it("close() is idempotent — second call is a no-op", () => {
    const opts = makeOpts();
    const handle = openParentWs(opts);

    handle.close();
    handle.close();
    expect(opts.onClose).toHaveBeenCalledOnce();
  });
});
