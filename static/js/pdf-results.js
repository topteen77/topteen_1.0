// pdf-results.js - JavaScript for dynamic PDF results
// Global chart instance references
let personalityChartInstance = null;
let motivationChartInstance = null;
let careerChartInstance = null;
let aptitudeChartInstance = null;
// Utility functions
function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function getScoreLevel(score, maxScore = 5) {
  // console.log("score of the personality:", score);

  if (score >= 1 && score <= 17) {
    return 'low';
  } else if (score >= 18 && score <= 33) {
    return 'medium';
  } else if (score >= 34) {
    return 'high';
  } else {
    return 'unknown'; // for score <= 0 or invalid values
  }
}

// Main function to load test results
async function loadTestResults() {
  try {
    // First check if we have results in the Django context
    if (typeof window.testResults !== 'undefined' && window.testResults.length > 0) {
      console.log('Using test results from Django context:', window.testResults);
      window.testResults.forEach((result, index) => {
        processTestResult(result, index);
      });
      return;
    }

    // If not, try the API (this is the fallback method)
    console.log('No results in Django context, trying API...');
    const response = await fetch('/api/results/');
    const data = await response.json();

    if (!data.results || data.results.length === 0) {
      console.log('No test results found from API');
      return;
    }

    // Process each test result
    data.results.forEach((result, index) => {
      processTestResult(result, index);
    });

  } catch (error) {
    console.error('Error loading test results:', error);
  }
}


// Process individual test results
function processTestResult(result, index) {
  const testTitle = result.test_title.toLowerCase();

  if (testTitle.includes('personality')) {
    handlePersonalityResults(result, index);
  } else if (testTitle.includes('motivation')) {
    handleMotivationResults(result, index);
  } else if (testTitle.includes('career') || testTitle.includes('interest')) {
    handleCareerResults(result, index);
  } else if (testTitle.includes('aptitude') || result.test_id === 4) {
    handleAptitudeResults(result, index);
  }
}

// Handle Personality Test Results
function handlePersonalityResults(result, index) {
  const personalityPage = document.getElementById('personality-results-page');
  if (!personalityPage) return;

  personalityPage.style.display = 'block';

  const dimensionsContainer = document.getElementById('personality-dimensions');
  if (!dimensionsContainer) return;

  dimensionsContainer.innerHTML = '';

  // Process personality dimensions
  const dimensions = [];
  const labels = [];
  const scores = [];

  // Map dimension letters to full names
  const dimensionNames = {
    'H': 'Honesty-Humility',
    'E': 'Emotionality',
    'X': 'Extraversion',   // fixed typo "Xetraversion"
    'A': 'Agreeableness',
    'C': 'Conscientiousness',
    'O': 'Openness to Experience'
  };

  // enforce HEXACO order
  const hexacoOrder = ["H", "E", "X", "A", "C", "O"];

  for (const dim of hexacoOrder) {
    const data = result.result_data[dim];
    if (!data) continue;

    const score = data.score || 0;
    console.log("score", dim, score);

    const percentage = (score / 50) * 100; // 50 = max score per dimension (10 questions × 5 points)

    dimensions.push({
      code: dim,
      name: dimensionNames[dim] || `Dimension ${dim}`,
      score: score,
      percentage: percentage,
      level: getScoreLevel(score, 50) // pass correct max
    });

    labels.push(dim); // use full names instead of "Dimension X"
    scores.push(score);
  }

  // Sort dimensions by score (highest first)
  dimensions.sort((a, b) => parseFloat(b.score) - parseFloat(a.score));

  // Get top 3 and lowest dimension
  const topThree = dimensions.slice(0, 2);
  const lowest = dimensions[dimensions.length - 1];

  // Create HEXACO code from top 3
  const hexacoCode = topThree.map(dim => dim.code);

  // Display total time duration
  const timeDurationElement = document.createElement('div');
  timeDurationElement.className = 'time-duration-display';
  timeDurationElement.innerHTML = `
    <h3 style="color: #3F37C9; text-align: center; margin: 20px 0;">Total Time Duration : <strong>${result.duration_minutes} minutes </strong></h3>
  `;

  dimensionsContainer.appendChild(timeDurationElement);

  // Display HEXACO code
  const hexacoCodeElement = document.createElement('div');
  hexacoCodeElement.className = 'hexaco-code-display';
  hexacoCodeElement.innerHTML = `
    <h3 style="color: color: #362C64; text-align: center; margin: 20px 0;">Your HEXACO Code: <strong style="font-size: 25px;color: green;">${hexacoCode}</strong></h3>
  `;

  dimensionsContainer.appendChild(hexacoCodeElement);

  // Create section for top 3 dimensions
  const topSection = document.createElement('div');
  topSection.className = 'top-dimensions-section';
  topSection.innerHTML = '<h4 style="color: #3F37C9; margin: 15px 0;">Your Top 2 Personality Dimensions:</h4>';
  dimensionsContainer.appendChild(topSection);

  
  // Add top 3 dimension cards
  topThree.forEach((dim, index) => {
    const card = createPersonalityDimensionCard(dim, index + 1);
    topSection.appendChild(card);
  });

  // Create section for lowest dimension
  const lowestSection = document.createElement('div');
  lowestSection.className = 'lowest-dimension-section';
  lowestSection.innerHTML = '<h4 style="color: #c94837ff; margin: 20px 0 15px 0;">Your Lowest Dimension:</h4>';
  dimensionsContainer.appendChild(lowestSection);

  // Add lowest dimension card
  const lowestCard = createPersonalityDimensionCard(lowest, 'lowest');
  lowestSection.appendChild(lowestCard);

  // Create personality chart with all dimensions
  createPersonalityChart(labels, scores, index);
}


// Handle Motivation Test Results
function handleMotivationResults(result, index) {
  const motivationPage = document.getElementById('motivation-results-page');
  if (!motivationPage) return;

  motivationPage.style.display = 'block';

  const categoriesContainer = document.getElementById('motivation-categories');
  if (!categoriesContainer) return;

  categoriesContainer.innerHTML = '';

  const categories = Object.entries(result.category_counts || {});
  // Sort by count descending
  categories.sort((a, b) => b[1] - a[1]);
  if (categories.length === 0) return;

  const topCount = categories[0][1];

  // Find all categories with the top count
  const topCategories = categories.filter(([_, count]) => count === topCount);

  // Determine second priority only if there's a tie at the top
  let secondPriorityCategories = [];
  if (topCategories.length > 1) {
    const nextCount = categories.find(([_, count]) => count < topCount)?.[1];
    secondPriorityCategories = categories.filter(([_, count]) => count === nextCount);
  }

  // Total duration display
  const timeDurationElement = document.createElement('div');
  timeDurationElement.className = 'time-duration-display';
  timeDurationElement.innerHTML = `
    <h3 style="color: #3F37C9; text-align: center; margin: 20px 0;">
      Total Time Duration: <strong>${result.duration_minutes} minutes</strong>
    </h3>
  `;
  categoriesContainer.appendChild(timeDurationElement);

  // Top motivation display
  const topMotivationElement = document.createElement('div');
  topMotivationElement.className = 'top-motivation-display';
  topMotivationElement.innerHTML = `
    <h3 style="color: #362C64; text-align: center; margin: 20px 0;">
      Your Primary Motivation: <strong style="font-size: 25px; color: green;">${topCategories[0][0]}</strong>
    </h3>
  `;
  categoriesContainer.appendChild(topMotivationElement);

  // Render high priority cards
  topCategories.forEach(([category], i) => {
    const isTop = i === 0;
    const categoryCard = createMotivationCategoryCard(category, 'High Priority', isTop);
    categoriesContainer.appendChild(categoryCard);
  });

  // Render second priority cards only if needed
  secondPriorityCategories.forEach(([category]) => {
    const categoryCard = createMotivationCategoryCard(category, 'Second Priority', false);
    categoriesContainer.appendChild(categoryCard);
  });

  // Create motivation chart
  createMotivationChart(categories, index);
}

// Handle Career Interest Results
function handleCareerResults(result, index) {
  const careerPage = document.getElementById('career-results-page');
  if (!careerPage) return;

  careerPage.style.display = 'block';

  const dimensionsContainer = document.getElementById('career-dimensions');
  if (!dimensionsContainer) return;

  dimensionsContainer.innerHTML = '';

  // Log the result structure for debugging
  console.log('Career test result:', result);

  // Process career dimensions
  const dimensions = [];
  const labels = [];
  const scores = [];

  // Map RIASEC letters to full names
  const riasecNames = {
    'R': 'Realistic',
    'I': 'Investigative',
    'A': 'Artistic',
    'S': 'Social',
    'E': 'Enterprising',
    'C': 'Conventional'
  };

  // Try to get result data - handle different possible structures
  let resultData = result.result_data || {};
  console.log('Career result data:', resultData);

  // If result_data is empty or not in expected format, try to extract from responses
  if (Object.keys(resultData).length === 0 && result.responses) {
    console.log('Attempting to extract career data from responses');
    const responses = result.responses || [];
    
    // Try to find RIASEC data in responses
    for (const response of responses) {
      if (response.selected_answer && typeof response.selected_answer === 'object') {
        if (response.selected_answer.riasec_scores) {
          resultData = response.selected_answer.riasec_scores;
          console.log('Found RIASEC data in response.selected_answer.riasec_scores', resultData);
          break;
        } else if (response.selected_answer.dimensions) {
          resultData = response.selected_answer.dimensions;
          console.log('Found RIASEC data in response.selected_answer.dimensions', resultData);
          break;
        }
      }
      
      // Check if response itself has RIASEC data
      if (response.riasec_scores) {
        resultData = response.riasec_scores;
        console.log('Found RIASEC data in response.riasec_scores', resultData);
        break;
      }
    }
  }

  // Process the entries - handle different possible formats
  let entries = [];
  if (Array.isArray(resultData)) {
    // Handle array format
    entries = resultData.map(item => {
      const code = Object.keys(riasecNames).find(key => 
        riasecNames[key].toLowerCase() === item.name.toLowerCase()
      ) || item.code;
      return [code, { score: item.score }];
    });
  } else {
    // Handle object format
    entries = Object.entries(resultData);
  }

  // Filter out non-RIASEC entries if needed
  const validEntries = entries.filter(([dimension]) => {
    const cleanCode = dimension.replace(/\d+$/, ''); // Removes trailing numbers
    return Object.keys(riasecNames).includes(cleanCode);
  });

  // Use all entries if we have 6 or fewer, otherwise slice to exclude potential non-RIASEC entries
  const processedEntries = validEntries.length <= 6 ? validEntries : validEntries.slice(0, 6);

  // Process each dimension
  for (const [dimension, data] of processedEntries) {
    // Handle both object and primitive value formats
    const score = typeof data === 'object' ? (data.score || 0) : (parseInt(data) || 0);
    const cleanCode = dimension.replace(/\d+$/, ''); // Removes trailing numbers

    const name = riasecNames[cleanCode] || dimension;
    dimensions.push({
      code: cleanCode,
      name: name,
      score: score,
      percentage: (score / 25) * 100, // Assuming max score is 25 for RIASEC
      level: getScoreLevel(score, 25)
    });

    labels.push(cleanCode);
    scores.push(score);
  }

  // If we couldn't find any dimensions, create generic ones
  if (dimensions.length === 0) {
    console.log('No RIASEC dimensions found, creating generic ones');
    Object.entries(riasecNames).forEach(([code, name]) => {
      const randomScore = Math.floor(Math.random() * 25); // For demo purposes only
      dimensions.push({
        code: code,
        name: name,
        score: randomScore,
        percentage: (randomScore / 25) * 100,
        level: getScoreLevel(randomScore, 25)
      });
      labels.push(code);
      scores.push(randomScore);
    });
  }

  // Sort dimensions by score (highest first)
  dimensions.sort((a, b) => b.score - a.score);

  // Get top 3
  const topThree = dimensions.slice(0, 3);

  // Create RIASEC code from top 3
  const riasecCode = topThree.map(dim => dim.code).join('');

  // Display total time duration
  const timeDurationElement = document.createElement('div');
  timeDurationElement.className = 'time-duration-display';
  timeDurationElement.innerHTML = `
    <h3 style="color: #3F37C9; text-align: center; margin: 20px 0;">Total Time Duration : <strong>${result.duration_minutes} minutes </strong></h3>
  `;

  dimensionsContainer.appendChild(timeDurationElement);

  // Display RIASEC code
  const riasecCodeElement = document.createElement('div');
  riasecCodeElement.className = 'riasec-code-display';
  riasecCodeElement.innerHTML = `
    <h3 style="color: #362C64; text-align: center; margin: 20px 0;">Your RIASEC Code: <strong style="font-size: 25px;color: green;">${riasecCode}</strong></h3>
  `;
  dimensionsContainer.appendChild(riasecCodeElement);

  // Create section for top 3 interests
  const topSection = document.createElement('div');
  topSection.className = 'top-interests-section';
  topSection.innerHTML = '<h4 style="color: #3F37C9; margin: 15px 0;">Your Top 3 Career Interests:</h4>';
  dimensionsContainer.appendChild(topSection);

  // Create grid container for top 3 cards
  const gridContainer = document.createElement('div');
  gridContainer.className = 'top-interests-grid';
  gridContainer.style.display = 'grid';
  gridContainer.style.gridTemplateColumns = 'repeat(3, 1fr)';
  gridContainer.style.gap = '20px';
  topSection.appendChild(gridContainer);

  // Add top 3 interest cards with random border colors
  topThree.forEach((dim, index) => {
    const card = createCareerDimensionCard(dim, index + 1);

    // Generate random border color using a more consistent palette
    const colors = ['#3F37C9', '#4361EE', '#4895EF', '#4CC9F0', '#560BAD', '#7209B7'];
    const randomColor = colors[index % colors.length];
    card.style.border = `2px solid ${randomColor}`;
    card.style.borderRadius = '8px';

    gridContainer.appendChild(card);
  });

  // Create career chart (radar chart) with all dimensions
  createCareerChart(labels, scores, index);
}

// Handle Aptitude Test Results
function handleAptitudeResults(result, index) {
  const aptitudePage = document.getElementById('aptitude-results-page');
  if (!aptitudePage) return;

  aptitudePage.style.display = 'block';

  const timersectionsContainer = document.getElementById('timer-sections');
  if (!timersectionsContainer) return;

  timersectionsContainer.innerHTML = '';

  const sectionsContainer = document.getElementById('aptitude-sections');
  if (!sectionsContainer) return;

  sectionsContainer.innerHTML = '';

  // Log the result structure for debugging
  console.log('Aptitude test result:', result);
  
  const timerSection = document.createElement('div');
  timerSection.className = 'test-timing';

  const testTimer = `
    <p>
      <span style="font-weight: bold;">Total Test Time :</span>
      <span> ${result.duration_minutes} minutes</span>
    </p>`;

  timersectionsContainer.innerHTML = testTimer;

  const sectionScores = result.result_data || {};
  const responses = result.responses || [];
  // Process sections and categorize by performance
  const sectionsData = [];

  console.log('Section scores:', sectionScores);
  console.log('Responses:', responses);

  // Try multiple approaches to extract section data
  let sectionsDataRaw = null;
  let mainResponse = null;

  // Approach 1: Look for the standard structure
  mainResponse = responses.find(response =>
    response.selected_answer && response.selected_answer.sections
  );
  
  if (mainResponse && mainResponse.selected_answer.sections) {
    console.log('Found section data in standard location');
    sectionsDataRaw = mainResponse.selected_answer.sections;
  } 
  // Approach 2: Look for section data directly in responses
  else if (responses.length > 0 && responses[0].sections) {
    console.log('Found section data directly in responses');
    sectionsDataRaw = responses[0].sections;
  }
  // Approach 3: Check if responses contain section_data
  else {
    const sectionDataResponse = responses.find(response => 
      response.section_data || 
      (response.selected_answer && response.selected_answer.section_data)
    );
    
    if (sectionDataResponse) {
      if (sectionDataResponse.section_data) {
        console.log('Found section data in response.section_data');
        sectionsDataRaw = sectionDataResponse.section_data;
      } else if (sectionDataResponse.selected_answer && sectionDataResponse.selected_answer.section_data) {
        console.log('Found section data in response.selected_answer.section_data');
        sectionsDataRaw = sectionDataResponse.selected_answer.section_data;
      }
    }
  }

  // If we found section data through any approach, process it
  if (sectionsDataRaw) {
    console.log('Processing found section data:', sectionsDataRaw);
    
    // Process each section
    Object.entries(sectionsDataRaw).forEach(([sectionName, sectionData]) => {
      const sectionScore = sectionScores[sectionName] || 0;
      let totalQuestions = 15; // Default
      let correctAnswers = sectionScore;
      
      // Try to extract submitted answers if available
      const answers = sectionData.submitted_answers || sectionData.answers || {};
      
      if (Object.keys(answers).length > 0) {
        totalQuestions = Object.keys(answers).length;
        
        // Count correct answers if we have the data
        if (Object.values(answers).some(ans => ans.correct_answer !== undefined)) {
          correctAnswers = Object.values(answers).filter(ans =>
            ans.correct_answer && ans.selected_answer &&
            ans.correct_answer.toString().toLowerCase() === ans.selected_answer.toString().toLowerCase()
          ).length;
        }
      }

      sectionsData.push({
        name: sectionName,
        score: sectionScore,
        totalQuestions: totalQuestions,
        correctAnswers: correctAnswers,
        accuracy: totalQuestions > 0 ? ((correctAnswers / totalQuestions) * 100) : 0
      });
    });
  } 
  // Fallback: If we couldn't find section data, use section scores only
  else {
    console.log('Using fallback section processing based on scores only');
    
    // Extract section names and scores from result_data
    Object.entries(sectionScores).forEach(([sectionName, sectionScore]) => {
      // Try to determine the total questions for this section
      // Default to 15 if we can't determine it
      const totalQuestions = 15;
      
      sectionsData.push({
        name: sectionName,
        score: sectionScore,
        totalQuestions: totalQuestions,
        correctAnswers: sectionScore,
        accuracy: (sectionScore / totalQuestions) * 100
      });
    });
  }

  // If we still don't have any section data, create a generic one
  if (sectionsData.length === 0) {
    console.log('No section data found, creating generic section');
    
    // Calculate total score across all sections if available
    const totalScore = Object.values(sectionScores).reduce((sum, score) => sum + score, 0);
    
    sectionsData.push({
      name: "Overall Aptitude",
      score: totalScore,
      totalQuestions: 100, // Generic assumption
      correctAnswers: totalScore,
      accuracy: totalScore
    });
  }

  // Filter out internal sections (e.g., performance_level metadata)
  const internalSectionPattern = /performance[_\s-]?levels?/i;
  const filteredSectionsData = sectionsData.filter(section => !internalSectionPattern.test(section.name));
  const finalSectionsData = filteredSectionsData.length ? filteredSectionsData : sectionsData;

  // Populate the existing average-cards div
  populateAverageCards(finalSectionsData);

  // Create individual section cards
  finalSectionsData.forEach(section => {
    const sectionCard = createEnhancedAptitudeSectionCard(section);
    sectionsContainer.appendChild(sectionCard);
  });

  // Create aptitude chart
  createAptitudeChart(
    finalSectionsData.map(s => s.name),
    finalSectionsData.map(s => s.score),
    index
  );
}

// Populate the existing average-cards div with performance boxes
function populateAverageCards(sectionsData) {
  // Find the existing average-cards div
  const averageCardsContainer = document.querySelector('.average-cards');
  if (!averageCardsContainer) {
    console.error('average-cards div not found');
    return;
  }

  // Clear any existing content
  averageCardsContainer.innerHTML = '';

  // Categorize sections by performance level
  const performanceLevels = {
    'Above Average': [],
    'Average': [],
    'Below Average': []
  };

  sectionsData.forEach(section => {
    const accuracy = section.accuracy;
    if (accuracy >= 70) {
      performanceLevels['Above Average'].push(section.name);
    } else if (accuracy >= 40) {
      performanceLevels['Average'].push(section.name);
    } else {
      performanceLevels['Below Average'].push(section.name);
    }
  });

  // Create Above Average box
  if (performanceLevels['Above Average'].length > 0) {
    const aboveAverageBox = createCustomPerformanceBox(
      'Above Average',
      performanceLevels['Above Average'],
      {
        background: '#E7E5FF',
        borderColor: '#3F37C9',
        textColor: '#3F37C9'
      }
    );
    averageCardsContainer.appendChild(aboveAverageBox);
  }

  // Create Average box
  if (performanceLevels['Average'].length > 0) {
    const averageBox = createCustomPerformanceBox(
      'Average',
      performanceLevels['Average'],
      {
        background: '#E5F9FF',
        borderColor: '#2E8AA6',
        textColor: '#2E8AA6'
      }
    );
    averageCardsContainer.appendChild(averageBox);
  }

  // Create Below Average box
  if (performanceLevels['Below Average'].length > 0) {
    const belowAverageBox = createCustomPerformanceBox(
      'Below Average',
      performanceLevels['Below Average'],
      {
        background: '#FFE5E5',
        borderColor: '#C24E4E',
        textColor: '#A22717'
      }
    );
    averageCardsContainer.appendChild(belowAverageBox);
  }
}

// Create individual performance box using your exact HTML structure
function createCustomPerformanceBox(level, sections, colors) {
  const box = document.createElement('div');
  box.className = 'box-i onebox';

  box.style.cssText = `
    background: ${colors.background};
    margin: 20px 8px;
    border-radius: 10px;
    border-right: 4px solid ${colors.borderColor};
    border-bottom: 4px solid ${colors.borderColor};
    width: 210px;
    padding: 15px;
    height:auto;
  `;

  // Create the title
  const title = `<p style="color: ${colors.textColor}; font-weight: 700; font-size: 16px; margin-bottom: 10px;">${level}</p>`;

  // Create sections list using your exact paragraph structure
  const sectionsList = sections.map(section =>
    `<p style="color: #494949; font-size: 12px; font-weight: 600; margin-bottom: 5px; text-align: center;">${section}</p>`
  ).join('');

  box.innerHTML = title + sectionsList;

  return box;
}


function createPersonalityDimensionCard(dimension, rank) {
  const card = document.createElement('div');
  card.className = `dimension-card ${dimension.level || ''}`;

  // Add rank indicator for top 3
  const rankIndicator = rank === 'lowest' ? '' :
    rank <= 3 ? `<span class="rank-indicator">#${rank}</span>` : '';

  card.innerHTML = `
    <div class="dimension-header">
      <span class="dimension-info">
        ${rankIndicator}
        <span class="dimension-name">${dimension.name} (${dimension.code})</span>
      </span>
      <span class="dimension-score">${dimension.score.toFixed(1)}</span>
    </div>
    <div class="progress-bar-container">
      <div class="progress-bar" style="width: ${dimension.percentage}%"></div>
    </div>
  `;

  return card;
}

// Create motivation category card
function createMotivationCategoryCard(category, priority, isTop = false) {
  const card = document.createElement('div');
  card.className = 'motivation-category';

  if (isTop) {
    card.style.border = '2px solid #3F37C9';
    card.style.backgroundColor = '#f0f4ff';
    card.style.position = 'relative';
  }

  card.innerHTML = `
    ${isTop ? '<span class="rank-indicator" style="position: absolute; top: -10px; right: -10px; background: #3F37C9; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">#1</span>' : ''}
    <div class="category-priority" style="${isTop ? 'color: #3F37C9; font-weight: bold;' : ''}">${priority}</div>
    <div class="category-name" style="${isTop ? 'color: #3F37C9; font-weight: 600;' : ''}">${category}</div>
  `;

  return card;
}

// Create career dimension card
function createCareerDimensionCard(dimension, rank) {
  const card = document.createElement('div');
  card.className = `career-dimension-card ${dimension.name} ${dimension.level}`;

  const rankIndicator = rank === 'lowest' ? '' :
    rank <= 3 ? `<span style="background: #3F37C9; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-right: 8px;">#${rank}</span>` : '';

  card.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
      <span style="display: flex; align-items: center;">
        ${rankIndicator}
        <span style="font-weight: 600; color: #333;">${dimension.name} (${dimension.code})</span>
      </span>
      <span style="font-size: 24px; font-weight: bold; color: #3F37C9;">${dimension.score.toFixed(0)}</span>
    </div>
    <div class="progress-bar-container">
      <div class="progress-bar" style="width: ${dimension.percentage}%"></div>
    </div>
  `;

  return card;
}


function createEnhancedAptitudeSectionCard(section) {

  const card = document.createElement('div');
  card.className = 'section-card';

  // Determine performance level for styling
  const accuracy = section.accuracy;
  let performanceClass = 'average';
  let performanceColor = '#2E8AA6';

  if (accuracy >= 70) {
    performanceClass = 'above-average';
    performanceColor = '#3F37C9';
  } else if (accuracy < 40) {
    performanceClass = 'below-average';
    performanceColor = '#C24E4E';
  }

  // Add performance indicator to card
  card.style.borderLeft = `4px solid ${performanceColor}`;

  let questionBreakdown = '';
  if (section.totalQuestions > 0) {
    questionBreakdown = `
      <div class="question-breakdown">
        <h5>Performance Summary:</h5>
        
        <div class="question-item">
          <span>Total Questions:</span>
          <span>${section.totalQuestions}</span>
        </div>
        <div class="question-item">
          <span>Correct Answers:</span>
          <span class="question-status correct">${section.correctAnswers}</span>
        </div>
        <div class="question-item">
          <span>Accuracy:</span>
          <span style="color: ${performanceColor}; font-weight: 600;">${section.accuracy.toFixed(1)}%</span>
        </div>
      </div>
    `;
  }

  card.innerHTML = `
    <div class="section-header">
      <span class="section-title">${section.name}</span>
      <span class="section-score" style="background-color: ${performanceColor};">${section.score}/${section.totalQuestions}</span>
    </div>
    ${questionBreakdown}
  `;

  return card;
}

// Add CSS styles for the custom boxes
const customBoxStyles = `
  <style>
    .average-cards {
      display: flex !important;
      justify-content: center !important;
      margin: 30px 0 !important;
      flex-wrap: wrap;
    }
    
    .box-i.onebox {
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      cursor: default;
    }
    
    .box-i.onebox:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    

    
    .section-card:hover {
      box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
 
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    
    .section-title {
      font-weight: 600;
      color: #333;
    }
    
    .question-breakdown h5 {
      color: #495057;
      margin-bottom: 10px;
      font-size: 14px;
    }
    
    .question-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 0;
      border-bottom: 1px solid #f0f0f0;
      font-size: 13px;
    }
    
    .question-item:last-child {
      border-bottom: none;
    }
    
    .section-score {
      background: #3F37C9;
      color: white;
      padding: 4px 12px;
      border-radius: 15px;
      font-size: 0.9em;
      font-weight: 600;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
      .average-cards {
        flex-direction: column !important;
        align-items: center !important;
      }
      
      .box-i.onebox {
        width: 90% !important;
        max-width: 300px !important;
        margin: 10px 0 !important;
      }
      
     
    }
    
    @media print {
      .average-cards,
      .box-i.onebox,
      .section-card {
        page-break-inside: avoid;
      }
    }
  </style>
`;

// Inject styles into document head
if (!document.getElementById('custom-box-styles')) {
  const styleElement = document.createElement('div');
  styleElement.id = 'custom-box-styles';
  styleElement.innerHTML = customBoxStyles;
  document.head.appendChild(styleElement);
}


// Chart creation functions
function createPersonalityChart(labels, scores, index) {
  const ctx = document.getElementById('personality-chart');
  if (!ctx) return;

  if (personalityChartInstance) {
    personalityChartInstance.destroy();
  }

  personalityChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Personality Dimensions',
        data: scores,
        backgroundColor: 'rgba(63, 55, 201, 0.6)',
        borderColor: 'rgba(63, 55, 201, 1)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
          max: 60,
          title: {
            display: true,
            text: 'Score'
          }
        }
      },
      plugins: {
        legend: {
          display: true,
          position: 'top'
        },
        title: {
          display: true,
          text: 'Personality Assessment Results'
        }
      }
    }
  });
}

function createMotivationChart(categories, index) {
  const ctx = document.getElementById('motivation-chart');
  if (!ctx) return;

  if (motivationChartInstance) {
    motivationChartInstance.destroy();
  }

  motivationChartInstance = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: categories.map(([category]) => category),
      datasets: [{
        data: categories.map(([, count]) => count),
        backgroundColor: [
          'rgba(255, 99, 132, 0.6)',
          'rgba(54, 162, 235, 0.6)',
          'rgba(255, 206, 86, 0.6)',
          'rgba(75, 192, 192, 0.6)',
          'rgba(153, 102, 255, 0.6)',
          'rgba(255, 159, 64, 0.6)'
        ],
        borderColor: [
          'rgba(255, 99, 132, 1)',
          'rgba(54, 162, 235, 1)',
          'rgba(255, 206, 86, 1)',
          'rgba(75, 192, 192, 1)',
          'rgba(153, 102, 255, 1)',
          'rgba(255, 159, 64, 1)'
        ],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'right'
        },
        title: {
          display: true,
          text: 'Motivation Categories Distribution'
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              return context.label; // show only category name
            }
          }
        }
      }
    }
  });
}


function createCareerChart(labels, scores, index) {
  const ctx = document.getElementById('career-chart');
  if (!ctx) return;

  // Destroy the previous chart instance if it exists
  if (careerChartInstance) {
    careerChartInstance.destroy();
  }

  // Create new chart instance and store it
  careerChartInstance = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Career Interest Scores',
        data: scores,
        backgroundColor: 'rgba(63, 55, 201, 0.2)',
        borderColor: 'rgba(63, 55, 201, 1)',
        borderWidth: 2,
        pointBackgroundColor: 'rgba(63, 55, 201, 1)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgba(63, 55, 201, 1)',
        pointRadius: 5,
        pointHoverRadius: 7
      }]
    },
    options: {
      responsive: true,
      scales: {
        r: {
          beginAtZero: true,
          max: 25,
          ticks: {
            stepSize: 5
          },
          grid: {
            color: 'rgba(0, 0, 0, 0.1)'
          },
          angleLines: {
            color: 'rgba(0, 0, 0, 0.1)'
          }
        }
      },
      plugins: {
        legend: {
          position: 'top'
        },
        title: {
          display: true,
          text: 'RIASEC Career Interest Profile'
        }
      },
      elements: {
        line: {
          tension: 0.1
        }
      }
    }
  });
}


function createAptitudeChart(labels, scores, index) {
  const ctx = document.getElementById('aptitude-chart');
  if (!ctx) return;

  if (aptitudeChartInstance) {
    aptitudeChartInstance.destroy();
  }

  aptitudeChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Aptitude Scores',
        data: scores,
        backgroundColor: [
          'rgba(255, 99, 132, 0.6)',
          'rgba(54, 162, 235, 0.6)',
          'rgba(255, 206, 86, 0.6)',
          'rgba(75, 192, 192, 0.6)',
          'rgba(153, 102, 255, 0.6)',
          'rgba(255, 159, 64, 0.6)',
          'rgba(199, 199, 199, 0.6)'
        ],
        borderColor: [
          'rgba(255, 99, 132, 1)',
          'rgba(54, 162, 235, 1)',
          'rgba(255, 206, 86, 1)',
          'rgba(75, 192, 192, 1)',
          'rgba(153, 102, 255, 1)',
          'rgba(255, 159, 64, 1)',
          'rgba(199, 199, 199, 1)'
        ],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      indexAxis: 'y',
      scales: {
        x: {
          beginAtZero: true,
          max: 15,
          title: {
            display: true,
            text: 'Score (out of 15)'
          }
        },
        y: {
          title: {
            display: true,
            text: 'Aptitude Sections'
          }
        }
      },
      plugins: {
        legend: {
          display: false
        },
        title: {
          display: true,
          text: 'Aptitude Assessment Results by Section'
        }
      }
    }
  });
}

// Helper function to show loading state
function showLoading(containerId) {
  const container = document.getElementById(containerId);
  if (container) {
    container.innerHTML = '<div class="loading">Loading results...</div>';
  }
}

// Helper function to show error state
function showError(containerId, message) {
  const container = document.getElementById(containerId);
  if (container) {
    container.innerHTML = `<div class="error">Error: ${message}</div>`;
  }
}

// Function to handle API errors gracefully
function handleApiError(error, testType) {
  console.error(`Error loading ${testType} results:`, error);
  showError(`${testType}-results`, `Failed to load ${testType} results`);
}

// Alternative function to load results from Django context (if available)
function loadResultsFromContext() {
  // Check if results are available in Django context
  if (typeof window.testResults !== 'undefined' && window.testResults.length > 0) {
    console.log('Loading results from Django context:', window.testResults);
    window.testResults.forEach((result, index) => {
      processTestResult(result, index);
    });
    return true;
  }
  return false;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, attempting to load test results');
  
  // Try to load from context first
  const loadedFromContext = loadResultsFromContext();
  
  // If not loaded from context, try API
  if (!loadedFromContext) {
    console.log('No results in context, trying API...');
    loadTestResults();
  }
});

// Export functions for external use
window.PDFResults = {
  loadTestResults,
  processTestResult,
  handlePersonalityResults,
  handleMotivationResults,
  handleCareerResults,
  handleAptitudeResults
}; // 