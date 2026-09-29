/**
 * CameraStatusCard Component — Sprint 16.
 *
 * Displays live operational health and capture statistics for all cameras
 * assigned to the active venue.
 * Never displays camera credentials or raw video frames.
 */
'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { cameraApi } from '@/services/api/cameras';

const STATUS_BADGES = {
  ONLINE: {
    bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    dot: 'bg-emerald-400',
    label: 'ONLINE',
  },
  DEGRADED: {
    bg: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    dot: 'bg-amber-400',
    label: 'DEGRADED',
  },
  RECONNECTING: {
    bg: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400 animate-pulse',
    dot: 'bg-yellow-400',
    label: 'RECONNECTING',
  },
  OFFLINE: {
    bg: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
    dot: 'bg-rose-400',
    label: 'OFFLINE',
  },
  REGISTERED: {
    bg: 'bg-slate-500/10 border-slate-500/30 text-slate-400',
    dot: 'bg-slate-400',
    label: 'REGISTERED',
  },
};

export function CameraStatusCard({ venueId, wsCameras = {}, isLoading = false }) {
  const [cameras, setCameras] = useState([]);
  const [fetching, setFetching] = useState(false);

  const fetchCameras = useCallback(async () => {
    if (!venueId) return;
    setFetching(true);
    try {
      const res = await cameraApi.listCameras(venueId);
      if (res && res.cameras) {
        setCameras(res.cameras);
      }
    } catch (err) {
      // Non-fatal if cameras endpoint fails or no cameras configured
      setCameras([]);
    } finally {
      setFetching(false);
    }
  }, [venueId]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  // Merge REST camera list with live WebSocket health updates
  const cameraList = cameras.map((cam) => {
    const wsData = wsCameras[cam.camera_id];
    if (wsData) {
      return {
        ...cam,
        status: wsData.status || cam.status,
        measured_fps: wsData.measured_fps ?? cam.measured_fps,
        processing_latency_ms: wsData.processing_latency_ms ?? cam.processing_latency_ms,
        reconnect_count: wsData.reconnect_count ?? cam.reconnect_count,
        last_frame_at: wsData.last_frame_at || cam.last_frame_at,
        healthy: wsData.healthy ?? true,
      };
    }
    return cam;
  });

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
          <h2 className="text-sm font-semibold tracking-wider text-slate-300 uppercase">
            Live Camera Runtime
          </h2>
        </div>
        <span className="text-xs text-slate-500">
          {cameraList.length} {cameraList.length === 1 ? 'camera' : 'cameras'}
        </span>
      </div>

      {isLoading || fetching ? (
        <div className="space-y-3 py-2">
          <div className="h-10 bg-slate-800/50 rounded-lg animate-pulse" />
          <div className="h-10 bg-slate-800/50 rounded-lg animate-pulse" />
        </div>
      ) : cameraList.length === 0 ? (
        <div className="py-6 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
          No cameras registered for this venue.
        </div>
      ) : (
        <div className="space-y-3">
          {cameraList.map((cam) => {
            const badge = STATUS_BADGES[cam.status] || STATUS_BADGES.REGISTERED;
            const gateText = cam.gate_id ? `Gate: ${cam.gate_id}` : 'No Gate';

            return (
              <div
                key={cam.camera_id}
                className="bg-slate-800/40 border border-slate-700/40 rounded-lg p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-slate-200 truncate">
                      {cam.camera_name || cam.camera_id}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      ({cam.camera_type?.toUpperCase()})
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                    <span>{gateText}</span>
                    <span>•</span>
                    <span>{cam.measured_fps ? `${cam.measured_fps} FPS` : '0 FPS'}</span>
                    <span>•</span>
                    <span>{cam.processing_latency_ms ? `${cam.processing_latency_ms}ms` : '0ms'}</span>
                    {cam.reconnect_count > 0 && (
                      <>
                        <span>•</span>
                        <span className="text-amber-400">Retries: {cam.reconnect_count}</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-center">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${badge.bg}`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                    {badge.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
