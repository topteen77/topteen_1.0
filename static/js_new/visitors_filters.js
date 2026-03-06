/**
 * Visitors Filters - Autocomplete and Tab Management
 * Handles Select2 dropdowns with autocomplete for filter options
 */

function initVisitorsFilters(config) {
    const {
        period = '30days',
        filterOptionsUrl = '/user-analytics/api/visitors/filter-options/',
        userType = 'all'
    } = config || {};

    // Check if jQuery and Select2 are available
    if (typeof $ === 'undefined') {
        console.error('jQuery is required for filter dropdowns');
        return;
    }
    
    if (typeof $.fn.select2 === 'undefined') {
        console.error('Select2 is required for filter dropdowns');
        return;
    }

    // Initialize Select2 for filter dropdowns
    const filterSelects = ['#source-filter', '#device-filter', '#country-filter', '#entry-page-filter'];
    
    filterSelects.forEach(function(selector) {
        const $select = $(selector);
        const filterType = $select.data('filter-type');
        
        if (!$select.length) {
            console.warn('Filter select not found:', selector);
            return;
        }
        
        // Get current selected value if any
        const currentValue = $select.val();
        const currentText = $select.find('option:selected').text();
        
            // Initialize Select2 with proper configuration
        try {
            $select.select2({
                placeholder: `Select ${filterType}...`,
                allowClear: true,
                width: '100%',
                dropdownParent: $select.parent(), // Ensure dropdown appears in correct container
                ajax: {
                    url: filterOptionsUrl,
                    dataType: 'json',
                    delay: 300,
                    cache: true,
                    data: function(params) {
                        return {
                            filter_type: filterType,
                            period: period,
                            q: params.term || ''
                        };
                    },
                    processResults: function(data) {
                        if (data && data.success && data.options) {
                            const sourceLabels = (filterType === 'source' && data.source_labels) ? data.source_labels : {};
                            const results = data.options.map(function(option) {
                                const val = String(option);
                                const text = sourceLabels[val] || val;
                                return {
                                    id: val,
                                    text: text
                                };
                            });
                            
                            // If we have a current value that's not in results, add it
                            if (currentValue && currentText && 
                                currentText !== `All ${filterType.charAt(0).toUpperCase() + filterType.slice(1)}s` &&
                                currentText !== 'All Sources' && currentText !== 'All Devices' && 
                                currentText !== 'All Countries' && currentText !== 'All Entry Pages') {
                                const exists = results.some(function(r) { return r.id === String(currentValue); });
                                if (!exists) {
                                    results.unshift({
                                        id: String(currentValue),
                                        text: String(currentText)
                                    });
                                }
                            }
                            
                            return { results: results };
                        }
                        return { results: [] };
                    },
                    error: function(xhr, status, error) {
                        console.error('Error loading filter options for', filterType, ':', error, xhr);
                        // Return empty results on error
                        return { results: [] };
                    }
                },
                minimumInputLength: 0 // Allow selection without typing
            });
            
            // If there's a pre-selected value, ensure it's displayed
            if (currentValue) {
                // Ensure the option exists
                if (!$select.find('option[value="' + currentValue + '"]').length) {
                    const option = new Option(currentText || currentValue, currentValue, true, true);
                    $select.append(option);
                }
                // Set value after Select2 is initialized
                setTimeout(function() {
                    try {
                        $select.val(currentValue).trigger('change.select2');
                    } catch (e) {
                        console.warn('Could not set Select2 value:', e);
                    }
                }, 200);
            }
        } catch (error) {
            console.error('Error initializing Select2 for', filterType, ':', error);
        }
    });
    
    // Reload filter options when period changes
    $('#period-select').on('change', function() {
        const newPeriod = $(this).val();
        filterSelects.forEach(function(selector) {
            const $select = $(selector);
            if ($select.length && $select.data('select2')) {
                // Save current value
                const currentValue = $select.val();
                const currentText = $select.find('option:selected').text();
                
                // Update the AJAX URL with new period
                const filterType = $select.data('filter-type');
                $select.select2('destroy');
                
                $select.select2({
                    placeholder: `Select ${filterType}...`,
                    allowClear: true,
                    width: '100%',
                    dropdownParent: $select.parent(),
                    ajax: {
                        url: filterOptionsUrl,
                        dataType: 'json',
                        delay: 300,
                        cache: true,
                        data: function(params) {
                            return {
                                filter_type: filterType,
                                period: newPeriod,
                                q: params.term || ''
                            };
                        },
                        processResults: function(data) {
                            if (data.success && data.options) {
                                const sourceLabels = (filterType === 'source' && data.source_labels) ? data.source_labels : {};
                                const results = data.options.map(function(option) {
                                    const val = String(option);
                                    const text = sourceLabels[val] || val;
                                    return {
                                        id: val,
                                        text: text
                                    };
                                });
                                
                                // Preserve current selection if it exists
                                if (currentValue && currentText) {
                                    const exists = results.some(function(r) { return r.id === currentValue; });
                                    if (!exists) {
                                        results.unshift({
                                            id: currentValue,
                                            text: currentText
                                        });
                                    }
                                }
                                
                                return { results: results };
                            }
                            return { results: [] };
                        }
                    },
                    minimumInputLength: 0
                });
                
                // Restore value if it existed
                if (currentValue) {
                    setTimeout(function() {
                        $select.val(currentValue).trigger('change.select2');
                    }, 200);
                }
            }
        });
    });
    
    // Auto-submit form when filters change (optional - can be removed if manual submit preferred)
    // Uncomment if you want auto-submit on filter change
    /*
    filterSelects.forEach(function(selector) {
        $(selector).on('change', function() {
            $('#visitors-filter-form').submit();
        });
    });
    */
    
    console.log('Visitors filters initialized', {
        period: period,
        filterOptionsUrl: filterOptionsUrl,
        userType: userType
    });
    
    // Debug: Log if jQuery/Select2 are available
    if (typeof $ === 'undefined') {
        console.error('jQuery is not loaded!');
    }
    if (typeof $.fn.select2 === 'undefined') {
        console.error('Select2 is not loaded!');
    }
    
    // Re-initialize filters when page loads with URL parameters (e.g., from pagination)
    // This ensures selected values are properly displayed
    filterSelects.forEach(function(selector) {
        const $select = $(selector);
        if ($select.length) {
            const currentValue = $select.val();
            if (currentValue) {
                // Force update after a short delay to ensure Select2 is ready
                setTimeout(function() {
                    $select.trigger('change.select2');
                }, 300);
            }
        }
    });
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initVisitorsFilters };
}
