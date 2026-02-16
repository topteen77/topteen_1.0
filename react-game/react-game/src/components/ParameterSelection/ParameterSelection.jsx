import { useState } from 'react';
import { PARAMETERS, MIN_PARAMETER_SELECTION } from '../../utils/constants';
import './ParameterSelection.css';

const ParameterSelection = ({ selectedStreams, onFight }) => {
  const [selectedParameters, setSelectedParameters] = useState([]);

  const handleParameterToggle = (parameterId) => {
    if (selectedParameters.includes(parameterId)) {
      // Deselect if already selected
      setSelectedParameters(selectedParameters.filter(id => id !== parameterId));
    } else {
      // Select parameter
      setSelectedParameters([...selectedParameters, parameterId]);
    }
  };

  const handleFight = () => {
    if (selectedParameters.length >= MIN_PARAMETER_SELECTION && onFight) {
      onFight({
        streams: selectedStreams,
        parameters: selectedParameters
      });
    }
  };

  const isParameterSelected = (parameterId) => selectedParameters.includes(parameterId);
  const canFight = selectedParameters.length >= MIN_PARAMETER_SELECTION;

  return (
    <div className="parameter-selection-container" role="region" aria-labelledby="parameter-selection-title">
      <div className="parameter-selection-header">
        <h1 id="parameter-selection-title" className="parameter-selection-title">Select Comparison Parameters</h1>
        <p className="parameter-selection-subtitle" id="parameter-selection-description">
          Choose the criteria for comparing your selected streams
        </p>
        
        {/* Display selected streams */}
        {selectedStreams && selectedStreams.length > 0 && (
          <div className="selected-streams-context">
            <span className="context-label">Comparing:</span>
            <div className="streams-badge-container">
              {selectedStreams.map((stream, index) => (
                <span key={stream} className="stream-badge">
                  {stream}
                  {index < selectedStreams.length - 1 && (
                    <span className="vs-separator"> vs </span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        {selectedParameters.length > 0 && (
          <div className="selected-count">
            {selectedParameters.length} parameter{selectedParameters.length !== 1 ? 's' : ''} selected
          </div>
        )}
      </div>

      <div className="parameter-list" role="group" aria-labelledby="parameter-selection-title" aria-describedby="parameter-selection-description">
        {PARAMETERS.map((parameter) => {
          const isSelected = isParameterSelected(parameter.id);
          
          return (
            <div
              key={parameter.id}
              className={`parameter-item ${isSelected ? 'parameter-item-selected' : ''}`}
              onClick={() => handleParameterToggle(parameter.id)}
              role="checkbox"
              aria-checked={isSelected}
              aria-labelledby={`parameter-${parameter.id}-label`}
              aria-describedby={`parameter-${parameter.id}-desc`}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleParameterToggle(parameter.id);
                }
              }}
            >
              <div className="parameter-checkbox">
                <input
                  type="checkbox"
                  id={parameter.id}
                  checked={isSelected}
                  onChange={() => handleParameterToggle(parameter.id)}
                  className="checkbox-input"
                />
                <label htmlFor={parameter.id} className="checkbox-label">
                  <span className="checkbox-custom">
                    {isSelected && (
                      <span className="checkbox-checkmark">✓</span>
                    )}
                  </span>
                </label>
              </div>
              <div className="parameter-content">
                <label htmlFor={parameter.id} className="parameter-label" id={`parameter-${parameter.id}-label`}>
                  {parameter.label}
                </label>
                <p className="parameter-description" id={`parameter-${parameter.id}-desc`}>{parameter.description}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="parameter-selection-footer">
        <button
          className={`fight-button ${canFight ? 'fight-button-active' : 'fight-button-disabled'}`}
          onClick={handleFight}
          disabled={!canFight}
          aria-label={canFight ? 'Start comparison fight' : `Select at least ${MIN_PARAMETER_SELECTION} parameter to start fight`}
        >
          <span className="fight-button-icon" aria-hidden="true">⚔️</span>
          Fight!
        </button>
        {!canFight && (
          <p className="fight-button-hint" role="status" aria-live="polite">
            Select at least {MIN_PARAMETER_SELECTION} parameter to continue
          </p>
        )}
      </div>
    </div>
  );
};

export default ParameterSelection;
