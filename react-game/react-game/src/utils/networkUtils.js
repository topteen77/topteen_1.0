// Network Utilities

/**
 * Check if device is online
 * @returns {boolean} True if online, false otherwise
 */
export const isOnline = () => {
  return typeof navigator !== 'undefined' && navigator.onLine !== false;
};

/**
 * Add network status listener
 * @param {Function} onOnline - Callback when coming online
 * @param {Function} onOffline - Callback when going offline
 * @returns {Function} Cleanup function to remove listeners
 */
export const addNetworkListeners = (onOnline, onOffline) => {
  if (typeof window === 'undefined') return () => {};

  window.addEventListener('online', onOnline);
  window.addEventListener('offline', onOffline);

  return () => {
    window.removeEventListener('online', onOnline);
    window.removeEventListener('offline', onOffline);
  };
};

/**
 * Get network error message based on error type
 * @param {Object} error - Error object
 * @returns {string} User-friendly error message
 */
export const getNetworkErrorMessage = (error) => {
  if (!error) return 'An unknown error occurred.';

  if (error.isNetworkError) {
    return 'No internet connection. Please check your network and try again.';
  }

  if (error.isTimeoutError) {
    return 'Request timed out. The server is taking too long to respond. Please try again.';
  }

  if (error.message) {
    if (error.message.includes('network') || error.message.includes('fetch')) {
      return 'Network error. Please check your internet connection.';
    }
    if (error.message.includes('timeout')) {
      return 'Request timed out. Please try again.';
    }
  }

  return error.reasoning || error.error || 'An error occurred. Please try again.';
};

