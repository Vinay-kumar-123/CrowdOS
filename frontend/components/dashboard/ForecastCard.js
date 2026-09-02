/**
 * ForecastCard — 5m / 10m / 15m occupancy & flow forecasts from Sprint 8 AI Engine.
 * All forecast values are sourced from backend — no client-side interpolation.
 */
'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';

function ForecastRow({ label, value, unit = '', trend }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-700/30 last:border-0">
      <span className="text-xs text-slate-400 font-medium">{label}</span>
      <div className="flex items-center gap-1.5">
        {trend && (
          <span className={`text-xs ${trend === 'up' ? 'text-rose-400' : trend === 'down' ? 'text-emerald-400' : 'text-slate-500'}`}>
            {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
          </span>
        )}
        <span className="text-sm font-semibold text-slate-200 tabular-nums">
          {value !== undefined && value !== null ? `${Math.round(value)} ${unit}`.trim() : '—'}
        </span>
      </div>
    </div>
  );
}

export function ForecastCard({
  occupancyForecast = null,
  flowForecast = null,
  currentOccupancy = 0,
  isLoading = false,
}) {
  const hasOccupancyForecast = occupancyForecast &&
    (occupancyForecast['5m'] !== undefined ||
     occupancyForecast['10m'] !== undefined ||
     occupancyForecast['15m'] !== undefined ||
     occupancyForecast.forecast_5m !== undefined);

  const hasFlowForecast = flowForecast &&
    (flowForecast['5m'] !== undefined || flowForecast.forecast_5m !== undefined);

  const getOccForecastVal = (key) => {
    if (!occupancyForecast) return null;
    return occupancyForecast[key] ?? occupancyForecast[`forecast_${key}`] ?? null;
  };

  const getFlowForecastVal = (key) => {
    if (!flowForecast) return null;
    return flowForecast[key] ?? flowForecast[`forecast_${key}`] ?? null;
  };

  const occ5m = getOccForecastVal('5m');
  const occ10m = getOccForecastVal('10m');
  const occ15m = getOccForecastVal('15m');

  const flow5m = getFlowForecastVal('5m');
  const flow10m = getFlowForecastVal('10m');

  function trendVsNow(val) {
    if (val === null || val === undefined) return null;
    if (val > currentOccupancy + 5) return 'up';
    if (val < currentOccupancy - 5) return 'down';
    return 'stable';
  }

  return (
    <Card title="Forecast" subtitle="AI-predicted values (Sprint 8)" className="h-full">
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[...Array(4)].map((_, i) => <div key={i} className="h-7 bg-slate-700/50 rounded" />)}
        </div>
      ) : (!hasOccupancyForecast && !hasFlowForecast) ? (
        <div className="text-center py-6 text-slate-500 text-sm">
          <svg className="mx-auto mb-2 w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          No forecast data available yet
        </div>
      ) : (
        <div>
          {hasOccupancyForecast && (
            <div className="mb-3">
              <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">Occupancy Forecast</span>
              <div className="mt-1.5">
                <ForecastRow label="+5 min" value={occ5m} unit="ppl" trend={trendVsNow(occ5m)} />
                <ForecastRow label="+10 min" value={occ10m} unit="ppl" trend={trendVsNow(occ10m)} />
                <ForecastRow label="+15 min" value={occ15m} unit="ppl" trend={trendVsNow(occ15m)} />
              </div>
            </div>
          )}
          {hasFlowForecast && (
            <div>
              <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">Flow Forecast</span>
              <div className="mt-1.5">
                <ForecastRow label="+5 min" value={flow5m} unit="ppm" />
                <ForecastRow label="+10 min" value={flow10m} unit="ppm" />
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
