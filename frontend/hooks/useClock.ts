"use client";

import { useState, useEffect } from "react";

/**
 * Formats the current time as HH:MM:SS (24-hour format).
 */
function formatTime(date: Date): string {
  const hours = date.getHours().toString().padStart(2, "0");
  const minutes = date.getMinutes().toString().padStart(2, "0");
  const seconds = date.getSeconds().toString().padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

/**
 * Real-time clock hook that returns the current time as "HH:MM:SS".
 * Updates every second. Cleans up the interval on unmount.
 *
 * Initializes with an empty string to avoid hydration mismatch
 * (server and client would render different times), then sets
 * the real time on first client-side effect.
 */
export function useClock(): string {
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    // Set immediately on client mount
    setTime(formatTime(new Date()));

    const intervalId = setInterval(() => {
      setTime(formatTime(new Date()));
    }, 1000);

    return () => {
      clearInterval(intervalId);
    };
  }, []);

  return time;
}
