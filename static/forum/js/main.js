// API Base URL
const API_BASE_URL = '/forum/api';

// Get CSRF token for Django
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// Submit query to API
async function submitQuery() {
    const queryInput = document.getElementById('userQuery');
    const query = queryInput.value.trim();
    
    // Clear previous validation errors
    clearValidationError();
    
    // Validate query
    if (!query) {
        showValidationError('Please enter your question before submitting! 💬');
        queryInput.focus();
        return;
    }
    
    if (query.length < 10) {
        showValidationError('Please provide a more detailed question (at least 10 characters). 📝');
        queryInput.focus();
        return;
    }
    
    if (query.length > 1000) {
        showValidationError('Your question is too long. Please limit it to 1000 characters. ✂️');
        queryInput.focus();
        return;
    }

    // Clear any previous response
    document.getElementById('aiResponse').innerHTML = '';
    
    // Show typing indicator
    document.getElementById('typingIndicator').style.display = 'block';
    document.getElementById('aiResponse').style.display = 'none';

    try {
        // Submit query to API
        const response = await fetch(`${API_BASE_URL}/queries/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({
                question: query
            })
        });

        if (!response.ok) {
            // Try to get error message from response
            let errorMessage = 'Failed to submit query';
            try {
                const errorData = await response.json();
                if (errorData.error) {
                    errorMessage = errorData.error;
                }
            } catch (e) {
                // If response is not JSON, use status text
                errorMessage = response.statusText || 'Failed to submit query';
            }
            
            // Log detailed error to console
            console.error('❌ Query Submission Failed');
            console.error('Status:', response.status, response.statusText);
            console.error('Error Message:', errorMessage);
            
            throw new Error(errorMessage);
        }

        const data = await response.json();
        
        // Check if response contains an error
        if (data.error) {
            console.error('❌ API Returned Error:', data.error);
            displayError(data.error || 'Failed to get response. Please try again.');
            return;
        }
        
        // Check if response is already available
        if (data.response && data.response.response_text) {
            let responseText = data.response.response_text;
            // Clean markdown code blocks if present
            responseText = responseText.replace(/```html\n?/g, '').replace(/```\n?/g, '');
            displayAIResponse(responseText);
            // Refresh popular queries after successful submission
            loadPopularQueries();
            loadTrendingQueries();
            loadInitialData(); // Refresh statistics
        } else if (data.id) {
            // Wait for response (polling)
            await waitForResponse(data.id);
            // Refresh after getting response
            loadPopularQueries();
            loadTrendingQueries();
            loadInitialData();
        } else {
            throw new Error('No response data received');
        }
        
    } catch (error) {
        // Enhanced error logging
        console.error('❌ Error in submitQuery:');
        console.error('Error Type:', error.name);
        console.error('Error Message:', error.message);
        console.error('Full Error Object:', error);
        
        // Show user-friendly error message
        const userMessage = error.message && error.message !== 'Failed to submit query' 
            ? error.message 
            : 'Failed to get response. Please try again.';
        displayError(userMessage);
    }
}

// Wait for AI response
async function waitForResponse(queryId) {
    const maxAttempts = 30;
    let attempts = 0;
    
    while (attempts < maxAttempts) {
        try {
            const response = await fetch(`${API_BASE_URL}/queries/${queryId}/response/`);
            
            if (response.ok) {
                const data = await response.json();
                
                // Check if response contains an error
                if (data.error) {
                    console.error('❌ API Returned Error in waitForResponse:', data.error);
                    displayError(data.error || 'Failed to get response. Please try again.');
                    return;
                }
                
                let responseText = data.response_text || '';
                // Clean markdown code blocks if present
                responseText = responseText.replace(/```html\n?/g, '').replace(/```\n?/g, '');
                displayAIResponse(responseText);
                return;
            } else if (response.status === 404) {
                // Still processing, wait and retry
                await new Promise(resolve => setTimeout(resolve, 1000));
                attempts++;
            } else {
                // Try to get error message from response
                let errorMessage = 'Failed to get response';
                try {
                    const errorData = await response.json();
                    if (errorData.error) {
                        errorMessage = errorData.error;
                    }
                } catch (e) {
                    errorMessage = response.statusText || 'Failed to get response';
                }
                
                // Log detailed error
                console.error('❌ Response Polling Failed');
                console.error('Status:', response.status, response.statusText);
                console.error('Error Message:', errorMessage);
                
                throw new Error(errorMessage);
            }
        } catch (error) {
            // Enhanced error logging
            console.error('❌ Error in waitForResponse:');
            console.error('Error Type:', error.name);
            console.error('Error Message:', error.message);
            console.error('Full Error Object:', error);
            
            // Show user-friendly error message
            const userMessage = error.message && error.message !== 'Failed to get response'
                ? error.message
                : 'Failed to get response. Please try again.';
            displayError(userMessage);
            return;
        }
    }
    
    displayError('Response timeout. Please try again.');
}

// Display AI response
function displayAIResponse(responseText, isWelcomeMessage = false) {
    document.getElementById('typingIndicator').style.display = 'none';
    const responseDiv = document.getElementById('aiResponse');
    
    // For welcome message, don't add the "AI Expert Response" header
    if (isWelcomeMessage) {
        responseDiv.innerHTML = responseText;
    } else {
        // For actual AI responses, add the header
        responseDiv.innerHTML = `
            <h3><i class="fas fa-robot"></i> AI Expert Response</h3>
            <div>
                ${responseText}
            </div>
        `;
    }
    responseDiv.style.display = 'block';
}

// Display error
function displayError(message) {
    document.getElementById('typingIndicator').style.display = 'none';
    const responseDiv = document.getElementById('aiResponse');
    responseDiv.innerHTML = `
        <div class="error-message">
            <h3><i class="fas fa-exclamation-triangle"></i> Error</h3>
            <p>${message}</p>
        </div>
    `;
    responseDiv.style.display = 'block';
}

// Show validation error (styled message near input)
function showValidationError(message) {
    // Remove any existing validation error
    clearValidationError();
    
    const queryInput = document.getElementById('userQuery');
    if (!queryInput) return;
    
    // Create validation error element
    const errorDiv = document.createElement('div');
    errorDiv.id = 'queryValidationError';
    errorDiv.className = 'validation-error';
    errorDiv.innerHTML = `
        <div class="validation-error-content">
            <i class="fas fa-info-circle"></i>
            <span>${message}</span>
        </div>
    `;
    
    // Insert after the input field or its container
    const queryContainer = queryInput.closest('.query-input-area') || queryInput.parentElement;
    if (queryContainer) {
        // Insert after the input field within the container
        const submitBtn = queryContainer.querySelector('.submit-btn');
        if (submitBtn) {
            queryContainer.insertBefore(errorDiv, submitBtn);
        } else {
            queryContainer.appendChild(errorDiv);
        }
    } else {
        // Fallback: insert after input
        queryInput.insertAdjacentElement('afterend', errorDiv);
    }
    
    // Add error styling to input
    queryInput.classList.add('input-error');
    
    // Scroll to error for better visibility
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        clearValidationError();
    }, 5000);
}

// Clear validation error
function clearValidationError() {
    const errorDiv = document.getElementById('queryValidationError');
    if (errorDiv) {
        errorDiv.remove();
    }
    
    const queryInput = document.getElementById('userQuery');
    if (queryInput) {
        queryInput.classList.remove('input-error');
    }
}

// Quick query function - just fills input field
function quickQuery(question) {
    // Only set the question in the input field, don't submit
    document.getElementById('userQuery').value = question;
    
    // Clear any previous response (including welcome message)
    document.getElementById('aiResponse').innerHTML = '';
    document.getElementById('aiResponse').style.display = 'none';
    document.getElementById('typingIndicator').style.display = 'none';
    
    // Clear any validation errors
    clearValidationError();
    
    // Scroll to input area for better UX
    document.querySelector('.query-input-area').scrollIntoView({ behavior: 'smooth', block: 'start' });
    
    // Focus on the input field
    document.getElementById('userQuery').focus();
}

// Show stored answer from database
function showStoredAnswer(question, responseText) {
    // Fill the input field with the question
    document.getElementById('userQuery').value = question;
    
    // Clean markdown code blocks if present
    let cleanedResponse = responseText.replace(/```html\n?/g, '').replace(/```\n?/g, '');
    
    // Display the stored answer
    displayAIResponse(cleanedResponse);
    
    // Scroll to response area for better UX
    document.querySelector('.query-input-area').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Switch category
function switchCategory(category, element) {
    // Update active tab
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Activate the clicked tab
    if (element) {
        element.classList.add('active');
    } else {
        // Fallback: find tab by category
        const tabs = document.querySelectorAll('.category-tab');
        tabs.forEach(tab => {
            const text = tab.textContent.trim().toLowerCase();
            if ((category === 'all' && text === 'all topics') ||
                (category === 'admission' && text === 'admission') ||
                (category === 'visa' && text.includes('visa')) ||
                (category === 'finance' && text.includes('finance')) ||
                (category === 'accommodation' && text === 'accommodation') ||
                (category === 'work' && text.includes('work')) ||
                (category === 'predeparture' && text.includes('pre-departure')) ||
                (category === 'country' && text.includes('country'))) {
                tab.classList.add('active');
            }
        });
    }
    
    // Load category-specific queries
    loadCategoryQueries(category);
}

// Load queries by category
async function loadCategoryQueries(category) {
    try {
        // Build URL with category filter
        let url = `${API_BASE_URL}/popular-queries/`;
        if (category && category !== 'all') {
            url += `?category=${category}`;
        }
        
        const response = await fetch(url);
        if (response.ok) {
            const queries = await response.json();
            // If no queries for this category, show message
            if (queries.length === 0 && category !== 'all') {
                const container = document.getElementById('popularQueries');
                if (container) {
                    container.innerHTML = '<div style="text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; border-radius: 8px; margin: 20px 0;"><i class="fas fa-inbox" style="font-size: 32px; color: #ccc; margin-bottom: 10px; display: block;"></i>No questions available for this category yet.<br><small style="color: #999;">Try asking a question to get started!</small></div>';
                }
            } else {
                displayPopularQueries(queries);
            }
        }
    } catch (error) {
        console.error('Error loading category queries:', error);
        loadPopularQueries(); // Fallback to all queries
    }
}

// Load categories and statistics on page load
async function loadInitialData() {
    try {
        // Load categories
        const categoriesResponse = await fetch(`${API_BASE_URL}/categories/`);
        if (categoriesResponse.ok) {
            const categories = await categoriesResponse.json();
            // Categories are already in HTML, but can be updated dynamically if needed
        }
        
        // Load user progress first to check if user is authenticated
        let userAuthenticated = false;
        try {
            const progressResponse = await fetch(`${API_BASE_URL}/user-progress/`);
            if (progressResponse.ok) {
                const progress = await progressResponse.json();
                userAuthenticated = progress.is_authenticated === true;
                
                if (userAuthenticated) {
                    // User is logged in - show user-specific progress
                    updateProgressTitle('Your Progress');
                    updateUserProgress(progress);
                } else {
                    // User is not logged in - show platform-wide statistics
                    updateProgressTitle('Overall Statistics');
                }
            }
        } catch (error) {
            // Error loading user progress, treat as not authenticated
            userAuthenticated = false;
            updateProgressTitle('Overall Statistics');
        }
        
        // If user is not logged in, show platform-wide statistics
        if (!userAuthenticated) {
            const statsResponse = await fetch(`${API_BASE_URL}/statistics/`);
            if (statsResponse.ok) {
                const stats = await statsResponse.json();
                updateStatistics(stats);
            }
        }
        
        // Load popular queries
        loadPopularQueries();
        
        // Load trending queries
        loadTrendingQueries();
        
        // Load AI Features
        loadAIFeatures();
        
        // Load AI Capabilities
        loadAICapabilities();
    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

// Load AI Features (only if not already loaded server-side)
async function loadAIFeatures() {
    const container = document.getElementById('aiFeatures');
    if (!container) return;
    
    // Check if features are already rendered server-side
    const existingFeatures = container.querySelectorAll('li');
    if (existingFeatures.length > 0 && !container.querySelector('li[style*="Loading"]')) {
        // Features already loaded server-side, skip
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/ai-features/`);
        if (response.ok) {
            const features = await response.json();
            displayAIFeatures(features);
        }
    } catch (error) {
        console.error('Error loading AI features:', error);
    }
}

// Display AI Features
function displayAIFeatures(features) {
    const container = document.getElementById('aiFeatures');
    if (!container) return;
    
    container.innerHTML = '';
    
    // If no features from database, show message
    if (!features || features.length === 0) {
        container.innerHTML = '<li style="color: #999; font-style: italic;">No features configured yet. Admin should add features in the database.</li>';
        return;
    }
    
    features.forEach(feature => {
        const li = document.createElement('li');
        const icon = feature.icon || 'fas fa-check-circle';
        
        // If feature has a link, make it clickable and open in new tab
        if (feature.link_url && feature.link_url.trim()) {
            li.innerHTML = `<a href="${feature.link_url}" class="feature-link" title="${feature.description || feature.name}" target="_blank" rel="noopener noreferrer"><i class="${icon}"></i> ${feature.name}</a>`;
            li.style.cursor = 'pointer';
        } else {
            li.innerHTML = `<i class="${icon}"></i> ${feature.name}`;
        }
        
        container.appendChild(li);
    });
}

// Load AI Capabilities (only if not already loaded server-side)
async function loadAICapabilities() {
    const container = document.getElementById('aiCapabilities');
    if (!container) return;
    
    // Check if capabilities are already rendered server-side
    const existingCapabilities = container.querySelectorAll('li');
    if (existingCapabilities.length > 0 && !container.querySelector('li[style*="Loading"]')) {
        // Capabilities already loaded server-side, skip
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/ai-capabilities/`);
        if (response.ok) {
            const capabilities = await response.json();
            displayAICapabilities(capabilities);
        }
    } catch (error) {
        console.error('Error loading AI capabilities:', error);
    }
}

// Display AI Capabilities
function displayAICapabilities(capabilities) {
    const container = document.getElementById('aiCapabilities');
    if (!container) return;
    
    container.innerHTML = '';
    
    // If no capabilities from database, show message
    if (!capabilities || capabilities.length === 0) {
        container.innerHTML = '<li style="color: #999; font-style: italic;">No capabilities configured yet. Admin should add capabilities in the database.</li>';
        return;
    }
    
    capabilities.forEach(capability => {
        const li = document.createElement('li');
        const icon = capability.icon || 'fas fa-brain';
        
        // If capability has a link, make it clickable and open in new tab
        if (capability.link_url && capability.link_url.trim()) {
            li.innerHTML = `<a href="${capability.link_url}" class="feature-link" title="${capability.description || capability.name}" target="_blank" rel="noopener noreferrer"><i class="${icon}"></i> ${capability.name}</a>`;
            li.style.cursor = 'pointer';
        } else {
            li.innerHTML = `<i class="${icon}"></i> ${capability.name}`;
        }
        
        container.appendChild(li);
    });
}

// Update statistics display (platform-wide stats)
function updateStatistics(stats) {
    // Format and update statistics - all from database
    const totalQueries = document.getElementById('stat-total-queries');
    const accuracy = document.getElementById('stat-accuracy');
    const countries = document.getElementById('stat-countries');
    const responseTime = document.getElementById('stat-response-time');
    
    if (totalQueries) {
        totalQueries.textContent = stats.total_queries_formatted || formatNumber(stats.total_queries) || '0';
    }
    if (accuracy) {
        accuracy.textContent = `${stats.accuracy_rate || 0}%`;
    }
    if (countries) {
        countries.textContent = stats.countries_covered || 0;
    }
    if (responseTime) {
        responseTime.textContent = stats.response_time || '<1s';
    }
}

// Update progress title
function updateProgressTitle(title) {
    const titleElement = document.getElementById('progress-title');
    if (titleElement) {
        titleElement.textContent = title;
    }
}

// Update user progress display (user-specific stats)
function updateUserProgress(progress) {
    // User progress stats use different IDs than platform stats
    const careersExplored = document.getElementById('stat-total-queries');
    const streamMatch = document.getElementById('stat-accuracy');
    const skillsIdentified = document.getElementById('stat-countries');
    const universitiesViewed = document.getElementById('stat-response-time');
    
    // Update user progress stats if elements exist (these are in the sidebar)
    if (careersExplored && progress.careers_explored !== undefined) {
        careersExplored.textContent = progress.careers_explored || 0;
    }
    if (streamMatch && progress.stream_match !== undefined) {
        streamMatch.textContent = `${progress.stream_match || 0}%`;
    }
    if (skillsIdentified && progress.skills_identified !== undefined) {
        skillsIdentified.textContent = progress.skills_identified || 0;
    }
    if (universitiesViewed && progress.universities_viewed !== undefined) {
        universitiesViewed.textContent = progress.universities_viewed || 0;
    }
}

// Format numbers for display
function formatNumber(num) {
    if (num >= 1_000_000) {
        return `${(num / 1_000_000).toFixed(1)}M`;
    } else if (num >= 1_000) {
        return `${(num / 1_000).toFixed(1)}K`;
    }
    return num.toString();
}

// Load popular queries
async function loadPopularQueries() {
    try {
        const response = await fetch(`${API_BASE_URL}/popular-queries/`);
        if (response.ok) {
            const queries = await response.json();
            displayPopularQueries(queries);
        }
    } catch (error) {
        console.error('Error loading popular queries:', error);
    }
}

// Display popular queries
function displayPopularQueries(queries) {
    const container = document.getElementById('popularQueries');
    if (!container) return;
    
    container.innerHTML = '';
    
    // If no queries from database, show message
    if (!queries || queries.length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; border-radius: 8px; margin: 20px 0;"><i class="fas fa-inbox" style="font-size: 32px; color: #ccc; margin-bottom: 10px; display: block;"></i>No questions available yet.<br><small style="color: #999;">Be the first to ask a career question!</small></div>';
        return;
    }
    
    // Deduplicate queries on frontend (safety measure)
    const seenQuestions = new Set();
    const uniqueQueries = [];
    
    queries.forEach(query => {
        // Normalize question for comparison (case-insensitive, trimmed)
        const normalizedQuestion = query.question.toLowerCase().trim();
        
        // Skip if we've already seen this question
        if (seenQuestions.has(normalizedQuestion)) {
            return;
        }
        
        seenQuestions.add(normalizedQuestion);
        uniqueQueries.push(query);
    });
    
    // Display only unique queries in accordion style
    uniqueQueries.forEach((query, index) => {
        const categoryEmoji = getCategoryEmoji(query.category_slug);
        const accordionItem = document.createElement('div');
        accordionItem.className = 'accordion-item';
        accordionItem.id = `accordion-${index}`;
        
        const hasResponse = query.response_text && query.response_text.trim();
        
        // Clean response text for display
        let cleanedResponse = '';
        if (hasResponse) {
            cleanedResponse = query.response_text.replace(/```html\n?/g, '').replace(/```\n?/g, '').trim();
        }
        
        // Get icon based on category
        const categoryIcon = getCategoryIcon(query.category_slug);
        
        accordionItem.innerHTML = `
            <div class="accordion-header" onclick="toggleAccordion(${index})">
                <div class="accordion-question">
                    <div class="accordion-icon-left">${categoryIcon}</div>
                    <div class="accordion-question-content">
                        <div class="query-text">${query.question}</div>
                        <div class="query-category">${categoryEmoji} ${query.category} • ${query.country_emoji} ${query.country}</div>
                    </div>
                </div>
                <span class="accordion-toggle-icon" id="icon-${index}">+</span>
            </div>
            <div class="accordion-content" id="content-${index}">
                ${hasResponse ? `
                    <div class="accordion-answer">
                        ${cleanedResponse}
                    </div>
                ` : `
                    <div class="accordion-no-answer">
                        <p>No answer available yet. Click to ask this question!</p>
                        <button class="ask-question-btn" onclick="event.stopPropagation(); quickQuery('${query.question.replace(/'/g, "\\'")}');">
                            <i class="fas fa-paper-plane"></i> Ask This Question
                        </button>
                    </div>
                `}
            </div>
        `;
        
        container.appendChild(accordionItem);
    });
}

// Get icon for category
function getCategoryIcon(slug) {
    const icons = {
        'admission': '📚',
        'visa': '📋',
        'finance': '💰',
        'accommodation': '🏠',
        'work': '💼',
        'predeparture': '✈️',
        'country': '🌍',
        'stem': '🔬',
        'commerce': '💼',
        'arts': '🎨',
        'vocational': '🛠️',
        'emerging': '🚀',
        'studyabroad': '🌍'
    };
    return icons[slug] || '❓';
}

// Toggle accordion expand/collapse
function toggleAccordion(index) {
    const accordionItem = document.getElementById(`accordion-${index}`);
    const content = document.getElementById(`content-${index}`);
    const icon = document.getElementById(`icon-${index}`);
    
    if (!accordionItem || !content || !icon) return;
    
    // Toggle active class
    const isActive = accordionItem.classList.contains('active');
    
    if (isActive) {
        // Collapse
        accordionItem.classList.remove('active');
        icon.textContent = '+';
    } else {
        // Expand
        accordionItem.classList.add('active');
        icon.textContent = '−';
    }
}

// Load trending queries
async function loadTrendingQueries() {
    try {
        const response = await fetch(`${API_BASE_URL}/trending/`);
        if (response.ok) {
            const queries = await response.json();
            displayTrendingQueries(queries);
        }
    } catch (error) {
        console.error('Error loading trending queries:', error);
    }
}

// Display trending queries
function displayTrendingQueries(queries) {
    const container = document.getElementById('trendingQueries');
    if (!container) return;
    
    container.innerHTML = '';
    
    // If no trending queries from database, show message
    if (!queries || queries.length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 20px; color: #666; font-size: 13px; background: #f8f9fa; border-radius: 8px;"><i class="fas fa-info-circle" style="margin-right: 5px;"></i>No trending questions yet. Ask a question to get started!</div>';
        return;
    }
    
    // Deduplicate queries on frontend (safety measure)
    const seenQuestions = new Set();
    const uniqueQueries = [];
    
    queries.forEach(query => {
        // Normalize question for comparison (case-insensitive, trimmed)
        const normalizedQuestion = query.question.toLowerCase().trim();
        
        // Skip if we've already seen this question
        if (seenQuestions.has(normalizedQuestion)) {
            return;
        }
        
        seenQuestions.add(normalizedQuestion);
        uniqueQueries.push(query);
    });
    
    // Display only unique queries
    uniqueQueries.forEach(query => {
        const tagEmoji = getTagEmoji(query.tag);
        const queryItem = document.createElement('div');
        queryItem.className = 'query-item';
        if (query.id) {
            // If response exists, show it on click; otherwise just fill input
            if (query.response_text && query.response_text.trim()) {
                queryItem.onclick = () => showStoredAnswer(query.question, query.response_text);
            } else {
                queryItem.onclick = () => quickQuery(query.question);
            }
            queryItem.style.cursor = 'pointer';
        }
        queryItem.innerHTML = `
            <div class="query-text">${query.question}</div>
            <div class="query-category">${tagEmoji} ${query.tag}</div>
        `;
        container.appendChild(queryItem);
    });
}

// Get category emoji
function getCategoryEmoji(slug) {
    const emojis = {
        'admission': '📚',
        'visa': '📋',
        'finance': '💰',
        'accommodation': '🏠',
        'work': '💼',
        'predeparture': '✈️',
        'country': '🌍',
        'stem': '🔬',
        'commerce': '💼',
        'arts': '🎨',
        'vocational': '🛠️',
        'emerging': '🚀',
        'studyabroad': '🌍'
    };
    return emojis[slug] || '📝';
}

// Get tag emoji
function getTagEmoji(tag) {
    if (tag.includes('Hot Topic')) return '🔥';
    if (tag.includes('Urgent')) return '⏰';
    if (tag.includes('Free')) return '💰';
    return '📌';
}

// Show welcome message
function showWelcomeMessage() {
    const welcomeResponse = `
        <h3><i class="fas fa-hand-peace"></i> Welcome to TopTeen Career AI!</h3>
        <p>I'm your personal AI career counselor, specially designed for high school students like you! Ask me about:</p>
        <ul>
            <li>Stream selection after 10th</li>
            <li>Career options in different streams</li>
            <li>College and course guidance</li>
            <li>Entrance exam preparation</li>
            <li>Study abroad opportunities</li>
            <li>Emerging careers and future jobs</li>
            <li>Part-time work options</li>
            <li>Skill development paths</li>
        </ul>
        <p><strong>Simply type your career question above and get instant, personalized guidance!</strong></p>
        <p><small>💡 Tip: I consider your grade, stream, and psychometric assessment results to give you the best advice!</small></p>
    `;
    displayAIResponse(welcomeResponse, true); // Pass true to indicate it's a welcome message
}

// Initialize on page load
window.addEventListener('load', function() {
    loadInitialData();
    
    // Show welcome message immediately on page load
    showWelcomeMessage();
});

// Auto-suggestions as user types (optional)
document.getElementById('userQuery').addEventListener('input', function() {
    const query = this.value.toLowerCase();
    if (query.length > 3) {
        // Can implement auto-suggestion logic here
        console.log('Searching for suggestions:', query);
    }
});

// Submit query on Enter key press (Shift+Enter for new line)
document.getElementById('userQuery').addEventListener('keydown', function(e) {
    // Submit on Enter, but allow Shift+Enter for new lines
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault(); // Prevent default new line behavior
        submitQuery();
    }
});
