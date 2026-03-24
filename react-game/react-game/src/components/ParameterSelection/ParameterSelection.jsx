import { useState } from 'react';
import { PARAMETERS, MIN_PARAMETER_SELECTION } from '../../utils/constants';
import './ParameterSelection.css';
import iconSelectTick from '../../assets/images/pruple-select-tick.svg';

const ParameterSelection = ({ selectedStreams, onFight }) => {
  const [selectedParameters, setSelectedParameters] = useState([]);

  const PARAM_ICONS = {
    job_placement: { iconClass: 'bx bx-briefcase-alt-2', colorClass: 'parameter-icon-bg-1' },
    job_security: { iconClass: 'bx bx-shield-quarter', colorClass: 'parameter-icon-bg-2' },
    fees_cost: { iconClass: 'bx bx-rupee', colorClass: 'parameter-icon-bg-3' },
    location: { iconClass: 'bx bx-map-pin', colorClass: 'parameter-icon-bg-4' },
    career_growth: { iconClass: 'bx bx-trending-up', colorClass: 'parameter-icon-bg-5' },
    industry_demand: { iconClass: 'bx bxl-graphql', colorClass: 'parameter-icon-bg-6' }
  };

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
        <h1 id="parameter-selection-title" className="parameter-selection-title">Select <span className="text-purple">Comparison</span>  Parameters</h1>
       
       <p>Choose the criteria for comparing your selected streams</p>
       
        {Array.isArray(selectedStreams) && selectedStreams.length === 2 && (
          <div className="selected-streams-context" aria-label={`Comparing ${selectedStreams[0]} versus ${selectedStreams[1]}`}>
            <span className="context-label">COMPARING:</span>
            <div className="streams-badge-container">
              <span className="stream-badge">{selectedStreams[0]}</span>
              <span className="vs-separator">vs</span>
              <span className="stream-badge">{selectedStreams[1]}</span>
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
          const iconCfg = PARAM_ICONS[parameter.id] || PARAM_ICONS.job_placement;
          
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
              <div className="parameter-icon-wrapper" aria-hidden="true">
                <div className={`parameter-icon ${iconCfg.colorClass}`}>
                  <i className={iconCfg.iconClass}></i>
                </div>
              </div>
              <div className="parameter-content">
                <span className="parameter-label" id={`parameter-${parameter.id}-label`}>
                  {parameter.label}
                </span>
                <p className="parameter-description" id={`parameter-${parameter.id}-desc`}>{parameter.description}</p>
              </div>
              {isSelected && (
                <span className="parameter-checkmark" aria-hidden="true">
                  <img src={iconSelectTick} alt="" className="parameter-checkmark-img" />
                </span>
              )}
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
