import { useState } from 'react';
import { EDUCATION_BACKGROUNDS } from '../../utils/constants';
import { checkCourseEligibility } from '../../services/firebase';
import { trackUserAction, saveUserData, getAllUserData, getUserData, hasEligibilityEmailBeenSent, markEligibilityEmailAsSent } from '../../utils/userStorage';
import { sendCourseApplicationEmail, sendUserDataEmailSilently } from '../../services/emailService';
import './CourseEligibility.css';

const CourseEligibility = ({ winnerStream, fightResult, selectedStreams, selectedParameters, selectedCluster, onBack, onReset }) => {
  const [step, setStep] = useState(1); // 1: education background, 2: stream, 3: specific area, 4: study location, 5: results
  const [educationBackground, setEducationBackground] = useState(null);
  const [selectedStream, setSelectedStream] = useState(null);
  const [specificArea, setSpecificArea] = useState(null);
  const [studyLocation, setStudyLocation] = useState(null); // 'India' or 'Study Abroad'
  const [courses, setCourses] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showSuccessPopup, setShowSuccessPopup] = useState(false);
  const [applyingCourse, setApplyingCourse] = useState(null);

  const handleEducationBackgroundSelect = (background) => {
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      trackUserAction(phoneNumber, 'education_background_selected', { background });
    }
    setEducationBackground(background);
    setStep(2);
  };

  const handleStreamSelect = (stream) => {
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      trackUserAction(phoneNumber, 'education_stream_selected', { stream, background: educationBackground });
    }
    setSelectedStream(stream);
    setStep(3);
  };

  const handleSpecificAreaSelect = (area) => {
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      trackUserAction(phoneNumber, 'specific_area_selected', { area, stream: selectedStream, background: educationBackground });
    }
    setSpecificArea(area);
  };

  const handleStudyLocationSelect = (location) => {
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      trackUserAction(phoneNumber, 'study_location_selected', { location });
    }
    setStudyLocation(location);
  };

  const handleCheck = async () => {
    if (!educationBackground || !selectedStream || !specificArea || !studyLocation) {
      setError('Please complete all selections');
      return;
    }

    // Get phone number from localStorage
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      console.log('User phone number:', phoneNumber);
    } else {
      console.log('No phone number found in storage');
    }

    setLoading(true);
    setError(null);

    try {
      const educationInfo = {
        background: educationBackground,
        stream: selectedStream,
        specificArea: specificArea,
        studyLocation: studyLocation
      };

      const result = await checkCourseEligibility({
        educationBackground: {
          background: educationBackground,
          stream: selectedStream,
          specificArea: specificArea
        },
        winnerStream: winnerStream
      });

      const coursesList = result.courses || [];
      setCourses(coursesList);

      // Store complete user data
      if (phoneNumber) {
        const userData = {
          educationInfo,
          courses: coursesList,
          winnerStream,
          fightResult,
          selectedStreams,
          selectedParameters,
          selectedCluster
        };
        saveUserData(phoneNumber, userData);
        trackUserAction(phoneNumber, 'eligibility_checked', { 
          courses: coursesList,
          educationInfo 
        });

        // Send email silently (backend only, no UI feedback)
        // Check if email has already been sent to avoid duplicates
        const emailAlreadySent = hasEligibilityEmailBeenSent(phoneNumber);
        
        if (!emailAlreadySent) {
          const emailData = {
            phoneNumber: phoneNumber,
            careerCluster: selectedCluster || null,
            selectedStreams: selectedStreams || [],
            winnerStream: winnerStream || null,
            educationInfo: educationInfo
          };
          // Fire and forget - don't await or show any feedback
          sendUserDataEmailSilently(emailData)
            .then(result => {
              // Mark email as sent only if successful
              if (result.success) {
                markEligibilityEmailAsSent(phoneNumber);
                console.log('Eligibility email sent and marked as sent');
              }
            })
            .catch(err => {
              // Silently handle errors - no user feedback
              console.error('Silent email error:', err);
            });
        } else {
          console.log('Eligibility email already sent, skipping duplicate');
        }
      }

      setStep(5);
    } catch (err) {
      console.error('Error checking course eligibility:', err);
      setError(err.message || 'Failed to check course eligibility. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const canCheck = educationBackground && selectedStream && specificArea && studyLocation;

  const handleApplyCourse = async (course) => {
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (!phoneNumber) {
      alert('No user data found. Please login first.');
      return;
    }

    setApplyingCourse(course);

    try {
      const allUserData = getAllUserData(phoneNumber);
      const applicationData = {
        phoneNumber: phoneNumber,
        careerCluster: selectedCluster || null,
        selectedStreams: selectedStreams || [],
        winnerStream: winnerStream || null,
        educationInfo: allUserData.educationInfo || null,
        course: course
      };

      // Send email
      const emailResult = await sendCourseApplicationEmail(applicationData);
      
      if (emailResult.success) {
        setShowSuccessPopup(true);
        // Track the application
        trackUserAction(phoneNumber, 'course_application', { course });
      } else {
        alert(`Failed to send application: ${emailResult.message}`);
        setApplyingCourse(null);
      }
    } catch (error) {
      console.error('Error sending course application:', error);
      alert(`Error sending application: ${error.message}`);
      setApplyingCourse(null);
    }
  };

  const handleSuccessPopupOk = () => {
    setShowSuccessPopup(false);
    setApplyingCourse(null);
    if (onReset) {
      onReset();
    } else if (onBack) {
      onBack();
    }
    // Reload the page to reset to home
    window.location.reload();
  };

  return (
    <div className="course-eligibility-container" role="region" aria-labelledby="course-eligibility-title">
      <div className="course-eligibility-header">
        <h1 id="course-eligibility-title" className="course-eligibility-title">
          Course Eligibility Check
        </h1>
        <p className="course-eligibility-subtitle">
          Based on your education background and the winner stream: <strong>{winnerStream}</strong>
        </p>
      </div>

      {step < 5 && (
        <div className="step-indicator">
          <div className={`step ${step >= 1 ? 'step-active' : ''}`}>
            <span className="step-number">1</span>
            <span className="step-label">Education</span>
          </div>
          <div className={`step-connector ${step >= 2 ? 'connector-active' : ''}`}></div>
          <div className={`step ${step >= 2 ? 'step-active' : ''}`}>
            <span className="step-number">2</span>
            <span className="step-label">Stream</span>
          </div>
          <div className={`step-connector ${step >= 3 ? 'connector-active' : ''}`}></div>
          <div className={`step ${step >= 3 ? 'step-active' : ''}`}>
            <span className="step-number">3</span>
            <span className="step-label">Area</span>
          </div>
          <div className={`step-connector ${step >= 4 ? 'connector-active' : ''}`}></div>
          <div className={`step ${step >= 4 ? 'step-active' : ''}`}>
            <span className="step-number">4</span>
            <span className="step-label">Location</span>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="eligibility-step">
          <h2 className="step-title">Select Your Education Background</h2>
          <div className="options-grid">
            {Object.keys(EDUCATION_BACKGROUNDS).map((background) => (
              <button
                key={background}
                className={`option-card ${educationBackground === background ? 'option-card-selected' : ''}`}
                onClick={() => handleEducationBackgroundSelect(background)}
                aria-pressed={educationBackground === background}
              >
                <span className="option-name">{background}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {step === 2 && educationBackground && (
        <div className="eligibility-step">
          <h2 className="step-title">Select Your Stream</h2>
          <div className="options-grid">
            {EDUCATION_BACKGROUNDS[educationBackground].streams.map((stream) => (
              <button
                key={stream}
                className={`option-card ${selectedStream === stream ? 'option-card-selected' : ''}`}
                onClick={() => handleStreamSelect(stream)}
                aria-pressed={selectedStream === stream}
              >
                <span className="option-name">{stream}</span>
              </button>
            ))}
          </div>
          <button className="back-button" onClick={() => setStep(1)}>
            ← Back
          </button>
        </div>
      )}

      {step === 3 && educationBackground && selectedStream && (
        <div className="eligibility-step">
          <h2 className="step-title">Select Specific Area</h2>
          <div className="options-grid">
            {EDUCATION_BACKGROUNDS[educationBackground].specificAreas[selectedStream].map((area) => (
              <button
                key={area}
                className={`option-card ${specificArea === area ? 'option-card-selected' : ''}`}
                onClick={() => handleSpecificAreaSelect(area)}
                aria-pressed={specificArea === area}
              >
                <span className="option-name">{area}</span>
              </button>
            ))}
          </div>
          <div className="step-actions">
            <button className="back-button" onClick={() => setStep(2)}>
              ← Back
            </button>
            {specificArea && (
              <button className="continue-button" onClick={() => setStep(4)}>
                Continue →
              </button>
            )}
          </div>
        </div>
      )}

      {step === 4 && educationBackground && selectedStream && specificArea && (
        <div className="eligibility-step">
          <h2 className="step-title">Select Study Location</h2>
          <div className="options-grid">
            <button
              className={`option-card ${studyLocation === 'India' ? 'option-card-selected' : ''}`}
              onClick={() => handleStudyLocationSelect('India')}
              aria-pressed={studyLocation === 'India'}
            >
              <span className="option-name">🇮🇳 India</span>
            </button>
            <button
              className={`option-card ${studyLocation === 'Study Abroad' ? 'option-card-selected' : ''}`}
              onClick={() => handleStudyLocationSelect('Study Abroad')}
              aria-pressed={studyLocation === 'Study Abroad'}
            >
              <span className="option-name">🌍 Study Abroad</span>
            </button>
          </div>
          <div className="step-actions">
            <button className="back-button" onClick={() => setStep(3)}>
              ← Back
            </button>
            <button
              className={`check-button ${canCheck ? 'check-button-active' : 'check-button-disabled'}`}
              onClick={handleCheck}
              disabled={!canCheck || loading}
            >
              {loading ? 'Checking...' : 'Check Eligibility'}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      {step === 5 && courses && (
        <div className="courses-results">
          <h2 className="results-title">Eligible Courses</h2>
          <div className="courses-list">
            {courses.length > 0 ? (
              <ul className="courses-ul">
                {courses.map((course, index) => (
                  <li key={index} className="course-item">
                    <span className="course-icon">📚</span>
                    <span className="course-name">{course}</span>
                    <button
                      className="apply-button"
                      onClick={() => handleApplyCourse(course)}
                      disabled={applyingCourse === course}
                    >
                      {applyingCourse === course ? 'Sending...' : 'Apply'}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="no-courses">No eligible courses found.</p>
            )}
          </div>
          <div className="results-actions">
            <button className="back-button" onClick={onBack}>
              ← Back to Game
            </button>
          </div>
        </div>
      )}

      {/* Success Popup */}
      {showSuccessPopup && (
        <div className="success-popup-overlay" onClick={handleSuccessPopupOk}>
          <div className="success-popup" onClick={(e) => e.stopPropagation()}>
            <div className="success-popup-icon">✅</div>
            <h2 className="success-popup-title">Thank You!</h2>
            <p className="success-popup-message">
              Our counsellor will contact you soon regarding your application for:
            </p>
            <p className="success-popup-course">{applyingCourse}</p>
            <button className="success-popup-button" onClick={handleSuccessPopupOk}>
              OK
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default CourseEligibility;

