/**
 * Unified Dashboard & Health API Service.
 */
import { api } from '../../lib/api';

export const dashboardApi = {
  /**
   * Get full live dashboard snapshot for a venue session.
   * @param {string} venueId
   * @param {string} sessionId
   * @returns {Promise<object>} DashboardSnapshotResponse
   */
  async getVenueSessionDashboard(venueId, sessionId) {
    return api.get(
      `/api/v1/venues/${encodeURIComponent(venueId)}/sessions/${encodeURIComponent(sessionId)}/dashboard`
    );
  },

  /**
   * Get unified dashboard snapshot by session ID.
   * @param {string} sessionId
   */
  async getSessionDashboard(sessionId) {
    return api.get(`/api/v1/sessions/${encodeURIComponent(sessionId)}/dashboard`);
  },

  /**
   * Get system infrastructure status (DB, Redis, Version).
   */
  async getSystemStatus() {
    return api.get('/api/status');
  },

  /**
   * Health probe check.
   */
  async getHealth() {
    return api.get('/health');
  },
};
