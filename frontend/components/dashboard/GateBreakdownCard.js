/**
 * GateBreakdownCard — Per-gate occupancy and flow telemetry table.
 */
'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';

function GateRow({ gateId, occupancy, entries, exits, flowRate }) {
  return (
    <tr className="border-b border-slate-700/30 hover:bg-slate-800/40 transition-colors">
      <td className="py-2 px-3 text-sm font-medium text-cyan-400">{gateId}</td>
      <td className="py-2 px-3 text-sm text-slate-200 text-right tabular-nums">
        {occupancy !== undefined ? occupancy.toLocaleString() : '—'}
      </td>
      <td className="py-2 px-3 text-sm text-emerald-400 text-right tabular-nums">
        {entries !== undefined ? entries.toLocaleString() : '—'}
      </td>
      <td className="py-2 px-3 text-sm text-rose-400 text-right tabular-nums">
        {exits !== undefined ? exits.toLocaleString() : '—'}
      </td>
      <td className="py-2 px-3 text-sm text-slate-300 text-right tabular-nums">
        {flowRate !== undefined ? flowRate.toFixed(1) : '—'}
      </td>
    </tr>
  );
}

export function GateBreakdownCard({
  gateOccupancies = {},
  gateFlows = {},
  gateSummaries = {},
  isLoading = false,
}) {
  // Merge gate data from all available sources
  const allGateIds = Array.from(new Set([
    ...Object.keys(gateOccupancies),
    ...Object.keys(gateFlows),
    ...Object.keys(gateSummaries),
  ])).sort();

  return (
    <Card title="Gate Breakdown" className="h-full">
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[...Array(4)].map((_, i) => <div key={i} className="h-8 bg-slate-700/50 rounded" />)}
        </div>
      ) : allGateIds.length === 0 ? (
        <div className="text-center py-6 text-slate-500 text-sm">
          <svg className="mx-auto mb-2 w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          No gate data available
        </div>
      ) : (
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-left">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-700/60">
                <th className="pb-2 px-3 font-medium">Gate</th>
                <th className="pb-2 px-3 font-medium text-right">Occupancy</th>
                <th className="pb-2 px-3 font-medium text-right">Entries</th>
                <th className="pb-2 px-3 font-medium text-right">Exits</th>
                <th className="pb-2 px-3 font-medium text-right">Rate</th>
              </tr>
            </thead>
            <tbody>
              {allGateIds.map((gateId) => {
                const summary = gateSummaries[gateId] || {};
                const flow = gateFlows[gateId] || {};
                return (
                  <GateRow
                    key={gateId}
                    gateId={gateId}
                    occupancy={gateOccupancies[gateId] ?? summary.occupancy}
                    entries={summary.total_entries ?? flow.total_entries}
                    exits={summary.total_exits ?? flow.total_exits}
                    flowRate={flow.entry_rate_5m ?? summary.entry_rate_5m}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
