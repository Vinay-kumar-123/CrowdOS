'use client';

/**
 * Dashboard layout shell.
 * HeaderBar is rendered inside the dashboard page itself because it needs
 * access to venue-specific WebSocket state that's owned by the page component.
 */
export default function DashboardLayout({ children }) {
  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      {children}
    </div>
  );
}
