"use client";

import React from "react";

interface MascotProps {
  mood?: "idle" | "thinking" | "happy" | "encouraging" | "break";
  size?: number;
  className?: string;
}

/**
 * Pip the Mascot - A friendly, colorful companion for young learners.
 * Rendered purely with inline SVG for crisp display, zero network assets,
 * and high accessibility.
 */
export default function Mascot({
  mood = "idle",
  size = 72,
  className = "",
}: MascotProps) {
  return (
    <div
      className={`inline-flex items-center justify-center select-none ${className}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        className={`transition-transform duration-300 ${
          mood === "thinking"
            ? "animate-pulse"
            : mood === "happy"
            ? "animate-bounce"
            : "hover:scale-105"
        }`}
      >
        {/* Soft background glow */}
        <circle cx="50" cy="50" r="46" fill="#FEF3C7" opacity="0.6" />

        {/* Mascot Body - warm sunny yellow/amber */}
        <circle cx="50" cy="54" r="34" fill="#F59E0B" />
        <circle cx="50" cy="54" r="30" fill="#FBBF24" />

        {/* Belly patch - soft cream */}
        <ellipse cx="50" cy="62" rx="18" ry="16" fill="#FFFBEB" />

        {/* Little Owl Ears / Tufts */}
        <path d="M 28 32 Q 24 20 36 28 Z" fill="#D97706" />
        <path d="M 72 32 Q 76 20 64 28 Z" fill="#D97706" />

        {/* Wing Left */}
        <path
          d={
            mood === "happy"
              ? "M 22 50 Q 12 38 20 60 Z"
              : "M 22 52 Q 14 60 22 68 Z"
          }
          fill="#D97706"
          className={mood === "happy" ? "animate-wiggle" : ""}
        />

        {/* Wing Right */}
        <path
          d={
            mood === "happy"
              ? "M 78 50 Q 88 38 80 60 Z"
              : "M 78 52 Q 86 60 78 68 Z"
          }
          fill="#D97706"
        />

        {/* Big expressive eye sockets */}
        <circle cx="39" cy="46" r="11" fill="#FFFFFF" />
        <circle cx="61" cy="46" r="11" fill="#FFFFFF" />

        {/* Pupils */}
        {mood === "break" ? (
          // Sleepy / restful closed eyes
          <>
            <path
              d="M 32 48 Q 39 53 46 48"
              stroke="#1E293B"
              strokeWidth="3"
              fill="none"
              strokeLinecap="round"
            />
            <path
              d="M 54 48 Q 61 53 68 48"
              stroke="#1E293B"
              strokeWidth="3"
              fill="none"
              strokeLinecap="round"
            />
          </>
        ) : mood === "thinking" ? (
          // Looking up playfully
          <>
            <circle cx="41" cy="42" r="5" fill="#0F172A" />
            <circle cx="43" cy="40" r="2" fill="#FFFFFF" />
            <circle cx="63" cy="42" r="5" fill="#0F172A" />
            <circle cx="65" cy="40" r="2" fill="#FFFFFF" />
          </>
        ) : (
          // Friendly direct gaze with cheerful sparkle
          <>
            <circle cx="39" cy="47" r="6" fill="#0F172A" />
            <circle cx="41" cy="45" r="2.5" fill="#FFFFFF" />
            <circle cx="61" cy="47" r="6" fill="#0F172A" />
            <circle cx="63" cy="45" r="2.5" fill="#FFFFFF" />
          </>
        )}

        {/* Rosy cheeks */}
        <circle cx="28" cy="56" r="5" fill="#FDA4AF" opacity="0.8" />
        <circle cx="72" cy="56" r="5" fill="#FDA4AF" opacity="0.8" />

        {/* Cute orange beak */}
        <polygon points="50,50 44,57 56,57" fill="#EA580C" />

        {/* Little explorer scarf / star collar */}
        <path d="M 38 72 Q 50 78 62 72 Q 50 82 38 72 Z" fill="#38BDF8" />
        <circle cx="50" cy="76" r="3" fill="#FCD34D" />

        {/* Tiny cute feet */}
        <ellipse cx="43" cy="84" rx="4" ry="2.5" fill="#EA580C" />
        <ellipse cx="57" cy="84" rx="4" ry="2.5" fill="#EA580C" />
      </svg>
    </div>
  );
}
