/**
 * Chatbot Auto-Open Functionality
 * Opens chatbot automatically after user stops scrolling/navigating for X seconds
 * Shows page-specific questions based on current page
 */

(function() {
  'use strict';

  // Configuration
  const INACTIVITY_DELAY = 5000; // 5 seconds of inactivity before auto-opening
  const AUTO_OPEN_ENABLED = true; // Set to false to disable auto-open
  
  // State variables
  let inactivityTimer = null;
  let hasAutoOpened = false;
  let isUserInteracting = false;
  let lastActivityTime = Date.now();

  // Get page-specific questions based on current URL
  function getPageSpecificQuestions() {
    const path = window.location.pathname.toLowerCase();
    const questions = [];

    // Career detail page
    if (path.includes('/career/') && path.includes('-detail')) {
      const careerName = document.querySelector('h1, .career-name, [data-career-name]')?.textContent?.trim() || 'this career';
      questions.push(
        `Tell me more about ${careerName}`,
        `What are the career prospects for ${careerName}?`,
        `What skills do I need for ${careerName}?`,
        `How can I become a ${careerName}?`
      );
    }
    // Career list page
    else if (path.includes('/careers') || path.includes('/career')) {
      questions.push(
        'What careers are available?',
        'Help me find the right career',
        'What career matches my interests?',
        'Show me popular careers'
      );
    }
    // Blog page
    else if (path.includes('/blog')) {
      questions.push(
        'What articles do you recommend?',
        'Help me find relevant articles',
        'What should I read about career planning?',
        'Show me latest blog posts'
      );
    }
    // College/Institute page
    else if (path.includes('/college') || path.includes('/institute')) {
      questions.push(
        'Help me find colleges',
        'What are the admission requirements?',
        'Which colleges are best for my field?',
        'Tell me about college rankings'
      );
    }
    // Assessment/Test page
    else if (path.includes('/test') || path.includes('/assessment') || path.includes('/psychometric')) {
      questions.push(
        'What assessments should I take?',
        'Help me understand my test results',
        'What do these assessments measure?',
        'How can assessments help my career?'
      );
    }
    // Home page
    else if (path === '/' || path.includes('/home')) {
      questions.push(
        'How can TopTeen help me?',
        'What services do you offer?',
        'Help me get started',
        'Tell me about career guidance'
      );
    }
    // Default questions
    else {
      questions.push(
        'How can I find the right career?',
        'What services does TopTeen offer?',
        'Help me with career planning',
        'Tell me more about TopTeen'
      );
    }

    return questions.slice(0, 3); // Return max 3 questions
  }

  // Create quick question buttons
  function createQuickQuestions() {
    const questions = getPageSpecificQuestions();
    if (questions.length === 0) return '';

    let html = '<div class="quick-questions" style="margin-top: 15px; display: flex; flex-direction: column; gap: 8px;">';
    questions.forEach((question, index) => {
      html += `
        <button class="quick-question-btn" data-question="${question.replace(/"/g, '&quot;')}" 
                style="background: #f2f2ff; border: 1px solid #ccccf5; border-radius: 8px; 
                       padding: 10px 15px; text-align: left; font-size: 0.9rem; color: #3f37c9; 
                       cursor: pointer; transition: all 0.2s ease; width: 100%;">
          ${question}
        </button>
      `;
    });
    html += '</div>';
    return html;
  }

  // Reset inactivity timer
  function resetInactivityTimer() {
    // Clear existing timer
    if (inactivityTimer) {
      clearTimeout(inactivityTimer);
      inactivityTimer = null;
    }

    // Don't auto-open if user is already interacting or has manually closed
    if (isUserInteracting || hasAutoOpened) {
      return;
    }

    // Set new timer
    inactivityTimer = setTimeout(() => {
      if (!document.body.classList.contains('show-chatbot') && AUTO_OPEN_ENABLED) {
        openChatbotAuto();
        hasAutoOpened = true;
      }
    }, INACTIVITY_DELAY);
  }

  // Auto-open chatbot
  function openChatbotAuto() {
    const chatbotPopup = document.querySelector('.chatbot-popup');
    const chatBody = document.querySelector('.chat-body');
    
    if (!chatbotPopup || !chatBody) return;

    // Add quick questions to initial bot message if not already added
    const botMessage = chatBody.querySelector('.bot-message .message-text');
    if (botMessage && !botMessage.querySelector('.quick-questions')) {
      const quickQuestionsHTML = createQuickQuestions();
      if (quickQuestionsHTML) {
        botMessage.innerHTML += quickQuestionsHTML;
        
        // Add click handlers for quick question buttons
        const quickQuestionBtns = botMessage.querySelectorAll('.quick-question-btn');
        quickQuestionBtns.forEach(btn => {
          btn.addEventListener('click', function() {
            const question = this.getAttribute('data-question');
            if (question) {
              const messageInput = document.querySelector('.message-input');
              const sendBtn = document.querySelector('#send-message');
              
              if (messageInput) {
                // Set the question as input value
                messageInput.value = question;
                
                // Trigger input event to update UI
                messageInput.dispatchEvent(new Event('input', { bubbles: true }));
                
                // Small delay to ensure UI updates, then send
                setTimeout(() => {
                  if (sendBtn) {
                    sendBtn.click();
                  } else {
                    // Fallback: trigger form submit
                    const form = document.querySelector('.chat-form');
                    if (form) {
                      const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
                      form.dispatchEvent(submitEvent);
                    }
                  }
                }, 100);
              }
            }
          });
        });
      }
    }

    // Open chatbot
    document.body.classList.add('show-chatbot');
    
    // Optional: Add a subtle animation
    chatbotPopup.style.animation = 'slideUpFadeIn 0.3s ease';
  }

  // Track user activity
  function trackActivity() {
    lastActivityTime = Date.now();
    
    // If chatbot is open and user is active, don't auto-open again
    if (document.body.classList.contains('show-chatbot')) {
      isUserInteracting = true;
      return;
    }

    // Reset timer on any activity
    resetInactivityTimer();
  }

  // Initialize chatbot auto-open functionality
  function initChatbotAutoOpen() {
    // Ensure chatbot starts closed
    document.body.classList.remove('show-chatbot');
    hasAutoOpened = false;
    isUserInteracting = false;

    // Track scroll events
    let scrollTimeout;
    window.addEventListener('scroll', function() {
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        // User stopped scrolling
        resetInactivityTimer();
      }, 300); // Wait 300ms after scroll stops
    }, { passive: true });

    // Track mouse movement (but with debounce)
    let mouseMoveTimeout;
    document.addEventListener('mousemove', function() {
      clearTimeout(mouseMoveTimeout);
      mouseMoveTimeout = setTimeout(() => {
        trackActivity();
      }, 500); // Debounce mouse movement
    }, { passive: true });

    // Track clicks
    document.addEventListener('click', trackActivity, { passive: true });

    // Track keyboard input
    document.addEventListener('keydown', trackActivity, { passive: true });

    // Track page navigation (for SPA or regular navigation)
    let navigationTimeout;
    const originalPushState = history.pushState;
    const originalReplaceState = history.replaceState;

    history.pushState = function() {
      originalPushState.apply(history, arguments);
      clearTimeout(navigationTimeout);
      navigationTimeout = setTimeout(() => {
        hasAutoOpened = false; // Reset on navigation
        resetInactivityTimer();
      }, 500);
    };

    history.replaceState = function() {
      originalReplaceState.apply(history, arguments);
      clearTimeout(navigationTimeout);
      navigationTimeout = setTimeout(() => {
        hasAutoOpened = false; // Reset on navigation
        resetInactivityTimer();
      }, 500);
    };

    // Track page visibility (when user switches tabs)
    document.addEventListener('visibilitychange', function() {
      if (document.hidden) {
        // Page is hidden, clear timer
        if (inactivityTimer) {
          clearTimeout(inactivityTimer);
          inactivityTimer = null;
        }
      } else {
        // Page is visible again, reset timer
        hasAutoOpened = false;
        resetInactivityTimer();
      }
    });

    // Start timer after initial page load delay
    setTimeout(() => {
      resetInactivityTimer();
    }, 2000); // Wait 2 seconds after page load before starting timer

    // Handle manual chatbot close - reset auto-open flag after a delay
    const closeChatbotBtn = document.querySelector('#close-chatbot');
    const chatbotToggler = document.querySelector('#chatbot-toggler');
    
    if (closeChatbotBtn) {
      closeChatbotBtn.addEventListener('click', function() {
        setTimeout(() => {
          if (!document.body.classList.contains('show-chatbot')) {
            hasAutoOpened = false;
            isUserInteracting = false;
          }
        }, 1000);
      });
    }

    if (chatbotToggler) {
      chatbotToggler.addEventListener('click', function() {
        if (document.body.classList.contains('show-chatbot')) {
          isUserInteracting = true;
        } else {
          setTimeout(() => {
            hasAutoOpened = false;
            isUserInteracting = false;
          }, 1000);
        }
      });
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChatbotAutoOpen);
  } else {
    initChatbotAutoOpen();
  }

  // Re-initialize on page navigation (for SPAs)
  window.addEventListener('popstate', function() {
    setTimeout(() => {
      hasAutoOpened = false;
      resetInactivityTimer();
    }, 500);
  });

})();

