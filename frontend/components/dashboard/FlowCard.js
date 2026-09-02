/**
 * FlowCard — Real-time entry/exit flow rates and busiest gate indicator.
 */
'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';

function RateRow({ label, value, unit = 'ppm', colorClass = 'text-slate-200' }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-slate-700/30 last:border-0">
      <span className="text-sm text-slate-400">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${colorClass}`}>
        {value !== undefined && value !== null ? value.toFixed(2) : '—'} <span className="text-xs text-slate-500">{unit}</span>
      </span>
    </div>
  );
}

export function FlowCard({
  entryRate1m = 0,
  entryRate5m = 0,
  exitRate5m = 0,
  netFlowRate5m = 0,
  busiestGate = null,
  isLoading = false,
}) {
  return (
    <Card title="Flow Rates" className="h-full">
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-8 bg-slate-700/50 rounded" />
          ))}
        </div>
      ) : (
        <div className="space-y-1">
          <RateRow
            label="Entry Rate (1m)"
            value={entryRate1m}
            unit="ppm"
            colorClass="text-emerald-400"
          />
          <RateRow
            label="Entry Rate (5m)"
            value={entryRate5m}
            unit="ppm"
            colorClass="text-emerald-400"
          />
          <RateRow
            label="Exit Rate (5m)"
            value={exitRate5m}
            unit="ppm"
            colorClass="text-rose-400"
          />
          <RateRow
            label="Net Flow (5m)"
            value={netFlowRate5m}
            unit="ppm"
            colorClass={netFlowRate5m >= 0 ? 'text-sky-400' : 'text-amber-400'}
          />

          {/* Busiest Gate */}
          <div className="pt-3 mt-1">
            <div className="flex items-center justify-between bg-slate-900/40 rounded-lg px-3 py-2.5">
              <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Busiest Gate</span>
              <span className="text-sm font-bold text-cyan-400">
                {busiestGate || <span className="text-slate-500 font-normal">N/A</span>}
              </span>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
