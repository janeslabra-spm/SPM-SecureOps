"use client";

import { Bell, Cloud, MapPin, Menu, Users, WifiOff } from "lucide-react";
import { useClock } from "@/hooks/useClock";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

export interface TopbarProps {
  onMenu: () => void;
  connectionError?: boolean;
}

export function Topbar({ onMenu, connectionError = false }: TopbarProps) {
  const time = useClock();

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-xl md:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={onMenu}
        aria-label="Open navigation"
      >
        <Menu className="size-5" />
      </Button>

      {/* Monitored area */}
      <div className="flex items-center gap-2">
        <MapPin className="size-4 text-primary" />
        <div className="leading-tight">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
            Monitored Area
          </p>
          <p className="text-sm font-semibold">Production Floor A</p>
        </div>
      </div>

      {/* Monitoring Active pill */}
      <div className="mx-auto hidden items-center gap-2 rounded-full border border-success/30 bg-success/10 px-3 py-1.5 sm:flex">
        <span className="relative flex size-2">
          <span className="pulse-dot absolute inline-flex size-2 rounded-full bg-success" />
          <span className="relative inline-flex size-2 rounded-full bg-success" />
        </span>
        <span className="text-xs font-semibold text-success">Monitoring Active</span>
      </div>

      <div className="ml-auto flex items-center gap-2 sm:gap-4">
        {/* Clock */}
        <span className="hidden font-mono text-sm tabular-nums text-muted-foreground lg:inline">
          {time}
        </span>

        {/* Connected users */}
        <div className="hidden items-center gap-1.5 text-sm text-muted-foreground md:flex">
          <Users className="size-4" />
          <span className="font-medium text-foreground">8</span>
          <span className="hidden lg:inline">connected</span>
        </div>

        {/* AWS / Connection status */}
        {connectionError ? (
          <div className="flex items-center gap-1.5 rounded-full border border-danger/30 bg-danger/10 px-2.5 py-1 text-xs">
            <WifiOff className="size-3.5 text-danger" />
            <span className="text-danger font-medium">Disconnected</span>
          </div>
        ) : (
          <div className="hidden items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs sm:flex">
            <Cloud className="size-3.5 text-success" />
            <span className="text-muted-foreground">AWS</span>
            <span className="size-1.5 rounded-full bg-success" />
          </div>
        )}

        {/* Notifications */}
        <button
          className="relative grid size-9 place-items-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Notifications"
        >
          <Bell className="size-4" />
          <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-warning ring-2 ring-card" />
        </button>

        {/* Avatar */}
        <Avatar className="size-9 border border-border">
          <AvatarFallback className="bg-primary/15 text-xs font-semibold text-primary">
            DO
          </AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}

export default Topbar;
