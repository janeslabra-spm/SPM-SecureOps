import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  HealthProgressBar,
  getHealthColor,
} from "@/components/widgets/HealthProgressBar";

describe("getHealthColor", () => {
  it("returns green class for values > 90", () => {
    expect(getHealthColor(91)).toBe("bg-green-500");
    expect(getHealthColor(100)).toBe("bg-green-500");
    expect(getHealthColor(95)).toBe("bg-green-500");
  });

  it("returns amber class for values 70-90 inclusive", () => {
    expect(getHealthColor(70)).toBe("bg-amber-500");
    expect(getHealthColor(80)).toBe("bg-amber-500");
    expect(getHealthColor(90)).toBe("bg-amber-500");
  });

  it("returns red class for values < 70", () => {
    expect(getHealthColor(0)).toBe("bg-red-500");
    expect(getHealthColor(69)).toBe("bg-red-500");
    expect(getHealthColor(50)).toBe("bg-red-500");
  });

  it("handles boundary at 90/91", () => {
    expect(getHealthColor(90)).toBe("bg-amber-500");
    expect(getHealthColor(91)).toBe("bg-green-500");
  });

  it("handles boundary at 69/70", () => {
    expect(getHealthColor(69)).toBe("bg-red-500");
    expect(getHealthColor(70)).toBe("bg-amber-500");
  });
});

describe("HealthProgressBar component", () => {
  it("renders the label", () => {
    render(<HealthProgressBar label="Camera" value={95} status="healthy" />);
    expect(screen.getByText("Camera")).toBeInTheDocument();
  });

  it("renders percentage value for non-zero values", () => {
    render(<HealthProgressBar label="Backend" value={85} status="warning" />);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it('shows "Unreachable" label when value is 0%', () => {
    render(<HealthProgressBar label="AI Engine" value={0} status="unreachable" />);
    expect(screen.getByText("Unreachable")).toBeInTheDocument();
    expect(screen.getByText("Component is not responding")).toBeInTheDocument();
  });

  it("does not show unreachable text for non-zero values", () => {
    render(<HealthProgressBar label="Database" value={50} status="critical" />);
    expect(screen.queryByText("Unreachable")).not.toBeInTheDocument();
    expect(screen.queryByText("Component is not responding")).not.toBeInTheDocument();
  });

  it("has correct aria-label for healthy state", () => {
    render(<HealthProgressBar label="Camera" value={100} status="healthy" />);
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuenow", "100");
    expect(progressbar).toHaveAttribute("aria-valuemin", "0");
    expect(progressbar).toHaveAttribute("aria-valuemax", "100");
    expect(progressbar).toHaveAttribute("aria-label", "Camera health: 100%");
  });

  it("has correct aria-label for unreachable state", () => {
    render(<HealthProgressBar label="AI Engine" value={0} status="unreachable" />);
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuenow", "0");
    expect(progressbar).toHaveAttribute("aria-label", "AI Engine health: Unreachable");
  });

  it("clamps value above 100 to 100", () => {
    render(<HealthProgressBar label="Backend" value={150} status="healthy" />);
    expect(screen.getByText("100%")).toBeInTheDocument();
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuenow", "100");
  });

  it("clamps negative values to 0", () => {
    render(<HealthProgressBar label="Camera" value={-10} status="unreachable" />);
    expect(screen.getByText("Unreachable")).toBeInTheDocument();
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuenow", "0");
  });

  it("applies glass-card styling", () => {
    const { container } = render(
      <HealthProgressBar label="Camera" value={95} status="healthy" />
    );
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain("glass-card");
  });
});
