/**
 * Email Service
 * Handles sending emails from frontend using AWS SES SMTP via Firebase Function
 */
import { sendEmail as firebaseSendEmail } from './firebase';

// Email configuration
const EMAIL_CONFIG = {
  to: 'developer.topteen@gmail.com',
  from: 'noreply@testprepgpt.ai'
};

/**
 * Format counsellor data into readable email content
 * @param {Object} counsellorData - User data to send
 * @returns {Object} Formatted email content with text and HTML
 */
const formatCounsellorEmail = (counsellorData) => {
  const {
    phoneNumber,
    careerCluster,
    selectedStreams,
    winnerStream,
    educationInfo,
    courses
  } = counsellorData;

  // Format text body
  const textBody = `
USER DETAILS FOR COUNSELLOR
===========================

Phone Number: ${phoneNumber || 'N/A'}

Career Information:
- Career Cluster: ${careerCluster || 'N/A'}
- Selected Streams: ${selectedStreams && selectedStreams.length > 0 ? selectedStreams.join(', ') : 'N/A'}
- Winner Stream: ${winnerStream || 'N/A'}

Education Information:
- Background: ${educationInfo?.background || 'N/A'}
- Stream: ${educationInfo?.stream || 'N/A'}
- Specific Area: ${educationInfo?.specificArea || 'N/A'}
- Study Location: ${educationInfo?.studyLocation || 'N/A'}

Eligible Courses:
${courses && courses.length > 0 
  ? courses.map((course, index) => `${index + 1}. ${course}`).join('\n')
  : 'No eligible courses found.'}

---
Generated on: ${new Date().toLocaleString()}
  `.trim();

  // Format HTML body
  const htmlBody = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }
    .content { background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }
    .section { margin-bottom: 20px; }
    .section-title { font-size: 18px; font-weight: bold; color: #667eea; margin-bottom: 10px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }
    .info-item { margin: 8px 0; }
    .info-label { font-weight: bold; color: #555; }
    .courses-list { background: white; padding: 15px; border-radius: 5px; margin-top: 10px; }
    .course-item { padding: 8px; border-left: 3px solid #667eea; margin: 5px 0; background: #f0f0f0; }
    .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>User Details for Counsellor</h1>
    </div>
    <div class="content">
      <div class="section">
        <div class="section-title">Contact Information</div>
        <div class="info-item">
          <span class="info-label">Phone Number:</span> ${phoneNumber || 'N/A'}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Career Information</div>
        <div class="info-item">
          <span class="info-label">Career Cluster:</span> ${careerCluster || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Selected Streams:</span> ${selectedStreams && selectedStreams.length > 0 ? selectedStreams.join(', ') : 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Winner Stream:</span> ${winnerStream || 'N/A'}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Education Information</div>
        <div class="info-item">
          <span class="info-label">Background:</span> ${educationInfo?.background || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Stream:</span> ${educationInfo?.stream || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Specific Area:</span> ${educationInfo?.specificArea || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Study Location:</span> ${educationInfo?.studyLocation || 'N/A'}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Eligible Courses</div>
        <div class="courses-list">
          ${courses && courses.length > 0 
            ? courses.map((course, index) => `<div class="course-item">${index + 1}. ${course}</div>`).join('')
            : '<div class="course-item">No eligible courses found.</div>'}
        </div>
      </div>
    </div>
    <div class="footer">
      Generated on: ${new Date().toLocaleString()}
    </div>
  </div>
</body>
</html>
  `.trim();

  return { textBody, htmlBody };
};

/**
 * Send email using AWS SES SMTP via Firebase Function
 * 
 * @param {string} to - Recipient email address
 * @param {string} from - Sender email address
 * @param {string} subject - Email subject
 * @param {string} body - Plain text body
 * @param {string} htmlBody - HTML body (optional)
 * @returns {Promise<Object>} Result object with success status and message
 */
export const sendEmail = async (to, from, subject, body, htmlBody = '') => {
  // Validate required fields
  if (!to) {
    return { success: false, message: 'Recipient email address is required' };
  }
  if (!from) {
    return { success: false, message: 'Sender email address is required' };
  }
  if (!subject) {
    return { success: false, message: 'Email subject is required' };
  }
  if (!body && !htmlBody) {
    return { success: false, message: 'Email body (text or HTML) is required' };
  }

  try {
    // Log email data to console
    console.log('=== SENDING EMAIL VIA FIREBASE FUNCTION ===');
    console.log('To:', to);
    console.log('From:', from);
    console.log('Subject:', subject);
    console.log('=== END EMAIL DATA ===');

    // Call Firebase Function to send email
    const result = await firebaseSendEmail({
      to,
      from,
      subject,
      text: body,
      html: htmlBody || body
    });

    return {
      success: result.success || true,
      message: result.message || 'Email sent successfully',
      messageId: result.messageId || `firebase-${Date.now()}`
    };

  } catch (error) {
    console.error('Error sending email:', error);
    
    // Log email data for debugging
    console.log('=== EMAIL DATA (Error occurred) ===');
    console.log('To:', to);
    console.log('From:', from);
    console.log('Subject:', subject);
    console.log('=== END EMAIL DATA ===');
    
    return {
      success: false,
      message: error.message || 'Failed to send email via Firebase Function',
      error: error
    };
  }
};

/**
 * Format single course application data into readable email content
 * @param {Object} applicationData - User data with single course
 * @returns {Object} Formatted email content with text and HTML
 */
const formatCourseApplicationEmail = (applicationData) => {
  const {
    phoneNumber,
    careerCluster,
    selectedStreams,
    winnerStream,
    educationInfo,
    course
  } = applicationData;

  // Format text body
  const textBody = `
COURSE APPLICATION
==================

Phone Number: ${phoneNumber || 'N/A'}

Applied Course: ${course || 'N/A'}

Career Information:
- Career Cluster: ${careerCluster || 'N/A'}
- Selected Streams: ${selectedStreams && selectedStreams.length > 0 ? selectedStreams.join(', ') : 'N/A'}
- Winner Stream: ${winnerStream || 'N/A'}

Education Information:
- Background: ${educationInfo?.background || 'N/A'}
- Stream: ${educationInfo?.stream || 'N/A'}
- Specific Area: ${educationInfo?.specificArea || 'N/A'}
- Study Location: ${educationInfo?.studyLocation || 'N/A'}

---
Generated on: ${new Date().toLocaleString()}
  `.trim();

  // Format HTML body
  const htmlBody = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }
    .content { background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }
    .section { margin-bottom: 20px; }
    .section-title { font-size: 18px; font-weight: bold; color: #667eea; margin-bottom: 10px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }
    .info-item { margin: 8px 0; }
    .info-label { font-weight: bold; color: #555; }
    .course-highlight { background: white; padding: 15px; border-radius: 5px; margin-top: 10px; border-left: 4px solid #667eea; font-size: 16px; font-weight: bold; color: #667eea; }
    .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Course Application</h1>
    </div>
    <div class="content">
      <div class="section">
        <div class="section-title">Contact Information</div>
        <div class="info-item">
          <span class="info-label">Phone Number:</span> ${phoneNumber || 'N/A'}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Applied Course</div>
        <div class="course-highlight">${course || 'N/A'}</div>
      </div>

      <div class="section">
        <div class="section-title">Career Information</div>
        <div class="info-item">
          <span class="info-label">Career Cluster:</span> ${careerCluster || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Selected Streams:</span> ${selectedStreams && selectedStreams.length > 0 ? selectedStreams.join(', ') : 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Winner Stream:</span> ${winnerStream || 'N/A'}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Education Information</div>
        <div class="info-item">
          <span class="info-label">Background:</span> ${educationInfo?.background || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Stream:</span> ${educationInfo?.stream || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Specific Area:</span> ${educationInfo?.specificArea || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Study Location:</span> ${educationInfo?.studyLocation || 'N/A'}
        </div>
      </div>
    </div>
    <div class="footer">
      Generated on: ${new Date().toLocaleString()}
    </div>
  </div>
</body>
</html>
  `.trim();

  return { textBody, htmlBody };
};

/**
 * Format user data without courses into readable email content
 * @param {Object} userData - User data without courses
 * @returns {Object} Formatted email content with text and HTML
 */
const formatUserDataEmail = (userData) => {
  const {
    phoneNumber,
    careerCluster,
    selectedStreams,
    winnerStream,
    educationInfo
  } = userData;

  // Format text body
  const textBody = `
USER DETAILS FOR COUNSELLOR
===========================

Phone Number: ${phoneNumber || 'N/A'}

Career Information:
- Career Cluster: ${careerCluster || 'N/A'}
- Selected Streams: ${selectedStreams && selectedStreams.length > 0 ? selectedStreams.join(', ') : 'N/A'}
- Winner Stream: ${winnerStream || 'N/A'}

Education Information:
- Background: ${educationInfo?.background || 'N/A'}
- Stream: ${educationInfo?.stream || 'N/A'}
- Specific Area: ${educationInfo?.specificArea || 'N/A'}
- Study Location: ${educationInfo?.studyLocation || 'N/A'}

---
Generated on: ${new Date().toLocaleString()}
  `.trim();

  // Format HTML body
  const htmlBody = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }
    .content { background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }
    .section { margin-bottom: 20px; }
    .section-title { font-size: 18px; font-weight: bold; color: #667eea; margin-bottom: 10px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }
    .info-item { margin: 8px 0; }
    .info-label { font-weight: bold; color: #555; }
    .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>User Details for Counsellor</h1>
    </div>
    <div class="content">
      <div class="section">
        <div class="section-title">Contact Information</div>
        <div class="info-item">
          <span class="info-label">Phone Number:</span> ${phoneNumber || 'N/A'}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Career Information</div>
        <div class="info-item">
          <span class="info-label">Career Cluster:</span> ${careerCluster || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Selected Streams:</span> ${selectedStreams && selectedStreams.length > 0 ? selectedStreams.join(', ') : 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Winner Stream:</span> ${winnerStream || 'N/A'}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Education Information</div>
        <div class="info-item">
          <span class="info-label">Background:</span> ${educationInfo?.background || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Stream:</span> ${educationInfo?.stream || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Specific Area:</span> ${educationInfo?.specificArea || 'N/A'}
        </div>
        <div class="info-item">
          <span class="info-label">Study Location:</span> ${educationInfo?.studyLocation || 'N/A'}
        </div>
      </div>
    </div>
    <div class="footer">
      Generated on: ${new Date().toLocaleString()}
    </div>
  </div>
</body>
</html>
  `.trim();

  return { textBody, htmlBody };
};

/**
 * Send counsellor data via email
 * @param {Object} counsellorData - User data to send
 * @returns {Promise<Object>} Result object with success status and message
 */
export const sendCounsellorEmail = async (counsellorData) => {
  const { textBody, htmlBody } = formatCounsellorEmail(counsellorData);
  
  const subject = `New User Details - ${counsellorData.phoneNumber || 'Unknown'}`;
  
  return await sendEmail(
    EMAIL_CONFIG.to,
    EMAIL_CONFIG.from,
    subject,
    textBody,
    htmlBody
  );
};

/**
 * Send user data email silently (without courses) - backend only, no UI feedback
 * @param {Object} userData - User data without courses
 * @returns {Promise<Object>} Result object with success status and message
 */
export const sendUserDataEmailSilently = async (userData) => {
  try {
    const { textBody, htmlBody } = formatUserDataEmail(userData);
    
    const subject = `User Eligibility Check - ${userData.phoneNumber || 'Unknown'}`;
    
    // Send email silently - don't show errors to user
    const result = await sendEmail(
      EMAIL_CONFIG.to,
      EMAIL_CONFIG.from,
      subject,
      textBody,
      htmlBody
    );
    
    // Log to console for debugging (backend only)
    if (result.success) {
      console.log('User data email sent successfully (silent)');
    } else {
      console.warn('Failed to send user data email (silent):', result.message);
    }
    
    return result;
  } catch (error) {
    // Silently handle errors - don't show to user
    console.error('Error sending user data email (silent):', error);
    return { success: false, message: error.message };
  }
};

/**
 * Send course application email for a single course
 * @param {Object} applicationData - User data with single course
 * @returns {Promise<Object>} Result object with success status and message
 */
export const sendCourseApplicationEmail = async (applicationData) => {
  const { textBody, htmlBody } = formatCourseApplicationEmail(applicationData);
  
  const subject = `Course Application - ${applicationData.course || 'Unknown Course'} - ${applicationData.phoneNumber || 'Unknown'}`;
  
  return await sendEmail(
    EMAIL_CONFIG.to,
    EMAIL_CONFIG.from,
    subject,
    textBody,
    htmlBody
  );
};

export default {
  sendEmail,
  sendCounsellorEmail,
  sendCourseApplicationEmail,
  sendUserDataEmailSilently,
  EMAIL_CONFIG
};
