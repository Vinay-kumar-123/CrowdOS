/**
 * Dynamic Progress Bar with Threshold Color Coding.
 */
import React from 'react';

export function ProgressBar({
  value = 0,
  max = 100,
  label = null,
  showValue = false,
  size = 'md',
  className = '',
}) {
  const percentage = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;

  // Determine dynamic bar color based on percentage threshold
  let barColor = 'bg-emerald-500';
  if (percentage >= 90) {
    barColor = 'bg-rose-500';
  } else if (percentage >= 75) {
    barColor = 'bg-orange-500';
  } else if (percentage >= 50) {
    barColor = 'bg-amber-500';
  }

  const heightClasses = {
    sm: 'h-1.5',
    md: 'h-2.5',
    lg: 'h-4',
  }[size] || 'h-2.5';

  return (
    <div className={`w-full ${className}`}>
      {(label || showValue) && (
        <div className="flex justify-between items-center text-xs mb-1.5 text-slate-300">
          {label && <span className="font-medium text-slate-400">{label}</span>}
          {showValue && (
            <span className="font-semibold text-slate-200">
              {percentage.toFixed(1)}%
            </span>
          )}
        </div>
      )}
      <div className={`w-full bg-slate-700/60 rounded-full overflow-hidden ${heightClasses}`}>
        <div
          className={`${barColor} ${heightClasses} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
