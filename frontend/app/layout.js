import './globals.css';

export const metadata = {
  title: 'CrowdOS — AI Crowd Intelligence Platform',
  description: 'Enterprise AI-powered crowd monitoring and intelligence platform',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-900 text-slate-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
