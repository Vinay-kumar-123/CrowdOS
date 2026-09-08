'use client';

/**
 * LoginPage — Sprint 15 Authentication.
 *
 * Collects email + password, POSTs to /api/v1/auth/login.
 * On success the backend sets an HttpOnly access_token cookie and
 * returns a TokenResponse; we redirect to /dashboard.
 * Tokens are NEVER stored in localStorage / sessionStorage.
 */

import React, { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { API_BASE_URL } from '@/lib/constants';

const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_LENGTH = 72; // bcrypt hard limit enforced server-side too

function EyeIcon({ open }) {
  return open ? (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.477 0 8.268 2.943 9.542 7-1.274 4.057-5.065 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.477 0-8.268-2.943-9.542-7a9.956 9.956 0 012.223-3.592M6.34 6.34A9.956 9.956 0 0112 5c4.477 0 8.268 2.943 9.542 7a9.979 9.979 0 01-4.137 5.12M3 3l18 18" />
    </svg>
  );
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      setError(null);

      // Client-side length guard (server enforces the real limit)
      if (password.length < MIN_PASSWORD_LENGTH) {
        setError('Password must be at least 8 characters.');
        return;
      }
      if (password.length > MAX_PASSWORD_LENGTH) {
        setError('Password must not exceed 72 characters.');
        return;
      }

      setLoading(true);
      try {
        const res = await fetch(
          `${API_BASE_URL.replace(/\/$/, '')}/api/v1/auth/login`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
            // Transmit and receive HttpOnly cookie — NEVER store token in JS
            credentials: 'include',
          },
        );

        if (res.ok) {
          // Cookie set by server — redirect to dashboard
          router.replace('/dashboard');
          return;
        }

        // Parse error body
        let detail = `Login failed (HTTP ${res.status}).`;
        try {
          const body = await res.json();
          if (typeof body.detail === 'string') detail = body.detail;
          else if (typeof body.message === 'string') detail = body.message;
        } catch {
          // ignore JSON parse error
        }
        setError(detail);
      } catch (err) {
        setError('Unable to connect to CrowdOS backend. Check your network and try again.');
      } finally {
        setLoading(false);
      }
    },
    [email, password, router],
  );

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      {/* Card */}
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-900/40">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.477 0 8.268 2.943 9.542 7-1.274 4.057-5.065 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </div>
          <div>
            <p className="text-xl font-bold text-white tracking-tight">CrowdOS</p>
            <p className="text-xs text-slate-400">Crowd Intelligence Platform</p>
          </div>
        </div>

        {/* Form card */}
        <div className="bg-slate-900 border border-slate-700/60 rounded-2xl shadow-2xl shadow-slate-900/80 p-8">
          <h1 className="text-lg font-semibold text-white mb-1">Sign in to your account</h1>
          <p className="text-sm text-slate-400 mb-6">Enter your credentials to access the operator dashboard.</p>

          {error && (
            <div className="mb-5 px-4 py-3 rounded-lg bg-rose-900/40 border border-rose-700/60 text-rose-300 text-sm flex items-start gap-2" role="alert">
              <svg className="w-4 h-4 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            {/* Email */}
            <div className="mb-4">
              <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-1.5">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                placeholder="operator@example.com"
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-800 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 disabled:opacity-50 transition"
              />
            </div>

            {/* Password */}
            <div className="mb-6">
              <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 pr-10 rounded-lg bg-slate-800 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 disabled:opacity-50 transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 hover:text-slate-200 transition"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  <EyeIcon open={showPassword} />
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !email || !password}
              className="w-full py-2.5 px-4 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-cyan-900/30"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                  Signing in...
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
          CrowdOS — Secure operator access only. Unauthorized use is prohibited.
        </p>
      </div>
    </div>
  );
}
