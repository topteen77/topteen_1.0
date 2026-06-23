import { useState } from 'react';
import { CAREER_CLUSTERS } from '../../utils/constants';
import './CareerClusterSelection.css';
import iconSelectTick from '../../assets/images/pruple-select-tick.svg';

const CareerClusterSelection = ({ careerClusters, fightHistory = [], onContinue, onBack }) => {
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const rawClusters = careerClusters && Object.keys(careerClusters).length > 0 ? careerClusters : CAREER_CLUSTERS;
  const clusters = typeof rawClusters === 'object' && rawClusters !== null ? rawClusters : CAREER_CLUSTERS;

  const handleClusterClick = (clusterName) => {
    setSelectedCluster(clusterName);
  };

  const handleContinue = () => {
    if (selectedCluster && onContinue) {
      onContinue(selectedCluster);
    }
  };

  const clusterNames = Object.keys(clusters || {});
  const getStreams = (name) => {
    const s = clusters[name];
    return Array.isArray(s) ? s : [];
  };
  const safeHistory = Array.isArray(fightHistory) ? fightHistory : [];

  return (
    <div className="career-cluster-selection-container" role="region" aria-labelledby="cluster-selection-title">
      <div className="career-cluster-selection-header">
        <h1 id="cluster-selection-title" className="career-cluster-selection-title">
          Select <span className="text-purple">Career </span> Cluster
        </h1>
        <p className="career-cluster-selection-subtitle" id="cluster-selection-description">
          Choose any one career cluster to explore related streams
        </p>
        {selectedCluster && (
          <div className="selected-cluster-info">
            <span className="selected-cluster-label">Selected:</span>
            <span className="selected-cluster-name">{selectedCluster}</span>
            <span className="streams-count">
              ({getStreams(selectedCluster).length} streams available)
            </span>
          </div>
        )}
      </div>

      {safeHistory.length > 0 && (
        <div className="fight-history-section">
          <button
            type="button"
            className="fight-history-toggle"
            onClick={() => setHistoryOpen(!historyOpen)}
            aria-expanded={historyOpen}
            aria-controls="fight-history-list"
          >
            <span className="fight-history-toggle-icon" aria-hidden="true">{historyOpen ? '▼' : '▶'}</span>
            Your fight history ({safeHistory.length})
          </button>
          {historyOpen && (
            <ul id="fight-history-list" className="fight-history-list" role="list">
              {safeHistory.map((f) => (
                <li key={f.id} className="fight-history-item">
                  <span className="fight-history-title">{f.title}</span>
                  {f.winner && (
                    <span className="fight-history-winner">Winner: {f.winner}</span>
                  )}
                  {f.created && (
                    <span className="fight-history-date">
                      {new Date(f.created).toLocaleDateString(undefined, { dateStyle: 'short' })}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="cluster-grid" role="group" aria-labelledby="cluster-selection-title" aria-describedby="cluster-selection-description">
        {clusterNames.map((clusterName) => {
          const isSelected = selectedCluster === clusterName;
          const streams = getStreams(clusterName);
          if (streams.length === 0) return null;
          return (
            <button
              key={clusterName}
              className={`cluster-card ${isSelected ? 'cluster-card-selected' : ''}`}
              onClick={() => handleClusterClick(clusterName)}
              aria-pressed={isSelected}
              aria-label={`${clusterName} - ${streams.length} streams available${isSelected ? ' - Selected' : ''}`}
            >
              <div className="cluster-card-content">


                <h2 className="cluster-name">{clusterName}</h2>
                
                <div className="cluster-streams-preview">
                  <span className="streams-count-badge">{streams.length} streams</span>
                  <div className="streams-list-preview">
                    {streams.slice(0, 3).map((stream, idx) => (
                      <span key={idx} className="stream-preview-item">{stream}</span>
                    ))}
                    {streams.length > 3 && (
                      <span className="stream-preview-more">+{streams.length - 3} more</span>
                    )}
                  </div>
                </div>
                {isSelected && (
                  <span className="cluster-checkmark" aria-label="Selected" aria-hidden="true">
                    <img src={iconSelectTick} alt="" className="cluster-checkmark-img" />
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <div className="career-cluster-selection-footer">
        {onBack && (
          <button type="button" className="back-button" onClick={onBack}>
            <i className='back-button-icon bx bx-left-arrow-alt' ></i> Back
          </button>
        )}
        <button
          className={`continue-button ${selectedCluster ? 'continue-button-active' : 'continue-button-disabled'}`}
          onClick={handleContinue}
          disabled={!selectedCluster}
          aria-label={selectedCluster ? 'Continue to stream selection' : 'Select a career cluster to continue'}
        >
          Continue <i className='bx bx-right-arrow-alt' ></i>
        </button>
      </div>
    </div>
  );
};

export default CareerClusterSelection;

