/**
 * EventSimulator — Operator testing tool for ENTRY/EXIT event ingestion.
 *
 * Sends events through the backend REST API only.
 * Dashboard state updates come exclusively from the backend/WebSocket response —
 * this component does NOT directly manipulate shared telemetry state.
 */
'use client';

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { eventApi } from '@/services/api/events';

const COMMON_GATES = ['gate_a', 'gate_b', 'gate_c', 'gate_d', 'gate_main', 'gate_north', 'gate_south'];

export function EventSimulator({
  venueId,
  activeSessionId,
  sessionStatus,
}) {
  const [eventType, setEventType] = useState('ENTRY');
  const [gateId, setGateId] = useState('gate_a');
  const [customGate, setCustomGate] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [error, setError] = useState(null);

  const isSessionActive = (sessionStatus || '').toUpperCase() === 'ACTIVE';
  const effectiveGate = customGate.trim() || gateId;

  async function handleSend() {
    if (!venueId || !activeSessionId) return;
    setIsLoading(true);
    setError(null);
    setLastResult(null);
    try {
      const result = await eventApi.ingestEvent(venueId, activeSessionId, {
        event_type: eventType,
        gate_id: effectiveGate,
      });
      setLastResult(result);
    } catch (err) {
      setError(err.message || 'Event ingestion failed');
    } finally {
      setIsLoading(false);
    }
  }

  async function handleBurst(count) {
    if (!venueId || !activeSessionId) return;
    setIsLoading(true);
    setError(null);
    setLastResult(null);
    try {
      // Sequential burst — avoids hammering server in parallel
      let lastRes = null;
      for (let i = 0; i < count; i++) {
        lastRes = await eventApi.ingestEvent(venueId, activeSessionId, {
          event_type: eventType,
          gate_id: effectiveGate,
        });
      }
      setLastResult({ burst: count, last: lastRes });
    } catch (err) {
      setError(err.message || 'Burst event ingestion failed');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card title="Event Simulator" subtitle="Operator testing tool" className="h-full">
      <div className="space-y-3">
        {/* Inactive warning */}
        {!isSessionActive && (
          <div className="bg-amber-900/20 border border-amber-500/30 rounded-lg px-3 py-2 text-xs text-amber-400">
            {!activeSessionId
              ? 'No active session. Create and start a session first.'
              : `Session is ${sessionStatus || 'inactive'}. Resume or start a session to send events.`}
          </div>
        )}

        {/* Event Type Toggle */}
        <div>
          <label className="text-xs text-slate-400 font-medium uppercase tracking-wider mb-1.5 block">Event Type</label>
          <div className="flex rounded-lg overflow-hidden border border-slate-600">
            <button
              onClick={() => setEventType('ENTRY')}
              className={`flex-1 text-sm py-2 font-medium transition-colors ${
                eventType === 'ENTRY'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              ENTRY
            </button>
            <button
              onClick={() => setEventType('EXIT')}
              className={`flex-1 text-sm py-2 font-medium transition-colors ${
                eventType === 'EXIT'
                  ? 'bg-rose-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              EXIT
            </button>
          </div>
        </div>

        {/* Gate selection */}
        <div>
          <label className="text-xs text-slate-400 font-medium uppercase tracking-wider mb-1.5 block">Gate</label>
          <select
            value={gateId}
            onChange={(e) => { setGateId(e.target.value); setCustomGate(''); }}
            className="w-full bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-cyan-500 mb-1.5"
          >
            {COMMON_GATES.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Custom gate ID (optional)"
            value={customGate}
            onChange={(e) => setCustomGate(e.target.value)}
            className="w-full bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-cyan-500 placeholder-slate-600"
          />
        </div>

        {/* Send buttons */}
        <div className="flex gap-2">
          <Button
            variant={eventType === 'ENTRY' ? 'success' : 'danger'}
            onClick={handleSend}
            isLoading={isLoading}
            disabled={!isSessionActive}
            className="flex-1"
          >
            Send ×1
          </Button>
          <Button
            variant="secondary"
            onClick={() => handleBurst(5)}
            isLoading={isLoading}
            disabled={!isSessionActive}
            className="flex-1"
          >
            Burst ×5
          </Button>
          <Button
            variant="secondary"
            onClick={() => handleBurst(10)}
            isLoading={isLoading}
            disabled={!isSessionActive}
            className="flex-1"
          >
            Burst ×10
          </Button>
        </div>

        {/* Result / Error */}
        {error && (
          <div className="bg-rose-900/20 border border-rose-500/30 rounded-lg px-3 py-2 text-xs text-rose-400">
            {error}
          </div>
        )}
        {lastResult && (
          <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-lg px-3 py-2 text-xs text-emerald-400">
            {lastResult.burst
              ? `Sent ${lastResult.burst} ${eventType} events via ${effectiveGate}`
              : `Event accepted: ${lastResult.event_id || 'OK'}`}
          </div>
        )}

        <p className="text-xs text-slate-600 italic">
          Dashboard updates from WebSocket after event processing.
        </p>
      </div>
    </Card>
  );
}
