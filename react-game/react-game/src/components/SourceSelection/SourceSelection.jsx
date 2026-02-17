import { useState, useEffect } from 'react';
import './SourceSelection.css';

const SOURCE_OPTIONS = [
  { id: 'past_battles', label: 'Past battles', short: 'Your previous fights', icon: '⚔️' },
  { id: 'shown_interest', label: 'Favourites', short: 'Streams you liked (winners)', icon: '⭐' },
  { id: 'psychometric', label: 'My test results', short: 'Careers from your report', icon: '📋' },
  { id: 'shortlist', label: 'Shortlist', short: 'Careers you saved', icon: '📌' },
  { id: 'all_clusters', label: 'All careers', short: 'Pick from every cluster', icon: '🌐' },
];

const SourceSelection = ({ onContinue, onSkipToClusters }) => {
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [loadingAvailable, setLoadingAvailable] = useState(true);
  const [error, setError] = useState(null);
  const [availableCounts, setAvailableCounts] = useState(null);

  useEffect(() => {
    fetch('/career-battle/api/stream-sources/?available=1', { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => {
        setAvailableCounts(data.available || {});
      })
      .catch(() => setAvailableCounts({ all_clusters: 1 }))
      .finally(() => setLoadingAvailable(false));
  }, []);

  const visibleOptions = SOURCE_OPTIONS.filter((opt) => {
    const count = availableCounts && typeof availableCounts[opt.id] === 'number' ? availableCounts[opt.id] : 0;
    return count > 0;
  });

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setError(null);
  };

  const handleContinue = () => {
    if (selected.size === 0) {
      setError('Pick at least one option');
      return;
    }
    setLoading(true);
    setError(null);
    const sourcesParam = [...selected].join(',');
    fetch(`/career-battle/api/stream-sources/?sources=${encodeURIComponent(sourcesParam)}`, { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => {
        const streams = Array.isArray(data.streams) ? data.streams : [];
        if (streams.length < 2) {
          setError('Need at least 2 streams to battle. Pick another option or try "All careers".');
          setLoading(false);
          return;
        }
        onContinue(streams);
      })
      .catch(() => {
        setError('Something went wrong. Try again.');
        setLoading(false);
      });
  };

  if (loadingAvailable) {
    return (
      <div className="source-selection-container source-selection-loading">
        <div className="source-loading-dots">
          <span aria-hidden="true">.</span><span aria-hidden="true">.</span><span aria-hidden="true">.</span>
        </div>
        <p className="source-loading-text">Loading options</p>
      </div>
    );
  }

  if (visibleOptions.length === 0) {
    return (
      <div className="source-selection-container">
        <p className="source-no-options">No options available right now. Try again later.</p>
      </div>
    );
  }

  return (
    <div className="source-selection-container" role="region" aria-labelledby="source-selection-title">
      <div className="source-selection-header">
        <h1 id="source-selection-title" className="source-selection-title">
          Choose your arena
        </h1>
        <p className="source-selection-subtitle" id="source-selection-description">
          Where should we get your 2 fighters from? Pick one or mix several.
        </p>
        {selected.size > 0 && (
          <div className="selected-sources-count">
            {selected.size} chosen
          </div>
        )}
      </div>

      <div className="source-options" role="group" aria-labelledby="source-selection-title">
        {visibleOptions.map((opt) => {
          const isSelected = selected.has(opt.id);
          const count = (availableCounts && availableCounts[opt.id]) || 0;
          return (
            <button
              key={opt.id}
              type="button"
              className={`source-option-card ${isSelected ? 'source-option-card-selected' : ''}`}
              onClick={() => toggle(opt.id)}
              aria-pressed={isSelected}
              aria-label={`${opt.label}${isSelected ? ' - Selected' : ''}`}
            >
              <span className="source-option-icon" aria-hidden="true">{opt.icon}</span>
              <span className="source-option-label">{opt.label}</span>
              <span className="source-option-short">{opt.short}</span>
              {count > 0 && <span className="source-option-count">{count}</span>}
              {isSelected && <span className="source-option-check" aria-hidden="true">✓</span>}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="source-selection-error" role="alert">
          {error}
        </div>
      )}

      <div className="source-selection-footer">
        {onSkipToClusters && visibleOptions.some((o) => o.id === 'all_clusters') && (
          <button type="button" className="source-skip-to-clusters" onClick={onSkipToClusters}>
            Browse by cluster instead
          </button>
        )}
        <button
          type="button"
          className={`continue-button ${selected.size > 0 && !loading ? 'continue-button-active' : 'continue-button-disabled'}`}
          onClick={handleContinue}
          disabled={selected.size === 0 || loading}
          aria-label={selected.size > 0 ? 'Continue to pick 2 streams' : 'Pick at least one option'}
        >
          {loading ? 'Loading…' : "Let's go"}
        </button>
      </div>
    </div>
  );
};

export default SourceSelection;
