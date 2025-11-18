/* DOCX Processing JavaScript */
function processDocxFile(input) {
    const file = input.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.docx')) {
        alert('Please select a DOCX file.');
        input.value = '';
        return;
    }
    
    // Validate file size (10MB limit)
    if (file.size > 10 * 1024 * 1024) {
        alert('File size must be under 10MB.');
        input.value = '';
        return;
    }
    
    // Show processing status
    showProcessingStatus();
    
    // Create FormData for file upload
    const formData = new FormData();
    formData.append('docx_file', file);
    formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
    
    // Start actual processing
    processDocxContent(file);
}

function showProcessingStatus() {
    const statusDiv = document.getElementById('docx-processing-status');
    if (statusDiv) {
        statusDiv.style.display = 'block';
        updateProgress(0, 'Starting processing...');
    }
}

function updateProgress(percent, message) {
    const progressBar = document.getElementById('progress-bar');
    const processingMessage = document.getElementById('processing-message');
    
    if (progressBar) {
        progressBar.style.width = percent + '%';
    }
    
    if (processingMessage) {
        processingMessage.textContent = message;
    }
}

function processDocxContent(file) {
    // Show processing status first
    showProcessingStatus();
    
    // Create FormData for file upload
    const formData = new FormData();
    formData.append('docx_file', file);
    formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
    
    updateProgress(10, 'Sending to server...');
    
    // Send to server for processing
    fetch('/careers/api/process-docx/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => {
        updateProgress(50, 'Processing file...');
        return response.json();
    })
    .then(data => {
        updateProgress(80, 'Extracting content...');
        
        if (data.success) {
            // Populate the form fields with extracted content
            populateFormFields(data);
            
            updateProgress(100, 'Processing completed successfully!');
            
            setTimeout(() => {
                hideProcessingStatus();
                showSuccessMessage('DOCX file processed successfully! Career fields have been updated.');
            }, 1000);
        } else {
            throw new Error(data.error || 'Unknown error occurred');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        updateProgress(0, 'Error processing file');
        showErrorMessage('Error processing DOCX file: ' + error.message);
    });
}

function populateFormFields(content) {
    console.log('Populating form fields with:', content);
    
    // Find and populate the name field
    const nameField = document.querySelector('input[name="name"]');
    if (nameField && content.title) {
        nameField.value = content.title;
        nameField.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('✅ Name field updated:', content.title);
    } else {
        console.log('❌ Name field not found or no title');
    }
    
    // Find and populate the summary field
    const summaryField = document.querySelector('textarea[name="summary"]');
    if (summaryField && content.summary) {
        summaryField.value = content.summary;
        summaryField.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('✅ Summary field updated');
    } else {
        console.log('❌ Summary field not found or no summary');
    }
    
    // Find and populate the description field
    const descriptionField = document.querySelector('textarea[name="description"]');
    if (descriptionField && content.description) {
        descriptionField.value = content.description;
        descriptionField.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('✅ Description field updated');
    } else {
        console.log('❌ Description field not found or no description');
    }
    
    // Also populate English fields if they exist
    const nameEnField = document.querySelector('input[name="name_en"]');
    if (nameEnField && content.title) {
        nameEnField.value = content.title;
        nameEnField.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('✅ Name EN field updated');
    }
    
    const summaryEnField = document.querySelector('textarea[name="summary_en"]');
    if (summaryEnField && content.summary) {
        summaryEnField.value = content.summary;
        summaryEnField.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('✅ Summary EN field updated');
    }
    
    const descriptionEnField = document.querySelector('textarea[name="description_en"]');
    if (descriptionEnField && content.description) {
        descriptionEnField.value = content.description;
        descriptionEnField.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('✅ Description EN field updated');
    }
    
    console.log('Form population completed');
}

function hideProcessingStatus() {
    const statusDiv = document.getElementById('docx-processing-status');
    if (statusDiv) {
        statusDiv.style.display = 'none';
    }
}

function showSuccessMessage(message) {
    const processingMessage = document.getElementById('processing-message');
    if (processingMessage) {
        processingMessage.textContent = message;
        processingMessage.className = 'processing-message success-message';
    }
}

function showErrorMessage(message) {
    const processingMessage = document.getElementById('processing-message');
    if (processingMessage) {
        processingMessage.textContent = message;
        processingMessage.className = 'processing-message error-message';
    }
}

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

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Add any initialization code here if needed
    console.log('DOCX processing script loaded');
});
