// Firebase Services
import { httpsCallable } from 'firebase/functions';
import { functions } from '../firebase/config';

/**
 * Call the compareStreams Cloud Function
 * @param {Object} data - Comparison data
 * @param {string[]} data.streams - Selected streams (2 items)
 * @param {string[]} data.parameters - Selected parameters
 * @returns {Promise<Object>} Comparison result with winner and reasoning
 */
export const compareStreams = async (data) => {
  try {
    // Validate input data
    if (!data || !data.streams || !data.parameters) {
      throw new Error('Invalid data format. Expected { streams: [], parameters: [] }');
    }

    console.log('Calling compareStreams function with data:', data);
    
    const compareStreamsFunction = httpsCallable(functions, 'compareStreams');
    const result = await compareStreamsFunction(data);
    
    console.log('Function response received:', result);
    return result.data;
  } catch (error) {
    console.error('Error calling compareStreams function:', error);
    console.error('Error code:', error.code);
    console.error('Error message:', error.message);
    console.error('Error details:', error.details);
    
    // Provide more detailed error information
    if (error.code === 'invalid-argument') {
      throw new Error(`Invalid argument: ${error.message || 'The function received invalid data. Please check your selections and try again.'}`);
    } else if (error.code === 'not-found') {
      throw new Error('Function not found. The function may not be deployed yet. Please check Firebase Console.');
    } else if (error.code === 'permission-denied') {
      throw new Error('Permission denied. The function may require authentication or may not allow public access.');
    } else {
      throw error;
    }
  }
};

/**
 * Check course eligibility based on education background and winner stream
 * @param {Object} data - Eligibility check data
 * @param {Object} data.educationBackground - Education background information
 * @param {string} data.winnerStream - Winner stream name
 * @returns {Promise<Object>} Result with eligible courses list
 */
export const checkCourseEligibility = async (data) => {
  try {
    // Validate input data
    if (!data || !data.educationBackground || !data.winnerStream) {
      throw new Error('Invalid data format. Expected { educationBackground: {}, winnerStream: string }');
    }

    console.log('Calling checkCourseEligibility function with data:', data);
    
    const checkCourseEligibilityFunction = httpsCallable(functions, 'checkCourseEligibility');
    const result = await checkCourseEligibilityFunction(data);
    
    console.log('Function response received:', result);
    return result.data;
  } catch (error) {
    console.error('Error calling checkCourseEligibility function:', error);
    console.error('Error code:', error.code);
    console.error('Error message:', error.message);
    console.error('Error details:', error.details);
    
    // Provide more detailed error information
    if (error.code === 'invalid-argument') {
      throw new Error(`Invalid argument: ${error.message || 'The function received invalid data. Please check your selections and try again.'}`);
    } else if (error.code === 'not-found') {
      throw new Error('Function not found. The function may not be deployed yet. Please check Firebase Console.');
    } else if (error.code === 'permission-denied') {
      throw new Error('Permission denied. The function may require authentication or may not allow public access.');
    } else {
      throw error;
    }
  }
};

/**
 * Send email using AWS SES SMTP via Firebase Function
 * @param {Object} data - Email data
 * @param {string} data.to - Recipient email address
 * @param {string} data.from - Sender email address
 * @param {string} data.subject - Email subject
 * @param {string} data.text - Plain text body
 * @param {string} data.html - HTML body (optional)
 * @returns {Promise<Object>} Result with success status and message
 */
export const sendEmail = async (data) => {
  try {
    // Validate input data
    if (!data || !data.to || !data.from || !data.subject) {
      throw new Error('Invalid data format. Expected { to: string, from: string, subject: string, text: string, html?: string }');
    }

    if (!data.text && !data.html) {
      throw new Error('Email body (text or HTML) is required');
    }

    console.log('Calling sendEmail function with data:', {
      to: data.to,
      from: data.from,
      subject: data.subject
    });
    
    const sendEmailFunction = httpsCallable(functions, 'sendEmail');
    const result = await sendEmailFunction(data);
    
    console.log('Email sent successfully:', result);
    return result.data;
  } catch (error) {
    console.error('Error calling sendEmail function:', error);
    console.error('Error code:', error.code);
    console.error('Error message:', error.message);
    console.error('Error details:', error.details);
    
    // Provide more detailed error information
    if (error.code === 'invalid-argument') {
      throw new Error(`Invalid argument: ${error.message || 'The function received invalid data. Please check your email data and try again.'}`);
    } else if (error.code === 'not-found') {
      throw new Error('Function not found. The function may not be deployed yet. Please check Firebase Console.');
    } else if (error.code === 'permission-denied') {
      throw new Error('Permission denied. The function may require authentication or may not allow public access.');
    } else {
      throw error;
    }
  }
};
