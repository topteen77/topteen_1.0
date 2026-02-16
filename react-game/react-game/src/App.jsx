import { useState, useEffect, lazy, Suspense } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { GAME_STATES } from './utils/constants';
import { isOnline, addNetworkListeners } from './utils/networkUtils';
import { trackUserAction, initializeUserData, clearAllStorage } from './utils/userStorage';
import PhoneLoginPopup from './components/PhoneLoginPopup/PhoneLoginPopup';
import './styles/responsive.css';
import './App.css';

// Lazy load components for code splitting
const CareerClusterSelection = lazy(() => import('./components/CareerClusterSelection/CareerClusterSelection'));
const StreamSelection = lazy(() => import('./components/StreamSelection/StreamSelection'));
const ParameterSelection = lazy(() => import('./components/ParameterSelection/ParameterSelection'));
const FightAnimation = lazy(() => import('./components/FightAnimation/FightAnimation'));
const ResultDisplay = lazy(() => import('./components/ResultDisplay/ResultDisplay'));
const CourseEligibility = lazy(() => import('./components/CourseEligibility/CourseEligibility'));

// Loading fallback component
const LoadingFallback = () => (
  <div className="loading-fallback" role="status" aria-live="polite">
    <div className="loading-spinner-large"></div>
    <p>Loading...</p>
  </div>
);

// Page transition variants
const pageVariants = {
  initial: {
    opacity: 0,
    y: 20,
    scale: 0.98
  },
  animate: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.4,
      ease: [0.22, 1, 0.36, 1]
    }
  },
  exit: {
    opacity: 0,
    y: -20,
    scale: 0.98,
    transition: {
      duration: 0.3,
      ease: [0.22, 1, 0.36, 1]
    }
  }
};

function App() {
  const [gameState, setGameState] = useState(GAME_STATES.SELECT_CAREER_CLUSTER);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [selectedStreams, setSelectedStreams] = useState([]);
  const [selectedParameters, setSelectedParameters] = useState([]);
  const [fightResult, setFightResult] = useState(null);
  const [disqualifiedStreams, setDisqualifiedStreams] = useState([]);
  const [isOnlineStatus, setIsOnlineStatus] = useState(isOnline());
  const [showPhoneLogin, setShowPhoneLogin] = useState(false);

  // Monitor network status
  useEffect(() => {
    const cleanup = addNetworkListeners(
      () => setIsOnlineStatus(true),
      () => setIsOnlineStatus(false)
    );
    return cleanup;
  }, []);

  // Focus management for accessibility
  useEffect(() => {
    // Focus on main content when game state changes
    const mainContent = document.querySelector('[role="main"]') || document.querySelector('.app-container');
    if (mainContent) {
      mainContent.focus();
    }
  }, [gameState]);

  const handleClusterSelect = (cluster) => {
    console.log('Selected cluster:', cluster);
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      trackUserAction(phoneNumber, 'cluster_selected', { cluster });
    }
    setSelectedCluster(cluster);
    setGameState(GAME_STATES.SELECT_STREAMS);
  };

  const handleStreamContinue = (streams) => {
    // Validation: Ensure exactly 2 unique streams
    if (!streams || !Array.isArray(streams) || streams.length !== 2) {
      console.error('Invalid streams selection:', streams);
      alert('Please select exactly 2 different streams to continue.');
      return;
    }

    // Check for duplicates (edge case)
    if (streams[0] === streams[1]) {
      console.error('Duplicate stream selected:', streams);
      alert('Please select two different streams to compare.');
      return;
    }

    console.log('Selected streams:', streams);
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      trackUserAction(phoneNumber, 'streams_selected', { streams, cluster: selectedCluster });
    }
    setSelectedStreams(streams);
    setGameState(GAME_STATES.SELECT_PARAMETERS);
  };

  const handleFight = (data) => {
    // Validation: Ensure valid data
    if (!data || !data.streams || !data.parameters) {
      console.error('Invalid fight data:', data);
      alert('Invalid selection. Please try again.');
      return;
    }

    // Validate streams
    if (!Array.isArray(data.streams) || data.streams.length !== 2) {
      console.error('Invalid streams:', data.streams);
      alert('Please select exactly 2 streams.');
      return;
    }

    // Validate parameters
    if (!Array.isArray(data.parameters) || data.parameters.length === 0) {
      console.error('Invalid parameters:', data.parameters);
      alert('Please select at least one comparison parameter.');
      return;
    }

    console.log('Fight data:', data);
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      trackUserAction(phoneNumber, 'parameters_selected', { 
        streams: data.streams, 
        parameters: data.parameters 
      });
    }
    setSelectedStreams(data.streams);
    setSelectedParameters(data.parameters);
    setGameState(GAME_STATES.FIGHTING);
  };

  const handleFightComplete = (result) => {
    console.log('Fight result:', result);
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    if (phoneNumber) {
      trackUserAction(phoneNumber, 'fight_completed', { 
        result,
        streams: selectedStreams,
        parameters: selectedParameters
      });
    }
    setFightResult(result);
    setGameState(GAME_STATES.RESULT);
  };

  const handleInterested = () => {
    // Check if phone number exists in localStorage
    const phoneNumber = localStorage.getItem('userPhoneNumber');
    
    if (!phoneNumber) {
      // Show phone login popup
      setShowPhoneLogin(true);
    } else {
      // Phone number exists, proceed to course eligibility
      console.log('User is interested in the winner');
      if (fightResult && fightResult.winner) {
        setGameState(GAME_STATES.COURSE_ELIGIBILITY);
      } else {
        resetGame();
      }
    }
  };

  const handlePhoneLoginSuccess = (phoneNumber) => {
    console.log('Phone number saved:', phoneNumber);
    // Initialize user data
    initializeUserData(phoneNumber);
    trackUserAction(phoneNumber, 'phone_login', { phoneNumber });
    // Close popup and proceed to course eligibility
    setShowPhoneLogin(false);
    if (fightResult && fightResult.winner) {
      setGameState(GAME_STATES.COURSE_ELIGIBILITY);
    } else {
      resetGame();
    }
  };

  const handlePhoneLoginClose = () => {
    setShowPhoneLogin(false);
  };

  const handleCourseEligibilityBack = () => {
    // Go back to result screen
    setGameState(GAME_STATES.RESULT);
  };

  const resetGame = () => {
    // Reset all game state to initial values
    setGameState(GAME_STATES.SELECT_CAREER_CLUSTER);
    setSelectedCluster(null);
    setSelectedStreams([]);
    setSelectedParameters([]);
    setFightResult(null);
    setDisqualifiedStreams([]);
  };

  const handleFightAgain = () => {
    // Disqualify the winner and go back to stream selection
    console.log('Fight again - disqualifying winner');
    if (fightResult && fightResult.winner) {
      const newDisqualified = [...disqualifiedStreams, fightResult.winner];
      setDisqualifiedStreams(newDisqualified);
    }
    setGameState(GAME_STATES.SELECT_STREAMS);
    setSelectedStreams([]);
    setSelectedParameters([]);
    setFightResult(null);
  };

  const handleLogout = () => {
    if (window.confirm('Are you sure you want to logout? This will clear all your data.')) {
      clearAllStorage();
      // Reset all game state
      resetGame();
      setShowPhoneLogin(false);
      alert('Logged out successfully. All data has been cleared.');
    }
  };

  return (
    <div className="app-container" role="main" tabIndex={-1} aria-label="Stream Comparison Game">
      {/* Logout Button - Fixed position, visible everywhere */}
      <button
        className="logout-button"
        onClick={handleLogout}
        aria-label="Logout and clear all data"
        title="Logout"
      >
        <span className="logout-icon" aria-hidden="true">🚪</span>
        <span className="logout-text">Logout</span>
      </button>

      {/* Phone Login Popup */}
      {showPhoneLogin && (
        <PhoneLoginPopup
          onClose={handlePhoneLoginClose}
          onSuccess={handlePhoneLoginSuccess}
        />
      )}

      {/* Network Status Indicator */}
      {!isOnlineStatus && (
        <div className="offline-banner" role="alert" aria-live="polite" aria-atomic="true">
          <span className="offline-icon" aria-hidden="true">📡</span>
          <span className="offline-message">You're currently offline. Some features may not work.</span>
        </div>
      )}

      {/* Skip to main content link for accessibility */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <AnimatePresence mode="wait">
        <Suspense fallback={<LoadingFallback />}>
          {gameState === GAME_STATES.SELECT_CAREER_CLUSTER && (
            <motion.div
              key="career-cluster-selection"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              id="main-content"
            >
              <CareerClusterSelection 
                onContinue={handleClusterSelect}
              />
            </motion.div>
          )}

          {gameState === GAME_STATES.SELECT_STREAMS && (
            <motion.div
              key="stream-selection"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              id="main-content"
            >
              <StreamSelection 
                selectedCluster={selectedCluster}
                onContinue={handleStreamContinue}
                disqualifiedStreams={disqualifiedStreams}
                onReset={resetGame}
              />
            </motion.div>
          )}
          
          {gameState === GAME_STATES.SELECT_PARAMETERS && (
            <motion.div
              key="parameter-selection"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              id="main-content"
            >
              <ParameterSelection 
                selectedStreams={selectedStreams}
                onFight={handleFight}
              />
            </motion.div>
          )}

          {gameState === GAME_STATES.FIGHTING && (
            <motion.div
              key="fighting"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              id="main-content"
            >
              <FightAnimation 
                streams={selectedStreams}
                parameters={selectedParameters}
                onComplete={handleFightComplete}
              />
            </motion.div>
          )}

          {gameState === GAME_STATES.RESULT && (
            <motion.div
              key="result"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              id="main-content"
            >
              <ResultDisplay 
                result={fightResult}
                streams={selectedStreams}
                onInterested={handleInterested}
                onFightAgain={handleFightAgain}
              />
            </motion.div>
          )}

          {gameState === GAME_STATES.COURSE_ELIGIBILITY && fightResult && fightResult.winner && (
            <motion.div
              key="course-eligibility"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              id="main-content"
            >
              <CourseEligibility 
                winnerStream={fightResult.winner}
                fightResult={fightResult}
                selectedStreams={selectedStreams}
                selectedParameters={selectedParameters}
                selectedCluster={selectedCluster}
                onBack={handleCourseEligibilityBack}
                onReset={resetGame}
              />
            </motion.div>
          )}
        </Suspense>
      </AnimatePresence>
    </div>
  );
}

export default App;
