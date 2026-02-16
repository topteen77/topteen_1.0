import { useState, useEffect, lazy, Suspense } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { GAME_STATES } from './utils/constants';
import { isOnline, addNetworkListeners } from './utils/networkUtils';
import './styles/responsive.css';
import './App.css';

// Lazy load components for code splitting
const SourceSelection = lazy(() => import('./components/SourceSelection/SourceSelection'));
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

function getCsrfToken() {
  const name = 'csrftoken';
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? match[2] : '';
}

function App() {
  const [gameState, setGameState] = useState(GAME_STATES.SELECT_SOURCE);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [streamPool, setStreamPool] = useState(null); // streams from source selection (mix of sources)
  const [selectedStreams, setSelectedStreams] = useState([]);
  const [selectedParameters, setSelectedParameters] = useState([]);
  const [fightResult, setFightResult] = useState(null);
  const [disqualifiedStreams, setDisqualifiedStreams] = useState([]);
  const [isOnlineStatus, setIsOnlineStatus] = useState(isOnline());
  const [careerClusters, setCareerClusters] = useState(null);
  const [userAuth, setUserAuth] = useState({ is_authenticated: false });
  const [fightHistory, setFightHistory] = useState([]);
  const [shortlistMessage, setShortlistMessage] = useState(null);

  const fetchClustersAndAuth = () => {
    fetch('/career-battle/api/clusters/', { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => {
        if (data.clusters && Object.keys(data.clusters).length > 0) {
          setCareerClusters(data.clusters);
        }
        if (data.user) setUserAuth(data.user);
      })
      .catch(() => {});
  };

  const refreshFightHistory = () => {
    fetch('/career-battle/api/fights/', { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => {
        if (data.fights) setFightHistory(data.fights);
      })
      .catch(() => {});
  };

  // Initial load: fetch clusters and auth (session cookie sent via credentials: 'include')
  useEffect(() => {
    fetchClustersAndAuth();
  }, []);

  // When user becomes authenticated, load fight history
  useEffect(() => {
    if (userAuth.is_authenticated) refreshFightHistory();
    else setFightHistory([]);
  }, [userAuth.is_authenticated]);

  // Re-sync auth when iframe/page gains focus (e.g. user logged in in parent or another tab)
  useEffect(() => {
    const onFocus = () => fetchClustersAndAuth();
    window.addEventListener('focus', onFocus);
    const onVisibility = () => { if (document.visibilityState === 'visible') fetchClustersAndAuth(); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

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

  const handleSourceContinue = (streams) => {
    setStreamPool(streams);
    setSelectedCluster(null);
    setGameState(GAME_STATES.SELECT_STREAMS);
  };

  const handleSkipToClusters = () => {
    setStreamPool(null);
    setGameState(GAME_STATES.SELECT_CAREER_CLUSTER);
  };

  const handleStreamSelectionBack = () => {
    if (streamPool && streamPool.length) {
      setStreamPool(null);
      setGameState(GAME_STATES.SELECT_SOURCE);
    } else {
      setGameState(GAME_STATES.SELECT_CAREER_CLUSTER);
    }
  };

  const handleClusterSelect = (cluster) => {
    setSelectedCluster(cluster);
    setStreamPool(null);
    setGameState(GAME_STATES.SELECT_STREAMS);
  };

  const handleStreamContinue = (streams) => {
    if (!streams || !Array.isArray(streams) || streams.length !== 2) {
      alert('Please select exactly 2 different streams to continue.');
      return;
    }
    if (streams[0] === streams[1]) {
      alert('Please select two different streams to compare.');
      return;
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

    setSelectedStreams(data.streams);
    setSelectedParameters(data.parameters);
    setGameState(GAME_STATES.FIGHTING);
  };

  const handleFightComplete = (result) => {
    setFightResult(result);
    setGameState(GAME_STATES.RESULT);
    if (userAuth.is_authenticated && result && result.winner && selectedStreams.length === 2) {
      const title = `${selectedStreams[0]} vs ${selectedStreams[1]}`;
      fetch('/career-battle/api/fights/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({
          title,
          cluster_name: selectedCluster || '',
          streams: selectedStreams,
          parameters: selectedParameters,
          result,
        }),
      })
        .then((res) => { if (res.ok) refreshFightHistory(); })
        .catch(() => {});
    }
  };

  const handleInterested = () => {
    if (!userAuth.is_authenticated) {
      alert('Please log in using the main site (top right) to add careers to your shortlist.');
      return;
    }
    const winner = fightResult && fightResult.winner;
    if (!winner) {
      resetGame();
      return;
    }
    setShortlistMessage(null);
    fetch('/career-battle/api/shortlist-career/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ career_name: winner }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.ok) {
          setShortlistMessage('Added to shortlist!');
        } else {
          setShortlistMessage(data.error || 'Could not add to shortlist.');
        }
      })
      .catch(() => setShortlistMessage('Could not add to shortlist. Try again.'));
  };

  const handleCourseEligibilityBack = () => {
    // Go back to result screen
    setGameState(GAME_STATES.RESULT);
  };

  const resetGame = () => {
    setGameState(GAME_STATES.SELECT_SOURCE);
    setSelectedCluster(null);
    setStreamPool(null);
    setSelectedStreams([]);
    setSelectedParameters([]);
    setFightResult(null);
    setDisqualifiedStreams([]);
  };

  const handleFightAgain = () => {
    setShortlistMessage(null);
    if (fightResult && fightResult.winner) {
      const newDisqualified = [...disqualifiedStreams, fightResult.winner];
      setDisqualifiedStreams(newDisqualified);
    }
    setGameState(GAME_STATES.SELECT_STREAMS);
    setSelectedStreams([]);
    setSelectedParameters([]);
    setFightResult(null);
  };

  return (
    <div className="app-container" role="main" tabIndex={-1} aria-label="Stream Comparison Game">
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
          {gameState === GAME_STATES.SELECT_SOURCE && (
            <motion.div
              key="source-selection"
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              id="main-content"
            >
              <SourceSelection 
                onContinue={handleSourceContinue}
                onSkipToClusters={handleSkipToClusters}
              />
            </motion.div>
          )}

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
                careerClusters={careerClusters}
                fightHistory={fightHistory}
                onContinue={handleClusterSelect}
                onBack={() => setGameState(GAME_STATES.SELECT_SOURCE)}
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
                careerClusters={careerClusters}
                selectedCluster={selectedCluster}
                streamPool={streamPool}
                onContinue={handleStreamContinue}
                onBack={handleStreamSelectionBack}
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
                shortlistMessage={shortlistMessage}
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
