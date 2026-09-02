/**
 * AlertsCard — Real-time active alert feed with severity badges.
 * Updates live via WebSocket alert_created / alert_resolved events.
 */
'use client';

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };

function formatAlertTime(isoStr) {
  if (!isoStr) return '';
  try {
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function AlertRow({ alert }) {
  const severity = alert.severity || alert.alert_type || 'MEDIUM';
  const alertType = alert.type || alert.alert_type || 'ALERT';
  const message = alert.message || alert.description || alertType;
  const time = formatAlertTime(alert.created_at || alert.timestamp);

  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-slate-700/30 last:border-0">
      <div className="shrink-0 mt-0.5">
        <Badge variant={severity} size="sm">{severity}</Badge>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-slate-200 truncate">{message}</p>
        <div className="flex items-center gap-2 mt-0.5">
          {alert.gate_id && (
            <span className="text-xs text-cyan-500/70">Gate {alert.gate_id}</span>
          )}
          {time && (
            <span className="text-xs text-slate-500">{time}</span>
          )}
        </div>
      </div>
    </div>
  );
}

export function AlertsCard({ activeAlerts = [], isLoading = false }) {
  const [filter, setFilter] = useState('ALL');

  const sortedAlerts = [...activeAlerts].sort((a, b) => {
    const sa = SEVERITY_ORDER[a.severity] ?? 99;
    const sb = SEVERITY_ORDER[b.severity] ?? 99;
    return sa - sb;
  });

  const filteredAlerts = filter === 'ALL'
    ? sortedAlerts
    : sortedAlerts.filter((a) => (a.severity || '').toUpperCase() === filter);

  const criticalCount = activeAlerts.filter((a) => a.severity === 'CRITICAL').length;
  const highCount = activeAlerts.filter((a) => a.severity === 'HIGH').length;

  const countBadge = activeAlerts.length > 0
    ? <Badge variant={criticalCount > 0 ? 'CRITICAL' : highCount > 0 ? 'HIGH' : 'ELEVATED'} size="sm">{activeAlerts.length}</Badge>
    : null;

  return (
    <Card title="Active Alerts" badge={countBadge} className="h-full">
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[...Array(3)].map((_, i) => <div key={i} className="h-12 bg-slate-700/50 rounded" />)}
        </div>
      ) : (
        <div>
          {/* Severity filter pills */}
          {activeAlerts.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3 -mt-1">
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
                <button
                  key={sev}
                  onClick={() => setFilter(sev)}
                  className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                    filter === sev
                      ? 'bg-cyan-600 border-cyan-500 text-white'
                      : 'bg-transparent border-slate-600 text-slate-400 hover:border-slate-500'
                  }`}
                >
                  {sev}
                  {sev !== 'ALL' && (
                    <span className="ml-1 opacity-70">
                      ({activeAlerts.filter((a) => a.severity === sev).length})
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Alert rows */}
          {filteredAlerts.length > 0 ? (
            <div className="max-h-64 overflow-y-auto pr-1">
              {filteredAlerts.map((alert, idx) => (
                <AlertRow key={alert.alert_id || idx} alert={alert} />
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              <svg className="mx-auto mb-2 w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm">
                {filter !== 'ALL' ? `No ${filter} alerts` : 'No active alerts'}
              </p>
              {filter === 'ALL' && <p className="text-xs mt-1 text-slate-600">All clear — system operating normally.</p>}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
