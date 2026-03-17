document.addEventListener('DOMContentLoaded', function() {
  const searchToggles = document.querySelectorAll('.search-toggle, #searchToggle');
  const searchContainer = document.querySelector('.search-container');
  const searchInput = document.querySelector('.search-input');
  const searchClose = document.querySelector('.search-close');
  const searchBtn = document.querySelector('.search-btn');
  const searchResults = document.querySelector('.search-results');
  const isMobile = window.innerWidth < 768;
  
  // Only initialize search if elements exist
  if (!searchContainer || !searchInput) {
    return;
  }

  if (!searchContainer || searchToggles.length === 0) {
    console.warn('Search elements not found in the DOM');
    return;
  }

  // Ensure search box is always empty on load (no pre-filled text)
  searchInput.value = '';

  let searchTimeout = null;
  
  // Toggle search container
  searchToggles.forEach(toggle => {
    toggle.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      // Close mobile menu if open (for better UX on mobile)
      const navbarCollapse = document.querySelector('.navbar-collapse.show');
      if (navbarCollapse && isMobile) {
        const bsCollapse = new bootstrap.Collapse(navbarCollapse);
        bsCollapse.hide();
      }
      
      // Toggle search container
      searchContainer.classList.toggle('active');
      
      if (searchContainer.classList.contains('active')) {
        // Focus the input after a short delay to ensure it's visible
        setTimeout(() => {
          searchInput.focus();
        }, 100);
      }
    });
  });
  
  // Close search container when clicking outside
  document.addEventListener('click', function(e) {
    const isClickInsideSearch = searchContainer.contains(e.target);
    const isClickOnToggle = Array.from(searchToggles).some(toggle => toggle.contains(e.target));
    
    if (!isClickInsideSearch && !isClickOnToggle && searchContainer.classList.contains('active')) {
      searchContainer.classList.remove('active');
      searchResults.innerHTML = '';
      searchInput.value = '';
    }
  });
  
  // Close search container with close button
  if (searchClose) {
    searchClose.addEventListener('click', function(e) {
      e.preventDefault();
      searchContainer.classList.remove('active');
      searchResults.innerHTML = '';
      searchInput.value = '';
    });
  }
  
  // Search functionality with AJAX
  function performSearch(query) {
    if (query.length < 2) {
      searchResults.innerHTML = '';
      return;
    }
    
    // Show loading state
    searchResults.innerHTML = '<div class="p-3 text-center"><i class="bx bx-loader-alt bx-spin"></i> Searching...</div>';
    
    // Make AJAX request to search endpoint
    fetch(`/searchand-explore-result/?search=${encodeURIComponent(query)}`)
      .then(response => response.text())
      .then(html => {
        // Parse the HTML response
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        
        // Extract search results from the response
        const results = extractSearchResults(doc, query);
        displayResults(results, query);
      })
      .catch(error => {
        console.error('Search error:', error);
        searchResults.innerHTML = '<div class="p-3 text-center text-danger"><i class="bx bx-error"></i> Error performing search. Please try again.</div>';
      });
  }
  
  // Extract search results from HTML response
  function extractSearchResults(doc, query) {
    const results = {
      careers: [],
      professions: [],
      videos: [],
      blogs: [],
      courses: [],
      colleges: [],
      entranceExams: []
    };
    
    // Extract careers
    const careerLinks = doc.querySelectorAll('a[href*="/careers/career/"]');
    careerLinks.forEach(link => {
      const name = link.textContent.trim();
      if (name.toLowerCase().includes(query.toLowerCase())) {
        results.careers.push({
          name: name,
          url: link.getAttribute('href'),
          type: 'career'
        });
      }
    });
    
    // Extract colleges
    const collegeLinks = doc.querySelectorAll('a[href*="/colleges/college/"]');
    collegeLinks.forEach(link => {
      const name = link.textContent.trim();
      if (name.toLowerCase().includes(query.toLowerCase())) {
        results.colleges.push({
          name: name,
          url: link.getAttribute('href'),
          type: 'college'
        });
      }
    });
    
    // Extract videos
    const videoLinks = doc.querySelectorAll('a[href*="/careers/video/"]');
    videoLinks.forEach(link => {
      const name = link.textContent.trim();
      if (name.toLowerCase().includes(query.toLowerCase())) {
        results.videos.push({
          name: name,
          url: link.getAttribute('href'),
          type: 'video'
        });
      }
    });
    
    // Extract courses (if any course links exist)
    const courseLinks = doc.querySelectorAll('a[href*="/skilllab/"]');
    courseLinks.forEach(link => {
      const name = link.textContent.trim();
      if (name.toLowerCase().includes(query.toLowerCase())) {
        results.courses.push({
          name: name,
          url: link.getAttribute('href'),
          type: 'course'
        });
      }
    });
    
    // Extract blogs
    const blogLinks = doc.querySelectorAll('a[href*="/blog/"]');
    blogLinks.forEach(link => {
      const name = link.textContent.trim();
      if (name.toLowerCase().includes(query.toLowerCase())) {
        results.blogs.push({
          name: name,
          url: link.getAttribute('href'),
          type: 'blog'
        });
      }
    });
    
    // Extract entrance exams (Entrance Test Prep - /entrance-test-prep/exam/...)
    const examLinks = doc.querySelectorAll('a[href*="/entrance-test-prep/exam/"]');
    examLinks.forEach(link => {
      const titleEl = link.querySelector('.search-result-title');
      const name = titleEl ? titleEl.textContent.trim() : link.textContent.trim();
      if (name && name.toLowerCase().includes(query.toLowerCase())) {
        results.entranceExams.push({
          name: name,
          url: link.getAttribute('href'),
          type: 'entranceExam'
        });
      }
    });
    
    return results;
  }
  
  // Search input event with debounce
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      const query = this.value.trim();
      
      // Clear previous timeout
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }
      
      // Set new timeout for debounce
      searchTimeout = setTimeout(() => {
        performSearch(query);
      }, 300);
    });
  }
  
  // Search button click
  if (searchBtn) {
    searchBtn.addEventListener('click', function(e) {
      e.preventDefault();
      const query = searchInput.value.trim();
      
      if (query.length < 2) {
        return;
      }
      
      // Navigate to full search results page
      window.location.href = `/searchand-explore-result/?search=${encodeURIComponent(query)}`;
    });
  }
  
  // Handle Enter key press
  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        const query = this.value.trim();
        
        if (query.length >= 2) {
          // Navigate to full search results page
          window.location.href = `/searchand-explore-result/?search=${encodeURIComponent(query)}`;
        }
      }
      
      // Close search on Escape key
      if (e.key === 'Escape') {
        searchContainer.classList.remove('active');
        searchResults.innerHTML = '';
        searchInput.value = '';
      }
    });
  }
  
  // Get selected filters
  function getSelectedFilters() {
    const checkboxes = document.querySelectorAll('.search-filter-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.value);
  }
  
  // Display search results
  function displayResults(results, query) {
    searchResults.innerHTML = '';
    
    // Get selected filters
    const selectedFilters = getSelectedFilters();
    
    // Filter results based on selected checkboxes
    const filteredResults = {};
    if (selectedFilters.includes('careers')) filteredResults.careers = results.careers;
    if (selectedFilters.includes('professions')) filteredResults.professions = results.professions;
    if (selectedFilters.includes('colleges')) filteredResults.colleges = results.colleges;
    if (selectedFilters.includes('videos')) filteredResults.videos = results.videos;
    if (selectedFilters.includes('blogs')) filteredResults.blogs = results.blogs;
    if (selectedFilters.includes('courses')) filteredResults.courses = results.courses;
    if (selectedFilters.includes('entranceExams')) filteredResults.entranceExams = results.entranceExams;
    
    const totalResults = Object.values(filteredResults).reduce((sum, arr) => sum + arr.length, 0);
    
    if (totalResults === 0) {
      if (selectedFilters.length === 0) {
        searchResults.innerHTML = '<div class="p-3 text-center"><i class="bx bx-info-circle"></i> Please select at least one filter</div>';
      } else {
        searchResults.innerHTML = '<div class="p-3 text-center"><i class="bx bx-search-alt-2"></i> No results found</div>';
      }
      return;
    }
    
    // Create result sections
    const resultSections = [];
    
    if (selectedFilters.includes('careers') && results.careers.length > 0) {
      resultSections.push({
        title: 'Careers',
        items: results.careers.slice(0, 5),
        icon: 'bx-briefcase-alt-2'
      });
    }
    
    if (selectedFilters.includes('professions') && results.professions.length > 0) {
      resultSections.push({
        title: 'Professions',
        items: results.professions.slice(0, 5),
        icon: 'bx-user-circle'
      });
    }
    
    if (selectedFilters.includes('colleges') && results.colleges.length > 0) {
      resultSections.push({
        title: 'Colleges',
        items: results.colleges.slice(0, 5),
        icon: 'bx-building-house'
      });
    }
    
    if (selectedFilters.includes('videos') && results.videos.length > 0) {
      resultSections.push({
        title: 'Videos',
        items: results.videos.slice(0, 5),
        icon: 'bx-video'
      });
    }
    
    if (selectedFilters.includes('blogs') && results.blogs.length > 0) {
      resultSections.push({
        title: 'Blogs',
        items: results.blogs.slice(0, 5),
        icon: 'bx-news'
      });
    }
    
    if (selectedFilters.includes('courses') && results.courses.length > 0) {
      resultSections.push({
        title: 'Courses',
        items: results.courses.slice(0, 5),
        icon: 'bx-book-reader'
      });
    }
    
    if (selectedFilters.includes('entranceExams') && results.entranceExams.length > 0) {
      resultSections.push({
        title: 'Entrance Exams',
        items: results.entranceExams.slice(0, 5),
        icon: 'bx-certification'
      });
    }
    
    // Display each section
    resultSections.forEach(section => {
      const sectionDiv = document.createElement('div');
      sectionDiv.className = 'search-result-section';
      sectionDiv.innerHTML = `<h5 class="search-section-title"><i class="bx ${section.icon}"></i> ${section.title}</h5>`;
      
      section.items.forEach(item => {
        const resultItem = document.createElement('div');
        resultItem.className = 'search-result-item';
        resultItem.innerHTML = `
          <a href="${item.url}" style="text-decoration: none; color: inherit;">
            <h4>${item.name}</h4>
          </a>
        `;
        
        resultItem.addEventListener('click', function() {
          window.location.href = item.url;
          searchContainer.classList.remove('active');
        });
        
        sectionDiv.appendChild(resultItem);
      });
      
      // Add "View all" link if there are more results
      if (section.items.length >= 5) {
        const viewAllLink = document.createElement('div');
        viewAllLink.className = 'search-view-all';
        viewAllLink.innerHTML = `<a href="/searchand-explore-result/?search=${encodeURIComponent(query)}" style="color: #5046e5; font-weight: 600;">View all ${section.title.toLowerCase()}...</a>`;
        sectionDiv.appendChild(viewAllLink);
      }
      
      searchResults.appendChild(sectionDiv);
    });
    
    // Add "View all results" link at the bottom
    const viewAllDiv = document.createElement('div');
    viewAllDiv.className = 'search-view-all-results';
    viewAllDiv.innerHTML = `<a href="/searchand-explore-result/?search=${encodeURIComponent(query)}" style="color: #5046e5; font-weight: 600; display: block; text-align: center; padding: 10px; border-top: 1px solid #e0e0e0; margin-top: 10px;">View all results</a>`;
    searchResults.appendChild(viewAllDiv);
  }
  
  // Handle filter checkbox changes
  const filterCheckboxes = document.querySelectorAll('.search-filter-checkbox');
  filterCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      // Count how many checkboxes are currently checked
      const checkedCount = document.querySelectorAll('.search-filter-checkbox:checked').length;
      
      // Prevent unchecking if it's the last checked checkbox
      if (!this.checked && checkedCount === 0) {
        this.checked = true;
        // Show a brief message to user
        const messageDiv = document.createElement('div');
        messageDiv.className = 'search-filter-warning';
        messageDiv.innerHTML = '<i class="bx bx-info-circle"></i> At least one filter must be selected';
        messageDiv.style.cssText = 'padding: 8px; background: #fff3cd; color: #856404; border-radius: 4px; margin-top: 8px; font-size: 12px; text-align: center;';
        
        // Remove any existing warning
        const existingWarning = searchContainer.querySelector('.search-filter-warning');
        if (existingWarning) {
          existingWarning.remove();
        }
        
        // Add warning after filters
        const filtersDiv = searchContainer.querySelector('.search-filters');
        if (filtersDiv) {
          filtersDiv.insertAdjacentElement('afterend', messageDiv);
          
          // Remove warning after 3 seconds
          setTimeout(() => {
            messageDiv.remove();
          }, 3000);
        }
        return;
      }
      
      // If there's a query, re-run the search with new filters
      const query = searchInput.value.trim();
      if (query.length >= 2) {
        performSearch(query);
      } else {
        // Clear results if no query
        searchResults.innerHTML = '';
      }
    });
  });
  
  // Handle window resize events to update mobile status
  window.addEventListener('resize', function() {
    const wasIsMobile = isMobile;
    const newIsMobile = window.innerWidth < 768;
    
    // If transitioning between mobile and desktop, reset search
    if (wasIsMobile !== newIsMobile) {
      searchContainer.classList.remove('active');
      searchResults.innerHTML = '';
      searchInput.value = '';
    }
  });
  
  // Log initialization success
  console.log('Global search functionality initialized (search.js)');
});
