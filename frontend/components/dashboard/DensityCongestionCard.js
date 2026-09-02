/**
 * DensityCongestionCard — Displays crowd density and congestion state.
 */
'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const DENSITY_DESCRIPTIONS = {
  LOW: 'Crowd density is comfortable and well-distributed.',
  MODERATE: 'Density is building. Monitor high-traffic gates.',
  HIGH: 'Crowd density is elevated. Consider flow intervention.',
  CRITICAL: 'Critical crowd density detected. Immediate action required.',
};

const CONGESTION_DESCRIPTIONS = {
  NORMAL: 'Crowd flow is operating normally.',
  BUILDING: 'Congestion is beginning to form. Watch entry rates.',
  CONGESTED: 'Active congestion detected at key points.',
  SEVERE_CONGESTION: 'Severe congestion — deploy staff and redirect flow.',
};

function InfoRow({ label, value, variant }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-700/30 last:border-0">
      <span className="text-sm text-slate-400">{label}</span>
      <Badge variant={value || 'LOW'}>{value || '—'}</Badge>
    </div>
  );
}

export function DensityCongestionCard({
  densityLevel = 'LOW',
  congestionLevel = 'NORMAL',
  isLoading = false,
}) {
  const densityDesc = DENSITY_DESCRIPTIONS[densityLevel] || '';
  const congestionDesc = CONGESTION_DESCRIPTIONS[congestionLevel] || '';

  return (
    <Card title="Density & Congestion" className="h-full">
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          <div className="h-8 bg-slate-700/50 rounded" />
          <div className="h-8 bg-slate-700/50 rounded" />
        </div>
      ) : (
        <div className="space-y-1">
          <InfoRow label="Density Level" value={densityLevel} />
          <InfoRow label="Congestion State" value={congestionLevel} />

          {/* Contextual description */}
          <div className="pt-3 space-y-1.5">
            <p className="text-xs text-slate-400">{densityDesc}</p>
            {congestionLevel !== 'NORMAL' && (
              <p className="text-xs text-amber-400">{congestionDesc}</p>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
