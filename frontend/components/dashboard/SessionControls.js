/**
 * SessionControls — Session lifecycle management panel.
 *
 * All state transitions are driven by the FastAPI backend state machine.
 * The component respects the backend's valid transitions:
 *   NONE → create
 *   CREATED → start
 *   ACTIVE → pause | stop
 *   PAUSED → resume | stop
 *   STOPPED/EXPIRED → (create new)
 */
'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { sessionApi } from '@/services/api/sessions';

function ElapsedTimer({ startedAt }) {
  const [elapsed, setElapsed] = useState('');

  useEffect(() => {
    if (!startedAt) { setElapsed(''); return; }

    const update = () => {
      const now = Date.now();
      const start = new Date(startedAt).getTime();
      const diff = Math.max(0, now - start);
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setElapsed(`${h > 0 ? `${h}h ` : ''}${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`);
    };

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  return elapsed ? (
    <span className="text-xs text-slate-400">Running: <span className="text-cyan-400 font-mono">{elapsed}</span></span>
  ) : null;
}

export function SessionControls({
  venueId,
  activeSessionId = null,
  sessionStatus = null,
  sessionStartedAt = null,
  onSessionChange,
}) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [createCapacity, setCreateCapacity] = useState(1000);

  const status = (sessionStatus || '').toUpperCase();

  async function handleAction(action) {
    if (!venueId) return;
    setIsLoading(true);
    setError(null);
    try {
      let result;
      switch (action) {
        case 'create':
          result = await sessionApi.createSession(venueId, { venue_capacity: createCapacity });
          break;
        case 'start':
          result = await sessionApi.startSession(venueId, activeSessionId);
          break;
        case 'pause':
          result = await sessionApi.pauseSession(venueId, activeSessionId);
          break;
        case 'resume':
          result = await sessionApi.resumeSession(venueId, activeSessionId);
          break;
        case 'stop':
          result = await sessionApi.stopSession(venueId, activeSessionId);
          break;
        default:
          break;
      }
      // Notify parent; the WebSocket session_update event will also update state
      if (onSessionChange) onSessionChange(action, result);
    } catch (err) {
      setError(err.message || `Failed to ${action} session`);
    } finally {
      setIsLoading(false);
    }
  }

  const noSession = !activeSessionId || status === '' || status === 'STOPPED' || status === 'EXPIRED';

  return (
    <Card
      title="Session"
      badge={status ? <Badge variant={status} dot>{status}</Badge> : null}
      className="h-full"
    >
      <div className="space-y-3">
        {/* Session info */}
        {activeSessionId && (
          <div className="bg-slate-900/40 rounded-lg px-3 py-2 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Session ID</span>
            </div>
            <span className="text-xs text-cyan-400 font-mono break-all">{activeSessionId}</span>
            {sessionStartedAt && status === 'ACTIVE' && (
              <ElapsedTimer startedAt={sessionStartedAt} />
            )}
          </div>
        )}

        {/* Error display */}
        {error && (
          <div className="bg-rose-900/20 border border-rose-500/30 rounded-lg px-3 py-2 text-xs text-rose-400">
            {error}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2">
          {/* No active session — offer create */}
          {noSession && (
            <div className="w-full space-y-2">
              <div className="flex items-center gap-2">
                <label className="text-xs text-slate-400 whitespace-nowrap">Capacity</label>
                <input
                  type="number"
                  value={createCapacity}
                  onChange={(e) => setCreateCapacity(Number(e.target.value) || 1000)}
                  min={1}
                  className="w-full bg-slate-900/60 border border-slate-600 text-slate-200 text-sm rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                />
              </div>
              <Button
                variant="primary"
                onClick={() => handleAction('create')}
                isLoading={isLoading}
                disabled={!venueId}
                className="w-full"
              >
                Create Session
              </Button>
            </div>
          )}

          {/* CREATED — can start */}
          {status === 'CREATED' && (
            <Button
              variant="success"
              onClick={() => handleAction('start')}
              isLoading={isLoading}
              className="flex-1"
            >
              Start
            </Button>
          )}

          {/* ACTIVE — can pause or stop */}
          {status === 'ACTIVE' && (
            <>
              <Button
                variant="warning"
                onClick={() => handleAction('pause')}
                isLoading={isLoading}
                className="flex-1"
              >
                Pause
              </Button>
              <Button
                variant="danger"
                onClick={() => handleAction('stop')}
                isLoading={isLoading}
                className="flex-1"
              >
                Stop
              </Button>
            </>
          )}

          {/* PAUSED — can resume or stop */}
          {status === 'PAUSED' && (
            <>
              <Button
                variant="success"
                onClick={() => handleAction('resume')}
                isLoading={isLoading}
                className="flex-1"
              >
                Resume
              </Button>
              <Button
                variant="danger"
                onClick={() => handleAction('stop')}
                isLoading={isLoading}
                className="flex-1"
              >
                Stop
              </Button>
            </>
          )}
        </div>

        {!venueId && (
          <p className="text-xs text-slate-500 italic">Select a venue to manage sessions.</p>
        )}
      </div>
    </Card>
  );
}
