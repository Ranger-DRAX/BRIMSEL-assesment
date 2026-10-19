"use client";

import React, { useState } from "react";
import Mascot from "./Mascot";

interface PlacementActivityProps {
  nickname?: string;
  onFinish: (selectedLevel: "L1" | "L2" | "L3") => Promise<void>;
  onSkip: () => Promise<void>;
  isLoading: boolean;
}

interface PlacementQuestion {
  id: string;
  levelTarget: "L1" | "L2" | "L3";
  prompt: string;
  choices: Array<{ id: string; text: string }>;
  correctId: string;
}

const PLACEMENT_QUESTIONS: PlacementQuestion[] = [
  {
    id: "q1",
    levelTarget: "L1",
    prompt: "What color is the sun? ☀️",
    choices: [
      { id: "a", text: "Blue" },
      { id: "b", text: "Green" },
      { id: "c", text: "Yellow" },
    ],
    correctId: "c",
  },
  {
    id: "q2",
    levelTarget: "L2",
    prompt: "Which sentence sounds right? 🌟",
    choices: [
      { id: "a", text: "She are happy." },
      { id: "b", text: "She is happy." },
      { id: "c", text: "She am happy." },
    ],
    correctId: "b",
  },
  {
    id: "q3",
    levelTarget: "L3",
    prompt: "A kitten is very small. What will it grow into? 🐱",
    choices: [
      { id: "a", text: "An elephant" },
      { id: "b", text: "A cat" },
      { id: "c", text: "A frog" },
    ],
    correctId: "b",
  },
];

export default function PlacementActivity({
  nickname,
  onFinish,
  onSkip,
  isLoading,
}: PlacementActivityProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [selectedChoice, setSelectedChoice] = useState<string | null>(null);

  const currentQ = PLACEMENT_QUESTIONS[currentIndex];

  const handleChoice = async (choiceId: string) => {
    setSelectedChoice(choiceId);
    const isCorrect = choiceId === currentQ.correctId;
    const newCorrect = isCorrect ? correctCount + 1 : correctCount;
    setCorrectCount(newCorrect);

    // Short pause for feedback
    setTimeout(async () => {
      if (currentIndex + 1 < PLACEMENT_QUESTIONS.length) {
        setCurrentIndex(currentIndex + 1);
        setSelectedChoice(null);
      } else {
        // Compute level: 0-1 -> L1, 2 -> L2, 3 -> L3
        let targetLevel: "L1" | "L2" | "L3" = "L1";
        if (newCorrect >= 3) {
          targetLevel = "L3";
        } else if (newCorrect === 2) {
          targetLevel = "L2";
        }
        await onFinish(targetLevel);
      }
    }, 400);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-amber-50 via-orange-50 to-amber-100 flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-white rounded-3xl shadow-xl border-4 border-amber-200 p-6 sm:p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 border-b border-amber-100 pb-4">
          <div className="flex items-center gap-3">
            <Mascot mood="thinking" size={48} />
            <div>
              <h2 className="text-xl font-bold text-slate-800">
                Finding the Best Level{nickname ? ` for ${nickname}` : ""}
              </h2>
              <p className="text-xs text-amber-700 font-medium">
                Question {currentIndex + 1} of {PLACEMENT_QUESTIONS.length}
              </p>
            </div>
          </div>
          <button
            onClick={() => onSkip()}
            disabled={isLoading}
            className="text-xs font-semibold text-slate-500 hover:text-slate-700 py-1.5 px-3 rounded-lg border border-slate-200 hover:bg-slate-50 min-h-[44px]"
          >
            Skip to L1
          </button>
        </div>

        {/* Question Prompt */}
        <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl p-6 text-center mb-6">
          <p className="text-xl sm:text-2xl font-extrabold text-slate-800 leading-snug">
            {currentQ.prompt}
          </p>
        </div>

        {/* Choices */}
        <div className="space-y-3 mb-6" role="group" aria-label="Answer options">
          {currentQ.choices.map((choice) => {
            const isSelected = selectedChoice === choice.id;
            return (
              <button
                key={choice.id}
                onClick={() => handleChoice(choice.id)}
                disabled={selectedChoice !== null || isLoading}
                className={`w-full min-h-[52px] py-3.5 px-6 rounded-2xl text-lg font-bold transition-all text-left flex items-center justify-between border-2 ${
                  isSelected
                    ? "bg-amber-500 text-white border-amber-600 shadow-md scale-98"
                    : "bg-white hover:bg-amber-50/70 border-slate-200 hover:border-amber-300 text-slate-800 shadow-sm"
                } focus:outline-none focus:ring-4 focus:ring-amber-200`}
              >
                <span>{choice.text}</span>
                <span className="text-xs uppercase px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-semibold">
                  Choice
                </span>
              </button>
            );
          })}
        </div>

        <p className="text-center text-xs text-slate-400">
          Tip: Grown-ups can read the question out loud if needed! 💡
        </p>
      </div>
    </div>
  );
}
