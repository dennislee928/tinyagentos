import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { BackendBanner } from "../BackendBanner";

vi.mock("@/contexts/BackendStatusContext", () => ({
  useBackendStatus: vi.fn(),
}));
import { useBackendStatus } from "@/contexts/BackendStatusContext";

describe("<BackendBanner />", () => {
  beforeEach(() => vi.mocked(useBackendStatus).mockReset());

  it("renders nothing when status is 'up'", () => {
    vi.mocked(useBackendStatus).mockReturnValue({
      status: "up", currentVersion: "0.1.0", secondsReconnecting: 0,
    });
    const { container } = render(<BackendBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders 'taOS is restarting…' when reconnecting under 60s", () => {
    vi.mocked(useBackendStatus).mockReturnValue({
      status: "reconnecting", currentVersion: null, secondsReconnecting: 15,
    });
    render(<BackendBanner />);
    expect(screen.getByText(/taOS is restarting/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /refresh/i })).toBeNull();
  });

  it("renders 'taking longer than usual' with refresh button after 60s", () => {
    vi.mocked(useBackendStatus).mockReturnValue({
      status: "reconnecting", currentVersion: null, secondsReconnecting: 65,
    });
    render(<BackendBanner />);
    expect(screen.getByText(/taking longer than usual/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refresh/i })).toBeInTheDocument();
  });

  it("refresh button calls window.location.reload", () => {
    vi.mocked(useBackendStatus).mockReturnValue({
      status: "reconnecting", currentVersion: null, secondsReconnecting: 65,
    });
    const reload = vi.fn();
    Object.defineProperty(window, "location", {
      value: { reload }, writable: true, configurable: true,
    });
    render(<BackendBanner />);
    screen.getByRole("button", { name: /refresh/i }).click();
    expect(reload).toHaveBeenCalled();
  });
});
