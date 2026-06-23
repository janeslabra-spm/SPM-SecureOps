"use client";

import { useState } from "react";
import type { ViewKey } from "@/lib/constants";

/**
 * Manages which view is currently active in the Shell.
 * Defaults to "dashboard".
 */
export function useViewState(): {
  activeView: ViewKey;
  setActiveView: (view: ViewKey) => void;
} {
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");

  return { activeView, setActiveView };
}
