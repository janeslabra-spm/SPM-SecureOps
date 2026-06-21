interface StatusCardProps {
  title: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: {
    value: string;
    direction: 'up' | 'down' | 'neutral';
  };
  highlight?: boolean;
}

export default function StatusCard({ title, value, icon, trend, highlight = false }: StatusCardProps) {
  const trendColor = trend?.direction === 'up' 
    ? 'text-success' 
    : trend?.direction === 'down' 
      ? 'text-danger' 
      : 'text-text-muted';

  return (
    <div className={`flex-1 min-w-[200px] rounded-xl p-5 transition-all duration-200 ${
      highlight 
        ? 'bg-primary text-white shadow-lg shadow-primary/20' 
        : 'bg-bg-card border border-border shadow-sm hover:shadow-md'
    }`}>
      <div className="flex items-start justify-between mb-3">
        <span className={`text-sm font-medium ${highlight ? 'text-white/80' : 'text-text-secondary'}`}>
          {title}
        </span>
        {icon && (
          <div className={`w-9 h-9 rounded-full flex items-center justify-center ${
            highlight ? 'bg-white/20' : 'bg-bg-page'
          }`}>
            {icon}
          </div>
        )}
      </div>
      <div className={`text-2xl font-bold ${highlight ? 'text-white' : 'text-text-primary'}`}>
        {value}
      </div>
      {trend && (
        <div className="flex items-center gap-1 mt-2">
          <span className={`text-xs font-medium ${highlight ? (trend.direction === 'up' ? 'text-accent-green' : 'text-red-300') : trendColor}`}>
            {trend.direction === 'up' ? '↑' : trend.direction === 'down' ? '↓' : '→'} {trend.value}
          </span>
          <span className={`text-xs ${highlight ? 'text-white/60' : 'text-text-muted'}`}>
            from last hour
          </span>
        </div>
      )}
    </div>
  );
}
