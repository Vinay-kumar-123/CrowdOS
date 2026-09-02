/**
 * Event Ingestion API Service.
 */
import { api } from '../../lib/api';

export const eventApi = {
  /**
   * Ingest a movement event (ENTRY or EXIT).
   * @param {string} venueId
   * @param {string} sessionId
   * @param {object} payload - { event_type: 'ENTRY'|'EXIT', gate_id?: string, camera_id?: string, dwell_time?: number }
   */
  async ingestEvent(venueId, sessionId, payload) {
    return api.post(
      `/api/v1/venues/${encodeURIComponent(venueId)}/sessions/${encodeURIComponent(sessionId)}/events`,
      payload
    );
  },
};
