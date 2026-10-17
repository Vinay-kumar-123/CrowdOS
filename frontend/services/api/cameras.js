/**
 * Camera API Client Service — Sprint 16.
 *
 * REST API client for camera registration, stream controls, and health inspection.
 * Protected by Sprint 15 cookie authentication and venue authorization.
 */
import { api } from '../../lib/api';

export const cameraApi = {
  /**
   * List all registered cameras for a venue.
   */
  async listCameras(venueId) {
    return api.get(`/api/v1/venues/${encodeURIComponent(venueId)}/cameras`);
  },

  /**
   * Get live telemetry and health score for a specific camera.
   */
  async getCameraHealth(venueId, cameraId) {
    return api.get(
      `/api/v1/venues/${encodeURIComponent(venueId)}/cameras/${encodeURIComponent(cameraId)}/health`
    );
  },

  /**
   * Register a new camera for a venue (Venue Admin+).
   */
  async registerCamera(venueId, payload) {
    return api.post(
      `/api/v1/venues/${encodeURIComponent(venueId)}/cameras`,
      payload
    );
  },

  /**
   * Start camera stream capture loop (Operator+).
   */
  async startCamera(venueId, cameraId) {
    return api.post(
      `/api/v1/venues/${encodeURIComponent(venueId)}/cameras/${encodeURIComponent(cameraId)}/start`
    );
  },

  /**
   * Stop camera stream capture loop (Operator+).
   */
  async stopCamera(venueId, cameraId) {
    return api.post(
      `/api/v1/venues/${encodeURIComponent(venueId)}/cameras/${encodeURIComponent(cameraId)}/stop`
    );
  },

  /**
   * Delete camera registration and stop stream if running (Venue Admin+).
   */
  async deleteCamera(venueId, cameraId) {
    return api.delete(
      `/api/v1/venues/${encodeURIComponent(venueId)}/cameras/${encodeURIComponent(cameraId)}`
    );
  },
};
