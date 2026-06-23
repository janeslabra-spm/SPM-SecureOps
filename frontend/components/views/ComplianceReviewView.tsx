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
  X,
  ImageOff,
  Camera,
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
import type { ComplianceEvent, EventStatus } from "@/lib/types";
import { cn, formatTimestamp } from "@/lib/utils";

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

// Construct evidence image URL from screenshot_path
function getEvidenceUrl(screenshotPath: string): string {
  if (!screenshotPath) return "";
  // The backend serves screenshots at /screenshots/<filename>
  // screenshot_path from DB is typically "screenshots/filename.jpg"
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
  // Strip leading "screenshots/" if present since the route already includes it
  const filename = screenshotPath.replace(/^screenshots[/\\]/, "");
  return `${baseUrl}/screenshots/${filename}`;
}

/**
 * ComplianceReviewView — Structured review and resolution workflow.
 */
export function ComplianceReviewView() {
  const api = useApiClient();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<EventStatus | "All">("All");
  const [localUpdates, setLocalUpdates] = useState<Record<number, Partial<ComplianceEvent>>>({});
  const [evidenceModal, setEvidenceModal] = useState<ComplianceEvent | null>(null);

  const fetcher = useCallback(async (): Promise<ComplianceEvent[]> => {
    const raw = await api.getIncidents();
    const mapped = mapBackendIncidents(raw as BackendIncident[]);
    return mapped.sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [api]);

  const { data: events, loading, error } = usePolling<ComplianceEvent[]>(
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
    <div data-testid="view-review" className="flex flex-col gap-4">
      {/* Table card */}
      <div className="glass overflow-hidden rounded-2xl">
        {/* Table toolbar */}
        <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold">Compliance Review Workflow</h2>
            <p className="text-xs text-muted-foreground">
              {filteredEvents.length} events in current view
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
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
              className="gap-2 bg-success/10 text-success border-success/30 hover:bg-success/20"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </div>
        </div>

        {/* Error state */}
        {error && !events && (
          <div className="p-5">
            <p className="text-sm text-danger">Failed to load events. Retrying…</p>
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
                  <TableHead className="text-xs font-medium">Event ID</TableHead>
                  <TableHead className="text-xs font-medium">Timestamp</TableHead>
                  <TableHead className="text-xs font-medium">Event Type</TableHead>
                  <TableHead className="text-xs font-medium">Review Priority</TableHead>
                  <TableHead className="text-xs font-medium">Status</TableHead>
                  <TableHead className="text-xs font-medium">Reviewer</TableHead>
                  <TableHead className="text-xs font-medium">Notes</TableHead>
                  <TableHead className="text-xs font-medium">Evidence</TableHead>
                  <TableHead className="text-xs font-medium text-right">Actions</TableHead>
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
                        {event.eventType === "PHONE_ON_TABLE" || event.eventType === "PHONE_HELD_OR_NEAR_PERSON"
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
                          className={cn(
                            "h-7 gap-1.5 text-xs",
                            event.screenshotPath
                              ? "bg-primary/10 text-primary border-primary/30 hover:bg-primary/20 cursor-pointer"
                              : "bg-muted/50 text-muted-foreground border-border/50 cursor-not-allowed opacity-60"
                          )}
                          onClick={() => {
                            if (event.screenshotPath) {
                              setEvidenceModal(event);
                            }
                          }}
                          disabled={!event.screenshotPath}
                        >
                          <Eye className="h-3 w-3" />
                          {event.screenshotPath ? "View" : "N/A"}
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

      {/* Evidence Modal */}
      {evidenceModal && (
        <EvidenceModal event={evidenceModal} onClose={() => setEvidenceModal(null)} />
      )}
    </div>
  );
}

/** Full-screen modal to display evidence screenshot */
function EvidenceModal({ event, onClose }: { event: ComplianceEvent; onClose: () => void }) {
  const [imageError, setImageError] = useState(false);
  const evidenceUrl = getEvidenceUrl(event.screenshotPath);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Evidence viewer"
    >
      <div
        className="glass relative max-h-[90vh] max-w-4xl w-full overflow-hidden rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-lg bg-primary/12 text-primary">
              <Camera className="size-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Evidence — EVT-{String(event.id).padStart(5, "0")}</h3>
              <p className="text-xs text-muted-foreground">
                {formatTimestamp(event.timestamp)} · Confidence: {(event.confidence * 100).toFixed(0)}%
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid size-8 place-items-center rounded-lg hover:bg-muted transition-colors"
            aria-label="Close evidence viewer"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Image content */}
        <div className="relative flex items-center justify-center bg-black/40 p-4 min-h-[300px] max-h-[60vh]">
          {!imageError ? (
            <img
              src={evidenceUrl}
              alt={`Evidence screenshot for event EVT-${String(event.id).padStart(5, "0")}`}
              className="max-w-full max-h-[55vh] rounded-lg object-contain"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="flex flex-col items-center gap-3 py-12">
              <ImageOff className="size-12 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Evidence image not available</p>
              <p className="text-xs text-muted-foreground/70">
                The screenshot file may have been removed by the retention policy.
              </p>
            </div>
          )}
        </div>

        {/* Modal footer with event details */}
        <div className="grid grid-cols-2 gap-3 border-t border-border px-5 py-4 sm:grid-cols-4">
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Event Type</p>
            <p className="mt-0.5 text-xs font-medium">
              {event.eventType === "PHONE_ON_TABLE" || event.eventType === "PHONE_HELD_OR_NEAR_PERSON"
                ? "Mobile Device"
                : "Printed Material"}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Priority</p>
            <Badge variant="outline" className={`mt-0.5 text-[10px] ${PRIORITY_COLORS[event.priority] ?? ""}`}>
              {event.priority}
            </Badge>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Status</p>
            <Badge variant="outline" className={`mt-0.5 text-[10px] ${STATUS_COLORS[event.status] ?? ""}`}>
              {event.status}
            </Badge>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Zone</p>
            <p className="mt-0.5 text-xs font-medium">{event.zone || "Unknown"}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ComplianceReviewView;
