import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AdultSettings from "../components/AdultSettings";
import { SessionResponse } from "../lib/api";

const mockSession: SessionResponse = {
  nickname: "Charlie",
  level: "L2",
  mode: "conversation",
  recent_messages: [],
  active_activity: null,
  revision: 4,
  promotion_available: false,
};

describe("AdultSettings Component", () => {
  it("locks settings behind parental gate initially", () => {
    render(
      <AdultSettings
        session={mockSession}
        onReset={vi.fn()}
        onDelete={vi.fn()}
        onClose={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText(/Parental Gate/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/What is 7 \+ 8\?/i)).toBeInTheDocument();
    expect(screen.queryByText(/Current Profile Info/i)).not.toBeInTheDocument();
  });

  it("unlocks settings upon correct math answer", () => {
    render(
      <AdultSettings
        session={mockSession}
        onReset={vi.fn()}
        onDelete={vi.fn()}
        onClose={vi.fn()}
        isLoading={false}
      />
    );

    const input = screen.getByLabelText(/What is 7 \+ 8\?/i);
    fireEvent.change(input, { target: { value: "15" } });

    const unlockBtn = screen.getByRole("button", { name: /Unlock Settings/i });
    fireEvent.click(unlockBtn);

    expect(screen.getByText(/Current Profile Info/i)).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    expect(screen.getByText("L2")).toBeInTheDocument();
    expect(screen.getByText(/Local SQLite Storage/i)).toBeInTheDocument();
  });

  it("prompts confirmation before resetting learning data", () => {
    const handleReset = vi.fn();
    render(
      <AdultSettings
        session={mockSession}
        onReset={handleReset}
        onDelete={vi.fn()}
        onClose={vi.fn()}
        isLoading={false}
      />
    );

    // Pass gate
    fireEvent.change(screen.getByLabelText(/What is 7 \+ 8\?/i), {
      target: { value: "15" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Unlock Settings/i }));

    // Click Reset
    const resetBtn = screen.getByRole("button", {
      name: /Reset Learning Progress/i,
    });
    fireEvent.click(resetBtn);

    expect(
      screen.getByText(/Reset all scored activities/i)
    ).toBeInTheDocument();

    const confirmBtn = screen.getByRole("button", { name: /Confirm Reset/i });
    fireEvent.click(confirmBtn);

    expect(handleReset).toHaveBeenCalled();
  });
});
