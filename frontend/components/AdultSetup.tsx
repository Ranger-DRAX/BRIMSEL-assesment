"use client";

import React, { useState } from "react";
import Mascot from "./Mascot";

interface AdultSetupProps {
  onComplete: (nickname?: string, startingLevel?: string) => Promise<void>;
  onStartPlacement: (nickname?: string) => void;
  isLoading: boolean;
}

export default function AdultSetup({
  onComplete,
  onStartPlacement,
  isLoading,
}: AdultSetupProps) {
  const [nickname, setNickname] = useState("");
  const [levelChoice, setLevelChoice] = useState<"L1" | "placement">("L1");
  const [acknowledged, setAcknowledged] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!acknowledged) {
      setErrorMessage(
        "Please confirm that an adult will supervise this learning session."
      );
      return;
    }

    setErrorMessage("");

    if (levelChoice === "placement") {
      onStartPlacement(nickname.trim() || undefined);
    } else {
      await onComplete(nickname.trim() || undefined, "L1");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-amber-50 via-orange-50 to-amber-100 flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-white rounded-3xl shadow-xl border-4 border-amber-200 p-6 sm:p-8">
        {/* Mascot Banner */}
        <div className="flex flex-col items-center text-center mb-6">
          <Mascot mood="happy" size={96} className="mb-2" />
          <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">
            Little English Buddy
          </h1>
          <p className="text-amber-700 font-medium text-base mt-1">
            Grown-Up Setup & Onboarding
          </p>
        </div>

        {/* Informational Guidance Box */}
        <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl p-4 mb-6 text-sm text-slate-700 space-y-2">
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold text-lg leading-none">
              ℹ️
            </span>
            <p>
              <strong>AI-Generated Content:</strong> Responses are created by an
              artificial intelligence tutor and may occasionally make mistakes.
            </p>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold text-lg leading-none">
              📖
            </span>
            <p>
              <strong>Reading Support:</strong> This is a text-based prototype.
              Children under seven may need a grown-up to help read questions aloud
              and explore together.
            </p>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold text-lg leading-none">
              🔒
            </span>
            <p>
              <strong>Privacy First:</strong> Progress is stored only on this
              computer. We never ask for full names, addresses, birthdays, or
              contact info.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Optional Nickname */}
          <div>
            <label
              htmlFor="child-nickname"
              className="block text-base font-bold text-slate-800 mb-1"
            >
              Child&apos;s First Name or Nickname{" "}
              <span className="text-slate-400 font-normal">(Optional)</span>
            </label>
            <input
              id="child-nickname"
              type="text"
              maxLength={25}
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="e.g. Leo, Mia, Buddy"
              className="w-full px-4 py-3 text-lg border-2 border-slate-300 rounded-xl focus:outline-none focus:border-amber-500 text-slate-800 placeholder-slate-400 min-h-[48px]"
            />
          </div>

          {/* Starting Level Choice */}
          <fieldset>
            <legend className="text-base font-bold text-slate-800 mb-2">
              Where would you like to start?
            </legend>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label
                className={`flex items-start p-3.5 border-2 rounded-xl cursor-pointer transition-colors min-h-[56px] ${
                  levelChoice === "L1"
                    ? "border-amber-500 bg-amber-50/70"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="level"
                  value="L1"
                  checked={levelChoice === "L1"}
                  onChange={() => setLevelChoice("L1")}
                  className="mt-1 h-5 w-5 text-amber-500 focus:ring-amber-400"
                />
                <div className="ml-3">
                  <span className="block text-base font-bold text-slate-800">
                    Level 1 (Beginner)
                  </span>
                  <span className="block text-xs text-slate-600">
                    Colors, animals, greetings & single words
                  </span>
                </div>
              </label>

              <label
                className={`flex items-start p-3.5 border-2 rounded-xl cursor-pointer transition-colors min-h-[56px] ${
                  levelChoice === "placement"
                    ? "border-amber-500 bg-amber-50/70"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="level"
                  value="placement"
                  checked={levelChoice === "placement"}
                  onChange={() => setLevelChoice("placement")}
                  className="mt-1 h-5 w-5 text-amber-500 focus:ring-amber-400"
                />
                <div className="ml-3">
                  <span className="block text-base font-bold text-slate-800">
                    Placement Quiz 🎯
                  </span>
                  <span className="block text-xs text-slate-600">
                    3 quick questions to find the right level
                  </span>
                </div>
              </label>
            </div>
          </fieldset>

          {/* Adult Supervision Acknowledgement */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                id="adult-ack"
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => {
                  setAcknowledged(e.target.checked);
                  if (e.target.checked) setErrorMessage("");
                }}
                className="mt-1 h-5 w-5 rounded border-slate-300 text-amber-600 focus:ring-amber-500"
              />
              <span className="text-sm text-slate-700 leading-snug">
                I am a parent or adult supervisor. I understand this is an
                AI-powered learning prototype requiring adult presence.
              </span>
            </label>
          </div>

          {errorMessage && (
            <div
              role="alert"
              className="p-3 bg-rose-50 border border-rose-300 text-rose-800 rounded-xl text-sm font-medium"
            >
              ⚠️ {errorMessage}
            </div>
          )}

          {/* Action Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full min-h-[52px] py-3.5 px-6 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-extrabold text-lg rounded-2xl shadow-md transition-all transform active:scale-98 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-4 focus:ring-amber-300"
          >
            {isLoading
              ? "Starting up..."
              : levelChoice === "placement"
              ? "Start Placement Quiz 🎯"
              : "Start Learning with Pip! 🚀"}
          </button>
        </form>
      </div>
    </div>
  );
}
