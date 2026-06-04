/**
 * Pure Vanilla JavaScript Heatmap Dashboard
 * NO REACT - Pure DOM manipulation and vanilla JS
 */

(function() {
    'use strict';

    // Prevent double-registration when dashboard_shell + page both included this file.
    if (window.__ttv2HeatmapDashboardJsLoaded) {
        return;
    }
    window.__ttv2HeatmapDashboardJsLoaded = true;

    // State management using plain JavaScript object
    const HeatmapDashboard = {
        state: {
            view: 'grade', // 'grade', 'section', or 'stream'
            heatmapData: [],
            colorPalette: null,
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

        getDefaultColorPalette: function() {
            // Keep in sync with institute/utils.py::HEATMAP_CATEGORY_COLORS
            return {
                'High Risk': '#EF4444',
                'Maintenance': '#F59E0B',
                'High Alignment': '#10B981',
                'Monitor': '#6B7280',
                'No Data': '#E5E7EB',
            };
        },

        // Initialize the dashboard
        init: function() {
            this.bindEvents();
            this.loadData();
        },

        // Detect whether the heatmap markup exists on the page
        isHeatmapPresent: function() {
            return !!document.getElementById('heatmap-grid-container');
        },

        // Get institute slug from URL or data attribute
        getInstituteSlug: function() {
            // Check if there's a data attribute on the container
            const container = document.getElementById('heatmap-grid-container');
            if (container && container.dataset.instituteSlug) {
                return container.dataset.instituteSlug;
            }
            
            const path = window.location.pathname || '';
            const heatmapMatch = path.match(/\/institute\/([^/]+)\/heatmap\/?$/);
            if (heatmapMatch && heatmapMatch[1]) {
                return heatmapMatch[1];
            }
            const dashMatch = path.match(/\/institute\/([^/]+)\/?$/);
            if (dashMatch && dashMatch[1]) {
                const seg = dashMatch[1];
                const reserved = {
                    marketing_group_dashboard: 1,
                    institute_group_dashboard: 1,
                    marketing_group_heatmap: 1,
                    institute_group_heatmap: 1,
                };
                if (!reserved[seg]) {
                    return seg;
                }
            }
            return null;
        },

        // Bind event listeners (delegated — supports v2 AJAX-injected heatmap markup)
        bindEvents: function() {
            const self = this;
            if (window.__ttv2HeatmapEventsBound) {
                return;
            }
            window.__ttv2HeatmapEventsBound = true;
            document.body.addEventListener('click', function(e) {
                const t = e.target;
                if (!t || !t.closest) {
                    return;
                }
                if (t.closest('#heatmap-refresh-btn')) {
                    e.preventDefault();
                    self.loadData();
                    return;
                }
                if (t.closest('#heatmap-export-btn')) {
                    e.preventDefault();
                    self.exportData();
                    return;
                }
                const vb = t.closest('.heatmap-view-btn');
                if (vb && vb.dataset && vb.dataset.view) {
                    e.preventDefault();
                    self.switchView(vb.dataset.view);
                }
            });
        },

        // Load data from API
        loadData: function() {
            const self = this;
            if (!this.isHeatmapPresent()) {
                return;
            }
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
            .then(response => response.text().then(function(text) {
                if (!response.ok) {
                    var msg = 'Could not load heatmap data (' + response.status + ')';
                    try {
                        var errObj = JSON.parse(text);
                        if (errObj && errObj.error) {
                            msg = errObj.error;
                        }
                    } catch (e) {}
                    throw new Error(msg);
                }
                var data;
                try {
                    data = JSON.parse(text);
                } catch (e2) {
                    throw new Error('Invalid response from server (not JSON). Try signing in again.');
                }
                return data;
            }))
            .then(data => {
                if (data && data.error && !Array.isArray(data.heatmapData)) {
                    throw new Error(typeof data.error === 'string' ? data.error : 'Heatmap data unavailable');
                }
                self.state.heatmapData = data.heatmapData || [];
                self.state.colorPalette = data.colorPalette || self.getDefaultColorPalette();
                // Ensure demographics object has all keys
                self.state.demographics = {
                    grade: (data.demographics && data.demographics.grade) || [],
                    section: (data.demographics && data.demographics.section) || [],
                    stream: (data.demographics && data.demographics.stream) || []
                };
                self.state.stats = data.stats || { highRisk: 0, aligned: 0, avgClarityGap: 0 };
                self.render();
                self.state.loading = false;
                self.updateLoadingState(false);
            })
            .catch(error => {
                console.error('Error loading heatmap data:', error);
                self.state.loading = false;
                self.updateLoadingState(false);
                var msg = (error && error.message) ? error.message : 'Error loading heatmap data. Please try again.';
                alert(msg);
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
                return;
            }

            // Clear existing content
            container.innerHTML = '';

            const noDataColor = (this.state.colorPalette && this.state.colorPalette['No Data'])
                ? this.state.colorPalette['No Data']
                : '#E5E7EB';

            const demoCats = this.state.demographics[this.state.view] || [];
            const heatmapData = this.state.heatmapData;

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
                        color: noDataColor,
                        priority: 5,
                        studentCount: 0
                    };

                    // Create cell content
                    const cellDiv = document.createElement('div');
                    cellDiv.className = 'heatmap-cell-content';
                    if ((cellData.studentCount || 0) === 0) {
                        cellDiv.classList.add('is-no-data');
                    }
                    cellDiv.style.backgroundColor = cellData.color;
                    cellDiv.style.opacity = this.getIntensityOpacity(cellData.interest);
                    cellDiv.innerHTML = '<span class="heatmap-cell-text">' + cellData.studentCount + '</span>';
                    cellDiv.title = cluster + ' | ' + demo + ' | ' + (cellData.studentCount || 0) + ' students';
                    
                    // Add hover events
                    const self = this;
                    cellDiv.addEventListener('mouseenter', function(e) {
                        self.showTooltip(cellData, e.currentTarget || cellDiv);
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
        },

        // Get intensity opacity based on interest value
        getIntensityOpacity: function(value) {
            return 0.3 + (value / 100) * 0.7;
        },

        // Escape html to keep tooltip rendering safe
        escapeHtml: function(value) {
            return String(value === null || value === undefined ? '' : value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        getCategoryToneClass: function(category) {
            if (category === 'High Risk') return 'is-risk';
            if (category === 'Maintenance') return 'is-maintenance';
            if (category === 'High Alignment') return 'is-alignment';
            if (category === 'Monitor') return 'is-neutral';
            return 'is-neutral';
        },

        getCategoryHint: function(category) {
            if (category === 'High Risk') {
                return 'High interest with low pathway readiness. Prioritize orientation workshops and mentor checkpoints.';
            }
            if (category === 'Maintenance') {
                return 'Current engagement is stable. Keep reinforcement activities and periodic exposure sessions.';
            }
            if (category === 'High Alignment') {
                return 'Strong interest and knowledge match. Recommend advanced pathways and challenge projects.';
            }
            if (category === 'Monitor') {
                return 'Interest and knowledge are still developing. Track progress and plan targeted exposure sessions.';
            }
            if (category === 'No Data') {
                return 'Not enough student responses yet. Encourage participation to improve confidence.';
            }
            return 'Review this segment and plan the next counseling touchpoint.';
        },

        // Position tooltip within the viewport (fixed coords; avoids left-edge clipping)
        positionTooltip: function(tooltip, anchorEl) {
            const pad = 12;
            const rect = anchorEl.getBoundingClientRect();
            const tw = tooltip.offsetWidth;
            const th = tooltip.offsetHeight;

            let left = rect.right + pad;
            let top = rect.top + (rect.height / 2) - (th / 2);

            if (left + tw > window.innerWidth - pad) {
                left = rect.left - tw - pad;
            }
            if (left < pad) {
                left = Math.max(pad, rect.left + (rect.width / 2) - (tw / 2));
            }
            if (top + th > window.innerHeight - pad) {
                top = window.innerHeight - th - pad;
            }
            if (top < pad) {
                top = pad;
            }

            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
        },

        // Show tooltip
        showTooltip: function(cellData, anchorEl) {
            this.hideTooltip(); // Remove existing tooltip

            const tooltip = document.createElement('div');
            tooltip.id = 'heatmap-tooltip';
            tooltip.className = 'heatmap-tooltip';

            const category = this.escapeHtml(cellData.category || 'No Data');
            const toneClass = this.getCategoryToneClass(cellData.category);
            const safeCluster = this.escapeHtml(cellData.cluster);
            const safeDemographic = this.escapeHtml(cellData.demographic);
            const interest = Number(cellData.interest) || 0;
            const knowledge = Number(cellData.knowledge) || 0;
            const alignment = Number(cellData.alignment) || 0;
            const clarityGap = Number(cellData.clarityGap) || 0;
            const students = Number(cellData.studentCount) || 0;
            const insight = this.escapeHtml(this.getCategoryHint(cellData.category));

            tooltip.innerHTML = `
                <div class="heatmap-tooltip-head">
                    <div class="heatmap-tooltip-head-text">
                        <div class="heatmap-tooltip-title">${safeCluster}</div>
                        <div class="heatmap-tooltip-subtitle">${safeDemographic}</div>
                    </div>
                    <div class="heatmap-tooltip-chip ${toneClass}">${category}</div>
                </div>
                <div class="heatmap-tooltip-count">${students} students in this segment</div>
                <div class="heatmap-tooltip-metrics">
                    <div class="heatmap-tooltip-row">
                        <div class="heatmap-tooltip-row-label">Interest</div>
                        <div class="heatmap-tooltip-row-val">${interest}%</div>
                        <div class="heatmap-tooltip-bar"><span style="width:${interest}%;"></span></div>
                    </div>
                    <div class="heatmap-tooltip-row">
                        <div class="heatmap-tooltip-row-label">Knowledge</div>
                        <div class="heatmap-tooltip-row-val">${knowledge}%</div>
                        <div class="heatmap-tooltip-bar"><span style="width:${knowledge}%;"></span></div>
                    </div>
                    <div class="heatmap-tooltip-row">
                        <div class="heatmap-tooltip-row-label">2030 Alignment</div>
                        <div class="heatmap-tooltip-row-val">${alignment}%</div>
                        <div class="heatmap-tooltip-bar"><span style="width:${alignment}%;"></span></div>
                    </div>
                </div>
                <div class="heatmap-tooltip-gap">Clarity Gap: <strong>${clarityGap}%</strong></div>
                <div class="heatmap-tooltip-insight">${insight}</div>
            `;

            document.body.appendChild(tooltip);
            this.positionTooltip(tooltip, anchorEl);
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

    function safeInitOrReload() {
        if (!HeatmapDashboard.isHeatmapPresent()) {
            return;
        }
        // Bind events once (delegated) + (re)load data
        HeatmapDashboard.bindEvents();
        try { HeatmapDashboard.loadData(); } catch (e) {}
    }

    // Initialize only if heatmap markup exists
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', safeInitOrReload);
    } else {
        safeInitOrReload();
    }

    // v2 AJAX navigation injects markup; re-init after content load
    document.addEventListener('ttv2:content:loaded', function() {
        safeInitOrReload();
    });

    // Make it globally accessible if needed
    window.HeatmapDashboard = HeatmapDashboard;

    /** Call after v2 AJAX injects heatmap HTML (scripts in injected HTML do not run). */
    window.ttv2HeatmapReinitAfterPartialLoad = function() {
        if (!window.HeatmapDashboard) {
            return;
        }
        try {
            const el = document.getElementById('heatmap-refresh-date');
            if (el) {
                el.textContent = new Date().toLocaleDateString();
            }
        } catch (e) {}
        try {
            // Partial inject can finish before ttv2:content:loaded; always bind delegated handlers first.
            HeatmapDashboard.bindEvents();
            HeatmapDashboard.loadData();
        } catch (e2) {
            console.warn('ttv2HeatmapReinitAfterPartialLoad', e2);
        }
    };

})();

