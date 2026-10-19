"use client";

import React, { useState } from "react";
import { SessionResponse } from "../lib/api";

interface AdultSettingsProps {
  session: SessionResponse;
  onReset: () => Promise<void>;
  onDelete: () => Promise<void>;
  onClose: () => void;
  isLoading: boolean;
}

export default function AdultSettings({
  session,
  onReset,
  onDelete,
  onClose,
  isLoading,
}: AdultSettingsProps) {
  // Adult Gate State
  const [gatePassed, setGatePassed] = useState(false);
  const [gateAnswer, setGateAnswer] = useState("");
  const [gateError, setGateError] = useState("");

  // Confirmation Modals State
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Simple math challenge (e.g. 7 + 6 = 13)
  const num1 = 7;
  const num2 = 8;
  const expectedSum = 15;

  const handleVerifyGate = (e: React.FormEvent) => {
    e.preventDefault();
    if (parseInt(gateAnswer.trim(), 10) === expectedSum) {
      setGatePassed(true);
      setGateError("");
    } else {
      setGateError("Incorrect answer. Please try again.");
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="w-full max-w-lg bg-white rounded-3xl shadow-2xl border-4 border-amber-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="bg-gradient-to-r from-amber-500 to-orange-500 text-white p-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">⚙️</span>
            <h2 className="text-xl font-extrabold tracking-tight">
              Grown-Up Settings & Privacy
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="w-11 h-11 flex items-center justify-center rounded-xl bg-white/20 hover:bg-white/30 text-white font-bold transition-colors min-h-[44px] min-w-[44px]"
          >
            ✕
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {!gatePassed ? (
            /* Adult Gate Screen */
            <form onSubmit={handleVerifyGate} className="space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-slate-700">
                <p className="font-semibold text-slate-800 mb-1">
                  Parental Gate
                </p>
                <p>
                  To prevent young children from accidentally resetting learning
                  progress, please solve this simple question:
                </p>
              </div>

              <div>
                <label
                  htmlFor="gate-question"
                  className="block text-base font-bold text-slate-800 mb-2"
                >
                  What is {num1} + {num2}?
                </label>
                <input
                  id="gate-question"
                  type="number"
                  inputMode="numeric"
                  value={gateAnswer}
                  onChange={(e) => setGateAnswer(e.target.value)}
                  placeholder="Enter answer"
                  className="w-full px-4 py-3 text-lg border-2 border-slate-300 rounded-xl focus:outline-none focus:border-amber-500 min-h-[48px]"
                  autoFocus
                />
              </div>

              {gateError && (
                <p className="text-sm text-rose-600 font-medium">
                  ⚠️ {gateError}
                </p>
              )}

              <p className="text-xs text-slate-400 italic">
                Note: This gate prevents accidental taps by young children; it
                does not verify legal adult identity.
              </p>

              <button
                type="submit"
                className="w-full min-h-[48px] py-3 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl shadow-sm transition-colors text-base"
              >
                Unlock Settings 🔓
              </button>
            </form>
          ) : (
            /* Unlocked Settings */
            <div className="space-y-6">
              {/* Profile Overview */}
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 space-y-2 text-sm text-slate-700">
                <h3 className="font-bold text-slate-800 text-base mb-2">
                  Current Profile Info
                </h3>
                <div className="flex justify-between py-1 border-b border-slate-200">
                  <span className="text-slate-500">Learner Nickname:</span>
                  <span className="font-semibold text-slate-800">
                    {session.nickname || "(None set)"}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200">
                  <span className="text-slate-500">Curriculum Level:</span>
                  <span className="font-bold text-amber-600">
                    {session.level}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200">
                  <span className="text-slate-500">Current Mode:</span>
                  <span className="capitalize font-semibold text-slate-800">
                    {session.mode}
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">Revision State:</span>
                  <span className="font-mono text-xs text-slate-600">
                    v{session.revision}
                  </span>
                </div>
              </div>

              {/* Data Storage & Retention Policy */}
              <div className="bg-amber-50/70 border border-amber-200 rounded-2xl p-4 text-xs text-slate-700 space-y-1.5">
                <h4 className="font-bold text-slate-800 text-sm mb-1">
                  📁 Storage & Data Retention
                </h4>
                <p>
                  • <strong>Local SQLite Storage:</strong> All chat records,
                  activities, and level progress are persisted on this local
                  device in an SQLite database.
                </p>
                <p>
                  • <strong>Retention Period:</strong> Sessions expire
                  automatically after 30 days of inactivity.
                </p>
                <p>
                  • <strong>Privacy:</strong> We never log child names, passwords,
                  or personal communications.
                </p>
              </div>

              {/* Danger Zone: Reset and Delete */}
              <div className="border-t border-slate-200 pt-4 space-y-3">
                <h4 className="font-bold text-slate-800 text-sm">
                  Learning Data Actions
                </h4>

                {/* Reset Action */}
                {!showResetConfirm ? (
                  <button
                    onClick={() => setShowResetConfirm(true)}
                    disabled={isLoading}
                    className="w-full min-h-[48px] py-2.5 px-4 bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 font-bold rounded-xl text-sm transition-colors text-left flex items-center justify-between"
                  >
                    <span>Reset Learning Progress</span>
                    <span className="text-xs bg-amber-200 px-2 py-0.5 rounded-sm">
                      Clears answers
                    </span>
                  </button>
                ) : (
                  <div className="bg-amber-100 border border-amber-300 rounded-xl p-3.5 space-y-3">
                    <p className="text-xs text-amber-950 font-medium">
                      Reset all scored activities and return to starting lessons?
                      Chat history will be refreshed.
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={async () => {
                          await onReset();
                          setShowResetConfirm(false);
                          onClose();
                        }}
                        disabled={isLoading}
                        className="flex-1 min-h-[44px] py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-lg text-xs"
                      >
                        Confirm Reset
                      </button>
                      <button
                        onClick={() => setShowResetConfirm(false)}
                        className="flex-1 min-h-[44px] py-2 bg-white text-slate-700 border border-slate-300 font-semibold rounded-lg text-xs"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {/* Delete All Data Action */}
                {!showDeleteConfirm ? (
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    disabled={isLoading}
                    className="w-full min-h-[48px] py-2.5 px-4 bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-200 font-bold rounded-xl text-sm transition-colors text-left flex items-center justify-between"
                  >
                    <span>Delete All Data & Sign Out</span>
                    <span className="text-xs bg-rose-200 px-2 py-0.5 rounded-sm">
                      Full wipe
                    </span>
                  </button>
                ) : (
                  <div className="bg-rose-50 border border-rose-300 rounded-xl p-3.5 space-y-3">
                    <p className="text-xs text-rose-950 font-medium">
                      Are you sure? This deletes the profile and all local data
                      permanently. You will return to initial setup.
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={async () => {
                          await onDelete();
                          setShowDeleteConfirm(false);
                          onClose();
                        }}
                        disabled={isLoading}
                        className="flex-1 min-h-[44px] py-2 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-lg text-xs"
                      >
                        Permanently Delete
                      </button>
                      <button
                        onClick={() => setShowDeleteConfirm(false)}
                        className="flex-1 min-h-[44px] py-2 bg-white text-slate-700 border border-slate-300 font-semibold rounded-lg text-xs"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
