export default function DashboardLayout({ children }) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Sidebar / Header Navigation shell placeholder */}
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
