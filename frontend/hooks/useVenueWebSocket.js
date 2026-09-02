/**
 * Real-Time WebSocket Hook for CrowdOS Operator Dashboard.
 *
 * Connects to `/ws/venues/{venue_id}` and maintains:
 * - Resilient connection with exponential backoff reconnect
 * - Periodic ping/pong heartbeat (15s)
 * - Atomic telemetry state reduction
 * - Clean teardown on unmount or venue switch
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { WS_BASE_URL } from '@/lib/constants';

const HEARTBEAT_INTERVAL_MS = 15000;
const INITIAL_RETRY_DELAY_MS = 1000;
const MAX_RETRY_DELAY_MS = 16000;

export const ConnectionState = {
  IDLE: 'IDLE',
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  DISCONNECTED: 'DISCONNECTED',
  RECONNECTING: 'RECONNECTING',
  ERROR: 'ERROR',
};

const initialTelemetryState = {
  venueId: '',
  venueCapacity: 1000,
  activeSessionId: null,
  sessionStatus: null,
  currentOccupancy: 0,
  occupancyRatio: 0.0,
  totalEntries: 0,
  totalExits: 0,
  netFlow: 0,
  entryRate1m: 0.0,
  entryRate5m: 0.0,
  exitRate5m: 0.0,
  netFlowRate5m: 0.0,
  busiestGate: null,
  gateOccupancies: {},
  gateFlows: {},
  densityLevel: 'LOW',
  congestionLevel: 'NORMAL',
  riskScore: 0.0,
  riskLevel: 'LOW',
  trendDirection: 'STABLE',
  trendSlope: null,
  trendConfidence: 'LOW',
  primaryRecommendation: 'MONITOR',
  recommendations: ['MONITOR'],
  riskFactors: [],
  occupancyForecast: null,
  flowForecast: null,
  activeAlerts: [],
  activeAnomalies: [],
  gateSummaries: {},
  systemStatus: {
    database_connected: true,
    redis_configured: true,
    ai_engine_available: true,
  },
};

export function useVenueWebSocket(venueId, options = {}) {
  const { enabled = true, initialDashboard = null } = options;

  const [connectionStatus, setConnectionStatus] = useState(ConnectionState.IDLE);
  const [telemetry, setTelemetry] = useState(() => ({
    ...initialTelemetryState,
    venueId: venueId || '',
    ...(initialDashboard ? mapDashboardSnapshot(initialDashboard) : {}),
  }));
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);

  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);
  const retryCountRef = useRef(0);
  const isManuallyClosedRef = useRef(false);

  // Helper to construct WS URL
  const getWsUrl = useCallback((vid) => {
    let base = WS_BASE_URL || 'ws://localhost:8000/ws';
    // If WS_BASE_URL is generic ws://localhost:8000/ws, append /venues/{venueId}
    if (base.endsWith('/ws')) {
      base = `${base}/venues/${encodeURIComponent(vid)}`;
    } else if (base.endsWith('/')) {
      base = `${base}ws/venues/${encodeURIComponent(vid)}`;
    } else {
      base = `${base}/ws/venues/${encodeURIComponent(vid)}`;
    }
    return base;
  }, []);

  // Map backend DashboardSnapshotResponse into flat telemetry state
  function mapDashboardSnapshot(snap) {
    if (!snap) return {};
    return {
      venueId: snap.venue_id || '',
      venueCapacity: snap.venue_capacity || 1000,
      activeSessionId: snap.session_id || null,
      sessionStatus: snap.session_status || null,
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
      occupancyForecast: snap.occupancy_forecast || null,
      flowForecast: snap.flow_forecast || null,
      primaryRecommendation: snap.primary_recommendation || 'MONITOR',
      recommendations: snap.recommendations || ['MONITOR'],
      activeAlerts: snap.active_alerts || [],
      activeAnomalies: snap.active_anomalies || [],
      gateSummaries: snap.gate_summaries || {},
    };
  }

  // Message dispatcher
  const handleWebSocketMessage = useCallback((event) => {
    try {
      const envelope = JSON.parse(event.data);
      const { type, timestamp, data } = envelope;

      setLastUpdated(timestamp || new Date().toISOString());

      switch (type) {
        case 'initial_state':
          if (data) {
            setTelemetry((prev) => {
              const dashUpdates = data.dashboard ? mapDashboardSnapshot(data.dashboard) : {};
              return {
                ...prev,
                venueId: data.venue_id || prev.venueId,
                venueCapacity: data.venue_capacity || prev.venueCapacity,
                activeSessionId: data.active_session_id || prev.activeSessionId,
                sessionStatus: data.session_status || prev.sessionStatus,
                ...dashUpdates,
              };
            });
          }
          break;

        case 'occupancy_update':
          if (data) {
            setTelemetry((prev) => ({
              ...prev,
              currentOccupancy: data.current_occupancy ?? prev.currentOccupancy,
              venueCapacity: data.venue_capacity ?? prev.venueCapacity,
              occupancyRatio: data.occupancy_ratio ?? prev.occupancyRatio,
              totalEntries: data.total_entries ?? prev.totalEntries,
              totalExits: data.total_exits ?? prev.totalExits,
              netFlow: data.net_flow ?? prev.netFlow,
              gateOccupancies: data.gate_occupancies || prev.gateOccupancies,
            }));
          }
          break;

        case 'flow_update':
          if (data) {
            setTelemetry((prev) => ({
              ...prev,
              entryRate1m: data.entry_rate_1m ?? prev.entryRate1m,
              entryRate5m: data.entry_rate_5m ?? prev.entryRate5m,
              exitRate5m: data.exit_rate_5m ?? prev.exitRate5m,
              netFlowRate5m: data.net_flow_rate_5m ?? prev.netFlowRate5m,
              busiestGate: data.busiest_gate ?? prev.busiestGate,
              gateFlows: data.gate_flows || prev.gateFlows,
            }));
          }
          break;

        case 'intelligence_update':
          if (data) {
            setTelemetry((prev) => ({
              ...prev,
              densityLevel: data.density_level || prev.densityLevel,
              congestionLevel: data.congestion_level || prev.congestionLevel,
              ...(data.occupancy
                ? {
                    currentOccupancy: data.occupancy.current_occupancy ?? prev.currentOccupancy,
                    occupancyRatio: data.occupancy.occupancy_ratio ?? prev.occupancyRatio,
                    totalEntries: data.occupancy.total_entries ?? prev.totalEntries,
                    totalExits: data.occupancy.total_exits ?? prev.totalExits,
                    netFlow: data.occupancy.net_flow ?? prev.netFlow,
                  }
                : {}),
              ...(data.flow
                ? {
                    entryRate1m: data.flow.entry_rate_1m ?? prev.entryRate1m,
                    entryRate5m: data.flow.entry_rate_5m ?? prev.entryRate5m,
                    exitRate5m: data.flow.exit_rate_5m ?? prev.exitRate5m,
                    netFlowRate5m: data.flow.net_flow_rate_5m ?? prev.netFlowRate5m,
                  }
                : {}),
            }));
          }
          break;

        case 'prediction_update':
          if (data) {
            setTelemetry((prev) => ({
              ...prev,
              riskScore: data.risk_score ?? prev.riskScore,
              riskLevel: data.risk_level || prev.riskLevel,
              trendDirection: data.trend_direction || prev.trendDirection,
              trendSlope: data.trend_slope ?? prev.trendSlope,
              trendConfidence: data.trend_confidence || prev.trendConfidence,
              primaryRecommendation: data.primary_recommendation || prev.primaryRecommendation,
              recommendations: data.recommendations || prev.recommendations,
              riskFactors: data.factors || prev.riskFactors,
              occupancyForecast: data.occupancy_forecast ?? prev.occupancyForecast,
              flowForecast: data.flow_forecast ?? prev.flowForecast,
            }));
          }
          break;

        case 'alert_created':
          if (data && data.alert_id) {
            setTelemetry((prev) => {
              const existingIdx = prev.activeAlerts.findIndex((a) => a.alert_id === data.alert_id);
              let updatedAlerts;
              if (existingIdx >= 0) {
                updatedAlerts = [...prev.activeAlerts];
                updatedAlerts[existingIdx] = { ...updatedAlerts[existingIdx], ...data };
              } else {
                updatedAlerts = [data, ...prev.activeAlerts];
              }
              return { ...prev, activeAlerts: updatedAlerts };
            });
          }
          break;

        case 'alert_resolved':
          if (data && data.alert_id) {
            setTelemetry((prev) => ({
              ...prev,
              activeAlerts: prev.activeAlerts.filter((a) => a.alert_id !== data.alert_id),
            }));
          }
          break;

        case 'session_update':
          if (data) {
            setTelemetry((prev) => {
              let updatedSessionStatus = data.status || prev.sessionStatus;
              let updatedActiveId = prev.activeSessionId;

              if (data.action === 'create' || data.action === 'start') {
                updatedActiveId = data.session_id;
              } else if (data.action === 'stop' || data.action === 'expire') {
                if (prev.activeSessionId === data.session_id) {
                  updatedActiveId = null;
                }
              }

              return {
                ...prev,
                activeSessionId: updatedActiveId,
                sessionStatus: updatedSessionStatus,
              };
            });
          }
          break;

        case 'system_status':
          if (data) {
            setTelemetry((prev) => ({
              ...prev,
              systemStatus: { ...prev.systemStatus, ...data },
            }));
          }
          break;

        case 'pong':
          // Heartbeat ack
          break;

        default:
          break;
      }
    } catch (err) {
      console.warn('Error parsing incoming WebSocket envelope:', err);
    }
  }, []);

  // Connect function
  const connect = useCallback(() => {
    if (!enabled || !venueId) return;

    if (socketRef.current) {
      isManuallyClosedRef.current = true;
      socketRef.current.close();
      socketRef.current = null;
    }

    isManuallyClosedRef.current = false;
    const url = getWsUrl(venueId);

    setConnectionStatus((prev) =>
      prev === ConnectionState.IDLE ? ConnectionState.CONNECTING : ConnectionState.RECONNECTING
    );

    try {
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus(ConnectionState.CONNECTED);
        setError(null);
        retryCountRef.current = 0;

        // Start heartbeat ping
        if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, HEARTBEAT_INTERVAL_MS);
      };

      ws.onmessage = handleWebSocketMessage;

      ws.onerror = (evt) => {
        setError('WebSocket encountered an error');
      };

      ws.onclose = () => {
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
          heartbeatIntervalRef.current = null;
        }

        if (!isManuallyClosedRef.current) {
          setConnectionStatus(ConnectionState.DISCONNECTED);

          // Exponential backoff reconnect
          const delay = Math.min(
            INITIAL_RETRY_DELAY_MS * Math.pow(2, retryCountRef.current),
            MAX_RETRY_DELAY_MS
          );
          retryCountRef.current += 1;

          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (err) {
      setError(err.message || 'Failed to establish WebSocket connection');
      setConnectionStatus(ConnectionState.ERROR);
    }
  }, [enabled, venueId, getWsUrl, handleWebSocketMessage]);

  // Request fresh state snapshot from server
  const requestFreshState = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'get_state' }));
    }
  }, []);

  // Update telemetry manually (e.g. from REST fallback)
  const updateTelemetry = useCallback((data) => {
    setTelemetry((prev) => ({
      ...prev,
      ...data,
    }));
  }, []);

  // Lifecycle
  useEffect(() => {
    if (venueId && enabled) {
      setTelemetry((prev) => ({
        ...initialTelemetryState,
        venueId,
      }));
      connect();
    }

    return () => {
      isManuallyClosedRef.current = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      setConnectionStatus(ConnectionState.IDLE);
    };
  }, [venueId, enabled, connect]);

  return {
    telemetry,
    connectionStatus,
    lastUpdated,
    error,
    reconnect: connect,
    requestFreshState,
    updateTelemetry,
    isConnected: connectionStatus === ConnectionState.CONNECTED,
  };
}
