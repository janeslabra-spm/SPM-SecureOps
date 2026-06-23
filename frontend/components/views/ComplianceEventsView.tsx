"use client";

import { useCallback } from "react";

import { usePolling } from "@/hooks/usePolling";
import { useApiClient } from "@/hooks/useApiClient";
import { POLLING_INTERVALS } from "@/lib/constants";
import { mapBackendIncidents, BackendIncident } from "@/lib/incident-mapper";
import type { ComplianceEvent } from "@/lib/types";

import { SystemStatusCards } from "@/components/widgets/SystemStatusCards";
import { EventFeed } from "@/components/widgets/EventFeed";
import { AiAssistant } from "@/components/widgets/AiAssistant";

export function ComplianceEventsView() {
  const api = useApiClient();

  const fetcher = useCallback(async (): Promise<ComplianceEvent[]> => {
    const raw = await api.getIncidents();
    const mapped = mapBackendIncidents(raw as BackendIncident[]);
    return mapped.sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    ).slice(0, 100);
  }, [api]);

  const { data: events, loading } = usePolling<ComplianceEvent[]>(
    fetcher,
    POLLING_INTERVALS.DASHBOARD
  );

  const allEvents = events ?? [];

  return (
    <div data-testid="view-events" className="flex flex-col gap-4 h-[calc(100vh-180px)]">
      <SystemStatusCards />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5 flex-1 min-h-0">
        {/* Event Feed — scrollable within fixed height */}
        <div className="lg:col-span-3 min-h-0">
          <EventFeed
            events={allEvents}
            loading={loading && !events}
            maxItems={100}
            className="h-full max-h-[calc(100vh-320px)]"
          />
        </div>
        {/* AI Assistant — sticky sidebar */}
        <div className="lg:col-span-2 min-h-0">
          <AiAssistant
            events={allEvents}
            viewContext="events"
            className="h-fit lg:sticky lg:top-4"
          />
        </div>
      </div>
    </div>
  );
}

export default ComplianceEventsView;
