/**
 * Alert Management API Service.
 */
import { api } from '../../lib/api';

export const alertApi = {
  /**
   * Get all alerts (active + resolved) for venue.
   * @param {string} venueId
   */
  async getAllAlerts(venueId) {
    return api.get(`/api/v1/venues/${encodeURIComponent(venueId)}/alerts`);
  },

  /**
   * Get active unresolved alerts for venue.
   * @param {string} venueId
   */
  async getActiveAlerts(venueId) {
    return api.get(`/api/v1/venues/${encodeURIComponent(venueId)}/alerts/active`);
  },
};
