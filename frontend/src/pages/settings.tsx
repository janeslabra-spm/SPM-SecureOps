export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-text-primary">Settings</h2>
        <p className="text-sm text-text-muted mt-0.5">System configuration and security policies</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Detection Settings */}
        <div className="bg-bg-card border border-border rounded-xl shadow-sm p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Detection Settings</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-primary">Auto Detection</p>
                <p className="text-xs text-text-muted">Automatically detect policy violations</p>
              </div>
              <div className="w-10 h-6 bg-success rounded-full relative cursor-pointer">
                <div className="absolute right-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform" />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-primary">Alert Notifications</p>
                <p className="text-xs text-text-muted">Real-time incident notifications</p>
              </div>
              <div className="w-10 h-6 bg-success rounded-full relative cursor-pointer">
                <div className="absolute right-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform" />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-primary">Confidence Threshold</p>
                <p className="text-xs text-text-muted">Minimum confidence to log incident</p>
              </div>
              <span className="text-sm font-medium text-primary">60%</span>
            </div>
          </div>
        </div>

        {/* Data Retention */}
        <div className="bg-bg-card border border-border rounded-xl shadow-sm p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Data Retention</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-primary">Retention Period</p>
                <p className="text-xs text-text-muted">How long incidents are stored</p>
              </div>
              <span className="text-sm font-medium text-text-primary">7 Days</span>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-primary">Auto Delete</p>
                <p className="text-xs text-text-muted">Automatically purge old records</p>
              </div>
              <div className="w-10 h-6 bg-success rounded-full relative cursor-pointer">
                <div className="absolute right-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform" />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-primary">Compliance</p>
                <p className="text-xs text-text-muted">Data governance standard</p>
              </div>
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-success/10 text-success">ISO 27001</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
