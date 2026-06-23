import { describe, it, expect } from "vitest";

describe("Test setup verification", () => {
  it("should run vitest with jsdom environment", () => {
    expect(typeof document).toBe("object");
    expect(typeof window).toBe("object");
  });

  it("should have testing-library/jest-dom matchers available", () => {
    const div = document.createElement("div");
    div.textContent = "hello";
    document.body.appendChild(div);
    expect(div).toBeInTheDocument();
    document.body.removeChild(div);
  });
});
