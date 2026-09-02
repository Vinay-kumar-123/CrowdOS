/**
 * Reusable Card Container Component.
 */
import React from 'react';

export function Card({
  title,
  subtitle,
  badge,
  action,
  children,
  className = '',
  bodyClassName = '',
}) {
  return (
    <div
      className={`bg-slate-800/60 border border-slate-700/60 rounded-xl shadow-lg backdrop-blur-sm transition-all duration-200 hover:border-slate-600/80 ${className}`}
    >
      {(title || badge || action) && (
        <div className="px-5 py-4 border-b border-slate-700/40 flex items-center justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h3 className="text-sm font-semibold text-slate-200 tracking-wide uppercase flex items-center gap-2 truncate">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-slate-400 mt-0.5 truncate">{subtitle}</p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {badge}
            {action}
          </div>
        </div>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </div>
  );
}
