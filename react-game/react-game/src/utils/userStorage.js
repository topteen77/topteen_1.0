/**
 * User Storage Utility
 * Manages user data storage in localStorage, keyed by phone number
 */

/**
 * Get user data from localStorage
 * @param {string} phoneNumber - User's phone number
 * @returns {Object|null} User data object or null if not found
 */
export const getUserData = (phoneNumber) => {
  if (!phoneNumber) return null;
  
  try {
    const data = localStorage.getItem(`userData_${phoneNumber}`);
    return data ? JSON.parse(data) : null;
  } catch (error) {
    console.error('Error reading user data:', error);
    return null;
  }
};

/**
 * Save user data to localStorage
 * @param {string} phoneNumber - User's phone number
 * @param {Object} data - Data to save
 */
export const saveUserData = (phoneNumber, data) => {
  if (!phoneNumber) {
    console.error('Phone number is required to save user data');
    return;
  }

  try {
    const existingData = getUserData(phoneNumber) || {};
    const updatedData = {
      ...existingData,
      ...data,
      lastUpdated: new Date().toISOString()
    };
    localStorage.setItem(`userData_${phoneNumber}`, JSON.stringify(updatedData));
  } catch (error) {
    console.error('Error saving user data:', error);
  }
};

/**
 * Track user action
 * @param {string} phoneNumber - User's phone number
 * @param {string} action - Action name
 * @param {Object} data - Action data
 */
export const trackUserAction = (phoneNumber, action, data) => {
  if (!phoneNumber) return;

  try {
    const userData = getUserData(phoneNumber) || {};
    const actions = userData.actions || [];
    
    actions.push({
      action,
      data,
      timestamp: new Date().toISOString()
    });

    saveUserData(phoneNumber, {
      actions
    });
  } catch (error) {
    console.error('Error tracking user action:', error);
  }
};

/**
 * Get all user data for a phone number
 * @param {string} phoneNumber - User's phone number
 * @returns {Object} Complete user data object
 */
export const getAllUserData = (phoneNumber) => {
  return getUserData(phoneNumber) || {};
};

/**
 * Initialize user data when phone number is set
 * @param {string} phoneNumber - User's phone number
 */
export const initializeUserData = (phoneNumber) => {
  if (!phoneNumber) return;

  const existingData = getUserData(phoneNumber);
  if (!existingData) {
    saveUserData(phoneNumber, {
      phoneNumber,
      createdAt: new Date().toISOString(),
      actions: []
    });
  }
};

/**
 * Check if eligibility email has been sent for a user
 * @param {string} phoneNumber - User's phone number
 * @returns {boolean} True if email has been sent, false otherwise
 */
export const hasEligibilityEmailBeenSent = (phoneNumber) => {
  if (!phoneNumber) return false;
  
  try {
    const userData = getUserData(phoneNumber);
    return userData?.eligibilityEmailSent === true;
  } catch (error) {
    console.error('Error checking eligibility email status:', error);
    return false;
  }
};

/**
 * Mark eligibility email as sent for a user
 * @param {string} phoneNumber - User's phone number
 */
export const markEligibilityEmailAsSent = (phoneNumber) => {
  if (!phoneNumber) {
    console.error('Phone number is required to mark email as sent');
    return;
  }

  try {
    saveUserData(phoneNumber, {
      eligibilityEmailSent: true,
      eligibilityEmailSentAt: new Date().toISOString()
    });
  } catch (error) {
    console.error('Error marking eligibility email as sent:', error);
  }
};

/**
 * Clear all localStorage data (logout)
 */
export const clearAllStorage = () => {
  try {
    localStorage.clear();
    console.log('All localStorage data cleared');
  } catch (error) {
    console.error('Error clearing localStorage:', error);
  }
};
