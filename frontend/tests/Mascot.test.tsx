import React from "react";
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Mascot from "../components/Mascot";

describe("Mascot Component", () => {
  it("renders pure inline SVG without external image dependencies", () => {
    const { container } = render(<Mascot mood="idle" size={80} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("viewBox", "0 0 100 100");
  });

  it("applies thinking animation and mood styling", () => {
    const { container } = render(<Mascot mood="thinking" size={60} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("animate-pulse");
  });

  it("applies bounce animation when happy", () => {
    const { container } = render(<Mascot mood="happy" size={60} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("animate-bounce");
  });
});
