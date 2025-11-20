/**
 * Internet Speed Meter
 * Measures download/upload speeds and determines connection stability
 * Updates every 5 seconds
 */

(function() {
  'use strict';

  // Configuration
  const UPDATE_INTERVAL = 5000; // 5 seconds
  const STABILITY_THRESHOLD = 1.0; // 1 Mbps = stable
  const TEST_FILE_SIZE = 100000; // 100KB test file
  const TEST_ENDPOINT = '/static/topteenfrontend/assets/js/internet-speed-meter.js'; // Use existing file for download test

  let speedMeterInterval = null;
  let isRunning = false;

  /**
   * Measure download speed
   */
  async function measureDownloadSpeed() {
    try {
      // Use a larger file for more accurate measurement - try multiple endpoints
      const testFiles = [
        '/static/css_new/bootstrap.min.css',
        '/static/css_new/custom-min.css',
        '/static/js_new/main.js',
        '/static/topteenfrontend/assets/js/internet-speed-meter.js'
      ];
      
      let lastError = null;
      
      for (const testFile of testFiles) {
        try {
          const startTime = performance.now();
          const cacheBuster = '?t=' + Date.now() + '&r=' + Math.random();
          const response = await fetch(testFile + cacheBuster, {
            cache: 'no-cache',
            method: 'GET',
            headers: {
              'Cache-Control': 'no-cache',
              'Pragma': 'no-cache'
            }
          });
          
          if (!response.ok) {
            console.warn('File not found or error:', testFile, response.status);
            continue; // Try next file
          }

          const blob = await response.blob();
          const endTime = performance.now();
          const duration = (endTime - startTime) / 1000; // Convert to seconds
          
          if (duration < 0.001 || blob.size === 0) {
            console.warn('Duration too short or file empty:', testFile, duration, blob.size);
            continue; // Try next file
          }
          
          const fileSize = blob.size * 8; // Convert bytes to bits
          const speedMbps = (fileSize / duration) / 1000000; // Convert to Mbps

          if (speedMbps > 0 && speedMbps < 10000) { // Sanity check: between 0 and 10 Gbps
            console.log('Download speed test successful:', testFile, speedMbps, 'Mbps');
            return {
              success: true,
              speed: Math.round(speedMbps * 10) / 10, // Round to 1 decimal
              duration: duration
            };
          } else {
            console.warn('Speed calculation out of range:', speedMbps, 'Mbps');
          }
        } catch (error) {
          console.warn('Error testing file:', testFile, error);
          lastError = error;
          continue; // Try next file
        }
      }
      
      // If all files failed, throw the last error
      throw lastError || new Error('All download test files failed');
      
    } catch (error) {
      console.error('Download speed test error:', error);
      return {
        success: false,
        speed: 0,
        error: error ? error.message : 'Unknown error'
      };
    }
  }

  /**
   * Measure upload speed
   */
  async function measureUploadSpeed() {
    try {
      // Create a test blob
      const testData = new Blob([new ArrayBuffer(TEST_FILE_SIZE)], { type: 'application/octet-stream' });
      const formData = new FormData();
      formData.append('test', testData, 'speedtest.dat');

      const startTime = performance.now();
      const response = await fetch('/psychometric/speed-test/', {
        method: 'POST',
        body: formData,
        cache: 'no-cache'
      });
      const endTime = performance.now();
      const duration = (endTime - startTime) / 1000; // Convert to seconds

      if (!response.ok) {
        throw new Error('Upload test failed');
      }

      const fileSize = TEST_FILE_SIZE * 8; // Convert bytes to bits
      const speedMbps = (fileSize / duration) / 1000000; // Convert to Mbps

      return {
        success: true,
        speed: Math.round(speedMbps * 10) / 10, // Round to 1 decimal
        duration: duration
      };
    } catch (error) {
      // If upload endpoint doesn't exist, estimate based on download
      console.warn('Upload speed test error, using fallback:', error);
      return {
        success: false,
        speed: 0,
        error: error.message,
        fallback: true
      };
    }
  }

  /**
   * Determine connection stability
   */
  function determineStability(downloadSpeed, uploadSpeed) {
    // Use download speed as primary indicator, fallback to upload if download fails
    const primarySpeed = downloadSpeed > 0 ? downloadSpeed : uploadSpeed;
    // If both speeds are 0, connection is unstable
    if (primarySpeed === 0) {
      return false;
    }
    return primarySpeed >= STABILITY_THRESHOLD;
  }

  /**
   * Update UI with speed measurements
   */
  function updateSpeedMeterUI(downloadSpeed, uploadSpeed, isStable) {
    // Update all speed meter instances (mobile and desktop)
    const statusIndicators = document.querySelectorAll('.speed-status-indicator');
    const statusTexts = document.querySelectorAll('.speed-status-text');
    const downloadElements = document.querySelectorAll('.speed-download-value');
    const uploadElements = document.querySelectorAll('.speed-upload-value');

    console.log('UI Elements found:', {
      statusIndicators: statusIndicators.length,
      statusTexts: statusTexts.length,
      downloadElements: downloadElements.length,
      uploadElements: uploadElements.length
    });

    // Update all status indicators and texts
    statusIndicators.forEach(statusIndicator => {
      if (isStable) {
        statusIndicator.className = 'speed-status-indicator status-stable';
      } else {
        statusIndicator.className = 'speed-status-indicator status-unstable';
      }
    });

    statusTexts.forEach(statusText => {
      if (isStable) {
        statusText.textContent = 'Internet Stable';
        statusText.className = 'speed-status-text status-stable';
      } else {
        statusText.textContent = 'Internet Unstable';
        statusText.className = 'speed-status-text status-unstable';
      }
    });

    // Update all download elements
    const downloadDisplayText = downloadSpeed > 0 ? `${downloadSpeed} Mbps` : 'N/A';
    downloadElements.forEach(downloadElement => {
      downloadElement.textContent = downloadDisplayText;
    });
    if (downloadElements.length > 0) {
      console.log('Download elements updated:', downloadDisplayText);
    } else {
      console.warn('Download elements not found');
    }

    // Update all upload elements
    const uploadDisplayText = uploadSpeed > 0 ? `${uploadSpeed} Mbps` : 'N/A';
    uploadElements.forEach(uploadElement => {
      uploadElement.textContent = uploadDisplayText;
    });
    if (uploadElements.length > 0) {
      console.log('Upload elements updated:', uploadDisplayText);
    } else {
      console.warn('Upload elements not found');
    }
  }

  /**
   * Run speed test and update UI
   */
  async function runSpeedTest() {
    if (isRunning) {
      return; // Prevent overlapping tests
    }

    isRunning = true;

    // Show loading state for all speed meters
    const statusTexts = document.querySelectorAll('.speed-status-text');
    statusTexts.forEach(statusText => {
      statusText.textContent = 'Internet Checking...';
    });

    try {
      // Measure download speed
      const downloadResult = await measureDownloadSpeed();
      
      // Measure upload speed (with fallback if endpoint doesn't exist)
      let uploadResult = await measureUploadSpeed();
      
      // If upload failed and we have download speed, estimate upload as 70% of download
      if (!uploadResult.success && downloadResult.success && uploadResult.fallback) {
        uploadResult = {
          success: true,
          speed: Math.round((downloadResult.speed * 0.7) * 10) / 10
        };
      }

      const downloadSpeed = downloadResult.success ? downloadResult.speed : 0;
      const uploadSpeed = uploadResult.success ? uploadResult.speed : 0;
      const isStable = determineStability(downloadSpeed, uploadSpeed);
      
      // Debug logging
      console.log('Speed test results:', 
        'Download:', downloadSpeed, 'Mbps',
        'Upload:', uploadSpeed, 'Mbps',
        'Stable:', isStable,
        'Download Success:', downloadResult.success,
        'Upload Success:', uploadResult.success
      );
      
      if (downloadResult.error) {
        console.warn('Download error:', downloadResult.error);
      }
      if (uploadResult.error) {
        console.warn('Upload error:', uploadResult.error);
      }

      console.log('Updating UI with speeds:', downloadSpeed, uploadSpeed, isStable);
      updateSpeedMeterUI(downloadSpeed, uploadSpeed, isStable);
      
      // If speeds are 0, log more details
      if (downloadSpeed === 0 && uploadSpeed === 0) {
        console.warn('Both speeds are 0. Check network connectivity and file availability.');
      }
    } catch (error) {
      console.error('Speed test error:', error);
      updateSpeedMeterUI(0, 0, false);
    } finally {
      isRunning = false;
    }
  }

  /**
   * Initialize speed meter
   */
  function initSpeedMeter() {
    // Check if speed meter element exists (mobile or desktop)
    const speedMeters = document.querySelectorAll('.internet-speed-meter');
    if (speedMeters.length === 0) {
      console.log('Speed meter element not found');
      return; // Speed meter not present on this page
    }

    console.log('Speed meter initialized, found', speedMeters.length, 'instance(s)');
    
    // Run initial test after a short delay to ensure page is loaded
    setTimeout(() => {
      runSpeedTest();
    }, 1000);

    // Set up interval for continuous updates
    speedMeterInterval = setInterval(runSpeedTest, UPDATE_INTERVAL);
  }

  /**
   * Stop speed meter
   */
  function stopSpeedMeter() {
    if (speedMeterInterval) {
      clearInterval(speedMeterInterval);
      speedMeterInterval = null;
    }
    isRunning = false;
  }

  // Initialize when DOM is ready
  function startSpeedMeter() {
    console.log('Starting speed meter initialization...');
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function() {
        console.log('DOM loaded, initializing speed meter');
        initSpeedMeter();
      });
    } else {
      console.log('DOM already ready, initializing speed meter');
      initSpeedMeter();
    }
  }
  
  // Start the speed meter
  startSpeedMeter();

  // Clean up on page unload
  window.addEventListener('beforeunload', stopSpeedMeter);

  // Export for manual control if needed
  window.InternetSpeedMeter = {
    init: initSpeedMeter,
    stop: stopSpeedMeter,
    test: runSpeedTest
  };

})();

