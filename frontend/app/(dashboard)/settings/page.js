/**
 * CrowdOS Operational Settings & Administration Page — Phase 2B.
 *
 * Implements:
 * 1. Camera Management: List cameras, add camera modal, start/stop stream, delete camera.
 * 2. Venue Configuration: View venue details, capacity, AI engine availability, reset engine state (SUPER_ADMIN only with confirmation).
 * 3. Operator Management: List users, provision new operator user, toggle active/inactive status (SUPER_ADMIN only).
 */
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useVenues } from '@/hooks/useVenues';
import { HeaderBar } from '@/components/dashboard/HeaderBar';
import { CameraStatusCard } from '@/components/dashboard/CameraStatusCard';
import { cameraApi } from '@/services/api/cameras';
import { venueApi } from '@/services/api/venues';
import { userApi } from '@/services/api/users';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

const TABS = [
  { id: 'cameras', label: 'Cameras & Hardware' },
  { id: 'venue', label: 'Venue & Engine' },
  { id: 'users', label: 'Operators & Access' },
];

export default function SettingsPage() {
  const { venues, activeVenueId, setActiveVenueId, isLoading: isLoadingVenues } = useVenues();
  const [activeTab, setActiveTab] = useState('cameras');

  // Authenticated user state
  const [currentUser, setCurrentUser] = useState(null);
  const isSuperAdmin = currentUser?.role === 'SUPER_ADMIN' || currentUser?.role === 'super_admin';

  // Venue state
  const [venueInfo, setVenueInfo] = useState(null);
  const [venueLoading, setVenueLoading] = useState(false);
  const [venueError, setVenueError] = useState(null);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(null);

  // Users state
  const [usersList, setUsersList] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState(null);
  const [statusUpdating, setStatusUpdating] = useState({});
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [creatingUser, setCreatingUser] = useState(false);
  const [createUserError, setCreateUserError] = useState(null);
  const [newUserForm, setNewUserForm] = useState({
    email: '',
    password: '',
    display_name: '',
    role: 'OPERATOR',
    venue_ids: '',
  });

  // Cameras state for detailed camera management table
  const [cameraList, setCameraList] = useState([]);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraActionLoading, setCameraActionLoading] = useState({});
  const [cameraError, setCameraError] = useState(null);
  const [cameraSuccess, setCameraSuccess] = useState(null);

  // Load current user profile on mount
  useEffect(() => {
    userApi.getCurrentUser()
      .then((data) => setCurrentUser(data))
      .catch(() => {});
  }, []);

  // Fetch venue info
  const fetchVenueInfo = useCallback(async () => {
    if (!activeVenueId) return;
    setVenueLoading(true);
    setVenueError(null);
    try {
      const data = await venueApi.getVenueInfo(activeVenueId);
      setVenueInfo(data);
    } catch (err) {
      setVenueError(err.message || 'Failed to load venue information.');
    } finally {
      setVenueLoading(false);
    }
  }, [activeVenueId]);

  // Fetch camera list for detailed management
  const fetchCameras = useCallback(async () => {
    if (!activeVenueId) return;
    setCameraLoading(true);
    setCameraError(null);
    try {
      const res = await cameraApi.listCameras(activeVenueId);
      if (res && res.cameras) {
        setCameraList(res.cameras);
      }
    } catch (err) {
      setCameraList([]);
    } finally {
      setCameraLoading(false);
    }
  }, [activeVenueId]);

  // Fetch users if super admin
  const fetchUsers = useCallback(async () => {
    if (!isSuperAdmin) return;
    setUsersLoading(true);
    setUsersError(null);
    try {
      const data = await userApi.listUsers({ limit: 100 });
      setUsersList(Array.isArray(data) ? data : []);
    } catch (err) {
      setUsersError(err.message || 'Failed to load operator users.');
    } finally {
      setUsersLoading(false);
    }
  }, [isSuperAdmin]);

  useEffect(() => {
    fetchVenueInfo();
    fetchCameras();
  }, [fetchVenueInfo, fetchCameras]);

  useEffect(() => {
    if (activeTab === 'users' && isSuperAdmin) {
      fetchUsers();
    }
  }, [activeTab, isSuperAdmin, fetchUsers]);

  // Handle Venue Engine Reset
  const handleResetEngine = async () => {
    if (!activeVenueId || !isSuperAdmin) return;
    setResetting(true);
    setVenueError(null);
    setResetSuccess(null);
    try {
      const res = await venueApi.resetVenue(activeVenueId);
      setResetSuccess(res.message || `Venue '${activeVenueId}' engine state cleared successfully.`);
      setResetConfirmOpen(false);
      await fetchVenueInfo();
    } catch (err) {
      setVenueError(err.message || 'Failed to reset venue engine state.');
    } finally {
      setResetting(false);
    }
  };

  // Handle Camera Deletion
  const handleDeleteCamera = async (cameraId) => {
    if (!activeVenueId || !cameraId) return;
    if (!window.confirm(`Are you sure you want to delete camera '${cameraId}'? This stops the stream if running.`)) {
      return;
    }
    setCameraActionLoading((prev) => ({ ...prev, [cameraId]: true }));
    setCameraError(null);
    setCameraSuccess(null);
    try {
      await cameraApi.deleteCamera(activeVenueId, cameraId);
      setCameraSuccess(`Camera '${cameraId}' deleted successfully.`);
      await fetchCameras();
    } catch (err) {
      setCameraError(err.message || `Failed to delete camera '${cameraId}'.`);
    } finally {
      setCameraActionLoading((prev) => ({ ...prev, [cameraId]: false }));
    }
  };

  // Handle User Status Toggle
  const handleToggleUserStatus = async (userId, currentActive) => {
    if (!userId) return;
    setStatusUpdating((prev) => ({ ...prev, [userId]: true }));
    setUsersError(null);
    try {
      await userApi.updateUserStatus(userId, !currentActive);
      await fetchUsers();
    } catch (err) {
      setUsersError(err.message || 'Failed to update user status.');
    } finally {
      setStatusUpdating((prev) => ({ ...prev, [userId]: false }));
    }
  };

  // Handle Create User Submit
  const handleCreateUserSubmit = async (e) => {
    e.preventDefault();
    setCreatingUser(true);
    setCreateUserError(null);

    const venueIdsArray = newUserForm.venue_ids
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    const payload = {
      email: newUserForm.email.trim(),
      password: newUserForm.password,
      display_name: newUserForm.display_name.trim(),
      role: newUserForm.role,
      venue_ids: newUserForm.role === 'SUPER_ADMIN' ? ['*'] : (venueIdsArray.length > 0 ? venueIdsArray : [activeVenueId]),
    };

    try {
      await userApi.createUser(payload);
      setShowAddUserModal(false);
      setNewUserForm({
        email: '',
        password: '',
        display_name: '',
        role: 'OPERATOR',
        venue_ids: '',
      });
      await fetchUsers();
    } catch (err) {
      setCreateUserError(err.message || 'Failed to provision user.');
    } finally {
      setCreatingUser(false);
    }
  };

  return (
    <div className="min-h-screen text-slate-100 flex flex-col">
      {/* Top Navigation */}
      <HeaderBar
        venues={venues}
        activeVenueId={activeVenueId}
        onVenueChange={setActiveVenueId}
        isLoadingVenues={isLoadingVenues}
        user={currentUser}
      />

      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6 w-full space-y-6">
        {/* Page Title & Tab Navigation */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">System Settings & Administration</h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Manage physical capture hardware, venue configurations, and operator access controls.
            </p>
          </div>

          <div className="flex items-center gap-1.5 bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 self-start sm:self-auto">
            {TABS.map((tab) => {
              if (tab.id === 'users' && !isSuperAdmin) return null;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-cyan-500 text-slate-950 font-semibold shadow-md shadow-cyan-950/40'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── TAB 1: CAMERAS & HARDWARE ── */}
        {activeTab === 'cameras' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Live Camera Card */}
            <div className="lg:col-span-1 space-y-6">
              <CameraStatusCard venueId={activeVenueId} isLoading={isLoadingVenues} />
            </div>

            {/* Camera Management Table */}
            <div className="lg:col-span-2 space-y-4">
              <Card title="Registered Cameras" className="h-full">
                {cameraError && (
                  <div className="mb-4 p-3 bg-rose-950/40 border border-rose-500/30 rounded-lg text-xs text-rose-400">
                    {cameraError}
                  </div>
                )}
                {cameraSuccess && (
                  <div className="mb-4 p-3 bg-emerald-950/40 border border-emerald-500/30 rounded-lg text-xs text-emerald-400">
                    {cameraSuccess}
                  </div>
                )}

                {cameraLoading ? (
                  <div className="space-y-3 py-4">
                    <div className="h-10 bg-slate-800/50 rounded-lg animate-pulse" />
                    <div className="h-10 bg-slate-800/50 rounded-lg animate-pulse" />
                  </div>
                ) : cameraList.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
                    No cameras currently configured for venue &apos;{activeVenueId}&apos;.
                    Use the &quot;Add Camera&quot; button in the Live Camera Runtime card to register a stream.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-800 pb-2">
                        <tr>
                          <th className="pb-2.5 px-3">Camera Name</th>
                          <th className="pb-2.5 px-3">Type</th>
                          <th className="pb-2.5 px-3">Source (Masked)</th>
                          <th className="pb-2.5 px-3">Gate</th>
                          <th className="pb-2.5 px-3">FPS</th>
                          <th className="pb-2.5 px-3">Status</th>
                          <th className="pb-2.5 px-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {cameraList.map((cam) => {
                          const isBusy = cameraActionLoading[cam.camera_id];
                          return (
                            <tr key={cam.camera_id} className="hover:bg-slate-800/30 transition-colors">
                              <td className="py-3 px-3 font-medium text-slate-200">
                                {cam.camera_name || cam.camera_id}
                              </td>
                              <td className="py-3 px-3 uppercase text-[11px] font-mono text-cyan-400">
                                {cam.camera_type}
                              </td>
                              <td className="py-3 px-3 font-mono text-[11px] text-slate-400 truncate max-w-[150px]">
                                {cam.camera_source_masked || '—'}
                              </td>
                              <td className="py-3 px-3 text-slate-400">
                                {cam.gate_id || '—'}
                              </td>
                              <td className="py-3 px-3 text-slate-400">
                                {cam.configured_fps || 30}
                              </td>
                              <td className="py-3 px-3">
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-slate-800 border border-slate-700 text-slate-300">
                                  {cam.status}
                                </span>
                              </td>
                              <td className="py-3 px-3 text-right">
                                <button
                                  type="button"
                                  disabled={isBusy}
                                  onClick={() => handleDeleteCamera(cam.camera_id)}
                                  className="px-2 py-1 text-[11px] text-rose-400 hover:text-rose-300 hover:bg-rose-950/30 rounded border border-transparent hover:border-rose-500/30 disabled:opacity-50 transition-colors"
                                >
                                  {isBusy ? 'Deleting…' : 'Delete'}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </div>
          </div>
        )}

        {/* ── TAB 2: VENUE & ENGINE ── */}
        {activeTab === 'venue' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
            <Card title="Active Venue Details">
              {venueError && (
                <div className="mb-4 p-3 bg-rose-950/40 border border-rose-500/30 rounded-lg text-xs text-rose-400">
                  {venueError}
                </div>
              )}
              {resetSuccess && (
                <div className="mb-4 p-3 bg-emerald-950/40 border border-emerald-500/30 rounded-lg text-xs text-emerald-400">
                  {resetSuccess}
                </div>
              )}

              {venueLoading ? (
                <div className="space-y-3 py-4">
                  <div className="h-6 bg-slate-800/50 rounded animate-pulse" />
                  <div className="h-6 bg-slate-800/50 rounded animate-pulse" />
                </div>
              ) : venueInfo ? (
                <div className="space-y-4 text-xs">
                  <div className="flex justify-between py-2 border-b border-slate-800">
                    <span className="text-slate-400 font-medium">Venue ID</span>
                    <span className="font-mono text-cyan-400 font-semibold">{venueInfo.venue_id}</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-slate-800">
                    <span className="text-slate-400 font-medium">Configured Maximum Capacity</span>
                    <span className="font-semibold text-slate-200">{venueInfo.venue_capacity.toLocaleString()} persons</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-slate-800">
                    <span className="text-slate-400 font-medium">AI Engine Availability</span>
                    <span className={venueInfo.ai_engine_available ? 'text-emerald-400 font-semibold' : 'text-amber-400 font-semibold'}>
                      {venueInfo.ai_engine_available ? '● Active (YOLO + ByteTrack)' : '○ Degraded Mode'}
                    </span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-slate-800">
                    <span className="text-slate-400 font-medium">Active Monitoring Session</span>
                    <span className="font-mono text-slate-300">
                      {venueInfo.active_session_id || 'None (No active session)'}
                    </span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-slate-400 font-medium">Total Registered Venues</span>
                    <span className="text-slate-300 font-semibold">{venueInfo.registered_venues}</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500 py-4">No venue information available.</p>
              )}
            </Card>

            {/* Engine Reset & Administrative Actions */}
            <Card title="Engine State Maintenance">
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Clears the in-memory movement trajectories, intelligence sliding windows, active anomaly alerts,
                and predictive trend histories for venue &apos;{activeVenueId}&apos;.
              </p>

              {isSuperAdmin ? (
                <div className="p-4 bg-rose-950/20 border border-rose-500/20 rounded-xl space-y-3">
                  <div className="flex items-center gap-2 text-rose-400 text-xs font-semibold">
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    High-Impact Administrative Action
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Restricted to Super Administrators. This resets the venue&apos;s active mathematical state machine.
                  </p>

                  {resetConfirmOpen ? (
                    <div className="space-y-2 pt-2 border-t border-rose-500/20">
                      <p className="text-xs text-rose-300 font-medium">
                        Confirm: Are you sure you want to reset the in-memory engine state for &apos;{activeVenueId}&apos;?
                      </p>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          disabled={resetting}
                          onClick={handleResetEngine}
                          className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold disabled:opacity-50 transition-colors"
                        >
                          {resetting ? 'Resetting…' : 'Yes, Reset Engine'}
                        </button>
                        <button
                          type="button"
                          disabled={resetting}
                          onClick={() => setResetConfirmOpen(false)}
                          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setResetConfirmOpen(true)}
                      className="px-3.5 py-2 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 rounded-lg text-xs font-medium transition-colors"
                    >
                      Reset Engine State
                    </button>
                  )}
                </div>
              ) : (
                <div className="p-3 bg-slate-800/40 border border-slate-700/40 rounded-lg text-xs text-slate-400">
                  Engine reset requires <span className="text-rose-400 font-semibold">SUPER_ADMIN</span> privileges.
                </div>
              )}
            </Card>
          </div>
        )}

        {/* ── TAB 3: OPERATORS & ACCESS (SUPER_ADMIN ONLY) ── */}
        {activeTab === 'users' && isSuperAdmin && (
          <div className="space-y-4">
            <Card title="Operator User Management">
              <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">Registered Platform Users</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Provision new operator accounts and manage account activation status.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setCreateUserError(null);
                    setShowAddUserModal(true);
                  }}
                  className="px-3 py-1.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Create User
                </button>
              </div>

              {usersError && (
                <div className="mb-4 p-3 bg-rose-950/40 border border-rose-500/30 rounded-lg text-xs text-rose-400">
                  {usersError}
                </div>
              )}

              {usersLoading ? (
                <div className="space-y-3 py-4">
                  <div className="h-10 bg-slate-800/50 rounded animate-pulse" />
                  <div className="h-10 bg-slate-800/50 rounded animate-pulse" />
                </div>
              ) : usersList.length === 0 ? (
                <p className="text-xs text-slate-500 py-6 text-center">No operator users registered.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-800 pb-2">
                      <tr>
                        <th className="pb-2.5 px-3">Display Name</th>
                        <th className="pb-2.5 px-3">Email Address</th>
                        <th className="pb-2.5 px-3">Role</th>
                        <th className="pb-2.5 px-3">Venue Scope</th>
                        <th className="pb-2.5 px-3">Status</th>
                        <th className="pb-2.5 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {usersList.map((u) => {
                        const isUpdating = statusUpdating[u.user_id];
                        const isSelf = currentUser && currentUser.user_id === u.user_id;

                        return (
                          <tr key={u.user_id} className="hover:bg-slate-800/30 transition-colors">
                            <td className="py-3 px-3 font-medium text-slate-200">
                              {u.display_name}
                              {isSelf && <span className="ml-2 text-[10px] text-cyan-400 font-mono">(You)</span>}
                            </td>
                            <td className="py-3 px-3 font-mono text-slate-400">{u.email}</td>
                            <td className="py-3 px-3">
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-slate-800 border border-slate-700 text-slate-300">
                                {u.role}
                              </span>
                            </td>
                            <td className="py-3 px-3 font-mono text-[11px] text-slate-400">
                              {u.venue_ids?.includes('*') ? 'All Venues (*)' : u.venue_ids?.join(', ') || 'None'}
                            </td>
                            <td className="py-3 px-3">
                              <span
                                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                                  u.is_active
                                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                                    : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                                }`}
                              >
                                <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-400' : 'bg-rose-400'}`} />
                                {u.is_active ? 'ACTIVE' : 'INACTIVE'}
                              </span>
                            </td>
                            <td className="py-3 px-3 text-right">
                              {isSelf ? (
                                <span className="text-[11px] text-slate-600 italic">Protected</span>
                              ) : (
                                <button
                                  type="button"
                                  disabled={isUpdating}
                                  onClick={() => handleToggleUserStatus(u.user_id, u.is_active)}
                                  className={`px-2.5 py-1 text-[11px] rounded font-medium border transition-colors disabled:opacity-50 ${
                                    u.is_active
                                      ? 'text-rose-400 hover:text-rose-300 bg-rose-950/20 border-rose-500/30'
                                      : 'text-emerald-400 hover:text-emerald-300 bg-emerald-950/20 border-emerald-500/30'
                                  }`}
                                >
                                  {isUpdating ? 'Updating…' : u.is_active ? 'Deactivate' : 'Activate'}
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            {/* Create User Modal Dialog */}
            {showAddUserModal && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-5 shadow-2xl space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                    <h3 className="text-sm font-semibold text-slate-200">Provision New Operator</h3>
                    <button
                      type="button"
                      onClick={() => setShowAddUserModal(false)}
                      className="text-slate-400 hover:text-slate-200 text-lg leading-none"
                    >
                      ✕
                    </button>
                  </div>

                  {createUserError && (
                    <div className="p-2.5 bg-rose-950/40 border border-rose-500/30 rounded-lg text-xs text-rose-400">
                      {createUserError}
                    </div>
                  )}

                  <form onSubmit={handleCreateUserSubmit} className="space-y-3.5">
                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">
                        Display Name *
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. Alice Operator"
                        value={newUserForm.display_name}
                        onChange={(e) => setNewUserForm({ ...newUserForm, display_name: e.target.value })}
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">
                        Email Address *
                      </label>
                      <input
                        type="email"
                        required
                        placeholder="operator@crowdos.internal"
                        value={newUserForm.email}
                        onChange={(e) => setNewUserForm({ ...newUserForm, email: e.target.value })}
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">
                        Initial Password * (min 8 chars, max 72 bytes)
                      </label>
                      <input
                        type="password"
                        required
                        minLength={8}
                        maxLength={72}
                        placeholder="••••••••••••"
                        value={newUserForm.password}
                        onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value })}
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-slate-300 mb-1">
                          Role *
                        </label>
                        <select
                          value={newUserForm.role}
                          onChange={(e) => setNewUserForm({ ...newUserForm, role: e.target.value })}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                        >
                          <option value="OPERATOR">Operator</option>
                          <option value="ANALYST">Analyst</option>
                          <option value="VENUE_ADMIN">Venue Admin</option>
                          <option value="SUPER_ADMIN">Super Admin</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-slate-300 mb-1">
                          Authorized Venues
                        </label>
                        <input
                          type="text"
                          disabled={newUserForm.role === 'SUPER_ADMIN'}
                          placeholder={newUserForm.role === 'SUPER_ADMIN' ? 'All (*)' : 'venue_1, venue_2'}
                          value={newUserForm.role === 'SUPER_ADMIN' ? '*' : newUserForm.venue_ids}
                          onChange={(e) => setNewUserForm({ ...newUserForm, venue_ids: e.target.value })}
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                      <button
                        type="button"
                        disabled={creatingUser}
                        onClick={() => setShowAddUserModal(false)}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={creatingUser}
                        className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 disabled:opacity-50 transition-colors"
                      >
                        {creatingUser ? 'Creating…' : 'Create Operator'}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
