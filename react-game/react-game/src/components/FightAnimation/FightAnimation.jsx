import { useState, useEffect } from 'react';
import { compareStreamsWithLLM } from '../../services/llmService';
import battleVideo from '../../assets/battel-video.mp4';
import fighter1Video from '../../assets/fighter1-video.mp4';
import fighter2Video from '../../assets/fighter2-video.mp4';

import './FightAnimation.css';

const BATTLE_PHRASES = [
  'Analyzing streams...',
  'Comparing skills...',
  'Checking match-up...',
  'Choosing a winner...',
  'Almost there...',
];

const FightAnimation = ({ streams, parameters, onComplete }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const [battlePhrase, setBattlePhrase] = useState(BATTLE_PHRASES[0]);
  const MAX_RETRIES = 2;

  const performComparison = () => {
    setLoading(true);
    setError(null);
    setProgress(0);
    
    // Simulate progress for better UX
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) return prev; // Stop at 90% until real response
        return prev + Math.random() * 10;
      });
    }, 500);

    // Call LLM service
    compareStreamsWithLLM(streams, parameters)
      .then((response) => {
        clearInterval(progressInterval);
        setProgress(100);
        
        if (response.success) {
          setResult(response);
          setLoading(false);
          
          // Call onComplete after a short delay to show result
          setTimeout(() => {
            if (onComplete) {
              onComplete(response);
            }
          }, 1500);
        } else {
          setError(response);
          setLoading(false);
        }
      })
      .catch((err) => {
        clearInterval(progressInterval);
        setError({
          error: err.message || 'An unexpected error occurred',
          isNetworkError: false,
          isTimeoutError: false
        });
        setLoading(false);
      });

    return () => clearInterval(progressInterval);
  };

  useEffect(() => {
    performComparison();
  }, [streams, parameters, onComplete]);

  useEffect(() => {
    if (!loading) return;
    const idx = Math.floor(progress / 25) % BATTLE_PHRASES.length;
    setBattlePhrase(BATTLE_PHRASES[idx]);
  }, [loading, progress]);

  const handleRetry = () => {
    if (retryCount < MAX_RETRIES) {
      setIsRetrying(true);
      setRetryCount(prev => prev + 1);
      setTimeout(() => {
        performComparison();
        setIsRetrying(false);
      }, 500);
    } else {
      // Max retries reached, reload page
      window.location.reload();
    }
  };

  return (
    <div className="fight-animation-container" role="region" aria-labelledby="fight-title" aria-live="polite">
      {/* Cinematic battle video background */}
      <div className="fight-video-layer" aria-hidden="true">
        <video
          className="fight-background-video"
          src={battleVideo}
          autoPlay
          muted
          loop
          playsInline
        />
        <div className="fight-video-overlay" />
      </div>

      <div className="fight-arena-ring" aria-hidden="true"></div>

      <div className="fight-header">
        <h1 id="fight-title" className="fight-title">
          <span className="fight-title-icon" aria-hidden="true">⚔</span>
          {loading ? 'BATTLE!' : error ? 'Error' : 'Done!'}
          <span className="fight-title-icon" aria-hidden="true">⚔</span>
        </h1>
        <p className="fight-subtitle" id="fight-status">
          {loading ? battlePhrase : error ? 'Something went wrong' : 'Winner incoming!'}
        </p>
      </div>

      {/* Fight Arena */}
      <div className="fight-arena" role="group" aria-label="Fighting streams">
        <div className="fighter fighter-left" role="group" aria-label={`Fighter: ${streams[0]}`}>
          <div className="fighter-card">
            <div className="fighter-name">{streams[0]}</div>
            <div className="fighter-avatar">
              <div className="fighter-video-wrapper fighter-video-left">
                <video
                  className="fighter-video"
                  src={fighter1Video}
                  autoPlay
                  muted
                  loop
                  playsInline
                />
              </div>
              <div className="fighter-punch punch-left"></div>
            </div>
          </div>
        </div>

        <div className="vs-badge" aria-label="versus">
          <span className="vs-text">VS</span>
        </div>

        <div className="fighter fighter-right" role="group" aria-label={`Fighter: ${streams[1]}`}>
          <div className="fighter-card">
            <div className="fighter-name">{streams[1]}</div>
            <div className="fighter-avatar">
              <div className="fighter-video-wrapper fighter-video-right">
                <video
                  className="fighter-video"
                  src={fighter2Video}
                  autoPlay
                  muted
                  loop
                  playsInline
                />
              </div>
              <div className="fighter-punch punch-right"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Progress - Power bar style */}
      <div className="progress-container" role="progressbar" aria-valuenow={progress} aria-valuemin="0" aria-valuemax="100" aria-label="Battle progress">
        <div className="progress-label">{loading ? 'Powering up...' : 'Complete!'}</div>
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${progress}%` }}
            aria-hidden="true"
          ></div>
        </div>
        <div className="progress-text" aria-live="polite" aria-atomic="true">
          {loading ? (
            <span>{Math.round(progress)}%</span>
          ) : error ? (
            <span className="error-text">
              {error.reasoning || error.error || 'Unknown error'}
              {error.errorCode && ` (${error.errorCode})`}
            </span>
          ) : (
            <span className="success-text">✓ Ready!</span>
          )}
        </div>
      </div>

      {loading && (
        <div className="loading-spinner" aria-hidden="true">
          <div className="spinner"></div>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="error-container">
          <div className="error-icon">
            {error.isNetworkError ? '📡' : error.isTimeoutError ? '⏱️' : '⚠️'}
          </div>
          <h3 className="error-title">
            {error.isNetworkError ? 'Network Error' : 
             error.isTimeoutError ? 'Request Timeout' : 
             'Error Occurred'}
          </h3>
          <p className="error-message">
            {error.reasoning || error.error || 'An unexpected error occurred'}
            {error.errorCode && (
              <span style={{ display: 'block', fontSize: '0.9em', marginTop: '0.5rem', opacity: 0.8 }}>
                Error Code: {error.errorCode}
              </span>
            )}
          </p>
          <div className="error-actions">
            {retryCount < MAX_RETRIES ? (
              <button 
                className="retry-button"
                onClick={handleRetry}
                disabled={isRetrying}
              >
                {isRetrying ? 'Retrying...' : `Retry (${MAX_RETRIES - retryCount} left)`}
              </button>
            ) : (
              <button 
                className="retry-button"
                onClick={() => window.location.reload()}
              >
                Reload Page
              </button>
            )}
            <button 
              className="back-button"
              onClick={() => window.history.back()}
            >
              Go Back
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default FightAnimation;
