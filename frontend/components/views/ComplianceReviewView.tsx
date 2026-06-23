"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Search,
  Download,
  MoreHorizontal,
  UserPlus,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Eye,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { usePolling } from "@/hooks/usePolling";
import { useApiClient } from "@/hooks/useApiClient";
import { POLLING_INTERVALS, PRIORITY_COLORS, STATUS_COLORS } from "@/lib/constants";
import { mapBackendIncidents, BackendIncident } from "@/lib/incident-mapper";
import type { ComplianceEvent, EventStatus, ReviewPriority } from "@/lib/types";
import { formatTimestamp } from "@/lib/utils";

const ALL_STATUSES: Array<EventStatus | "All"> = [
  "All",
  "Pending Review",
  "Confirmed",
  "False Positive",
  "Warning Issued",
  "Coaching Required",
  "Escalated",
  "Resolved",
];

/**
 * ComplianceReviewView — Structured review and resolution workflow.
 *
 * Table columns: Event ID, Timestamp, Event Type, Review Priority, Status,
 * Reviewer, Notes, Evidence, Actions
 */
export function ComplianceReviewView() {
  const api = useApiClient();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<EventStatus | "All">("All");
  const [localUpdates, setLocalUpdates] = useState<Record<number, Partial<ComplianceEvent>>>({});

  const fetcher = useCallback(async (): Promise<ComplianceEvent[]> => {
    const raw = await api.getIncidents();
    const mapped = mapBackendIncidents(raw as BackendIncident[]);
    return mapped.sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [api]);

  const { data: events, loading, error, refresh } = usePolling<ComplianceEvent[]>(
    fetcher,
    POLLING_INTERVALS.DASHBOARD
  );

  // Merge local updates
  const mergedEvents = useMemo(() => {
    if (!events) return [];
    return events.map((event) => {
      const update = localUpdates[event.id];
      return update ? { ...event, ...update } : event;
    });
  }, [events, localUpdates]);

  // Apply search and filters
  const filteredEvents = useMemo(() => {
    let result = mergedEvents;

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (event) =>
          String(event.id).toLowerCase().includes(query) ||
          event.detail.toLowerCase().includes(query) ||
          event.eventType.toLowerCase().includes(query) ||
          event.reviewer.toLowerCase().includes(query) ||
          event.notes.toLowerCase().includes(query)
      );
    }

    if (statusFilter !== "All") {
      result = result.filter((event) => event.status === statusFilter);
    }

    return result;
  }, [mergedEvents, searchQuery, statusFilter]);

  // Action handlers
  const handleUpdateStatus = async (id: number, newStatus: EventStatus) => {
    try {
      await api.updateIncidentStatus(id, newStatus);
      setLocalUpdates((prev) => ({ ...prev, [id]: { status: newStatus } }));
    } catch {
      console.error(`Failed to update incident ${id} to ${newStatus}`);
    }
  };

  const handleAssignReviewer = async (id: number) => {
    const name = window.prompt("Enter reviewer name:");
    if (!name || !name.trim()) return;
    setLocalUpdates((prev) => ({
      ...prev,
      [id]: { ...prev[id], reviewer: name.trim() },
    }));
  };

  const handleExportCsv = async () => {
    try {
      const params: Record<string, string> = {};
      if (statusFilter !== "All") params.status = statusFilter;
      const blob = await api.exportIncidentsCsv(params);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "compliance-events.csv";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch {
      console.error("Failed to export CSV");
    }
  };

  return (
    <div data-testid="view-review" className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Compliance Review</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Structured review and resolution workflow
        </p>
      </div>

      {/* Table card */}
      <div className="glass-card overflow-hidden">
        {/* Table toolbar */}
        <div className="flex flex-col gap-3 p-4 border-b border-border/50 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-medium text-foreground">Compliance Review Workflow</h2>
            <p className="text-xs text-muted-foreground">
              {filteredEvents.length} events in current view
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search events..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 w-[200px] bg-muted/50 border-border/50"
              />
            </div>

            {/* Status Filter */}
            <Select
              value={statusFilter}
              onValueChange={(val) => setStatusFilter(val as EventStatus | "All")}
            >
              <SelectTrigger className="w-[140px] bg-muted/50 border-border/50">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                {ALL_STATUSES.map((status) => (
                  <SelectItem key={status} value={status}>
                    {status}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Export button */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportCsv}
              className="gap-2 bg-green-500/10 text-green-400 border-green-500/30 hover:bg-green-500/20"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </div>
        </div>

        {/* Error state */}
        {error && !events && (
          <div className="p-4">
            <p className="text-sm text-red-400">Failed to load events. Retrying…</p>
          </div>
        )}

        {/* Loading state */}
        {loading && !events && (
          <div className="p-8 text-center">
            <p className="text-sm text-muted-foreground">Loading compliance events...</p>
          </div>
        )}

        {/* Data Table */}
        {events && (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead className="text-xs">Event ID</TableHead>
                  <TableHead className="text-xs">Timestamp</TableHead>
                  <TableHead className="text-xs">Event Type</TableHead>
                  <TableHead className="text-xs">Review Priority</TableHead>
                  <TableHead className="text-xs">Status</TableHead>
                  <TableHead className="text-xs">Reviewer</TableHead>
                  <TableHead className="text-xs">Notes</TableHead>
                  <TableHead className="text-xs">Evidence</TableHead>
                  <TableHead className="text-xs text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEvents.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="h-24 text-center text-muted-foreground">
                      No events match the current filters.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredEvents.map((event) => (
                    <TableRow key={event.id} className="border-border/50 hover:bg-accent/30">
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        EVT-{String(event.id).padStart(5, "0")}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatTimestamp(event.timestamp)}
                      </TableCell>
                      <TableCell className="text-xs">
                        {event.eventType === "PHONE_ON_TABLE"
                          ? "Mobile Device Detection"
                          : event.eventType === "PHONE_HELD_OR_NEAR_PERSON"
                            ? "Mobile Device Detection"
                            : "Printed Material Detection"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${PRIORITY_COLORS[event.priority] ?? ""}`}
                        >
                          {event.priority}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${STATUS_COLORS[event.status] ?? ""}`}
                        >
                          {event.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {event.reviewer || "Unassigned"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[150px] truncate">
                        {event.notes || "—"}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 gap-1.5 text-xs bg-muted/50 border-border/50"
                        >
                          <Eye className="h-3 w-3" />
                          View
                        </Button>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-accent">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Actions</span>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleAssignReviewer(event.id)}>
                              <UserPlus className="h-4 w-4" />
                              Assign Reviewer
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => handleUpdateStatus(event.id, "Confirmed")}>
                              <CheckCircle className="h-4 w-4" />
                              Mark Confirmed
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleUpdateStatus(event.id, "False Positive")}>
                              <XCircle className="h-4 w-4" />
                              Mark False Positive
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleUpdateStatus(event.id, "Escalated")}>
                              <AlertTriangle className="h-4 w-4" />
                              Escalate
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}

export default ComplianceReviewView;
