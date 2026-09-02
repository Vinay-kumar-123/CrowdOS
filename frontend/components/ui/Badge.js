/**
 * Reusable Status & Severity Badge Component.
 */
import React from 'react';

const VARIANTS = {
  // Risk levels
  LOW: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  GUARDED: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  ELEVATED: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  HIGH: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  CRITICAL: 'bg-rose-500/10 text-rose-400 border-rose-500/30 animate-pulse',

  // Density levels
  MODERATE: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',

  // Congestion levels
  NORMAL: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  BUILDING: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  CONGESTED: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  SEVERE_CONGESTION: 'bg-rose-500/10 text-rose-400 border-rose-500/30',

  // Alert severities
  INFO: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
  MEDIUM: 'bg-amber-500/10 text-amber-400 border-amber-500/30',

  // Session statuses
  CREATED: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  ACTIVE: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  PAUSED: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  STOPPED: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  EXPIRED: 'bg-rose-500/10 text-rose-400 border-rose-500/30',

  // Connection states
  CONNECTED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  CONNECTING: 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse',
  RECONNECTING: 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse',
  DISCONNECTED: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  ERROR: 'bg-rose-500/10 text-rose-400 border-rose-500/30',

  // Default neutral
  default: 'bg-slate-800 text-slate-300 border-slate-700',
};

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  className = '',
}) {
  const normalizedVariant = String(variant).toUpperCase();
  const styleClasses = VARIANTS[normalizedVariant] || VARIANTS.default;

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5',
  }[size] || 'text-xs px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${styleClasses} ${sizeClasses} ${className}`}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            normalizedVariant === 'CONNECTED' || normalizedVariant === 'ACTIVE' || normalizedVariant === 'LOW'
              ? 'bg-emerald-400'
              : normalizedVariant === 'CRITICAL' || normalizedVariant === 'HIGH' || normalizedVariant === 'ERROR'
              ? 'bg-rose-400'
              : 'bg-amber-400'
          }`}
        />
      )}
      {children}
    </span>
  );
}
