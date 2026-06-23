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
    <div data-testid="view-events" className="flex flex-col gap-4">
      <SystemStatusCards />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <EventFeed events={allEvents} loading={loading && !events} maxItems={100} />
        <AiAssistant events={allEvents} viewContext="events" />
      </div>
    </div>
  );
}

export default ComplianceEventsView;
