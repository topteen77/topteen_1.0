/**
 * Career Description Admin JavaScript
 * Handles H2 conversion, JSON preview, and accordion preview
 */

(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('Career Description Admin JS loaded');
        
        // Inject description tools if they don't exist
        try {
            injectDescriptionTools();
            console.log('Description tools injected');
        } catch(e) {
            console.error('Error injecting description tools:', e);
        }
        
        // Move description field to editor tab - wait for CKEditor to initialize
        setTimeout(function() {
            try {
                moveDescriptionFieldToTab();
                console.log('Description field moved to tab');
            } catch(e) {
                console.error('Error moving description field:', e);
            }
        }, 2000); // Increased delay to ensure CKEditor is ready
        
        // Get career ID from URL
        var careerId = getCareerIdFromUrl();
        if (!careerId) {
            console.warn('Career ID not found in URL');
            return;
        }
        
        // Convert to H2 button - use event delegation
        $(document).on('click', '#convert-to-h2-btn', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Convert to H2 button clicked!');
            var instance = getCKEditorInstance();
            console.log('CKEditor instance:', instance ? 'found' : 'not found');
            console.log('Career ID:', careerId);
            if (!careerId) {
                alert('Error: Career ID not found. Please refresh the page and try again.');
                return;
            }
            convertToH2(careerId, instance);
        });
        
        // JSON Preview button
        $(document).on('click', '#json-preview-btn', function() {
            var instance = getCKEditorInstance();
            showJsonPreview(careerId, instance);
        });
        
        // Tab switching
        $(document).on('click', '.tab-button', function() {
            var tabName = $(this).data('tab');
            switchTab(tabName);
            
            // Load accordion preview when tab is clicked
            if (tabName === 'accordion') {
                var instance = getCKEditorInstance();
                loadAccordionPreview(careerId, instance);
            }
        });
        
        // Close JSON modal
        $(document).on('click', '#close-json-modal', function() {
            $('#json-preview-modal').hide();
        });
        
        // Close modal on outside click
        $(document).on('click', '#json-preview-modal', function(e) {
            if (e.target === this) {
                $(this).hide();
            }
        });
    });
    
    /**
     * Inject description tools UI if not present
     */
    function injectDescriptionTools() {
        // Check if tools already exist
        if ($('.description-tools-wrapper').length > 0) {
            console.log('Description tools already exist');
            return;
        }
        
        console.log('Injecting description tools...');
        
        // Find a good place to inject - after the Basic Information fieldset
        var basicInfoFieldset = $('fieldset:contains("Basic Information")');
        if (basicInfoFieldset.length === 0) {
            basicInfoFieldset = $('fieldset').first();
        }
        
        if (basicInfoFieldset.length === 0) {
            console.error('Could not find fieldset to inject tools after');
            return;
        }
        
        var toolsHtml = '<div class="description-tools-wrapper">' +
            '<div class="description-toolbar">' +
            '<button type="button" id="convert-to-h2-btn" class="button description-toolbar-btn">Convert to H2</button>' +
            '<button type="button" id="json-preview-btn" class="button description-toolbar-btn">JSON Preview</button>' +
            '</div>' +
            '<div class="description-tabs">' +
            '<button type="button" class="tab-button active" data-tab="editor">Editor</button>' +
            '<button type="button" class="tab-button" data-tab="accordion">Accordion Preview</button>' +
            '</div>' +
            '<div class="tab-content">' +
            '<div id="editor-tab" class="tab-pane active">' +
            '<div id="description-field-container"><p class="description-muted">Description Editor:</p></div>' +
            '</div>' +
            '<div id="accordion-tab" class="tab-pane" style="display: none;">' +
            '<div id="accordion-preview-container"><p class="description-muted">Click "Accordion Preview" tab to see how the description will render as accordions.</p></div>' +
            '</div>' +
            '</div>' +
            '</div>';
        
        basicInfoFieldset.after(toolsHtml);
        
        // Add JSON modal
        if ($('#json-preview-modal').length === 0) {
            $('body').append(
                '<div id="json-preview-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000;">' +
                '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 20px; border-radius: 5px; max-width: 800px; max-height: 80vh; overflow: auto;">' +
                '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">' +
                '<h2 style="margin: 0;">JSON Preview</h2>' +
                '<button type="button" id="close-json-modal" style="background: #dc3545; color: white; border: none; padding: 5px 15px; border-radius: 4px; cursor: pointer;">Close</button>' +
                '</div>' +
                '<pre id="json-preview-content" style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow: auto; max-height: 60vh;"></pre>' +
                '</div>' +
                '</div>'
            );
        }
    }
    
    /**
     * Move description field to Editor tab
     */
    function moveDescriptionFieldToTab() {
        console.log('Attempting to move description field...');
        
        // Find the description field - try multiple approaches
        var descriptionRow = null;
        var descriptionTextarea = $('textarea[name="description"]');
        
        if (descriptionTextarea.length > 0) {
            // Find the parent container
            descriptionRow = descriptionTextarea.closest('div').parent();
            console.log('Found description field by textarea');
        }
        
        // Try finding by class
        if (!descriptionRow || descriptionRow.length === 0) {
            descriptionRow = $('.field-description');
            console.log('Found description field by class');
        }
        
        // Try finding by label
        if (!descriptionRow || descriptionRow.length === 0) {
            $('label').each(function() {
                var labelText = $(this).text().trim().toLowerCase();
                if (labelText.includes('description') && !labelText.includes('role') && !labelText.includes('eligibility')) {
                    descriptionRow = $(this).closest('div').parent();
                    console.log('Found description field by label');
                    return false;
                }
            });
        }
        
        if (descriptionRow && descriptionRow.length > 0) {
            var container = $('#description-field-container');
            if (container.length > 0) {
                console.log('Moving description field to editor tab');
                
                // Get textarea ID
                var textarea = descriptionRow.find('textarea[name="description"]');
                var textareaId = textarea.length > 0 ? textarea.attr('id') : null;
                
                // Move the entire row
                var movedRow = descriptionRow.detach();
                movedRow.css('display', 'block');
                container.append(movedRow);
                
                // Reinitialize CKEditor after a short delay
                if (typeof CKEDITOR !== 'undefined' && textareaId) {
                    setTimeout(function() {
                        // Destroy existing instance
                        if (CKEDITOR.instances[textareaId]) {
                            CKEDITOR.instances[textareaId].destroy();
                        }
                        // Create new instance
                        CKEDITOR.replace(textareaId);
                        console.log('CKEditor reinitialized');
                    }, 300);
                }
                
                console.log('Description field moved successfully');
            } else {
                console.error('Description field container not found');
            }
        } else {
            console.warn('Description field not found');
        }
    }
    
    /**
     * Get CKEditor instance for description field
     */
    function getCKEditorInstance() {
        if (typeof CKEDITOR === 'undefined') {
            return null;
        }
        
        // Try to find description CKEditor instance
        var instances = CKEDITOR.instances;
        for (var name in instances) {
            if (name.indexOf('description') !== -1) {
                return instances[name];
            }
        }
        
        // If not found, try to get from textarea
        var textarea = $('textarea[name="description"]');
        if (textarea.length > 0) {
            var textareaId = textarea.attr('id');
            if (textareaId && CKEDITOR.instances[textareaId]) {
                return CKEDITOR.instances[textareaId];
            }
        }
        
        return null;
    }
    
    /**
     * Get career ID from current URL
     */
    function getCareerIdFromUrl() {
        var url = window.location.href;
        // Django admin URL pattern: /admin/careers/career/123/change/
        var match = url.match(/\/careers\/career\/(\d+)\//);
        if (match) {
            return match[1];
        }
        // Try alternative pattern
        match = url.match(/\/career\/(\d+)\//);
        if (match) {
            return match[1];
        }
        return null;
    }
    
    /**
     * Get description content from CKEditor or textarea
     */
    function getDescriptionContent(ckeditorInstance) {
        // Try to get from provided CKEditor instance
        if (ckeditorInstance && typeof ckeditorInstance.getData === 'function') {
            try {
                var data = ckeditorInstance.getData();
                if (data && data.trim()) {
                    console.log('Got content from provided CKEditor instance, length:', data.length);
                    return data;
                }
            } catch(e) {
                console.warn('Error getting data from provided CKEditor instance:', e);
            }
        }
        
        // Try to get fresh CKEditor instance
        var instance = getCKEditorInstance();
        if (instance && typeof instance.getData === 'function') {
            try {
                var data = instance.getData();
                if (data && data.trim()) {
                    console.log('Got content from fresh CKEditor instance, length:', data.length);
                    return data;
                }
            } catch(e) {
                console.warn('Error getting data from fresh CKEditor instance:', e);
            }
        }
        
        // Try all CKEditor instances
        if (typeof CKEDITOR !== 'undefined') {
            for (var name in CKEDITOR.instances) {
                if (name.indexOf('description') !== -1) {
                    try {
                        var data = CKEDITOR.instances[name].getData();
                        if (data && data.trim()) {
                            console.log('Got content from CKEditor instance:', name, 'length:', data.length);
                            return data;
                        }
                    } catch(e) {
                        console.warn('Error getting data from CKEditor instance', name, ':', e);
                    }
                }
            }
        }
        
        // Fallback to textarea - try multiple selectors
        var textarea = $('textarea[name="description"]');
        if (textarea.length) {
            var val = textarea.val();
            if (val && val.trim()) {
                console.log('Got content from textarea, length:', val.length);
                return val;
            }
        }
        
        // Try finding textarea by ID in all CKEditor instances
        if (typeof CKEDITOR !== 'undefined') {
            for (var name in CKEDITOR.instances) {
                if (name.indexOf('description') !== -1) {
                    var textareaEl = $('#' + name);
                    if (textareaEl.length) {
                        var val = textareaEl.val();
                        if (val && val.trim()) {
                            console.log('Got content from textarea by ID:', name, 'length:', val.length);
                            return val;
                        }
                    }
                }
            }
        }
        
        console.warn('Could not get description content from CKEditor or textarea');
        console.log('CKEditor instances:', typeof CKEDITOR !== 'undefined' ? Object.keys(CKEDITOR.instances) : 'CKEDITOR not defined');
        console.log('Textareas found:', $('textarea[name="description"]').length);
        return '';
    }
    
    /**
     * Set description content in CKEditor or textarea
     */
    function setDescriptionContent(ckeditorInstance, content) {
        console.log('setDescriptionContent called with content length:', content ? content.length : 0);
        
        // First, find and update the textarea directly
        var textarea = $('textarea[name="description"]');
        var textareaId = null;
        
        if (textarea.length) {
            textareaId = textarea.attr('id');
            console.log('Found textarea with ID:', textareaId);
            // Update textarea first
            textarea.val(content);
            textarea.trigger('input').trigger('change');
            console.log('Updated textarea directly');
        }
        
        // Now try to update CKEditor 4 instances
        if (typeof CKEDITOR !== 'undefined' && textareaId) {
            // Check if CKEditor 4 instance exists for this textarea
            if (CKEDITOR.instances[textareaId]) {
                try {
                    console.log('Updating CKEditor 4 instance:', textareaId);
                    CKEDITOR.instances[textareaId].setData(content, function() {
                        console.log('CKEditor 4 content updated successfully');
                    });
                    return;
                } catch(e) {
                    console.warn('Error updating CKEditor 4 instance:', e);
                }
            }
            
            // Try to find any description-related CKEditor 4 instance
            for (var name in CKEDITOR.instances) {
                if (name.indexOf('description') !== -1) {
                    try {
                        console.log('Updating CKEditor 4 instance:', name);
                        CKEDITOR.instances[name].setData(content, function() {
                            console.log('CKEditor 4 content updated successfully');
                        });
                        return;
                    } catch(e) {
                        console.warn('Error updating CKEditor 4 instance', name, ':', e);
                    }
                }
            }
        }
        
        // Try provided CKEditor instance (could be CKEditor 4 or 5)
        if (ckeditorInstance) {
            try {
                if (typeof ckeditorInstance.setData === 'function') {
                    console.log('Updating provided CKEditor instance');
                    if (ckeditorInstance.setData.length === 2) {
                        // CKEditor 4 - has callback
                        ckeditorInstance.setData(content, function() {
                            console.log('CKEditor content updated via provided instance');
                        });
                    } else {
                        // CKEditor 5 or other - no callback
                        ckeditorInstance.setData(content);
                        console.log('CKEditor content updated via provided instance');
                    }
                    return;
                }
            } catch(e) {
                console.warn('Error updating provided CKEditor instance:', e);
            }
        }
        
        // Try to get fresh CKEditor instance
        var instance = getCKEditorInstance();
        if (instance && typeof instance.setData === 'function') {
            try {
                console.log('Updating fresh CKEditor instance');
                if (instance.setData.length === 2) {
                    // CKEditor 4 - has callback
                    instance.setData(content, function() {
                        console.log('CKEditor content updated via fresh instance');
                    });
                } else {
                    // CKEditor 5 or other
                    instance.setData(content);
                    console.log('CKEditor content updated via fresh instance');
                }
                return;
            } catch(e) {
                console.warn('Error updating fresh CKEditor instance:', e);
            }
        }
        
        // Final fallback - at least textarea is updated
        if (textarea.length) {
            console.log('Content updated in textarea (CKEditor may need manual refresh)');
        } else {
            console.error('Could not find textarea to update');
        }
    }
    
    /**
     * Convert <p><strong> to H2 tags
     */
    function convertToH2(careerId, ckeditorInstance) {
        console.log('convertToH2 called with careerId:', careerId);
        
        // Get fresh CKEditor instance if not provided
        if (!ckeditorInstance) {
            ckeditorInstance = getCKEditorInstance();
        }
        
        var description = getDescriptionContent(ckeditorInstance);
        
        console.log('Convert to H2 - Description length:', description ? description.length : 0);
        
        // Even if description is empty from frontend, backend will use career's description
        // So we proceed with the conversion
        if (!description || !description.trim()) {
            console.log('No description from frontend, backend will use career description');
        }
        
        // Show loading state
        var btn = $('#convert-to-h2-btn');
        var originalText = btn.text();
        btn.prop('disabled', true).text('Converting...');
        
        var url = window.location.pathname.replace(/\/change\/?$/, '') + '/convert-to-h2/';
        console.log('Convert to H2 - URL:', url);
        
        $.ajax({
            url: url,
            method: 'POST',
            data: {
                'description': description,
                'csrfmiddlewaretoken': $('[name=csrfmiddlewaretoken]').val()
            },
            success: function(response) {
                console.log('Convert to H2 - Response:', response);
                if (response.success && response.converted_html) {
                    console.log('Conversion successful, updating editor with converted HTML...');
                    
                    // Get fresh CKEditor instance before updating
                    var instance = getCKEditorInstance();
                    console.log('CKEditor instance for update:', instance ? 'found' : 'not found');
                    
                    // Update CKEditor/textarea with converted HTML (temporary preview)
                    setDescriptionContent(instance, response.converted_html);
                    
                    // Wait a bit and verify the content was set
                    setTimeout(function() {
                        var verifyContent = getDescriptionContent(instance);
                        if (verifyContent && verifyContent.indexOf('<h2>') !== -1) {
                            console.log('✓ Content successfully updated in editor');
                        } else {
                            console.warn('⚠ Content may not have been updated correctly');
                        }
                    }, 500);
                    
                    // Show success message
                    var message = response.message || 'Successfully converted <p><strong> patterns to H2 tags! Click "Save" to save changes.';
                    alert(message);
                    
                    // Don't reload - let user review and save manually
                } else {
                    alert('Error: ' + (response.error || 'Unknown error'));
                }
            },
            error: function(xhr, status, error) {
                console.error('Convert to H2 - Error:', xhr, status, error);
                var errorMsg = 'Error converting to H2. ';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg += xhr.responseJSON.error;
                } else if (xhr.status === 404) {
                    errorMsg += 'Endpoint not found. Please check the URL.';
                } else if (xhr.status === 403) {
                    errorMsg += 'Permission denied.';
                } else {
                    errorMsg += 'Please try again. Status: ' + xhr.status;
                }
                alert(errorMsg);
            },
            complete: function() {
                btn.prop('disabled', false).text(originalText);
            }
        });
    }
    
    /**
     * Show JSON preview of parsed sections
     */
    function showJsonPreview(careerId, ckeditorInstance) {
        var description = getDescriptionContent(ckeditorInstance);
        
        if (!description || !description.trim()) {
            alert('No description content to preview.');
            return;
        }
        
        // Show loading state
        var btn = $('#json-preview-btn');
        var originalText = btn.text();
        btn.prop('disabled', true).text('Loading...');
        
        $.ajax({
            url: window.location.pathname.replace(/\/change\/?$/, '') + '/json-preview/',
            method: 'POST',
            data: {
                'description': description,
                'csrfmiddlewaretoken': $('[name=csrfmiddlewaretoken]').val()
            },
            success: function(response) {
                if (response.success) {
                    // Display JSON in modal
                    var jsonContent = JSON.stringify(response.sections, null, 2);
                    $('#json-preview-content').text(jsonContent);
                    $('#json-preview-modal').show();
                } else {
                    alert('Error: ' + (response.error || 'Unknown error'));
                }
            },
            error: function(xhr) {
                var errorMsg = 'Error loading JSON preview. ';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg += xhr.responseJSON.error;
                } else {
                    errorMsg += 'Please try again.';
                }
                alert(errorMsg);
            },
            complete: function() {
                btn.prop('disabled', false).text(originalText);
            }
        });
    }
    
    /**
     * Load accordion preview
     */
    function loadAccordionPreview(careerId, ckeditorInstance) {
        var description = getDescriptionContent(ckeditorInstance);
        
        var container = $('#accordion-preview-container');
        container.html('<p style="color: #666; padding: 20px;">Loading preview...</p>');
        
        $.ajax({
            url: window.location.pathname.replace(/\/change\/?$/, '') + '/accordion-preview/',
            method: 'GET',
            data: {
                'description': description
            },
            success: function(response) {
                if (response.success) {
                    container.html(response.html);
                } else {
                    container.html('<p style="color: #dc3545; padding: 20px;">Error: ' + (response.error || 'Unknown error') + '</p>');
                }
            },
            error: function(xhr) {
                container.html('<p style="color: #dc3545; padding: 20px;">Error loading accordion preview. Please try again.</p>');
            }
        });
    }
    
    /**
     * Switch between tabs
     */
    function switchTab(tabName) {
        // Update tab buttons
        $('.tab-button').removeClass('active');
        $('.tab-button[data-tab="' + tabName + '"]').addClass('active');
        
        // Update tab panes
        $('.tab-pane').removeClass('active').hide();
        $('#' + tabName + '-tab').addClass('active').show();
    }
    
})(django.jQuery || jQuery);
