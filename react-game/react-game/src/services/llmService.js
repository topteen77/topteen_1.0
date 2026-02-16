// LLM Service - Wrapper for Firebase Functions
// This service handles all LLM-related API calls through Firebase Functions

import { compareStreams as firebaseCompareStreams } from './firebase';

// Timeout duration in milliseconds (30 seconds)
const LLM_TIMEOUT = 30000;

/**
 * Check if device is online
 * @returns {boolean} True if online, false otherwise
 */
const isOnline = () => {
  return navigator.onLine !== false;
};

/**
 * Create a timeout promise
 * @param {number} ms - Timeout in milliseconds
 * @returns {Promise} Promise that rejects after timeout
 */
const createTimeout = (ms) => {
  return new Promise((_, reject) => {
    setTimeout(() => {
      reject(new Error('Request timeout. Please check your connection and try again.'));
    }, ms);
  });
};

/**
 * Compare two streams based on selected parameters
 * @param {string[]} streams - Array of 2 stream names
 * @param {string[]} parameters - Array of selected parameter IDs
 * @returns {Promise<Object>} Result object with winner, reasoning, and details
 */
export const compareStreamsWithLLM = async (streams, parameters) => {
  // Validate inputs
  if (!streams || !Array.isArray(streams) || streams.length !== 2) {
    return {
      winner: null,
      reasoning: 'Invalid streams selection. Please select exactly 2 streams.',
      details: {},
      success: false,
      error: 'Invalid streams'
    };
  }

  if (!parameters || !Array.isArray(parameters) || parameters.length === 0) {
    return {
      winner: null,
      reasoning: 'Invalid parameters selection. Please select at least one parameter.',
      details: {},
      success: false,
      error: 'Invalid parameters'
    };
  }

  // Check network connectivity
  if (!isOnline()) {
    return {
      winner: null,
      reasoning: 'No internet connection. Please check your network and try again.',
      details: {},
      success: false,
      error: 'Network offline',
      isNetworkError: true
    };
  }

  try {
    // Create timeout race condition
    const result = await Promise.race([
      firebaseCompareStreams({
        streams,
        parameters
      }),
      createTimeout(LLM_TIMEOUT)
    ]);
    
    // Validate response
    if (!result) {
      return {
        winner: null,
        reasoning: 'Empty response received. Please try again.',
        details: {},
        success: false,
        error: 'Empty response'
      };
    }

    // Check if winner is valid
    if (!result.winner || !streams.includes(result.winner)) {
      // Fallback: use first stream as winner if response is invalid
      return {
        winner: streams[0],
        reasoning: result.reasoning || `Based on the comparison, ${streams[0]} appears to be the better choice. However, the analysis was incomplete.`,
        details: result.details || {},
        success: true,
        warning: 'Response validation failed, using fallback'
      };
    }
    
    // Clean response: remove error fields if winner exists
    // Create a clean result object without error-related fields
    const cleanResult = {
      winner: result.winner,
      reasoning: result.reasoning || 'No detailed reasoning provided, but a winner was determined.',
      details: result.details || {},
      success: true
    };
    
    return cleanResult;
  } catch (error) {
    console.error('LLM Service Error:', error);
    console.error('Error code:', error.code);
    console.error('Error message:', error.message);
    console.error('Full error object:', JSON.stringify(error, null, 2));
    
    // Handle specific error types
    let errorMessage = 'An error occurred while comparing streams. Please try again.';
    let isNetworkError = false;
    let isTimeoutError = false;

    // Handle Firebase-specific errors
    if (error.code === 'invalid-argument') {
      errorMessage = 'Invalid request data. Please ensure you have selected 2 streams and at least 1 parameter.';
    } else if (error.code === 'not-found') {
      errorMessage = 'Function not found. The function may not be deployed. Please check Firebase Console.';
    } else if (error.code === 'permission-denied') {
      errorMessage = 'Permission denied. The function may require authentication. Please check Firebase Console permissions.';
    } else if (error.message && (error.message.includes('timeout') || error.message.includes('Timeout'))) {
      errorMessage = 'Request timed out. The comparison is taking longer than expected. Please try again.';
      isTimeoutError = true;
    } else if (error.message && (error.message.includes('network') || error.message.includes('Network') || error.message.includes('fetch'))) {
      errorMessage = 'Network error. Please check your internet connection and try again.';
      isNetworkError = true;
    } else if (error.message) {
      errorMessage = error.message;
    }

    return {
      winner: null,
      reasoning: errorMessage,
      details: {},
      success: false,
      error: error.message || error.code || 'Unknown error',
      errorCode: error.code,
      isNetworkError,
      isTimeoutError
    };
  }
};

