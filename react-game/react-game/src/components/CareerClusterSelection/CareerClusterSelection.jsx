import { useState } from 'react';
import { CAREER_CLUSTERS } from '../../utils/constants';
import './CareerClusterSelection.css';

const CareerClusterSelection = ({ onContinue }) => {
  const [selectedCluster, setSelectedCluster] = useState(null);

  const handleClusterClick = (clusterName) => {
    setSelectedCluster(clusterName);
  };

  const handleContinue = () => {
    if (selectedCluster && onContinue) {
      onContinue(selectedCluster);
    }
  };

  const clusterNames = Object.keys(CAREER_CLUSTERS);

  return (
    <div className="career-cluster-selection-container" role="region" aria-labelledby="cluster-selection-title">
      <div className="career-cluster-selection-header">
        <h1 id="cluster-selection-title" className="career-cluster-selection-title">
          Select Career Cluster
        </h1>
        <p className="career-cluster-selection-subtitle" id="cluster-selection-description">
          Choose a career cluster to explore related streams
        </p>
        {selectedCluster && (
          <div className="selected-cluster-info">
            <span className="selected-cluster-label">Selected:</span>
            <span className="selected-cluster-name">{selectedCluster}</span>
            <span className="streams-count">
              ({CAREER_CLUSTERS[selectedCluster].length} streams available)
            </span>
          </div>
        )}
      </div>

      <div className="cluster-grid" role="group" aria-labelledby="cluster-selection-title" aria-describedby="cluster-selection-description">
        {clusterNames.map((clusterName) => {
          const isSelected = selectedCluster === clusterName;
          const streams = CAREER_CLUSTERS[clusterName];
          
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
                    ✓
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <div className="career-cluster-selection-footer">
        <button
          className={`continue-button ${selectedCluster ? 'continue-button-active' : 'continue-button-disabled'}`}
          onClick={handleContinue}
          disabled={!selectedCluster}
          aria-label={selectedCluster ? 'Continue to stream selection' : 'Select a career cluster to continue'}
        >
          Continue
        </button>
      </div>
    </div>
  );
};

export default CareerClusterSelection;

