/**
 * User Management & Authentication Profile API Client Service — Sprint 15.
 *
 * REST API client for operator profile inspection and user provisioning.
 * Protected by Sprint 15 cookie authentication and role-based access control.
 */
import { api } from '../../lib/api';

export const userApi = {
  /**
   * Get current authenticated user profile.
   * @returns {Promise<object>} UserResponse
   */
  async getCurrentUser() {
    return api.get('/api/v1/auth/me');
  },

  /**
   * List all operator users (Super Admin only).
   * @param {object} params - { skip?: number, limit?: number }
   * @returns {Promise<object[]>} Array of UserResponse
   */
  async listUsers(params = {}) {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.set('skip', String(params.skip));
    if (params.limit !== undefined) query.set('limit', String(params.limit));
    const qs = query.toString() ? `?${query.toString()}` : '';
    return api.get(`/api/v1/users${qs}`);
  },

  /**
   * Provision a new operator user (Super Admin only).
   * @param {object} payload - { email, password, display_name, role, venue_ids }
   * @returns {Promise<object>} UserResponse
   */
  async createUser(payload) {
    return api.post('/api/v1/users', payload);
  },

  /**
   * Update user active status (Super Admin only).
   * @param {string} userId
   * @param {boolean} isActive
   * @returns {Promise<object>} UserResponse
   */
  async updateUserStatus(userId, isActive) {
    return api.patch(`/api/v1/users/${encodeURIComponent(userId)}/status`, {
      is_active: Boolean(isActive),
    });
  },
};
