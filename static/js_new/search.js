document.addEventListener('DOMContentLoaded', function() {
  const searchToggle = document.getElementById('searchToggle');
  const searchContainer = document.querySelector('.search-container');
  const searchInput = document.querySelector('.search-input');
  const searchClose = document.querySelector('.search-close');
  const searchBtn = document.querySelector('.search-btn');
  const searchResults = document.querySelector('.search-results');
  const isMobile = window.innerWidth < 768;
  
  // Sample career data (replace with your actual career data or API call)
  const careerData = [
    { title: 'Software Developer', category: 'Information Technology', description: 'Design and develop software applications' },
    { title: 'Web Developer', category: 'Information Technology', description: 'Create and maintain websites' },
    { title: 'Data Scientist', category: 'Information Technology', description: 'Analyze and interpret complex data' },
    { title: 'Customer Service Representative', category: 'Business Management', description: 'Handle customer inquiries and complaints' },
    { title: 'Marketing Manager', category: 'Business Management', description: 'Develop marketing strategies' },
    { title: 'Human Resources Specialist', category: 'Human Services', description: 'Recruit and hire employees' },
    { title: 'Financial Analyst', category: 'Finance', description: 'Analyze financial data and trends' },
    { title: 'Nurse', category: 'Healthcare', description: 'Provide patient care' },
    { title: 'Teacher', category: 'Education', description: 'Educate students in various subjects' }
  ];
  
  // Toggle search container
  searchToggle.addEventListener('click', function(e) {
    e.preventDefault();
    e.stopPropagation(); // Prevent event bubbling
    
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
  
  // Close search container when clicking outside
  document.addEventListener('click', function(e) {
    if (!searchToggle.contains(e.target) && !searchContainer.contains(e.target)) {
      searchContainer.classList.remove('active');
    }
  });
  
  // Close search container with close button
  searchClose.addEventListener('click', function(e) {
    e.preventDefault();
    searchContainer.classList.remove('active');
  });
  
  // Search functionality
  searchInput.addEventListener('input', function() {
    const query = this.value.toLowerCase().trim();
    
    if (query.length < 2) {
      searchResults.innerHTML = '';
      return;
    }
    
    const filteredResults = careerData.filter(career => 
      career.title.toLowerCase().includes(query) || 
      career.category.toLowerCase().includes(query) ||
      career.description.toLowerCase().includes(query)
    );
    
    displayResults(filteredResults);
  });
  
  // Search button click
  searchBtn.addEventListener('click', function(e) {
    e.preventDefault();
    const query = searchInput.value.toLowerCase().trim();
    
    if (query.length < 2) {
      return;
    }
    
    const filteredResults = careerData.filter(career => 
      career.title.toLowerCase().includes(query) || 
      career.category.toLowerCase().includes(query) ||
      career.description.toLowerCase().includes(query)
    );
    
    displayResults(filteredResults);
  });
  
  // Handle form submission (prevent default and perform search)
  const searchForm = searchInput.closest('form');
  if (searchForm) {
    searchForm.addEventListener('submit', function(e) {
      e.preventDefault();
      searchBtn.click();
    });
  }
  
  // Display search results
  function displayResults(results) {
    searchResults.innerHTML = '';
    
    if (results.length === 0) {
      searchResults.innerHTML = '<div class="p-3 text-center"><i class="bx bx-search-alt-2"></i> No results found</div>';
      return;
    }
    
    results.forEach(result => {
      const resultItem = document.createElement('div');
      resultItem.className = 'search-result-item';
      resultItem.innerHTML = `
        <h4>${result.title}</h4>
        <p><span class="badge bg-blue text-white">${result.category}</span> ${result.description}</p>
      `;
      
      resultItem.addEventListener('click', function() {
        // Navigate to career details page or show modal
        // For example: window.location.href = `/careers/${result.title.toLowerCase().replace(/\s+/g, '-')}`;
        alert(`You selected: ${result.title}`);
        searchContainer.classList.remove('active');
      });
      
      searchResults.appendChild(resultItem);
    });
  }
  
  // Handle window resize events to update mobile status
  window.addEventListener('resize', function() {
    const wasIsMobile = isMobile;
    isMobile = window.innerWidth < 768;
    
    // If transitioning between mobile and desktop, reset search
    if (wasIsMobile !== isMobile) {
      searchContainer.classList.remove('active');
    }
  });
  
  // Add keyboard navigation for accessibility
  searchInput.addEventListener('keydown', function(e) {
    // Close search on Escape key
    if (e.key === 'Escape') {
      searchContainer.classList.remove('active');
    }
  });
});