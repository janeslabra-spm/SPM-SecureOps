import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface IncidentRecord {
  timestamp: string;
}

interface AnalyticsGraphProps {
  incidents: IncidentRecord[];
}

interface HourlyData {
  hour: string;
  count: number;
}

function aggregateByHour(incidents: IncidentRecord[]): HourlyData[] {
  const now = new Date();
  const todayStart = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  );

  // Initialize all 24 hours
  const hourCounts: Record<number, number> = {};
  for (let h = 0; h < 24; h++) {
    hourCounts[h] = 0;
  }

  // Count incidents for today grouped by hour
  for (const incident of incidents) {
    const ts = new Date(incident.timestamp);
    if (ts >= todayStart && ts <= now) {
      const hour = ts.getHours();
      hourCounts[hour] = (hourCounts[hour] || 0) + 1;
    }
  }

  // Only include hours up to current hour
  const currentHour = now.getHours();
  const data: HourlyData[] = [];
  for (let h = 0; h <= currentHour; h++) {
    data.push({
      hour: `${h.toString().padStart(2, "0")}:00`,
      count: hourCounts[h],
    });
  }

  return data;
}

export default function AnalyticsGraph({ incidents }: AnalyticsGraphProps) {
  const data = aggregateByHour(incidents);
  const totalToday = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <div className="bg-bg-card border border-border rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">
            Detection Analytics
          </h3>
          <p className="text-xs text-text-muted mt-0.5">Incidents per hour today</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs text-text-muted">Today</div>
            <div className="text-lg font-bold text-text-primary">{totalToday}</div>
          </div>
          <button className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-bg-hover transition-colors">
            <svg className="w-4 h-4 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="1" />
              <circle cx="19" cy="12" r="1" />
              <circle cx="5" cy="12" r="1" />
            </svg>
          </button>
        </div>
      </div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
            <defs>
              <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22C55E" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorGradientOrange" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#FB923C" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#FB923C" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis
              dataKey="hour"
              tick={{ fill: "#9CA3AF", fontSize: 11 }}
              axisLine={{ stroke: "#E5E7EB" }}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "#9CA3AF", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#FFFFFF",
                border: "1px solid #E5E7EB",
                borderRadius: "8px",
                color: "#1B1B1B",
                boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
              }}
              labelStyle={{ color: "#6B7280" }}
            />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#22C55E"
              strokeWidth={2.5}
              fill="url(#colorGradient)"
              dot={false}
              activeDot={{ r: 5, fill: "#22C55E", stroke: "#fff", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
