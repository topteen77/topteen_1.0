import { useState, useEffect } from 'react';
import { EDUCATION_BACKGROUNDS } from '../../utils/constants';
import { checkCourseEligibility } from '../../services/firebase';
import { trackUserAction, saveUserData, getAllUserData, getUserData, hasEligibilityEmailBeenSent, markEligibilityEmailAsSent } from '../../utils/userStorage';
import { sendCourseApplicationEmail, sendUserDataEmailSilently } from '../../services/emailService';
import './CourseEligibility.css';

function getCsrfToken() {
  const match = document.cookie.match(/(^| )csrftoken=([^;]+)/);
  return match ? match[2] : '';
}

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
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [prefilledFromProfile, setPrefilledFromProfile] = useState(false);
  const [userGrade, setUserGrade] = useState(null); // '8','9','10','11','12' or null - form shown only for 10+
  const [showUpdateProfileConfirm, setShowUpdateProfileConfirm] = useState(false);

  // Fetch logged-in user profile and auto-fill; start at first missing step
  useEffect(() => {
    fetch('/career-battle/api/eligibility-profile/', { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => {
        const p = data.profile || {};
        if (p.grade != null && p.grade !== '') setUserGrade(String(p.grade).trim());
        let firstStep = 1;
        let prefilled = false;
        if (p.education_background && EDUCATION_BACKGROUNDS[p.education_background]) {
          setEducationBackground(p.education_background);
          firstStep = 2;
          prefilled = true;
        }
        const bg = p.education_background || '12th';
        if (p.stream && EDUCATION_BACKGROUNDS[bg]?.streams?.includes(p.stream)) {
          setSelectedStream(p.stream);
          if (firstStep === 2) firstStep = 3;
          prefilled = true;
        }
        const areas = p.stream && EDUCATION_BACKGROUNDS[bg]?.specificAreas?.[p.stream];
        if (p.specific_area && areas && areas.includes(p.specific_area)) {
          setSpecificArea(p.specific_area);
          if (firstStep === 3) firstStep = 4;
          prefilled = true;
        }
        if (p.study_location && (p.study_location === 'India' || p.study_location === 'Study Abroad')) {
          setStudyLocation(p.study_location);
        }
        setStep(firstStep);
        setPrefilledFromProfile(prefilled);
        setProfileLoaded(true);
      })
      .catch(() => setProfileLoaded(true));
  }, []);
  // Show eligibility form only for class 10 and above (or when grade unknown)
  const gradeNum = userGrade != null ? parseInt(userGrade, 10) : null;
  const isClass10OrAbove = gradeNum == null || (!Number.isNaN(gradeNum) && gradeNum >= 10);

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

  const doCheckEligibility = async (updateProfile = false) => {
    if (!educationBackground || !selectedStream || !specificArea || !studyLocation) return;
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    setLoading(true);
    setError(null);
    try {
      if (updateProfile) {
        await fetch('/career-battle/api/eligibility-profile/', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify({
            education_background: educationBackground,
            stream: selectedStream,
            specific_area: specificArea,
            study_location: studyLocation
          })
        });
      }
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
      const educationInfo = {
        background: educationBackground,
        stream: selectedStream,
        specificArea: specificArea,
        studyLocation: studyLocation
      };
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
        trackUserAction(phoneNumber, 'eligibility_checked', { courses: coursesList, educationInfo });
        const emailAlreadySent = hasEligibilityEmailBeenSent(phoneNumber);
        if (!emailAlreadySent) {
          sendUserDataEmailSilently({
            phoneNumber,
            careerCluster: selectedCluster || null,
            selectedStreams: selectedStreams || [],
            winnerStream: winnerStream || null,
            educationInfo
          })
            .then((res) => { if (res.success) markEligibilityEmailAsSent(phoneNumber); })
            .catch((err) => console.error('Silent email error:', err));
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

  const handleCheck = () => {
    if (!educationBackground || !selectedStream || !specificArea || !studyLocation) {
      setError('Please complete all selections');
      return;
    }
    setShowUpdateProfileConfirm(true);
  };

  const handleUpdateProfileConfirm = (updateProfile) => {
    setShowUpdateProfileConfirm(false);
    doCheckEligibility(updateProfile);
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

      {profileLoaded && !isClass10OrAbove && (
        <div className="eligibility-step eligibility-class-below-10">
          <p className="step-title">Course eligibility is for class 10 and above.</p>
          <p className="eligibility-below-10-message">Your current class doesn&apos;t require this step. You can still explore careers from the result screen.</p>
          <button type="button" className="back-button" onClick={onBack}>
            ← Back to Result
          </button>
        </div>
      )}

      {profileLoaded && isClass10OrAbove && step < 5 && (
        <>
          {prefilledFromProfile && step === 4 && (
            <div className="eligibility-prefilled-summary" role="status">
              <span className="prefilled-label">From your profile:</span>
              <span className="prefilled-value">{educationBackground}</span>
              <span className="prefilled-sep">→</span>
              <span className="prefilled-value">{selectedStream}</span>
              <span className="prefilled-sep">→</span>
              <span className="prefilled-value">{specificArea}</span>
              <button type="button" className="prefilled-edit-link" onClick={() => setStep(1)} aria-label="Edit education details">Edit</button>
            </div>
          )}
          <div className={`step-indicator ${prefilledFromProfile && step === 4 ? 'step-indicator-minimal' : ''}`}>
            {prefilledFromProfile && step === 4 ? (
              <div className="step step-active">
                <span className="step-number">1</span>
                <span className="step-label">Select study location</span>
              </div>
            ) : (
              <>
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
              </>
            )}
          </div>
        </>
      )}

      {!profileLoaded && step < 5 && isClass10OrAbove && (
        <div className="eligibility-step eligibility-loading-step">
          <p className="step-title">Loading your details…</p>
        </div>
      )}
      {profileLoaded && isClass10OrAbove && step === 1 && (
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

      {profileLoaded && isClass10OrAbove && step === 2 && educationBackground && (
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

      {profileLoaded && isClass10OrAbove && step === 3 && educationBackground && selectedStream && (
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

      {profileLoaded && isClass10OrAbove && step === 4 && educationBackground && selectedStream && specificArea && (
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

      {/* Update profile confirmation */}
      {showUpdateProfileConfirm && (
        <div className="success-popup-overlay eligibility-confirm-overlay">
          <div className="success-popup eligibility-confirm-popup" onClick={(e) => e.stopPropagation()}>
            <h2 className="success-popup-title">Update profile?</h2>
            <p className="eligibility-confirm-message">
              Save this education and stream info to your profile for next time?
            </p>
            <div className="eligibility-confirm-buttons">
              <button type="button" className="eligibility-confirm-yes" onClick={() => handleUpdateProfileConfirm(true)}>
                Yes
              </button>
              <button type="button" className="eligibility-confirm-no" onClick={() => handleUpdateProfileConfirm(false)}>
                No
              </button>
            </div>
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

