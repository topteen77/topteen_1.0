import { useEffect, useState } from 'react';
import { PARAMETERS } from '../../utils/constants';
import fighter1Video from '../../assets/fighter1-video.mp4';
import fighter2Video from '../../assets/fighter2-video.mp4';
import trophyGif from '../../assets/trophy-gif.gif';
import swordImage from '../../assets/sword-image.png';
import performanceIcon from '../../assets/images/performance-icon.webp';
import strengthIcon from '../../assets/images/strength-icon.png';
import weaknessIcon from '../../assets/images/weakness-icon.webp';
import greenTick from '../../assets/green-tick.png';
import redTick from '../../assets/red-tick.png';
import aiDetailIcon from '../../assets/images/ai-detail-performance.webp';
import './ResultDisplay.css';


const ResultDisplay = ({ result, streams, onInterested, onFightAgain, shortlistMessage }) => {
  const [showCelebration, setShowCelebration] = useState(true);
  const [isAnalysisExpanded, setIsAnalysisExpanded] = useState(false);
  const [stream1StrengthsExpanded, setStream1StrengthsExpanded] = useState(false);
  const [stream1WeaknessesExpanded, setStream1WeaknessesExpanded] = useState(false);
  const [stream2StrengthsExpanded, setStream2StrengthsExpanded] = useState(false);
  const [stream2WeaknessesExpanded, setStream2WeaknessesExpanded] = useState(false);

  useEffect(() => {
    // Trigger celebration animation on mount
    setShowCelebration(true);
    const timer = setTimeout(() => setShowCelebration(false), 3000);
    return () => clearTimeout(timer);
  }, []);

  if (!result || !result.winner) {
    return (
      <div className="result-display-container">
        <div className="error-state">
          <p>No result available. Please try again.</p>
        </div>
      </div>
    );
  }

  const winner = result.winner;
  const loser = streams.find(s => s !== winner) || streams[0];
  const winnerVideo = winner === streams[0] ? fighter1Video : fighter2Video;
  const details = result.details || {};
  const stream1Details = details.stream1 || {};
  const stream2Details = details.stream2 || {};

  // Check if reasoning contains error messages - hide it if so
  const reasoning = result.reasoning || '';
  const isErrorReasoning = reasoning.toLowerCase().includes('error') || 
                           reasoning.toLowerCase().includes('invalid') ||
                           reasoning.toLowerCase().includes('failed') ||
                           reasoning.toLowerCase().includes('try again');

  // Get parameter labels
  const getParameterLabel = (paramId) => {
    const param = PARAMETERS.find(p => p.id === paramId);
    return param ? param.label : paramId.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  // Format score value for better display
  const formatScore = (score) => {
    if (!score) return 'N/A';
    // If score contains "Very High", "High", etc., return as is
    if (typeof score === 'string' && (score.includes('High') || score.includes('Low') || score.includes('Medium') || score.includes('Flexible'))) {
      return score;
    }
    return score;
  };

  // Get score badge color based on value
  const getScoreBadgeClass = (score) => {
    if (!score) return 'score-badge-neutral';
    const scoreStr = String(score).toLowerCase();
    if (scoreStr.includes('very high') || scoreStr.includes('high') || scoreStr.includes('9') || scoreStr.includes('10') || scoreStr.includes('8')) {
      return 'score-badge-high';
    } else if (scoreStr.includes('medium') || scoreStr.includes('5') || scoreStr.includes('6') || scoreStr.includes('7')) {
      return 'score-badge-medium';
    } else if (scoreStr.includes('low') || scoreStr.includes('1') || scoreStr.includes('2') || scoreStr.includes('3') || scoreStr.includes('4')) {
      return 'score-badge-low';
    }
    return 'score-badge-neutral';
  };

  return (
    <div className="result-display-container" role="region" aria-labelledby="result-title">
      {/* Celebration Animation */}
      {showCelebration && (
        <div className="celebration-overlay" role="alert" aria-live="assertive" aria-atomic="true">
          {/* Confetti splash - bursts from center */}
          <div className="celebration-confetti" aria-hidden="true">
            {[...Array(48)].map((_, i) => (
              <div
                key={i}
                className="confetti-piece"
                style={{
                  '--angle': `${(i * 7.5) % 360}deg`,
                  '--delay': `${(i % 12) * 0.03}s`,
                  '--color': ['#ffd700', '#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dfe6e9', '#fd79a8'][i % 8],
                }}
              />
            ))}
          </div>
          <div className="celebration-content">
            <div className="celebration-trophy-wrap">
              <img src={trophyGif} alt="" className="celebration-trophy" aria-hidden="true" />
            </div>
            <div className="celebration-text">Winner!</div>
          </div>
        </div>
      )}

      {/* Winner Section */}
      <div className="winner-section">
        <div className="winner-badge">
        

          <div className="winner-context">  

            <div className="winner-name-container"> 

            <img src={trophyGif} alt="" className="winner-crown" aria-hidden="true" />
            <h1 id="result-title" className="winner-title">Winner</h1>

          <div className="winner-name" aria-label={`Winner: ${winner}`}>{winner}</div>


          </div> 


          <div className="winner-fighter-card" aria-hidden="true">
            <div className="winner-video-wrapper">
              <video
                className={`winner-character-video ${winner === streams[1] ? 'winner-video-flip' : ''}`}
                src={winnerVideo}
                autoPlay
                muted
                loop
                playsInline
              />
            </div>
          </div>
          </div>
          



          <div className="winner-subtitle">vs {loser}</div>
      
        </div>
      </div>

      {/* Comparison Details - Now appears first */}
      {details && (stream1Details.scores || stream2Details.scores) && (
        <div className="details-section">
          <h2 className="section-title">
            <span className="section-icon">  <img src={swordImage} alt="" className="fight-title-icon" aria-hidden="true" /></span>
            Detailed Comparison
          </h2>
          
          <div className="comparison-cards">
            {/* Stream 1 Card */}
            <div className={`comparison-card ${winner === stream1Details.name ? 'winner-card card-left' : 'card-left'}`}>
              {winner === stream1Details.name && (
                <img src={trophyGif} alt="" className="winner-card-trophy" aria-hidden="true" />
              )}
              <div className="card-header">
                <h3 className="card-title">{stream1Details.name}</h3>
                {winner === stream1Details.name && (
                  <span className="winner-tag">Winner</span>
                )}
              </div>
              
              {/* Performance Scores - Now at the top */}
              {stream1Details.scores && Object.keys(stream1Details.scores).length > 0 && (
                <div className="card-section">
                  <h4 className="section-label">
                    <img src={performanceIcon} alt="" className="label-icon label-icon-img" aria-hidden="true" />
                    Performance Scores
                  </h4>
                  <div className="scores-grid">
                    {Object.entries(stream1Details.scores).map(([paramId, score]) => (
                      <div key={paramId} className="score-item">
                        <span className="score-label">{getParameterLabel(paramId)}</span>
                        <span className={`score-value score-badge ${getScoreBadgeClass(score)}`}>
                          {formatScore(score)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {stream1Details.strengths && stream1Details.strengths.length > 0 && (
                <div className="card-section">
                  <h4 
                    className="section-label clickable-label"
                    onClick={() => setStream1StrengthsExpanded(!stream1StrengthsExpanded)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setStream1StrengthsExpanded(!stream1StrengthsExpanded);
                      }
                    }}
                  >
                    <img src={strengthIcon} alt="" className="label-icon label-icon-img" aria-hidden="true" />
                    Strengths
                    <span className="expand-icon">{stream1StrengthsExpanded ? '−' : '+'}</span>
                  </h4>
                  {stream1StrengthsExpanded && (
                    <ul className="strengths-list expanded">
                      {stream1Details.strengths.map((strength, index) => (
                        <li key={index}>
                          <img src={greenTick} alt="" className="list-icon list-icon-img" aria-hidden="true" />
                          <span className="list-text">{strength}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {stream1Details.weaknesses && stream1Details.weaknesses.length > 0 && (
                <div className="card-section">
                  <h4 
                    className="section-label clickable-label"
                    onClick={() => setStream1WeaknessesExpanded(!stream1WeaknessesExpanded)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setStream1WeaknessesExpanded(!stream1WeaknessesExpanded);
                      }
                    }}
                  >
                    <img src={weaknessIcon} alt="" className="label-icon label-icon-img" aria-hidden="true" />
                    Weaknesses
                    <span className="expand-icon">{stream1WeaknessesExpanded ? '−' : '+'}</span>
                  </h4>
                  {stream1WeaknessesExpanded && (
                    <ul className="weaknesses-list expanded">
                      {stream1Details.weaknesses.map((weakness, index) => (
                        <li key={index}>
                          <img src={redTick} alt="" className="list-icon list-icon-img" aria-hidden="true" />
                          <span className="list-text">{weakness}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            {/* Stream 2 Card */}
            <div className={`comparison-card ${winner === stream2Details.name ? 'winner-card card-right' : 'card-right'}`}>
              {winner === stream2Details.name && (
                <img src={trophyGif} alt="" className="winner-card-trophy" aria-hidden="true" />
              )}
              <div className="card-header">
                <h3 className="card-title">{stream2Details.name}</h3>
                {winner === stream2Details.name && (
                  <span className="winner-tag">Winner</span>
                )}
              </div>
              
              {/* Performance Scores - Now at the top */}
              {stream2Details.scores && Object.keys(stream2Details.scores).length > 0 && (
                <div className="card-section">
                  <h4 className="section-label">
                    <img src={performanceIcon} alt="" className="label-icon label-icon-img" aria-hidden="true" />
                    Performance Scores
                  </h4>
                  <div className="scores-grid">
                    {Object.entries(stream2Details.scores).map(([paramId, score]) => (
                      <div key={paramId} className="score-item">
                        <span className="score-label">{getParameterLabel(paramId)}</span>
                        <span className={`score-value score-badge ${getScoreBadgeClass(score)}`}>
                          {formatScore(score)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {stream2Details.strengths && stream2Details.strengths.length > 0 && (
                <div className="card-section">
                  <h4 
                    className="section-label clickable-label"
                    onClick={() => setStream2StrengthsExpanded(!stream2StrengthsExpanded)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setStream2StrengthsExpanded(!stream2StrengthsExpanded);
                      }
                    }}
                  >
                    <img src={strengthIcon} alt="" className="label-icon label-icon-img" aria-hidden="true" />
                    Strengths
                    <span className="expand-icon">{stream2StrengthsExpanded ? '−' : '+'}</span>
                  </h4>
                  {stream2StrengthsExpanded && (
                    <ul className="strengths-list expanded">
                      {stream2Details.strengths.map((strength, index) => (
                        <li key={index}>
                          <img src={greenTick} alt="" className="list-icon list-icon-img" aria-hidden="true" />
                          <span className="list-text">{strength}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {stream2Details.weaknesses && stream2Details.weaknesses.length > 0 && (
                <div className="card-section">
                  <h4 
                    className="section-label clickable-label"
                    onClick={() => setStream2WeaknessesExpanded(!stream2WeaknessesExpanded)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setStream2WeaknessesExpanded(!stream2WeaknessesExpanded);
                      }
                    }}
                  >
                    <img src={weaknessIcon} alt="" className="label-icon label-icon-img" aria-hidden="true" />
                    Weaknesses
                    <span className="expand-icon">{stream2WeaknessesExpanded ? '−' : '+'}</span>
                  </h4>
                  {stream2WeaknessesExpanded && (
                    <ul className="weaknesses-list expanded">
                      {stream2Details.weaknesses.map((weakness, index) => (
                        <li key={index}>
                          <img src={redTick} alt="" className="list-icon list-icon-img" aria-hidden="true" />
                          <span className="list-text">{weakness}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Reasoning Section - Now appears at the bottom with expandable functionality */}
      {reasoning && !isErrorReasoning && (
        <div className="reasoning-section">
          <h2 className="section-title">
            <img src={aiDetailIcon} alt="" className="section-icon section-icon-img" aria-hidden="true" />
            Detailed Analysis
          </h2>
          <div className={`reasoning-content ${isAnalysisExpanded ? 'expanded' : 'collapsed'}`}>
            <p>{reasoning}</p>
          </div>
          {reasoning.length > 200 && (
            <button 
              className="view-more-button"
              onClick={() => setIsAnalysisExpanded(!isAnalysisExpanded)}
              aria-expanded={isAnalysisExpanded}
            >
              {isAnalysisExpanded ? 'View Less' : 'View More'}
            </button>
          )}
        </div>
      )}

      {/* Shortlist feedback */}
      {shortlistMessage && (
        <div className={`shortlist-message ${shortlistMessage.includes('Added') ? 'shortlist-message-success' : 'shortlist-message-info'}`} role="status">
          {shortlistMessage}
        </div>
      )}

      {/* Action Buttons */}
      <div className="action-buttons-section" role="group" aria-label="Result actions">
        <button
          className="action-button interested-button"
          onClick={onInterested}
          aria-label="Add winner to shortlist"
        >
          <img src={greenTick} alt="" className="button-icon button-icon-img" aria-hidden="true" />
          Interested
        </button>
        <button
          className="action-button fight-again-button"
          onClick={onFightAgain}
          aria-label="Fight again with other streams"
        >
          <img src={swordImage} alt="" className="button-icon button-icon-img" aria-hidden="true" />
          Fight again with other
        </button>
      </div>
    </div>
  );
};

export default ResultDisplay;
