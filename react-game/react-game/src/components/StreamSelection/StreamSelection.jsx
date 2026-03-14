import { useState } from 'react';
import { CAREER_CLUSTERS, MAX_STREAM_SELECTION } from '../../utils/constants';
import './StreamSelection.css';
import iconSelectTick from '../../assets/images/pruple-select-tick.svg';



const StreamSelection = ({ careerClusters, selectedCluster, streamPool = null, onContinue, onBack, disqualifiedStreams = [], onReset }) => {
  const [selectedStreams, setSelectedStreams] = useState([]);
  const clusters = careerClusters && Object.keys(careerClusters).length > 0 ? careerClusters : CAREER_CLUSTERS;

  // Streams either from pool (source selection) or from selected cluster
  const clusterStreams = streamPool && Array.isArray(streamPool)
    ? streamPool
    : (selectedCluster && clusters[selectedCluster] ? clusters[selectedCluster] : []);

  const availableStreams = clusterStreams.filter(
    stream => !disqualifiedStreams.includes(stream)
  );

  const allDisqualified = availableStreams.length === 0;

  const handleStreamClick = (stream) => {
    if (selectedStreams.includes(stream)) {
      setSelectedStreams(selectedStreams.filter(s => s !== stream));
    } else if (selectedStreams.length < MAX_STREAM_SELECTION) {
      if (!selectedStreams.includes(stream)) {
        setSelectedStreams([...selectedStreams, stream]);
      }
    }
  };

  const handleContinue = () => {
    if (selectedStreams.length === MAX_STREAM_SELECTION && onContinue) {
      onContinue(selectedStreams);
    }
  };

  const isStreamSelected = (stream) => selectedStreams.includes(stream);
  const isStreamDisabled = (stream) =>
    !isStreamSelected(stream) && selectedStreams.length >= MAX_STREAM_SELECTION;
  const canContinue = selectedStreams.length === MAX_STREAM_SELECTION;

  return (
    <div className="stream-selection-container" role="region" aria-labelledby="stream-selection-title">
      <div className="stream-selection-header">
        <h1 id="stream-selection-title" className="stream-selection-title">
          {streamPool && streamPool.length ? (
            <>
              Select <span className="text-purple">Two Streams</span> to Battle
            </>
          ) : selectedCluster ? (
            <>
              Select <span className="text-purple">Two Streams</span> from {selectedCluster}
            </>
          ) : (
            <>
              Select <span className="text-purple">Two Streams</span>
            </>
          )}
        </h1>
        <p className="stream-selection-subtitle" id="stream-selection-description">
          Choose the streams you want to compare
        </p>
        {selectedStreams.length > 0 && (
          <div className="selected-count">
            {selectedStreams.length} of {MAX_STREAM_SELECTION} selected
          </div>
        )}
      </div>

      <div className="stream-grid" role="group" aria-labelledby="stream-selection-title" aria-describedby="stream-selection-description">
        {availableStreams.map((stream) => {
          const isSelected = isStreamSelected(stream);
          const isDisabled = isStreamDisabled(stream);

          return (
            <button
              key={stream}
              className={`stream-card ${isSelected ? 'stream-card-selected' : ''} ${isDisabled ? 'stream-card-disabled' : ''}`}
              onClick={() => handleStreamClick(stream)}
              disabled={isDisabled}
              aria-pressed={isSelected}
              aria-label={`${stream}${isSelected ? ' - Selected' : ''}${isDisabled ? ' - Unavailable' : ''}`}
              aria-describedby={`stream-${stream}-desc`}
            >
              <div className="stream-card-content">
                <span className="stream-name" id={`stream-${stream}-desc`}>{stream}</span>
                {isSelected && (
                  <span className="stream-checkmark" aria-label="Selected" aria-hidden="true">
                    <img src={iconSelectTick} alt="" className="stream-checkmark-img" />
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {allDisqualified && (
        <div className="no-streams-message">
          <div className="no-streams-icon">🏆</div>
          <h3 className="no-streams-title">All Streams Explored!</h3>
          <p className="no-streams-text">
            You&apos;ve compared all available streams. Start a fresh game to explore them again.
          </p>
          {onReset && (
            <button
              className="reset-game-button"
              onClick={onReset}
            >
              Start New Game
            </button>
          )}
        </div>
      )}

      {!allDisqualified && (
        <div className="stream-selection-footer">
          {onBack && (
            <button type="button" className="back-button" onClick={onBack}>
                <i className='back-button-icon bx bx-left-arrow-alt' ></i>  Back
            </button>
          )}
          <button
            className={`continue-button ${canContinue ? 'continue-button-active' : 'continue-button-disabled'}`}
            onClick={handleContinue}
            disabled={!canContinue}
            aria-label={canContinue ? 'Continue to parameter selection' : 'Select 2 streams to continue'}
          >
            Continue <i className='bx bx-right-arrow-alt' ></i>
          </button>
        </div>
      )}
    </div>
  );
};

export default StreamSelection;
