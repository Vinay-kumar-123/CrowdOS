/**
 * Prediction & Risk Intelligence API Service.
 */
import { api } from '../../lib/api';

export const predictionApi = {
  /**
   * Run and fetch full prediction cycle for venue.
   * @param {string} venueId
   */
  async getPrediction(venueId) {
    return api.get(`/api/v1/venues/${encodeURIComponent(venueId)}/predictions`);
  },

  /**
   * Get historical prediction snapshots.
   * @param {string} venueId
   * @param {object} params - { session_id?: string, limit?: number }
   */
  async getPredictionHistory(venueId, params = {}) {
    const query = new URLSearchParams();
    if (params.session_id) query.set('session_id', params.session_id);
    if (params.limit) query.set('limit', String(params.limit));
    const qs = query.toString() ? `?${query.toString()}` : '';
    return api.get(`/api/v1/venues/${encodeURIComponent(venueId)}/predictions/history${qs}`);
  },
};
