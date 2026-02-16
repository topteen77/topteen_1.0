import { useState } from 'react';
import './PhoneLoginPopup.css';

const PhoneLoginPopup = ({ onClose, onSuccess }) => {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Basic phone number validation
    const phoneRegex = /^[0-9]{10,15}$/;
    const cleanedPhone = phoneNumber.replace(/\D/g, ''); // Remove non-digits
    
    if (!cleanedPhone || cleanedPhone.length < 10) {
      setError('Please enter a valid phone number (at least 10 digits)');
      return;
    }

    if (!phoneRegex.test(cleanedPhone)) {
      setError('Please enter a valid phone number');
      return;
    }

    // Store phone number in localStorage
    localStorage.setItem('userPhoneNumber', cleanedPhone);
    
    // Call success callback
    if (onSuccess) {
      onSuccess(cleanedPhone);
    }
    
    // Close popup
    onClose();
  };

  const handlePhoneChange = (e) => {
    const value = e.target.value;
    setPhoneNumber(value);
    if (error) {
      setError('');
    }
  };

  return (
    <div className="phone-login-overlay" onClick={onClose}>
      <div className="phone-login-popup" onClick={(e) => e.stopPropagation()}>
        <button 
          className="phone-login-close" 
          onClick={onClose}
          aria-label="Close login form"
        >
          ×
        </button>
        <div className="phone-login-content">
          <h2 className="phone-login-title">Login</h2>
          <p className="phone-login-subtitle">Please enter your phone number to continue</p>
          <form onSubmit={handleSubmit} className="phone-login-form">
            <div className="phone-login-input-group">
              <label htmlFor="phone-number" className="phone-login-label">
                Phone Number
              </label>
              <input
                type="tel"
                id="phone-number"
                className="phone-login-input"
                value={phoneNumber}
                onChange={handlePhoneChange}
                placeholder="Enter your phone number"
                required
                autoFocus
              />
            </div>
            {error && (
              <div className="phone-login-error" role="alert">
                {error}
              </div>
            )}
            <button type="submit" className="phone-login-submit">
              Continue
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default PhoneLoginPopup;
