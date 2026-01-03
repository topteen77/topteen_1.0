/**
 * Pure Vanilla JavaScript Heatmap Dashboard
 * NO REACT - Pure DOM manipulation and vanilla JS
 */

(function() {
    'use strict';

    // State management using plain JavaScript object
    const HeatmapDashboard = {
        state: {
            view: 'grade', // 'grade', 'section', or 'stream'
            heatmapData: [],
            demographics: {
                grade: [],
                section: [],
                stream: []
            },
            stats: {
                highRisk: 0,
                aligned: 0,
                avgClarityGap: 0
            },
            hoveredCell: null,
            loading: false
        },

        // Career clusters
        careerClusters: [
            'AI & Digital Tech',
            'Renewable Energy',
            'Healthcare & Biotech',
            'Creative Arts',
            'Sustainable Agrotech',
            'Finance & Analytics',
            'Advanced Manufacturing',
            'Edu-Tech & Training',
            'Space & Aerospace',
            'Green Architecture',
            'Cybersecurity',
            'Robotics & Automation',
            'Social Innovation',
            'Hospitality & Tourism',
            'Legal & Governance',
            'Media & Communications'
        ],

        // Initialize the dashboard
        init: function() {
            this.bindEvents();
            this.loadData();
        },

        // Get institute slug from URL or data attribute
        getInstituteSlug: function() {
            // Check if there's a data attribute on the container
            const container = document.getElementById('heatmap-grid-container');
            if (container && container.dataset.instituteSlug) {
                return container.dataset.instituteSlug;
            }
            
            // Try to extract from URL (e.g., /institute/slug-name/)
            const urlMatch = window.location.pathname.match(/\/institute\/([^\/]+)\/?$/);
            if (urlMatch && urlMatch[1] && urlMatch[1] !== 'marketing_group_dashboard' && urlMatch[1] !== 'institute_group_dashboard') {
                return urlMatch[1];
            }
            
            return null;
        },

        // Bind event listeners
        bindEvents: function() {
            const self = this;
            
            // View switching buttons
            const viewButtons = document.querySelectorAll('.heatmap-view-btn');
            viewButtons.forEach(btn => {
                btn.addEventListener('click', function() {
                    const view = this.dataset.view;
                    self.switchView(view);
                });
            });

            // Refresh button
            const refreshBtn = document.getElementById('heatmap-refresh-btn');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', function() {
                    self.loadData();
                });
            }

            // Export button
            const exportBtn = document.getElementById('heatmap-export-btn');
            if (exportBtn) {
                exportBtn.addEventListener('click', function() {
                    self.exportData();
                });
            }
        },

        // Load data from API
        loadData: function() {
            const self = this;
            this.state.loading = true;
            this.updateLoadingState(true);

            // Check if we're on an individual institute dashboard
            const instituteSlug = this.getInstituteSlug();
            let apiUrl = '/institute/api/heatmap-data/?demographic_type=' + this.state.view;
            if (instituteSlug) {
                apiUrl += '&institute_slug=' + encodeURIComponent(instituteSlug);
            }
            
            fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log('Heatmap API Response:', data);
                self.state.heatmapData = data.heatmapData || [];
                // Ensure demographics object has all keys
                self.state.demographics = {
                    grade: (data.demographics && data.demographics.grade) || [],
                    section: (data.demographics && data.demographics.section) || [],
                    stream: (data.demographics && data.demographics.stream) || []
                };
                self.state.stats = data.stats || { highRisk: 0, aligned: 0, avgClarityGap: 0 };
                console.log('Heatmap Data:', self.state.heatmapData.length, 'items');
                if (self.state.heatmapData.length > 0) {
                    console.log('Heatmap Data Sample:', self.state.heatmapData[0]);
                }
                console.log('Demographics object:', JSON.stringify(self.state.demographics));
                console.log('Current view:', self.state.view);
                console.log('Demographics for current view:', self.state.demographics[self.state.view]);
                console.log('Demographics array length:', self.state.demographics[self.state.view] ? self.state.demographics[self.state.view].length : 0);
                self.render();
                self.state.loading = false;
                self.updateLoadingState(false);
            })
            .catch(error => {
                console.error('Error loading heatmap data:', error);
                self.state.loading = false;
                self.updateLoadingState(false);
                alert('Error loading heatmap data. Please try again.');
            });
        },

        // Switch view (grade/section/stream)
        switchView: function(view) {
            this.state.view = view;
            
            // Update button states
            document.querySelectorAll('.heatmap-view-btn').forEach(btn => {
                if (btn.dataset.view === view) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            // Reload data with new view
            this.loadData();
        },

        // Update loading state
        updateLoadingState: function(loading) {
            const refreshBtn = document.getElementById('heatmap-refresh-btn');
            if (refreshBtn) {
                if (loading) {
                    refreshBtn.disabled = true;
                    refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
                } else {
                    refreshBtn.disabled = false;
                    refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
                }
            }
        },

        // Render the entire dashboard
        render: function() {
            this.renderStats();
            this.renderHeatmap();
        },

        // Render statistics cards
        renderStats: function() {
            const stats = this.state.stats;
            
            const highRiskEl = document.getElementById('heatmap-stat-highrisk');
            const alignedEl = document.getElementById('heatmap-stat-aligned');
            const clarityGapEl = document.getElementById('heatmap-stat-claritygap');

            if (highRiskEl) highRiskEl.textContent = stats.highRisk || 0;
            if (alignedEl) alignedEl.textContent = stats.aligned || 0;
            if (clarityGapEl) clarityGapEl.textContent = (stats.avgClarityGap || 0) + '%';
        },

        // Render heatmap grid
        renderHeatmap: function() {
            const container = document.getElementById('heatmap-grid-container');
            if (!container) {
                console.error('heatmap-grid-container not found');
                return;
            }

            // Clear existing content
            container.innerHTML = '';

            const demoCats = this.state.demographics[this.state.view] || [];
            const heatmapData = this.state.heatmapData;

            console.log('Rendering heatmap - demoCats:', demoCats.length, 'heatmapData:', heatmapData.length);
            console.log('Demographics object:', JSON.stringify(this.state.demographics));
            console.log('Current view:', this.state.view);
            console.log('Demographics for view:', this.state.demographics[this.state.view]);

            if (demoCats.length === 0 || heatmapData.length === 0) {
                const message = demoCats.length === 0 
                    ? `No demographics found for ${this.state.view} view.` 
                    : 'No heatmap data available.';
                container.innerHTML = '<div class="text-center p-5 text-muted">' + message + '</div>';
                console.warn('Cannot render heatmap:', message);
                return;
            }

            // Create table
            const table = document.createElement('table');
            table.className = 'heatmap-table';
            table.style.width = '100%';
            table.style.borderCollapse = 'collapse';

            // Create header row
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            
            // First header cell (Career Clusters)
            const firstHeader = document.createElement('th');
            firstHeader.className = 'heatmap-header-first';
            firstHeader.innerHTML = '<div class="font-bold">Career Clusters</div>';
            headerRow.appendChild(firstHeader);

            // Demographic headers
            demoCats.forEach(demo => {
                const th = document.createElement('th');
                th.className = 'heatmap-header';
                th.innerHTML = '<div class="font-semibold">' + demo + '</div>';
                headerRow.appendChild(th);
            });

            thead.appendChild(headerRow);
            table.appendChild(thead);

            // Create body
            const tbody = document.createElement('tbody');

            // Get unique clusters from data
            const uniqueClusters = [...new Set(heatmapData.map(d => d.cluster))];
            
            // If no clusters in data, use default clusters
            const clusters = uniqueClusters.length > 0 ? uniqueClusters : this.careerClusters;

            clusters.forEach(cluster => {
                const row = document.createElement('tr');
                
                // Cluster name cell
                const clusterCell = document.createElement('td');
                clusterCell.className = 'heatmap-cluster-cell';
                clusterCell.innerHTML = '<div class="text-sm font-medium truncate">' + cluster + '</div>';
                row.appendChild(clusterCell);

                // Data cells for each demographic
                demoCats.forEach(demo => {
                    const cell = document.createElement('td');
                    cell.className = 'heatmap-cell';
                    
                    // Find matching data
                    const cellData = heatmapData.find(d => 
                        d.cluster === cluster && d.demographic === demo
                    ) || {
                        cluster: cluster,
                        demographic: demo,
                        interest: 0,
                        knowledge: 0,
                        alignment: 0,
                        clarityGap: 0,
                        category: 'No Data',
                        color: '#E5E7EB',
                        priority: 5,
                        studentCount: 0
                    };

                    // Create cell content
                    const cellDiv = document.createElement('div');
                    cellDiv.className = 'heatmap-cell-content';
                    cellDiv.style.backgroundColor = cellData.color;
                    cellDiv.style.opacity = this.getIntensityOpacity(cellData.interest);
                    cellDiv.innerHTML = '<span class="heatmap-cell-text">' + cellData.studentCount + '</span>';
                    
                    // Add hover events
                    const self = this;
                    cellDiv.addEventListener('mouseenter', function(e) {
                        self.showTooltip(cellData, e);
                    });
                    cellDiv.addEventListener('mouseleave', function() {
                        self.hideTooltip();
                    });

                    cell.appendChild(cellDiv);
                    row.appendChild(cell);
                });

                tbody.appendChild(row);
            });

            table.appendChild(tbody);
            container.appendChild(table);
            console.log('Heatmap table rendered with', clusters.length, 'clusters and', demoCats.length, 'demographics');
        },

        // Get intensity opacity based on interest value
        getIntensityOpacity: function(value) {
            return 0.3 + (value / 100) * 0.7;
        },

        // Show tooltip
        showTooltip: function(cellData, event) {
            this.hideTooltip(); // Remove existing tooltip

            const tooltip = document.createElement('div');
            tooltip.id = 'heatmap-tooltip';
            tooltip.className = 'heatmap-tooltip';
            
            const categoryClass = cellData.category === 'High Risk' ? 'text-red-600' :
                                 cellData.category === 'Maintenance' ? 'text-yellow-600' :
                                 cellData.category === 'High Alignment' ? 'text-green-600' :
                                 'text-gray-600';

            tooltip.innerHTML = `
                <div class="font-bold text-gray-900 mb-2">${cellData.cluster}</div>
                <div class="text-sm text-gray-600 mb-3">${cellData.demographic}</div>
                <div class="space-y-2">
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-600">Interest Level:</span>
                        <span class="font-semibold text-gray-900">${cellData.interest}%</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-600">Knowledge Level:</span>
                        <span class="font-semibold text-gray-900">${cellData.knowledge}%</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-600">2030 Alignment:</span>
                        <span class="font-semibold text-gray-900">${cellData.alignment}%</span>
                    </div>
                    <div class="border-t border-gray-200 pt-2 mt-2">
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-700 font-medium">Clarity Gap:</span>
                            <span class="font-bold text-blue-600">${cellData.clarityGap}%</span>
                        </div>
                        <div class="text-xs text-gray-500 mt-1">
                            Gap between interest and pathway knowledge
                        </div>
                    </div>
                    <div class="bg-gray-50 p-2 rounded mt-2">
                        <div class="text-xs text-gray-600">Category:</div>
                        <div class="text-sm font-semibold ${categoryClass}">
                            ${cellData.category}
                        </div>
                        <div class="text-xs text-gray-600 mt-1">
                            ${cellData.studentCount} students in this segment
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(tooltip);

            // Position tooltip
            const rect = event.target.getBoundingClientRect();
            tooltip.style.top = (rect.top + window.scrollY - 10) + 'px';
            tooltip.style.left = (rect.right + window.scrollX + 10) + 'px';

            // Adjust if tooltip goes off screen
            setTimeout(() => {
                const tooltipRect = tooltip.getBoundingClientRect();
                if (tooltipRect.right > window.innerWidth) {
                    tooltip.style.left = (rect.left + window.scrollX - tooltipRect.width - 10) + 'px';
                }
                if (tooltipRect.bottom > window.innerHeight) {
                    tooltip.style.top = (window.innerHeight - tooltipRect.height - 20) + 'px';
                }
            }, 0);
        },

        // Hide tooltip
        hideTooltip: function() {
            const tooltip = document.getElementById('heatmap-tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        },

        // Export data to CSV
        exportData: function() {
            const heatmapData = this.state.heatmapData;
            
            if (heatmapData.length === 0) {
                alert('No data to export');
                return;
            }

            // Create CSV header
            const headers = ['Career Cluster', 'Demographic', 'Interest %', 'Knowledge %', 'Alignment %', 'Clarity Gap %', 'Category', 'Students'];
            const csvRows = [headers.join(',')];

            // Add data rows
            heatmapData.forEach(d => {
                csvRows.push([
                    d.cluster,
                    d.demographic,
                    d.interest,
                    d.knowledge,
                    d.alignment,
                    d.clarityGap,
                    d.category,
                    d.studentCount
                ].join(','));
            });

            const csv = csvRows.join('\n');
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'career-analytics-' + new Date().toISOString().split('T')[0] + '.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            HeatmapDashboard.init();
        });
    } else {
        HeatmapDashboard.init();
    }

    // Make it globally accessible if needed
    window.HeatmapDashboard = HeatmapDashboard;

})();

