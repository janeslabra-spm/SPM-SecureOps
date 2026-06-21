import CameraPanel from "../components/CameraPanel";

export default function CamerasPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-text-primary">Camera Management</h2>
        <p className="text-sm text-text-muted mt-0.5">Monitor and manage connected cameras</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Camera feed */}
        <div className="bg-bg-card border border-border rounded-xl shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <h3 className="text-sm font-semibold text-text-primary">Camera 1 — Main Desk</h3>
            </div>
            <span className="text-xs text-text-muted">Live</span>
          </div>
          <div className="aspect-video">
            <CameraPanel />
          </div>
        </div>

        {/* Camera info card */}
        <div className="bg-bg-card border border-border rounded-xl shadow-sm p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-semibold text-text-primary mb-4">Camera Details</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-border-light">
                <span className="text-sm text-text-secondary">Name</span>
                <span className="text-sm font-medium text-text-primary">Main Desk Camera</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-border-light">
                <span className="text-sm text-text-secondary">Resolution</span>
                <span className="text-sm font-medium text-text-primary">1920×1080</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-border-light">
                <span className="text-sm text-text-secondary">Connection</span>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-success/10 text-success">Connected</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-border-light">
                <span className="text-sm text-text-secondary">Stream Type</span>
                <span className="text-sm font-medium text-text-primary">MJPEG</span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-text-secondary">Location</span>
                <span className="text-sm font-medium text-text-primary">Security Zone A</span>
              </div>
            </div>
          </div>
          <div className="mt-6">
            <button className="w-full py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-light transition-colors">
              Configure Camera
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
