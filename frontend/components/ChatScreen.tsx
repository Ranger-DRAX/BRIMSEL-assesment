"use client";

import React, { useEffect, useRef, useState } from "react";
import Mascot from "./Mascot";
import {
  ActivityPayload,
  ChatResponse,
  SessionResponse,
  generateRequestId,
  sendChatMessage,
} from "../lib/api";

interface MessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  source?: string;
  isError?: boolean;
}

interface ChatScreenProps {
  session: SessionResponse;
  onOpenSettings: () => void;
  onSessionUpdated: (newSession: Partial<SessionResponse>) => void;
}

export default function ChatScreen({
  session,
  onOpenSettings,
  onSessionUpdated,
}: ChatScreenProps) {
  // Messages stream
  const [messages, setMessages] = useState<MessageItem[]>(() => {
    if (session.recent_messages && session.recent_messages.length > 0) {
      return session.recent_messages.map((m, idx) => ({
        id: `init-${idx}`,
        role: m.role,
        content: m.content,
      }));
    }
    // Warm greeting if fresh session
    const greeting = session.nickname
      ? `Hi ${session.nickname}! I'm Pip! What would you like to do today? 🌟`
      : "Hello friend! I'm Pip, your English Buddy! What would you like to do today? 🌟";
    return [
      {
        id: "welcome-1",
        role: "assistant",
        content: greeting,
        source: "mock",
      },
    ];
  });

  // Turn state
  const [inputText, setInputText] = useState("");
  const [unsentDraft, setUnsentDraft] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  // Active activity and suggestions
  const [activeActivity, setActiveActivity] = useState<ActivityPayload | null>(
    session.active_activity
  );
  const [suggestedReplies, setSuggestedReplies] = useState<string[]>([
    "Learn something new 📚",
    "Let's chat! 💬",
    "Play a game 🎮",
  ]);
  const [currentLevel, setCurrentLevel] = useState<string>(session.level);
  const [currentMode, setCurrentMode] = useState<string>(session.mode);
  const [currentRevision, setCurrentRevision] = useState<number>(
    session.revision
  );
  const [promotionAvailable, setPromotionAvailable] = useState<boolean>(
    session.promotion_available
  );

  // Derive mascot mood directly from current state
  const mascotMood = isLoading
    ? "thinking"
    : currentMode === "support"
    ? "break"
    : currentMode === "learning"
    ? "encouraging"
    : "idle";

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Scroll to bottom smoothly when messages update
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, activeActivity]);

  // Core submission handler
  const handleSend = async (params: {
    message?: string;
    action?: string;
    answerOptionId?: string;
    activityInstanceId?: string;
  }) => {
    if (isLoading) return;

    const userMsgText = params.message || "";
    const isActionButton = !userMsgText && !!params.action;

    // Clear previous error
    setErrorMessage(null);

    // Optimistically show user message in chat if there is visible text
    if (userMsgText) {
      const userItem: MessageItem = {
        id: generateRequestId(),
        role: "user",
        content: userMsgText,
      };
      setMessages((prev) => [...prev, userItem]);
      setAnnouncement(`You said: ${userMsgText}`);
    } else if (isActionButton) {
      const actionLabels: Record<string, string> = {
        learn: "Let's learn! 📚",
        chat: "Let's chat! 💬",
        play: "Let's play! 🎮",
        break: "Take a break ☕",
        hint: "Need a hint 💡",
        skip: "Skip this one ⏩",
        accept_promotion: "Yes, let's try the next level! 🚀",
        decline_promotion: "I'll stay at this level for now 🌟",
      };
      const label = actionLabels[params.action || ""] || "Action selected";
      const actionItem: MessageItem = {
        id: generateRequestId(),
        role: "user",
        content: label,
      };
      setMessages((prev) => [...prev, actionItem]);
      setAnnouncement(`You chose: ${label}`);
    }

    // Save draft in case of failure
    if (userMsgText) {
      setUnsentDraft(userMsgText);
      setInputText("");
    }

    setIsLoading(true);

    try {
      const resp: ChatResponse = await sendChatMessage({
        message: userMsgText || null,
        action: params.action || null,
        answerOptionId: params.answerOptionId || null,
        activityInstanceId:
          params.activityInstanceId || activeActivity?.instance_id || null,
        expectedRevision: currentRevision,
      });

      // Turn succeeded! Clear draft
      setUnsentDraft("");

      // Append assistant message
      const botItem: MessageItem = {
        id: resp.request_id || generateRequestId(),
        role: "assistant",
        content: resp.reply,
        source: resp.source,
      };
      setMessages((prev) => [...prev, botItem]);
      setAnnouncement(`Pip said: ${resp.reply}`);

      // Update state
      setCurrentRevision(resp.revision);
      setCurrentLevel(resp.level);
      setCurrentMode(resp.mode);
      setActiveActivity(resp.activity);
      setSuggestedReplies(resp.suggested_replies || []);

      // Check if promotion was offered in reply
      if (resp.reply.includes("Would you like to try") && resp.reply.includes("level")) {
        setPromotionAvailable(true);
      }

      onSessionUpdated({
        level: resp.level,
        mode: resp.mode,
        revision: resp.revision,
      });
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Something went wrong. Let's try again!";
      setErrorMessage(errorMsg);
      setAnnouncement(`Error: ${errorMsg}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;
    handleSend({ message: inputText.trim() });
  };

  const handleSuggestedClick = (text: string) => {
    handleSend({ message: text });
  };

  const handleActionClick = (actionName: string) => {
    handleSend({ action: actionName });
  };

  const handleAnswerChoice = (choiceId: string, choiceText: string) => {
    handleSend({
      message: choiceText,
      answerOptionId: choiceId,
      activityInstanceId: activeActivity?.instance_id,
    });
  };

  const handleRetryDraft = () => {
    if (unsentDraft) {
      const draft = unsentDraft;
      setUnsentDraft("");
      handleSend({ message: draft });
    }
  };

  const friendlyLevelName = (lvl: string) => {
    switch (lvl) {
      case "L1":
        return "Level 1 Explorer 🌱";
      case "L2":
        return "Level 2 Adventurer 🚀";
      case "L3":
        return "Level 3 Champion 🏆";
      default:
        return `${lvl} Explorer`;
    }
  };

  return (
    <div className="flex flex-col h-screen max-h-screen bg-gradient-to-b from-amber-50/70 via-orange-50/30 to-amber-50/80 text-slate-800 antialiased overflow-hidden select-text">
      {/* Accessible Live Region for Screen Readers */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        id="sr-announcements"
      >
        {announcement}
      </div>

      {/* Top App Header */}
      <header className="bg-white/90 backdrop-blur-sm border-b-2 border-amber-200 px-4 py-2.5 flex items-center justify-between shadow-xs z-10">
        <div className="flex items-center gap-3">
          <Mascot mood={mascotMood} size={44} />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-black text-slate-800 tracking-tight leading-tight">
                Little English Buddy
              </h1>
              {session.nickname && (
                <span className="text-xs bg-amber-100 text-amber-900 font-bold px-2 py-0.5 rounded-full">
                  {session.nickname}
                </span>
              )}
            </div>
            <span className="text-xs font-semibold text-amber-700 block">
              {friendlyLevelName(currentLevel)}
            </span>
          </div>
        </div>

        {/* Grown-Up Settings Button */}
        <button
          onClick={onOpenSettings}
          aria-label="Open Grown-Up Settings"
          className="min-h-[44px] min-w-[44px] px-3 py-1.5 rounded-xl border border-slate-200 bg-slate-50 hover:bg-amber-100/60 text-slate-700 hover:text-slate-900 font-bold text-xs flex items-center gap-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <span>⚙️</span>
          <span className="hidden sm:inline">Grown-Up Settings</span>
        </button>
      </header>

      {/* Promotion Offer Banner */}
      {promotionAvailable && (
        <aside
          role="region"
          aria-label="Level promotion offer"
          className="bg-gradient-to-r from-emerald-500 to-teal-500 text-white px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-2 shadow-md animate-fadeIn"
        >
          <div className="flex items-center gap-2 text-center sm:text-left">
            <span className="text-2xl">🎉</span>
            <div>
              <p className="font-extrabold text-sm sm:text-base leading-tight">
                Amazing job! You are ready for the next level!
              </p>
              <p className="text-xs text-emerald-100">
                Would you like to try new activities?
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              onClick={() => {
                setPromotionAvailable(false);
                handleActionClick("accept_promotion");
              }}
              disabled={isLoading}
              className="flex-1 sm:flex-initial min-h-[44px] px-4 py-2 bg-white text-emerald-800 font-extrabold text-xs rounded-xl shadow-xs hover:bg-emerald-50"
            >
              Yes, let&apos;s go! 🚀
            </button>
            <button
              onClick={() => {
                setPromotionAvailable(false);
                handleActionClick("decline_promotion");
              }}
              disabled={isLoading}
              className="flex-1 sm:flex-initial min-h-[44px] px-3 py-2 bg-emerald-600/80 hover:bg-emerald-600 text-white font-semibold text-xs rounded-xl"
            >
              Stay here for now 🌟
            </button>
          </div>
        </aside>
      )}

      {/* Main Chat Stream Container */}
      <main
        role="log"
        aria-label="Conversation messages"
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4 max-w-2xl w-full mx-auto"
      >
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <article
              key={msg.id}
              className={`flex items-end gap-2.5 ${
                isUser ? "justify-end" : "justify-start"
              }`}
            >
              {!isUser && (
                <div className="flex-shrink-0 mb-1" aria-hidden="true">
                  <Mascot mood="idle" size={36} />
                </div>
              )}
              <div
                className={`max-w-[85%] sm:max-w-[75%] rounded-3xl p-4 sm:p-5 shadow-xs text-base sm:text-lg leading-relaxed ${
                  isUser
                    ? "bg-amber-500 text-white font-medium rounded-br-xs"
                    : "bg-white border-2 border-amber-200 text-slate-800 font-medium rounded-bl-xs"
                }`}
              >
                {/* Safe plain text render - never raw HTML */}
                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
              </div>
            </article>
          );
        })}

        {/* Active Activity Card (in Learning Mode) */}
        {activeActivity && !isLoading && (
          <section
            aria-label="Current learning activity"
            className="my-3 bg-white border-3 border-amber-400 rounded-3xl p-5 shadow-md max-w-lg mx-auto"
          >
            <div className="flex items-center justify-between mb-3 border-b border-amber-100 pb-2">
              <span className="text-xs uppercase font-extrabold px-2.5 py-1 rounded-full bg-amber-100 text-amber-800">
                {activeActivity.skill} Challenge 🎯
              </span>
              <button
                onClick={() => handleActionClick("hint")}
                className="text-xs font-bold text-amber-600 hover:text-amber-800 flex items-center gap-1 min-h-[44px] px-2"
              >
                <span>💡</span>
                <span>Need a Hint?</span>
              </button>
            </div>

            {/* Activity Prompt */}
            <h3 className="text-lg sm:text-xl font-extrabold text-slate-800 mb-4 text-center">
              {activeActivity.prompt}
            </h3>

            {/* Answer Choices Buttons */}
            {activeActivity.choices && activeActivity.choices.length > 0 && (
              <div
                className="grid grid-cols-1 sm:grid-cols-2 gap-2.5"
                role="group"
                aria-label="Activity choices"
              >
                {activeActivity.choices.map((choice) => (
                  <button
                    key={choice.id}
                    onClick={() => handleAnswerChoice(choice.id, choice.text)}
                    disabled={isLoading}
                    className="min-h-[48px] py-3 px-4 bg-amber-50 hover:bg-amber-100 border-2 border-amber-300 hover:border-amber-400 rounded-2xl text-base font-bold text-slate-800 transition-all text-center focus:outline-none focus:ring-4 focus:ring-amber-200 active:scale-98"
                  >
                    {choice.text}
                  </button>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Thinking Indicator */}
        {isLoading && (
          <div
            className="flex items-center gap-3 text-amber-800 font-semibold text-sm bg-white/80 border border-amber-200 rounded-2xl p-3 max-w-xs shadow-xs"
            role="status"
          >
            <Mascot mood="thinking" size={32} />
            <div className="flex items-center gap-1.5">
              <span>Pip is thinking</span>
              <span className="inline-flex gap-1">
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce"></span>
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce [animation-delay:0.4s]"></span>
              </span>
            </div>
          </div>
        )}

        {/* Error / Offline Banner with Recoverable Draft */}
        {errorMessage && (
          <div
            role="alert"
            className="p-4 bg-rose-50 border-2 border-rose-300 rounded-2xl text-slate-800 space-y-2 max-w-lg mx-auto shadow-sm"
          >
            <div className="flex items-start gap-2">
              <span className="text-xl">⚠️</span>
              <div>
                <p className="font-bold text-rose-900 text-sm">
                  Oops! We couldn&apos;t send that message.
                </p>
                <p className="text-xs text-rose-700">{errorMessage}</p>
              </div>
            </div>
            {unsentDraft && (
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={handleRetryDraft}
                  disabled={isLoading}
                  className="min-h-[44px] py-2 px-4 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs rounded-xl shadow-xs"
                >
                  Retry &quot;{unsentDraft}&quot; 🔄
                </button>
              </div>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </main>

      {/* Suggested Replies Bar */}
      {suggestedReplies.length > 0 && !isLoading && (
        <div className="px-4 py-2 border-t border-amber-100 bg-white/60">
          <div
            className="flex items-center gap-2 overflow-x-auto pb-1 max-w-2xl mx-auto no-scrollbar"
            role="group"
            aria-label="Suggested reply choices"
          >
            {suggestedReplies.map((replyText, idx) => (
              <button
                key={idx}
                onClick={() => handleSuggestedClick(replyText)}
                disabled={isLoading}
                className="flex-shrink-0 min-h-[44px] px-4 py-2 rounded-2xl bg-amber-100/90 hover:bg-amber-200 text-amber-900 font-bold text-sm transition-all border border-amber-300 shadow-2xs hover:scale-102 focus:outline-none focus:ring-2 focus:ring-amber-400"
              >
                {replyText}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Persistent Action Dock (Learn, Chat, Play, Break) */}
      <nav
        aria-label="Learning activities"
        className="px-4 py-2 bg-amber-100/90 border-t-2 border-amber-200"
      >
        <div className="grid grid-cols-4 gap-2 max-w-2xl mx-auto">
          <button
            onClick={() => handleActionClick("learn")}
            disabled={isLoading}
            className={`min-h-[44px] py-2 px-2 rounded-xl text-center font-extrabold text-xs sm:text-sm transition-all flex flex-col sm:flex-row items-center justify-center gap-1 ${
              currentMode === "learning"
                ? "bg-amber-500 text-white shadow-xs"
                : "bg-white text-amber-900 hover:bg-amber-50 border border-amber-200"
            } focus:outline-none focus:ring-2 focus:ring-amber-400`}
          >
            <span>📚</span>
            <span>Learn</span>
          </button>

          <button
            onClick={() => handleActionClick("chat")}
            disabled={isLoading}
            className={`min-h-[44px] py-2 px-2 rounded-xl text-center font-extrabold text-xs sm:text-sm transition-all flex flex-col sm:flex-row items-center justify-center gap-1 ${
              currentMode === "conversation"
                ? "bg-amber-500 text-white shadow-xs"
                : "bg-white text-amber-900 hover:bg-amber-50 border border-amber-200"
            } focus:outline-none focus:ring-2 focus:ring-amber-400`}
          >
            <span>💬</span>
            <span>Chat</span>
          </button>

          <button
            onClick={() => handleActionClick("play")}
            disabled={isLoading}
            className={`min-h-[44px] py-2 px-2 rounded-xl text-center font-extrabold text-xs sm:text-sm transition-all flex flex-col sm:flex-row items-center justify-center gap-1 ${
              currentMode === "engagement"
                ? "bg-amber-500 text-white shadow-xs"
                : "bg-white text-amber-900 hover:bg-amber-50 border border-amber-200"
            } focus:outline-none focus:ring-2 focus:ring-amber-400`}
          >
            <span>🎮</span>
            <span>Play</span>
          </button>

          <button
            onClick={() => handleActionClick("break")}
            disabled={isLoading}
            className={`min-h-[44px] py-2 px-2 rounded-xl text-center font-extrabold text-xs sm:text-sm transition-all flex flex-col sm:flex-row items-center justify-center gap-1 ${
              currentMode === "support"
                ? "bg-sky-500 text-white shadow-xs"
                : "bg-white text-sky-900 hover:bg-sky-50 border border-sky-200"
            } focus:outline-none focus:ring-2 focus:ring-sky-400`}
          >
            <span>☕</span>
            <span>Break</span>
          </button>
        </div>
      </nav>

      {/* Chat Input Bar */}
      <footer className="p-3 bg-white border-t border-amber-200 shadow-md">
        <form
          onSubmit={handleTextSubmit}
          className="flex items-center gap-2 max-w-2xl mx-auto"
        >
          <label htmlFor="chat-input-field" className="sr-only">
            Type a message to Pip
          </label>
          <input
            id="chat-input-field"
            ref={inputRef}
            type="text"
            value={inputText}
            maxLength={500}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isLoading}
            placeholder={
              currentMode === "learning"
                ? "Type your answer or question..."
                : "Talk to Pip..."
            }
            className="flex-1 min-h-[48px] px-4 py-2.5 text-base sm:text-lg border-2 border-slate-300 rounded-2xl focus:outline-none focus:border-amber-500 disabled:opacity-50 text-slate-800 placeholder-slate-400"
          />
          <button
            type="submit"
            disabled={!inputText.trim() || isLoading}
            aria-label="Send message"
            className="min-h-[48px] min-w-[56px] px-5 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-black text-lg rounded-2xl shadow-sm transition-all flex items-center justify-center focus:outline-none focus:ring-4 focus:ring-amber-300 active:scale-95"
          >
            Send
          </button>
        </form>
      </footer>
    </div>
  );
}
