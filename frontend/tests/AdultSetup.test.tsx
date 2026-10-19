import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AdultSetup from "../components/AdultSetup";

describe("AdultSetup Component", () => {
  it("displays mandatory disclosures: AI generation and adult reading help", () => {
    render(
      <AdultSetup
        onComplete={vi.fn()}
        onStartPlacement={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText(/AI-Generated Content/i)).toBeInTheDocument();
    expect(screen.getByText(/Reading Support/i)).toBeInTheDocument();
    expect(screen.getByText(/Children under seven may need a grown-up/i)).toBeInTheDocument();
  });

  it("blocks submission if adult supervision checkbox is unchecked", async () => {
    const handleComplete = vi.fn();
    render(
      <AdultSetup
        onComplete={handleComplete}
        onStartPlacement={vi.fn()}
        isLoading={false}
      />
    );

    const submitBtn = screen.getByRole("button", { name: /Start Learning/i });
    fireEvent.click(submitBtn);

    expect(handleComplete).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Please confirm that an adult will supervise this learning session"
    );
  });

  it("submits successfully with optional nickname and Level 1 when acknowledged", async () => {
    const handleComplete = vi.fn();
    render(
      <AdultSetup
        onComplete={handleComplete}
        onStartPlacement={vi.fn()}
        isLoading={false}
      />
    );

    // Enter nickname
    const input = screen.getByLabelText(/Child's First Name or Nickname/i);
    fireEvent.change(input, { target: { value: "Sammy" } });

    // Check adult supervisor acknowledgement
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);

    // Submit
    const submitBtn = screen.getByRole("button", { name: /Start Learning/i });
    fireEvent.click(submitBtn);

    expect(handleComplete).toHaveBeenCalledWith("Sammy", "L1");
  });

  it("triggers placement quiz when placement radio is selected", async () => {
    const handleStartPlacement = vi.fn();
    render(
      <AdultSetup
        onComplete={vi.fn()}
        onStartPlacement={handleStartPlacement}
        isLoading={false}
      />
    );

    // Select placement option
    const placementRadio = screen.getByLabelText(/Placement Quiz/i);
    fireEvent.click(placementRadio);

    // Check adult ack
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);

    // Submit button text changes
    const submitBtn = screen.getByRole("button", { name: /Start Placement Quiz/i });
    fireEvent.click(submitBtn);

    expect(handleStartPlacement).toHaveBeenCalled();
  });
});
