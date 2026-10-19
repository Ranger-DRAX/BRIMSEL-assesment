"use client";

import React, { useEffect, useState } from "react";
import AdultSetup from "../components/AdultSetup";
import AdultSettings from "../components/AdultSettings";
import PlacementActivity from "../components/PlacementActivity";
import ChatScreen from "../components/ChatScreen";
import Mascot from "../components/Mascot";
import {
  SessionResponse,
  createSession,
  deleteSession,
  getSession,
  resetSession,
} from "../lib/api";

export default function Home() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [inPlacement, setInPlacement] = useState(false);
  const [placementNickname, setPlacementNickname] = useState<string | undefined>();
  const [showSettings, setShowSettings] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Check existing session on mount
  useEffect(() => {
    async function init() {
      try {
        const existing = await getSession();
        setSession(existing);
      } catch (err) {
        console.error("Failed to load existing session:", err);
      } finally {
        setIsInitializing(false);
      }
    }
    init();
  }, []);

  // Handler: Adult setup completed with direct level choice
  const handleCompleteSetup = async (nickname?: string, startingLevel = "L1") => {
    setActionLoading(true);
    try {
      const newSession = await createSession(nickname, startingLevel);
      setSession(newSession);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to start session");
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Start placement quiz
  const handleStartPlacement = (nickname?: string) => {
    setPlacementNickname(nickname);
    setInPlacement(true);
  };

  // Handler: Placement quiz finished
  const handlePlacementFinish = async (selectedLevel: "L1" | "L2" | "L3") => {
    setActionLoading(true);
    try {
      const newSession = await createSession(placementNickname, selectedLevel);
      setSession(newSession);
      setInPlacement(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save placement result");
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Skip placement quiz
  const handlePlacementSkip = async () => {
    setActionLoading(true);
    try {
      const newSession = await createSession(placementNickname, "L1");
      setSession(newSession);
      setInPlacement(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Reset learning session
  const handleReset = async () => {
    setActionLoading(true);
    try {
      await resetSession();
      const updated = await getSession();
      setSession(updated);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to reset session");
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Delete profile and session
  const handleDelete = async () => {
    setActionLoading(true);
    try {
      await deleteSession();
      setSession(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete session");
    } finally {
      setActionLoading(false);
    }
  };

  // 1. Initial Loading Screen
  if (isInitializing) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-amber-50 to-orange-50 flex flex-col items-center justify-center p-4">
        <Mascot mood="thinking" size={96} className="mb-4" />
        <h2 className="text-xl font-bold text-slate-800">
          Waking up Little English Buddy... ☀️
        </h2>
        <p className="text-sm text-slate-500 mt-1">Connecting to your learning companion</p>
      </div>
    );
  }

  // 2. Placement Quiz Screen
  if (inPlacement) {
    return (
      <PlacementActivity
        nickname={placementNickname}
        onFinish={handlePlacementFinish}
        onSkip={handlePlacementSkip}
        isLoading={actionLoading}
      />
    );
  }

  // 3. Adult Setup Onboarding Screen (if no session active)
  if (!session) {
    return (
      <AdultSetup
        onComplete={handleCompleteSetup}
        onStartPlacement={handleStartPlacement}
        isLoading={actionLoading}
      />
    );
  }

  // 4. Main Child Chat Screen
  return (
    <>
      <ChatScreen
        session={session}
        onOpenSettings={() => setShowSettings(true)}
        onSessionUpdated={(updates) =>
          setSession((prev) => (prev ? { ...prev, ...updates } : null))
        }
      />

      {showSettings && (
        <AdultSettings
          session={session}
          onReset={handleReset}
          onDelete={handleDelete}
          onClose={() => setShowSettings(false)}
          isLoading={actionLoading}
        />
      )}
    </>
  );
}
