import { useState, useEffect } from 'react';
import { compareStreamsWithLLM } from '../../services/llmService';
import './FightAnimation.css';

const FightAnimation = ({ streams, parameters, onComplete }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
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
      <div className="fight-header">
        <h1 id="fight-title" className="fight-title">
          <span aria-hidden="true">⚔️</span> Battle in Progress! <span aria-hidden="true">⚔️</span>
        </h1>
        <p className="fight-subtitle" id="fight-status">
          {loading ? 'Analyzing your streams...' : error ? 'Error occurred' : 'Analysis complete'}
        </p>
      </div>

      {/* Fight Arena */}
      <div className="fight-arena" role="group" aria-label="Fighting streams">
        <div className="fighter fighter-left" role="group" aria-label={`Fighter: ${streams[0]}`}>
          <div className="fighter-name">{streams[0]}</div>
          <div className="fighter-avatar">
            <div className="fighter-body"></div>
            <div className="fighter-punch punch-left"></div>
          </div>
        </div>

        <div className="vs-badge" aria-label="versus" aria-hidden="true">VS</div>

        <div className="fighter fighter-right" role="group" aria-label={`Fighter: ${streams[1]}`}>
          <div className="fighter-name">{streams[1]}</div>
          <div className="fighter-avatar">
            <div className="fighter-body"></div>
            <div className="fighter-punch punch-right"></div>
          </div>
        </div>
      </div>

      {/* Progress Indicator */}
      <div className="progress-container" role="progressbar" aria-valuenow={progress} aria-valuemin="0" aria-valuemax="100" aria-label="Comparison progress">
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${progress}%` }}
            aria-hidden="true"
          ></div>
        </div>
        <div className="progress-text" aria-live="polite" aria-atomic="true">
          {loading ? (
            <span>Processing comparison... {Math.round(progress)}%</span>
          ) : error ? (
            <span className="error-text">
              Error: {error.reasoning || error.error || 'Unknown error'}
              {error.errorCode && ` (${error.errorCode})`}
            </span>
          ) : (
            <span className="success-text">✓ Analysis Complete!</span>
          )}
        </div>
      </div>

      {/* Loading Spinner */}
      {loading && (
        <div className="loading-spinner">
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
