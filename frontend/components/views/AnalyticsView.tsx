"use client";

import { useCallback, useMemo } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Cell,
  ResponsiveContainer,
} from "recharts";

import { usePolling } from "@/hooks/usePolling";
import { useApiClient } from "@/hooks/useApiClient";
import { POLLING_INTERVALS } from "@/lib/constants";
import { mapBackendIncidents, BackendIncident } from "@/lib/incident-mapper";
import type { ComplianceEvent } from "@/lib/types";

import { ComplianceScore } from "@/components/widgets/ComplianceScore";
import { AiAssistant } from "@/components/widgets/AiAssistant";

/** Color palette for pie chart segments */
const PIE_COLORS = ["#ef4444", "#22c55e", "#f59e0b"];

/** Day names for bar chart x-axis (Mon–Sun) */
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function getWeekStart(): Date {
  const now = new Date();
  const day = now.getDay();
  const diff = day === 0 ? 6 : day - 1;
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - diff);
  monday.setHours(0, 0, 0, 0);
  return monday;
}

function getSevenDaysAgo(): Date {
  const now = new Date();
  const past = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7);
  past.setHours(0, 0, 0, 0);
  return past;
}

function categorizeEvent(event: ComplianceEvent): string {
  if (event.status === "False Positive") return "False Positive";
  if (
    event.eventType === "PHONE_ON_TABLE" ||
    event.eventType === "PHONE_HELD_OR_NEAR_PERSON"
  ) return "Mobile Device";
  return "Printed Material";
}

/**
 * AnalyticsView — Compliance monitoring trends and distribution.
 *
 * Layout:
 * 1. Top row: Bar chart (Daily Events) + Donut (Event Categories)
 * 2. Middle: Line chart (Weekly Monitoring Trends) - full width
 * 3. Bottom: Compliance Score + AI Assistant
 */
export function AnalyticsView() {
  const api = useApiClient();

  const fetcher = useCallback(async (): Promise<ComplianceEvent[]> => {
    const raw = await api.getIncidents();
    return mapBackendIncidents(raw as BackendIncident[]);
  }, [api]);

  const { data: events } = usePolling<ComplianceEvent[]>(
    fetcher,
    POLLING_INTERVALS.DASHBOARD
  );

  const allEvents = events ?? [];

  const past7DaysEvents = useMemo(() => {
    const cutoff = getSevenDaysAgo();
    return allEvents.filter((e) => new Date(e.timestamp) >= cutoff);
  }, [allEvents]);

  // Bar Chart Data
  const barChartData = useMemo(() => {
    const weekStart = getWeekStart();
    const dayCounts = DAY_NAMES.map((name, index) => ({
      name,
      count: 0,
      date: new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + index),
    }));

    allEvents.forEach((event) => {
      const eventDate = new Date(event.timestamp);
      for (const day of dayCounts) {
        if (
          eventDate.getFullYear() === day.date.getFullYear() &&
          eventDate.getMonth() === day.date.getMonth() &&
          eventDate.getDate() === day.date.getDate()
        ) {
          day.count++;
          break;
        }
      }
    });

    return dayCounts.map(({ name, count }) => ({ name, count }));
  }, [allEvents]);

  // Pie Chart Data
  const pieChartData = useMemo(() => {
    const categoryMap = new Map<string, number>();
    past7DaysEvents.forEach((event) => {
      const category = categorizeEvent(event);
      categoryMap.set(category, (categoryMap.get(category) ?? 0) + 1);
    });
    return Array.from(categoryMap.entries()).map(([name, value]) => ({ name, value }));
  }, [past7DaysEvents]);

  // Line Chart Data
  const lineChartData = useMemo(() => {
    const cutoff = getSevenDaysAgo();
    const days: { name: string; reviews: number; confirmed: number }[] = [];

    for (let i = 0; i < 7; i++) {
      const dayDate = new Date(cutoff.getFullYear(), cutoff.getMonth(), cutoff.getDate() + i);
      const dayName = `Day ${i + 1}`;

      const dayEvents = past7DaysEvents.filter((e) => {
        const ed = new Date(e.timestamp);
        return (
          ed.getFullYear() === dayDate.getFullYear() &&
          ed.getMonth() === dayDate.getMonth() &&
          ed.getDate() === dayDate.getDate()
        );
      });

      const reviews = dayEvents.filter((e) => e.status !== "Pending Review").length;
      const confirmed = dayEvents.filter((e) => e.status === "Confirmed").length;
      days.push({ name: dayName, reviews, confirmed });
    }

    return days;
  }, [past7DaysEvents]);

  const barChartEmpty = barChartData.every((d) => d.count === 0);
  const pieChartEmpty = pieChartData.length === 0;
  const lineChartEmpty = lineChartData.every((d) => d.reviews === 0 && d.confirmed === 0);

  return (
    <div data-testid="view-analytics" className="space-y-6">
      {/* Page header */}
      <div>
        <p className="text-sm text-muted-foreground">
          Compliance monitoring trends and distribution
        </p>
      </div>

      {/* Top row: Bar + Donut */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[3fr_2fr]">
        {/* Bar Chart — Daily Compliance Events */}
        <section className="glass-card p-6" aria-label="Daily compliance events chart">
          <div className="mb-4">
            <h3 className="text-sm font-medium text-foreground">Daily Compliance Events</h3>
            <p className="text-xs text-muted-foreground">Events per day, current week</p>
          </div>
          {barChartEmpty ? (
            <div className="flex h-64 items-center justify-center">
              <p className="text-sm text-muted-foreground/60">No data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={256}>
              <BarChart data={barChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1a1f2e",
                    border: "1px solid #2a3040",
                    borderRadius: "8px",
                    color: "#e2e8f0",
                  }}
                />
                <Bar dataKey="count" name="Events" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>

        {/* Donut Chart — Event Categories */}
        <section className="glass-card p-6" aria-label="Event categories chart">
          <div className="mb-4">
            <h3 className="text-sm font-medium text-foreground">Event Categories</h3>
            <p className="text-xs text-muted-foreground">Distribution by detection type</p>
          </div>
          {pieChartEmpty ? (
            <div className="flex h-64 items-center justify-center">
              <p className="text-sm text-muted-foreground/60">No data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={256}>
              <PieChart>
                <Pie
                  data={pieChartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  dataKey="value"
                  nameKey="name"
                  strokeWidth={0}
                >
                  {pieChartData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1a1f2e",
                    border: "1px solid #2a3040",
                    borderRadius: "8px",
                    color: "#e2e8f0",
                  }}
                />
                <Legend
                  iconType="circle"
                  wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </section>
      </div>

      {/* Line Chart — Weekly Monitoring Trends (full width) */}
      <section className="glass-card p-6" aria-label="Weekly monitoring trends chart">
        <div className="mb-4">
          <h3 className="text-sm font-medium text-foreground">Weekly Monitoring Trends</h3>
          <p className="text-xs text-muted-foreground">Past 7 days, reviews vs confirmed</p>
        </div>
        {lineChartEmpty ? (
          <div className="flex h-64 items-center justify-center">
            <p className="text-sm text-muted-foreground/60">No data available</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={256}>
            <LineChart data={lineChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1f2e",
                  border: "1px solid #2a3040",
                  borderRadius: "8px",
                  color: "#e2e8f0",
                }}
              />
              <Legend iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
              <Line
                type="monotone"
                dataKey="confirmed"
                name="Confirmed"
                stroke="#22c55e"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="reviews"
                name="Reviews"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* Bottom: Compliance Score + AI Assistant */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ComplianceScore events={allEvents} />
        <AiAssistant events={allEvents} viewContext="analytics" />
      </div>
    </div>
  );
}

export default AnalyticsView;
