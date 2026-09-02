/**
 * HeaderBar — Top navigation bar for the operator dashboard.
 *
 * Shows: platform branding, venue selector, connection status, system health, last-update timestamp.
 */
'use client';

import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { ConnectionState } from '@/hooks/useVenueWebSocket';

const CONNECTION_LABELS = {
  [ConnectionState.CONNECTED]: 'Live',
  [ConnectionState.CONNECTING]: 'Connecting…',
  [ConnectionState.RECONNECTING]: 'Reconnecting…',
  [ConnectionState.DISCONNECTED]: 'Disconnected',
  [ConnectionState.ERROR]: 'Error',
  [ConnectionState.IDLE]: 'Idle',
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
}) {
  const connLabel = CONNECTION_LABELS[connectionStatus] || 'Unknown';

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

        {/* Right cluster: status indicators */}
        <div className="flex items-center gap-3 text-xs flex-wrap">
          {/* WebSocket Connection State */}
          <Badge
            variant={connectionStatus}
            dot
            size="sm"
          >
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
        </div>
      </div>
    </header>
  );
}
