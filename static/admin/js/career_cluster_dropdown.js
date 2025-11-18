// Career Cluster Dropdown JavaScript
function updateCareerCluster(careerId, clusterId) {
    if (!clusterId) {
        return;
    }
    
    // Show loading indicator
    const select = event.target;
    const originalValue = select.value;
    select.disabled = true;
    select.style.opacity = '0.6';
    
    // Get CSRF token
    const csrfToken = getCookie('csrftoken');
    
    // Create form data for AJAX request
    const formData = new FormData();
    formData.append('career_id', careerId);
    formData.append('cluster_id', clusterId);
    formData.append('csrfmiddlewaretoken', csrfToken);
    
    // Make AJAX request to custom endpoint
    fetch('/admin/careers/career/update-cluster-ajax/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            showMessage(data.message || 'Career cluster updated successfully!', 'success');
            // Reload the page to show updated data
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            throw new Error(data.error || 'Update failed');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Failed to update career cluster: ' + error.message, 'error');
        // Reset select value
        select.value = originalValue;
    })
    .finally(() => {
        select.disabled = false;
        select.style.opacity = '1';
    });
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

function showMessage(message, type) {
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 5px;
        color: white;
        font-weight: bold;
        z-index: 9999;
        max-width: 300px;
        ${type === 'success' ? 'background-color: #28a745;' : 'background-color: #dc3545;'}
    `;
    messageDiv.textContent = message;
    
    // Add to page
    document.body.appendChild(messageDiv);
    
    // Remove after 3 seconds
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.parentNode.removeChild(messageDiv);
        }
    }, 3000);
}

// Initialize dropdowns when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Add any initialization code here if needed
    console.log('Career cluster dropdown initialized');
});

// Publish Status Dropdown JavaScript
function updatePublishStatus(careerId, publishStatus, el) {
    if (publishStatus === undefined || publishStatus === null || publishStatus === '') {
        return;
    }

    const select = el || event.target;
    const originalValue = select.value;
    select.disabled = true;
    select.style.opacity = '0.6';

    const csrfToken = getCookie('csrftoken');
    const formData = new FormData();
    formData.append('career_id', careerId);
    formData.append('publish_status', publishStatus);
    formData.append('csrfmiddlewaretoken', csrfToken);

    fetch('/admin/careers/career/update-publish-ajax/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // Ensure an inline error container exists just after the select
        let err = select.nextElementSibling;
        if (!err || !err.classList.contains('inline-publish-error')) {
            err = document.createElement('div');
            err.className = 'inline-publish-error';
            err.style.cssText = 'color:#dc3545; font-size:11px; margin-top:4px; max-width:240px;';
            select.insertAdjacentElement('afterend', err);
        }

        if (data.success) {
            // Clear any previous error
            err.textContent = '';
            select.removeAttribute('title');
            showMessage(data.message || 'Publish status updated!', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 800);
        } else {
            // Show validation errors inline and as tooltip
            const errorText = (data.errors && Array.isArray(data.errors)) ? data.errors.join('; ') : (data.error || 'Update failed');
            err.textContent = errorText;
            select.setAttribute('title', errorText);
            // Visually mark invalid
            select.style.borderColor = '#dc3545';
            // revert value
            select.value = originalValue;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Failed to update publish status: ' + error.message, 'error');
        select.value = originalValue;
    })
    .finally(() => {
        select.disabled = false;
        select.style.opacity = '1';
    });
}
