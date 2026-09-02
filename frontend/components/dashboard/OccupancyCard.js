/**
 * OccupancyCard — Live occupancy, capacity, and flow totals.
 */
'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ProgressBar } from '@/components/ui/ProgressBar';

function getDensityVariant(ratio) {
  if (ratio >= 0.9) return 'CRITICAL';
  if (ratio >= 0.75) return 'HIGH';
  if (ratio >= 0.5) return 'ELEVATED';
  return 'LOW';
}

export function OccupancyCard({
  currentOccupancy = 0,
  venueCapacity = 1000,
  occupancyRatio = 0.0,
  totalEntries = 0,
  totalExits = 0,
  netFlow = 0,
  isLoading = false,
}) {
  const pct = (occupancyRatio * 100).toFixed(1);
  const capacityVariant = getDensityVariant(occupancyRatio);

  return (
    <Card
      title="Occupancy"
      badge={<Badge variant={capacityVariant} dot>{capacityVariant}</Badge>}
      className="h-full"
    >
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          <div className="h-10 bg-slate-700/50 rounded-lg w-2/3" />
          <div className="h-3 bg-slate-700/50 rounded w-full" />
        </div>
      ) : (
        <div className="space-y-4">
          {/* Primary occupancy display */}
          <div className="flex items-end justify-between">
            <div>
              <span className="text-4xl font-bold text-white tabular-nums">{currentOccupancy.toLocaleString()}</span>
              <span className="text-slate-400 ml-2 text-sm">/ {venueCapacity.toLocaleString()}</span>
            </div>
            <span className="text-2xl font-semibold text-cyan-400 tabular-nums">{pct}%</span>
          </div>

          {/* Capacity progress bar */}
          <ProgressBar
            value={currentOccupancy}
            max={venueCapacity}
            showValue={false}
            size="lg"
          />

          {/* Entry / Exit / Net flow row */}
          <div className="grid grid-cols-3 gap-3 pt-1">
            <div className="bg-slate-900/40 rounded-lg p-2.5 text-center">
              <div className="text-lg font-bold text-emerald-400 tabular-nums">{totalEntries.toLocaleString()}</div>
              <div className="text-xs text-slate-400 mt-0.5">Entries</div>
            </div>
            <div className="bg-slate-900/40 rounded-lg p-2.5 text-center">
              <div className="text-lg font-bold text-rose-400 tabular-nums">{totalExits.toLocaleString()}</div>
              <div className="text-xs text-slate-400 mt-0.5">Exits</div>
            </div>
            <div className="bg-slate-900/40 rounded-lg p-2.5 text-center">
              <div className={`text-lg font-bold tabular-nums ${netFlow >= 0 ? 'text-sky-400' : 'text-amber-400'}`}>
                {netFlow >= 0 ? '+' : ''}{netFlow.toLocaleString()}
              </div>
              <div className="text-xs text-slate-400 mt-0.5">Net Flow</div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
