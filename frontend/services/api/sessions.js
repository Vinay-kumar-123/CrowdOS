/**
 * Session Lifecycle Management API Service.
 */
import { api } from '../../lib/api';

export const sessionApi = {
  /**
   * List all sessions for a venue.
   * @param {string} venueId
   */
  async listSessions(venueId) {
    return api.get(`/api/v1/venues/${encodeURIComponent(venueId)}/sessions`);
  },

  /**
   * Get the active session for a venue.
   * @param {string} venueId
   * @returns {Promise<object|null>} SessionStatusResponse or null
   */
  async getActiveSession(venueId) {
    return api.get(`/api/v1/venues/${encodeURIComponent(venueId)}/sessions/active`);
  },

  /**
   * Create a new monitoring session for a venue.
   * @param {string} venueId
   * @param {object} payload - { venue_capacity?: number, max_duration_seconds?: number }
   */
  async createSession(venueId, payload = {}) {
    return api.post(`/api/v1/venues/${encodeURIComponent(venueId)}/sessions`, payload);
  },

  /**
   * Start a session (CREATED/PAUSED -> ACTIVE).
   * @param {string} venueId
   * @param {string} sessionId
   */
  async startSession(venueId, sessionId) {
    return api.post(
      `/api/v1/venues/${encodeURIComponent(venueId)}/sessions/${encodeURIComponent(sessionId)}/start`
    );
  },

  /**
   * Pause an active session (ACTIVE -> PAUSED).
   * @param {string} venueId
   * @param {string} sessionId
   */
  async pauseSession(venueId, sessionId) {
    return api.post(
      `/api/v1/venues/${encodeURIComponent(venueId)}/sessions/${encodeURIComponent(sessionId)}/pause`
    );
  },

  /**
   * Resume a paused session (PAUSED -> ACTIVE).
   * @param {string} venueId
   * @param {string} sessionId
   */
  async resumeSession(venueId, sessionId) {
    return api.post(
      `/api/v1/venues/${encodeURIComponent(venueId)}/sessions/${encodeURIComponent(sessionId)}/resume`
    );
  },

  /**
   * Stop a session (ACTIVE/PAUSED -> STOPPED).
   * @param {string} venueId
   * @param {string} sessionId
   */
  async stopSession(venueId, sessionId) {
    return api.post(
      `/api/v1/venues/${encodeURIComponent(venueId)}/sessions/${encodeURIComponent(sessionId)}/stop`
    );
  },
};
