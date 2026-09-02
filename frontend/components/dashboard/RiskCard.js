/**
 * RiskCard — Predictive risk score, level, trend, and top risk factors.
 * Sources all values from Sprint 8 AI Engine via backend telemetry — zero client-side calculations.
 */
'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const TREND_ICONS = {
  INCREASING: { icon: '↑', color: 'text-rose-400' },
  STABLE: { icon: '→', color: 'text-slate-400' },
  DECREASING: { icon: '↓', color: 'text-emerald-400' },
  INSUFFICIENT_DATA: { icon: '?', color: 'text-slate-500' },
};

const RISK_COLORS = {
  LOW: 'text-emerald-400',
  GUARDED: 'text-blue-400',
  ELEVATED: 'text-amber-400',
  HIGH: 'text-orange-400',
  CRITICAL: 'text-rose-400',
};

export function RiskCard({
  riskScore = 0,
  riskLevel = 'LOW',
  trendDirection = 'STABLE',
  trendSlope = null,
  riskFactors = [],
  isLoading = false,
}) {
  const trend = TREND_ICONS[trendDirection] || TREND_ICONS.STABLE;
  const scoreColor = RISK_COLORS[riskLevel] || 'text-slate-300';

  return (
    <Card
      title="Predictive Risk"
      badge={<Badge variant={riskLevel}>{riskLevel}</Badge>}
      className="h-full"
    >
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          <div className="h-12 bg-slate-700/50 rounded-lg w-1/2" />
          <div className="h-3 bg-slate-700/50 rounded w-full" />
        </div>
      ) : (
        <div className="space-y-4">
          {/* Score display */}
          <div className="flex items-end gap-4">
            <div>
              <span className={`text-5xl font-black tabular-nums ${scoreColor}`}>
                {Math.round(riskScore)}
              </span>
              <span className="text-slate-500 text-sm ml-1">/100</span>
            </div>
            <div className="flex items-center gap-1.5 pb-1">
              <span className={`text-2xl font-bold ${trend.color}`}>{trend.icon}</span>
              <span className={`text-sm ${trend.color}`}>{trendDirection}</span>
              {trendSlope !== null && (
                <span className="text-xs text-slate-500 ml-1">
                  ({trendSlope >= 0 ? '+' : ''}{trendSlope.toFixed(2)})
                </span>
              )}
            </div>
          </div>

          {/* Risk score bar */}
          <div className="relative w-full h-3 bg-slate-700/60 rounded-full overflow-hidden">
            {/* Color segments */}
            <div className="absolute inset-0 flex">
              <div className="flex-1 bg-emerald-500/30" />
              <div className="flex-1 bg-blue-500/30" />
              <div className="flex-1 bg-amber-500/30" />
              <div className="flex-1 bg-orange-500/30" />
              <div className="flex-1 bg-rose-500/30" />
            </div>
            {/* Needle */}
            <div
              className="absolute top-0 bottom-0 w-1 bg-white rounded-full shadow-lg shadow-white/20 transition-all duration-500"
              style={{ left: `calc(${Math.min(100, Math.max(0, riskScore))}% - 2px)` }}
            />
          </div>

          {/* Top risk factors */}
          {riskFactors && riskFactors.length > 0 ? (
            <div className="space-y-1.5">
              <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">Top Factors</span>
              {riskFactors.slice(0, 3).map((factor, idx) => {
                const name = factor.name || factor.factor_name || `Factor ${idx + 1}`;
                const contribution = factor.contribution ?? factor.weight ?? null;
                return (
                  <div key={idx} className="flex items-center justify-between text-xs">
                    <span className="text-slate-300 truncate max-w-[70%]">{name}</span>
                    {contribution !== null && (
                      <span className="text-slate-400 tabular-nums">{Number(contribution).toFixed(1)}</span>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No risk factor data available</p>
          )}
        </div>
      )}
    </Card>
  );
}
