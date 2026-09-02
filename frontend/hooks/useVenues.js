/**
 * Venues Management Hook.
 *
 * Fetches available venues from backend and manages active selection.
 */
import { useState, useEffect, useCallback } from 'react';
import { venueApi } from '@/services/api/venues';

export function useVenues() {
  const [venues, setVenues] = useState([]);
  const [activeVenueId, setActiveVenueId] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchVenues = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const list = await venueApi.listVenues();
      const validVenues = Array.isArray(list) ? list : [];
      setVenues(validVenues);

      // Auto-select first venue if none active or current no longer exists
      if (validVenues.length > 0) {
        setActiveVenueId((prev) => (validVenues.includes(prev) ? prev : validVenues[0]));
      } else {
        // Fallback default venue if backend returns empty list
        const fallback = 'default_venue';
        setVenues([fallback]);
        setActiveVenueId(fallback);
      }
    } catch (err) {
      console.warn('Failed to fetch venues, using fallback default_venue:', err);
      setError(err.message || 'Failed to load venues');
      setVenues(['default_venue']);
      setActiveVenueId('default_venue');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVenues();
  }, [fetchVenues]);

  return {
    venues,
    activeVenueId,
    setActiveVenueId,
    isLoading,
    error,
    refreshVenues: fetchVenues,
  };
}
