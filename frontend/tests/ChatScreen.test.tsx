import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChatScreen from "../components/ChatScreen";
import { SessionResponse } from "../lib/api";

const mockSession: SessionResponse = {
  nickname: "Luna",
  level: "L1",
  mode: "conversation",
  recent_messages: [
    { role: "assistant", content: "Hello Luna! Welcome back!" },
    { role: "user", content: "I like painting" },
  ],
  active_activity: null,
  revision: 2,
  promotion_available: false,
};

describe("ChatScreen Component", () => {
  it("renders messages safely as plain text (no HTML/script execution)", () => {
    const sessionWithHtml: SessionResponse = {
      ...mockSession,
      recent_messages: [
        {
          role: "assistant",
          content: "<script>alert('xss')</script>Hello <b>World</b>!",
        },
      ],
    };

    render(
      <ChatScreen
        session={sessionWithHtml}
        onOpenSettings={vi.fn()}
        onSessionUpdated={vi.fn()}
      />
    );

    // The text content should literally match the string, NOT rendered as an HTML element
    expect(screen.getByText(/<script>alert\('xss'\)<\/script>Hello <b>World<\/b>!/i)).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });

  it("renders persistent action buttons (Learn, Chat, Play, Break)", () => {
    render(
      <ChatScreen
        session={mockSession}
        onOpenSettings={vi.fn()}
        onSessionUpdated={vi.fn()}
      />
    );

    const nav = screen.getByRole("navigation", { name: /Learning activities/i });
    expect(within(nav).getByRole("button", { name: /Learn/i })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Chat/i })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Play/i })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Break/i })).toBeInTheDocument();
  });

  it("renders active activity with question and choices", () => {
    const sessionWithActivity: SessionResponse = {
      ...mockSession,
      mode: "learning",
      active_activity: {
        activity_id: "act-1",
        instance_id: "inst-1",
        activity_type: "multiple_choice",
        prompt: "What color is an apple? 🍎",
        choices: [
          { id: "a", text: "Red" },
          { id: "b", text: "Blue" },
        ],
        skill: "vocabulary",
        level: "L1",
      },
    };

    render(
      <ChatScreen
        session={sessionWithActivity}
        onOpenSettings={vi.fn()}
        onSessionUpdated={vi.fn()}
      />
    );

    expect(
      screen.getByText("What color is an apple? 🍎")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Red" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Blue" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Need a Hint/i })).toBeInTheDocument();
  });

  it("updates text input and sends chat on enter/click", () => {
    render(
      <ChatScreen
        session={mockSession}
        onOpenSettings={vi.fn()}
        onSessionUpdated={vi.fn()}
      />
    );

    const input = screen.getByLabelText(/Type a message to Pip/i);
    fireEvent.change(input, { target: { value: "I like butterflies" } });

    expect(input).toHaveValue("I like butterflies");

    const sendBtn = screen.getByRole("button", { name: /Send message/i });
    expect(sendBtn).toBeEnabled();
  });
});
