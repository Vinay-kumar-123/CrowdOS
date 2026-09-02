/**
 * CrowdOS Operator Dashboard — Main Page.
 *
 * Data flow:
 *   1. On mount: useVenues selects active venue
 *   2. useVenueWebSocket connects to /ws/venues/{venue_id}
 *   3. initial_state envelope hydrates telemetry state
 *   4. Subsequent WebSocket envelopes push incremental updates
 *   5. REST fallback provides initial session info if WS is delayed
 *   6. UI renders from telemetry state — no client-side AI computation
 */
'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useVenues } from '@/hooks/useVenues';
import { useVenueWebSocket, ConnectionState } from '@/hooks/useVenueWebSocket';
import { sessionApi } from '@/services/api/sessions';
import { dashboardApi } from '@/services/api/dashboard';

import { HeaderBar } from '@/components/dashboard/HeaderBar';
import { OccupancyCard } from '@/components/dashboard/OccupancyCard';
import { FlowCard } from '@/components/dashboard/FlowCard';
import { RiskCard } from '@/components/dashboard/RiskCard';
import { DecisionCard } from '@/components/dashboard/DecisionCard';
import { GateBreakdownCard } from '@/components/dashboard/GateBreakdownCard';
import { DensityCongestionCard } from '@/components/dashboard/DensityCongestionCard';
import { ForecastCard } from '@/components/dashboard/ForecastCard';
import { AlertsCard } from '@/components/dashboard/AlertsCard';
import { SessionControls } from '@/components/dashboard/SessionControls';
import { EventSimulator } from '@/components/dashboard/EventSimulator';

// ─── Connection Status Banner ──────────────────────────────────────────────

function ConnectionBanner({ connectionStatus }) {
  if (connectionStatus === ConnectionState.CONNECTED) return null;

  const configs = {
    [ConnectionState.CONNECTING]: {
      bg: 'bg-amber-900/20 border-amber-500/30 text-amber-400',
      message: 'Connecting to real-time stream…',
    },
    [ConnectionState.RECONNECTING]: {
      bg: 'bg-amber-900/20 border-amber-500/30 text-amber-400',
      message: 'Connection lost — reconnecting automatically…',
    },
    [ConnectionState.DISCONNECTED]: {
      bg: 'bg-rose-900/20 border-rose-500/30 text-rose-400',
      message: 'Real-time stream disconnected. Attempting to reconnect…',
    },
    [ConnectionState.ERROR]: {
      bg: 'bg-rose-900/20 border-rose-500/30 text-rose-400',
      message: 'WebSocket error. Reconnecting with exponential backoff…',
    },
    [ConnectionState.IDLE]: {
      bg: 'bg-slate-800/60 border-slate-600/30 text-slate-400',
      message: 'Initializing connection…',
    },
  };

  const config = configs[connectionStatus] || configs[ConnectionState.IDLE];

  return (
    <div className={`border rounded-lg px-4 py-2.5 text-sm flex items-center gap-2 ${config.bg}`}>
      <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
      {config.message}
    </div>
  );
}

// ─── No-Session Banner ─────────────────────────────────────────────────────

function NoSessionBanner() {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6 text-center text-slate-400">
      <svg className="mx-auto mb-3 w-10 h-10 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p className="font-semibold text-slate-300 mb-1">No active monitoring session</p>
      <p className="text-sm">Create and start a session using the Session Controls panel to begin real-time crowd monitoring.</p>
    </div>
  );
}

// ─── Main Page Component ───────────────────────────────────────────────────

export default function DashboardPage() {
  const { venues, activeVenueId, setActiveVenueId, isLoading: isLoadingVenues } = useVenues();

  const {
    telemetry,
    connectionStatus,
    lastUpdated,
    updateTelemetry,
    isConnected,
  } = useVenueWebSocket(activeVenueId, { enabled: Boolean(activeVenueId) });

  const [sessionFetchedAt, setSessionFetchedAt] = useState(null);

  // REST fallback: fetch active session and dashboard snapshot if WS hasn't provided it yet
  const fetchActiveSessionFallback = useCallback(async () => {
    if (!activeVenueId) return;
    try {
      const session = await sessionApi.getActiveSession(activeVenueId);
      if (session && session.session_id && !telemetry.activeSessionId) {
        updateTelemetry({
          activeSessionId: session.session_id,
          sessionStatus: session.status,
          venueCapacity: session.venue_capacity || telemetry.venueCapacity,
        });

        if (session.status === 'ACTIVE') {
          try {
            const snap = await dashboardApi.getVenueSessionDashboard(activeVenueId, session.session_id);
            if (snap) {
              updateTelemetry({
                currentOccupancy: snap.current_occupancy ?? 0,
                occupancyRatio: snap.occupancy_ratio ?? 0.0,
                totalEntries: snap.total_entries ?? 0,
                totalExits: snap.total_exits ?? 0,
                netFlow: snap.net_flow ?? 0,
                entryRate5m: snap.entry_rate_5m ?? 0.0,
                exitRate5m: snap.exit_rate_5m ?? 0.0,
                netFlowRate5m: snap.net_flow_rate_5m ?? 0.0,
                densityLevel: snap.density_level || 'LOW',
                congestionLevel: snap.congestion_level || 'NORMAL',
                riskLevel: snap.risk_level || 'LOW',
                riskScore: snap.risk_score ?? 0.0,
                riskFactors: snap.risk_factors || [],
                trendDirection: snap.trend_direction || 'STABLE',
                trendSlope: snap.trend_slope ?? null,
                primaryRecommendation: snap.primary_recommendation || 'MONITOR',
                recommendations: snap.recommendations || ['MONITOR'],
                activeAlerts: snap.active_alerts || [],
                occupancyForecast: snap.occupancy_forecast || null,
                flowForecast: snap.flow_forecast || null,
                gateSummaries: snap.gate_summaries || {},
              });
            }
          } catch {
            // Snapshot is best-effort; WS will fill the data
          }
        }
      }
    } catch {
      // REST fallback is best-effort; WS provides authoritative state
    }
    setSessionFetchedAt(Date.now());
  }, [activeVenueId, telemetry.activeSessionId, telemetry.venueCapacity, updateTelemetry]);

  // Run REST fallback once after WS connection if no session info yet
  useEffect(() => {
    if (isConnected && !telemetry.activeSessionId && !sessionFetchedAt) {
      const timer = setTimeout(fetchActiveSessionFallback, 1500);
      return () => clearTimeout(timer);
    }
  }, [isConnected, telemetry.activeSessionId, sessionFetchedAt, fetchActiveSessionFallback]);

  // Reset fallback tracker when venue switches
  useEffect(() => {
    setSessionFetchedAt(null);
  }, [activeVenueId]);

  const hasActiveSession = Boolean(telemetry.activeSessionId);
  const isLoading = connectionStatus === ConnectionState.CONNECTING && !lastUpdated;

  return (
    <div className="min-h-screen text-slate-100">
      {/* Sticky header */}
      <HeaderBar
        venues={venues}
        activeVenueId={activeVenueId}
        onVenueChange={setActiveVenueId}
        connectionStatus={connectionStatus}
        lastUpdated={lastUpdated}
        systemStatus={telemetry.systemStatus}
        isLoadingVenues={isLoadingVenues}
      />

      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-5 space-y-5">

        {/* Connection Status Banner */}
        <ConnectionBanner connectionStatus={connectionStatus} />

        {/* No venue selected */}
        {!activeVenueId && !isLoadingVenues && (
          <div className="text-center py-12 text-slate-400">
            <p className="text-lg font-medium">Select a venue to begin monitoring.</p>
          </div>
        )}

        {activeVenueId && (
          <>
            {/* ── Row 1: Metrics overview (4 cards) ── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
              <OccupancyCard
                currentOccupancy={telemetry.currentOccupancy}
                venueCapacity={telemetry.venueCapacity}
                occupancyRatio={telemetry.occupancyRatio}
                totalEntries={telemetry.totalEntries}
                totalExits={telemetry.totalExits}
                netFlow={telemetry.netFlow}
                isLoading={isLoading}
              />
              <FlowCard
                entryRate1m={telemetry.entryRate1m}
                entryRate5m={telemetry.entryRate5m}
                exitRate5m={telemetry.exitRate5m}
                netFlowRate5m={telemetry.netFlowRate5m}
                busiestGate={telemetry.busiestGate}
                isLoading={isLoading}
              />
              <RiskCard
                riskScore={telemetry.riskScore}
                riskLevel={telemetry.riskLevel}
                trendDirection={telemetry.trendDirection}
                trendSlope={telemetry.trendSlope}
                riskFactors={telemetry.riskFactors}
                isLoading={isLoading}
              />
              <DecisionCard
                primaryRecommendation={telemetry.primaryRecommendation}
                recommendations={telemetry.recommendations}
                isLoading={isLoading}
              />
            </div>

            {/* ── No-session state: show session controls prominently ── */}
            {!hasActiveSession && !isLoading && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div className="lg:col-span-2">
                  <NoSessionBanner />
                </div>
                <SessionControls
                  venueId={activeVenueId}
                  activeSessionId={telemetry.activeSessionId}
                  sessionStatus={telemetry.sessionStatus}
                  onSessionChange={() => {}}
                />
              </div>
            )}

            {/* ── Row 2: Main telemetry section (active session) ── */}
            {hasActiveSession && (
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
                {/* Left column (2/3 width) */}
                <div className="xl:col-span-2 space-y-5">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <DensityCongestionCard
                      densityLevel={telemetry.densityLevel}
                      congestionLevel={telemetry.congestionLevel}
                      isLoading={isLoading}
                    />
                    <ForecastCard
                      occupancyForecast={telemetry.occupancyForecast}
                      flowForecast={telemetry.flowForecast}
                      currentOccupancy={telemetry.currentOccupancy}
                      isLoading={isLoading}
                    />
                  </div>
                  <GateBreakdownCard
                    gateOccupancies={telemetry.gateOccupancies}
                    gateFlows={telemetry.gateFlows}
                    gateSummaries={telemetry.gateSummaries}
                    isLoading={isLoading}
                  />
                </div>

                {/* Right column (1/3 width) */}
                <div className="space-y-5">
                  <AlertsCard
                    activeAlerts={telemetry.activeAlerts}
                    isLoading={isLoading}
                  />
                  <SessionControls
                    venueId={activeVenueId}
                    activeSessionId={telemetry.activeSessionId}
                    sessionStatus={telemetry.sessionStatus}
                    onSessionChange={() => {}}
                  />
                </div>
              </div>
            )}

            {/* ── Row 3: Event Simulator (collapsible) ── */}
            {hasActiveSession && (
              <details className="group">
                <summary className="cursor-pointer text-sm text-slate-500 hover:text-slate-300 flex items-center gap-2 select-none py-1">
                  <svg className="w-4 h-4 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  Event Simulator (Operator Testing Tool)
                </summary>
                <div className="mt-3 max-w-lg">
                  <EventSimulator
                    venueId={activeVenueId}
                    activeSessionId={telemetry.activeSessionId}
                    sessionStatus={telemetry.sessionStatus}
                  />
                </div>
              </details>
            )}
          </>
        )}
      </div>
    </div>
  );
}
