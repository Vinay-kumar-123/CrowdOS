/**
 * Venue Management API Service.
 */
import { api } from '../../lib/api';

export const venueApi = {
  /**
   * List all registered venues.
   * @returns {Promise<string[]>} List of venue IDs.
   */
  async listVenues() {
    return api.get('/api/v1/venues');
  },

  /**
   * Get metadata and live engine status for a venue.
   * @param {string} venueId
   * @returns {Promise<object>} VenueInfoResponse
   */
  async getVenueInfo(venueId) {
    return api.get(`/api/v1/venues/${encodeURIComponent(venueId)}`);
  },

  /**
   * Reset engine state for a venue (testing utility).
   * @param {string} venueId
   */
  async resetVenue(venueId) {
    return api.post(`/api/v1/venues/${encodeURIComponent(venueId)}/reset`);
  },
};
