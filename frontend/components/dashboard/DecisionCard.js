/**
 * DecisionCard — Operational recommendations from Sprint 8 Decision Engine.
 * Renders the primary directive prominently and secondary actions as a list.
 */
'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';

const ACTION_COLORS = {
  MONITOR: 'border-slate-600 bg-slate-900/40 text-slate-300',
  ALERT: 'border-amber-500/40 bg-amber-900/20 text-amber-300',
  REDUCE_CAPACITY: 'border-orange-500/40 bg-orange-900/20 text-orange-300',
  OPEN_GATES: 'border-emerald-500/40 bg-emerald-900/20 text-emerald-300',
  CLOSE_GATES: 'border-rose-500/40 bg-rose-900/20 text-rose-300',
  REDIRECT_FLOW: 'border-blue-500/40 bg-blue-900/20 text-blue-300',
  EVACUATE: 'border-rose-500 bg-rose-900/40 text-rose-200',
  DEPLOY_STAFF: 'border-cyan-500/40 bg-cyan-900/20 text-cyan-300',
};

function getActionColor(rec) {
  if (!rec) return ACTION_COLORS.MONITOR;
  const upper = String(rec).toUpperCase();
  for (const [key, cls] of Object.entries(ACTION_COLORS)) {
    if (upper.includes(key)) return cls;
  }
  return ACTION_COLORS.MONITOR;
}

export function DecisionCard({
  primaryRecommendation = 'MONITOR',
  recommendations = [],
  isLoading = false,
}) {
  const primaryColor = getActionColor(primaryRecommendation);

  return (
    <Card title="Operational Guidance" className="h-full">
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          <div className="h-14 bg-slate-700/50 rounded-lg" />
          <div className="h-6 bg-slate-700/50 rounded w-3/4" />
        </div>
      ) : (
        <div className="space-y-3">
          {/* Primary recommendation banner */}
          <div className={`border rounded-xl px-4 py-3 ${primaryColor}`}>
            <div className="text-xs font-semibold uppercase tracking-widest opacity-70 mb-1">Primary Action</div>
            <div className="text-base font-bold">{primaryRecommendation || 'MONITOR'}</div>
          </div>

          {/* Secondary recommendations */}
          {recommendations && recommendations.length > 1 && (
            <div className="space-y-1.5">
              <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">Additional Actions</span>
              {recommendations.slice(1, 5).map((rec, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2 text-sm text-slate-300"
                >
                  <span className="text-cyan-500 mt-0.5 shrink-0">›</span>
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          )}

          {(!recommendations || recommendations.length <= 1) && primaryRecommendation === 'MONITOR' && (
            <p className="text-xs text-slate-500 italic">No active situation requiring intervention.</p>
          )}
        </div>
      )}
    </Card>
  );
}
