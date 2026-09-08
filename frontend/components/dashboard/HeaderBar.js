/**
 * HeaderBar — Top navigation bar for the operator dashboard.
 *
 * Shows: platform branding, venue selector, connection status, system health,
 *        last-update timestamp, authenticated user display name + role badge,
 *        and a Logout button (Sprint 15).
 */
'use client';

import React, { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/Badge';
import { ConnectionState } from '@/hooks/useVenueWebSocket';
import { API_BASE_URL } from '@/lib/constants';

const CONNECTION_LABELS = {
  [ConnectionState.CONNECTED]: 'Live',
  [ConnectionState.CONNECTING]: 'Connecting…',
  [ConnectionState.RECONNECTING]: 'Reconnecting…',
  [ConnectionState.DISCONNECTED]: 'Disconnected',
  [ConnectionState.ERROR]: 'Error',
  [ConnectionState.IDLE]: 'Idle',
};

const ROLE_LABELS = {
  super_admin: 'Super Admin',
  venue_admin: 'Venue Admin',
  operator: 'Operator',
  analyst: 'Analyst',
  SUPER_ADMIN: 'Super Admin',
  VENUE_ADMIN: 'Venue Admin',
  OPERATOR: 'Operator',
  ANALYST: 'Analyst',
};

const ROLE_COLORS = {
  super_admin: 'text-rose-400 bg-rose-900/30 border-rose-700/50',
  venue_admin: 'text-amber-400 bg-amber-900/30 border-amber-700/50',
  operator: 'text-cyan-400 bg-cyan-900/30 border-cyan-700/50',
  analyst: 'text-violet-400 bg-violet-900/30 border-violet-700/50',
  SUPER_ADMIN: 'text-rose-400 bg-rose-900/30 border-rose-700/50',
  VENUE_ADMIN: 'text-amber-400 bg-amber-900/30 border-amber-700/50',
  OPERATOR: 'text-cyan-400 bg-cyan-900/30 border-cyan-700/50',
  ANALYST: 'text-violet-400 bg-violet-900/30 border-violet-700/50',
};

function formatTimestamp(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '—';
  }
}

export function HeaderBar({
  venues = [],
  activeVenueId = '',
  onVenueChange,
  connectionStatus = ConnectionState.IDLE,
  lastUpdated = null,
  systemStatus = null,
  isLoadingVenues = false,
  /** Sprint 15: authenticated user object from GET /api/v1/auth/me */
  user = null,
}) {
  const router = useRouter();
  const connLabel = CONNECTION_LABELS[connectionStatus] || 'Unknown';

  const handleLogout = useCallback(async () => {
    try {
      await fetch(
        `${API_BASE_URL.replace(/\/$/, '')}/api/v1/auth/logout`,
        {
          method: 'POST',
          credentials: 'include', // send HttpOnly cookie so server can revoke jti
        },
      );
    } catch {
      // Ignore network errors — clear cookie server-side best-effort
    } finally {
      // Always redirect to login; cookie cleared by server Set-Cookie response
      router.replace('/login');
    }
  }, [router]);

  return (
    <header className="sticky top-0 z-30 bg-slate-900/95 backdrop-blur-sm border-b border-slate-700/60 shadow-xl shadow-slate-900/50">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4 flex-wrap">

        {/* Brand */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-900/40">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.477 0 8.268 2.943 9.542 7-.274.823-.67 1.59-1.168 2.282M15.536 15.536A4.978 4.978 0 0112 17a4.978 4.978 0 01-3.536-1.464M9.88 9.88A3 3 0 0112 9" />
            </svg>
          </div>
          <div>
            <span className="text-base font-bold text-white tracking-tight">CrowdOS</span>
            <span className="ml-2 text-xs text-slate-400 hidden sm:inline">Operator Dashboard</span>
          </div>
        </div>

        {/* Venue Selector */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 font-medium hidden sm:block">Venue</label>
          <select
            value={activeVenueId}
            onChange={(e) => onVenueChange && onVenueChange(e.target.value)}
            disabled={isLoadingVenues || venues.length === 0}
            className="bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 disabled:opacity-50 min-w-[140px]"
          >
            {isLoadingVenues ? (
              <option>Loading…</option>
            ) : venues.length === 0 ? (
              <option>No venues</option>
            ) : (
              venues.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))
            )}
          </select>
        </div>

        {/* Right cluster: status indicators + user info + logout */}
        <div className="flex items-center gap-3 text-xs flex-wrap">
          {/* WebSocket Connection State */}
          <Badge variant={connectionStatus} dot size="sm">
            {connLabel}
          </Badge>

          {/* System Status indicators */}
          {systemStatus && (
            <>
              <span className={`hidden md:inline text-xs ${systemStatus.database_connected ? 'text-emerald-400' : 'text-rose-400'}`}>
                {systemStatus.database_connected ? '● DB' : '○ DB'}
              </span>
              <span className={`hidden md:inline text-xs ${systemStatus.redis_configured ? 'text-emerald-400' : 'text-slate-500'}`}>
                {systemStatus.redis_configured ? '● Redis' : '○ Redis'}
              </span>
              <span className={`hidden md:inline text-xs ${systemStatus.ai_engine_available ? 'text-cyan-400' : 'text-amber-400'}`}>
                {systemStatus.ai_engine_available ? '● AI' : '○ AI (stub)'}
              </span>
            </>
          )}

          {/* Last Updated */}
          {lastUpdated && (
            <span className="text-slate-500 hidden sm:block">
              Updated {formatTimestamp(lastUpdated)}
            </span>
          )}

          {/* User display name + role badge (Sprint 15) */}
          {user && (
            <div className="hidden sm:flex items-center gap-2 pl-2 border-l border-slate-700">
              <span className="text-slate-300 font-medium max-w-[120px] truncate" title={user.display_name || user.email}>
                {user.display_name || user.email}
              </span>
              {user.role && (
                <span
                  className={`px-1.5 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wide ${ROLE_COLORS[user.role] || 'text-slate-400 bg-slate-800 border-slate-700'}`}
                >
                  {ROLE_LABELS[user.role] || user.role}
                </span>
              )}
            </div>
          )}

          {/* Logout button (Sprint 15) */}
          <button
            onClick={handleLogout}
            className="ml-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-600 hover:border-slate-500 text-slate-300 hover:text-white text-xs font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-cyan-500"
            title="Sign out"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}

