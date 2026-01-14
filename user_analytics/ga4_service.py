"""
Enhanced GA4 Service for comprehensive analytics integration.
Provides detailed documentation and caching for optimal performance.
"""
import logging
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    OrderBy,
    FilterExpression,
    Filter,
)
from django.conf import settings
from django.core.cache import cache
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# GA4 Configuration - Update these in your settings.py
GA4_KEY_FILE_LOCATION = getattr(settings, 'GA4_KEY_FILE_LOCATION', './media/upload/demoproject.json')
GA4_PROPERTY_ID = getattr(settings, 'GA4_PROPERTY_ID', 'properties/493379109')
GA4_CACHE_TIMEOUT = getattr(settings, 'GA4_CACHE_TIMEOUT', 3600)  # 1 hour default


class GA4Service:
    """
    Service class for interacting with Google Analytics 4 API.
    Includes caching, error handling, and comprehensive metrics.
    
    Usage:
        service = GA4Service()
        metrics = service.get_user_metrics(time_period='30days')
    """
    
    def __init__(self):
        self.client = None
        self.property_id = GA4_PROPERTY_ID
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize GA4 client with service account credentials"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                GA4_KEY_FILE_LOCATION,
                scopes=['https://www.googleapis.com/auth/analytics.readonly']
            )
            self.client = BetaAnalyticsDataClient(credentials=credentials)
            logger.info("GA4 client initialized successfully")
        except FileNotFoundError:
            logger.warning(f"GA4 key file not found at {GA4_KEY_FILE_LOCATION}")
            self.client = None
        except Exception as e:
            logger.error(f"Error initializing GA4 client: {e}")
            self.client = None
    
    def _get_cache_key(self, method_name, *args, **kwargs):
        """Generate cache key for method call"""
        key_parts = [method_name]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"ga4_{'_'.join(key_parts)}"
    
    def _get_date_range(self, time_period):
        """
        Convert time period string to GA4 date range.
        
        Args:
            time_period: One of 'today', 'yesterday', '7days', '30days', '90days', 'alltime'
            
        Returns:
            tuple: (start_date, end_date) as strings
        """
        date_map = {
            'today': ('today', 'today'),
            'yesterday': ('yesterday', 'yesterday'),
            '7days': ('7daysAgo', 'today'),
            '30days': ('30daysAgo', 'today'),
            '90days': ('90daysAgo', 'today'),
            'alltime': ('2020-01-01', 'today'),  # Use a far back date for all time
        }
        return date_map.get(time_period, ('30daysAgo', 'today'))
    
    def get_user_metrics(self, time_period='30days', use_cache=True):
        """
        Get comprehensive user metrics for the specified time period.
        
        Metrics include:
        - Active users
        - Sessions
        - New users
        - Engaged sessions
        - Screen page views
        - Conversions
        - Total revenue
        
        Args:
            time_period: Time period string (default: '30days')
            use_cache: Whether to use cached data (default: True)
            
        Returns:
            dict: User metrics with dates and values
        """
        if not self.client:
            return None
        
        cache_key = self._get_cache_key('get_user_metrics', time_period)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Returning cached user metrics for {time_period}")
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="date")],
                metrics=[
                    Metric(name="activeUsers"),
                    Metric(name="sessions"),
                    Metric(name="newUsers"),
                    Metric(name="engagedSessions"),
                    Metric(name="screenPageViews"),
                    Metric(name="conversions"),
                    Metric(name="totalRevenue"),
                ],
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
            )
            
            response = self.client.run_report(request)
            
            result = {
                'dates': [],
                'activeUsers': [],
                'sessions': [],
                'newUsers': [],
                'engagedSessions': [],
                'screenPageViews': [],
                'conversions': [],
                'revenue': [],
            }
            
            for row in response.rows:
                date_str = row.dimension_values[0].value
                formatted_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                result['dates'].append(formatted_date)
                result['activeUsers'].append(int(row.metric_values[0].value))
                result['sessions'].append(int(row.metric_values[1].value))
                result['newUsers'].append(int(row.metric_values[2].value))
                result['engagedSessions'].append(int(row.metric_values[3].value))
                result['screenPageViews'].append(int(row.metric_values[4].value))
                result['conversions'].append(int(row.metric_values[5].value))
                result['revenue'].append(float(row.metric_values[6].value))
            
            # Cache the result
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching user metrics: {e}", exc_info=True)
            return None
    
    def get_device_breakdown(self, time_period='30days', use_cache=True):
        """
        Get user breakdown by device category.
        
        Args:
            time_period: Time period string
            use_cache: Whether to use cached data
            
        Returns:
            dict: Device breakdown with devices and user counts
        """
        if not self.client:
            return None
        
        cache_key = self._get_cache_key('get_device_breakdown', time_period)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="deviceCategory")],
                metrics=[Metric(name="activeUsers")],
            )
            
            response = self.client.run_report(request)
            
            result = {
                'devices': [],
                'users': []
            }
            
            for row in response.rows:
                result['devices'].append(row.dimension_values[0].value)
                result['users'].append(int(row.metric_values[0].value))
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching device breakdown: {e}", exc_info=True)
            return None
    
    def get_top_pages(self, time_period='30days', limit=10, use_cache=True):
        """
        Get top pages by pageviews.
        
        Args:
            time_period: Time period string
            limit: Number of top pages to return
            use_cache: Whether to use cached data
            
        Returns:
            list: List of dicts with page title, path, and pageviews
        """
        if not self.client:
            return None
        
        cache_key = self._get_cache_key('get_top_pages', time_period, limit)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="pageTitle"), Dimension(name="pagePath")],
                metrics=[Metric(name="screenPageViews")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                result.append({
                    'title': row.dimension_values[0].value,
                    'path': row.dimension_values[1].value,
                    'pageviews': int(row.metric_values[0].value)
                })
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching top pages: {e}", exc_info=True)
            return None
    
    def get_traffic_sources(self, time_period='30days', limit=10, use_cache=True):
        """
        Get traffic source breakdown.
        
        Args:
            time_period: Time period string
            limit: Number of top sources to return
            use_cache: Whether to use cached data
            
        Returns:
            dict: Traffic sources with sources and session counts
        """
        if not self.client:
            return None
        
        cache_key = self._get_cache_key('get_traffic_sources', time_period, limit)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="sessionSource")],
                metrics=[Metric(name="sessions")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = {
                'sources': [],
                'sessions': []
            }
            
            for row in response.rows:
                result['sources'].append(row.dimension_values[0].value)
                result['sessions'].append(int(row.metric_values[0].value))
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching traffic sources: {e}", exc_info=True)
            return None
    
    def get_real_time_users(self):
        """
        Get real-time active users.
        
        Returns:
            int: Number of active users currently on the site
        """
        if not self.client:
            return None
        
        try:
            from google.analytics.data_v1beta.types import RunRealtimeReportRequest
            
            request = RunRealtimeReportRequest(
                property=self.property_id,
                metrics=[Metric(name="activeUsers")]
            )
            
            response = self.client.run_realtime_report(request)
            
            if response.rows:
                return int(response.rows[0].metric_values[0].value)
            return 0
            
        except Exception as e:
            logger.error(f"Error fetching real-time users: {e}", exc_info=True)
            return None
    
    def get_real_time_users_breakdown(self):
        """
        Get real-time users breakdown by new vs returning.
        Note: GA4 real-time API doesn't support newVsReturning dimension.
        Returns total active users only.
        
        Returns:
            dict: {'total': int, 'new': 0, 'returning': 0}
        """
        if not self.client:
            return None
        
        try:
            from google.analytics.data_v1beta.types import RunRealtimeReportRequest
            
            # Get total active users (newVsReturning is not available in real-time API)
            request = RunRealtimeReportRequest(
                property=self.property_id,
                metrics=[Metric(name="activeUsers")]
            )
            
            response = self.client.run_realtime_report(request)
            
            result = {'total': 0, 'new': 0, 'returning': 0}
            
            if response.rows:
                total = int(response.rows[0].metric_values[0].value)
                result['total'] = total
                # Cannot determine new vs returning from real-time API
                # Return 0 for both (caller can use total)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching real-time users breakdown: {e}", exc_info=True)
            return None
    
    def get_real_time_users_by_country(self):
        """
        Get real-time active users by country.
        
        Returns:
            list: List of dicts with country and activeUsers count
        """
        if not self.client:
            return None
        
        try:
            from google.analytics.data_v1beta.types import RunRealtimeReportRequest
            
            request = RunRealtimeReportRequest(
                property=self.property_id,
                dimensions=[Dimension(name="country")],
                metrics=[Metric(name="activeUsers")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
                limit=10
            )
            
            response = self.client.run_realtime_report(request)
            
            result = []
            if response.rows:
                for row in response.rows:
                    result.append({
                        'country': row.dimension_values[0].value,
                        'activeUsers': int(row.metric_values[0].value)
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching real-time users by country: {e}", exc_info=True)
            return None
    
    def get_users_by_country(self, time_period='30days', limit=10, use_cache=True):
        """
        Get active users by country for a time period.
        
        Args:
            time_period: Time period string
            limit: Number of countries to return
            use_cache: Whether to use cached data
            
        Returns:
            list: List of dicts with country and activeUsers count
        """
        if not self.client:
            return None
        
        cache_key = self._get_cache_key('get_users_by_country', time_period, limit)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="country")],
                metrics=[Metric(name="activeUsers")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                result.append({
                    'country': row.dimension_values[0].value,
                    'activeUsers': int(row.metric_values[0].value)
                })
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching users by country: {e}", exc_info=True)
            return None
    
    def get_top_pages_with_trends(self, time_period='30days', limit=10, use_cache=True):
        """
        Get top pages by pageviews with percentage change from previous period.
        
        Args:
            time_period: Time period string
            limit: Number of top pages to return
            use_cache: Whether to use cached data
            
        Returns:
            list: List of dicts with page title, path, pageviews, and percentage change
        """
        if not self.client:
            return None
        
        cache_key = self._get_cache_key('get_top_pages_with_trends', time_period, limit)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            # Calculate previous period dates
            # Handle GA4 date format strings ('today', 'yesterday', '7daysAgo', etc.)
            if end_date == 'today':
                end_date_obj = datetime.now().date()
            elif end_date == 'yesterday':
                end_date_obj = (datetime.now() - timedelta(days=1)).date()
            elif end_date.endswith('daysAgo'):
                days = int(end_date.replace('daysAgo', ''))
                end_date_obj = (datetime.now() - timedelta(days=days)).date()
            else:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if start_date == 'today':
                start_date_obj = datetime.now().date()
            elif start_date == 'yesterday':
                start_date_obj = (datetime.now() - timedelta(days=1)).date()
            elif start_date.endswith('daysAgo'):
                days = int(start_date.replace('daysAgo', ''))
                start_date_obj = (datetime.now() - timedelta(days=days)).date()
            else:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            days_diff = (end_date_obj - start_date_obj).days
            prev_end_date_obj = start_date_obj
            prev_start_date_obj = prev_end_date_obj - timedelta(days=days_diff)
            
            # Convert back to GA4 date format strings ('YYYY-MM-DD')
            prev_end_date = prev_end_date_obj.strftime('%Y-%m-%d')
            prev_start_date = prev_start_date_obj.strftime('%Y-%m-%d')
            
            # Convert current period dates to 'YYYY-MM-DD' format for DateRange
            current_start = start_date_obj.strftime('%Y-%m-%d') if start_date in ['today', 'yesterday'] or start_date.endswith('daysAgo') else start_date
            current_end = end_date_obj.strftime('%Y-%m-%d') if end_date in ['today', 'yesterday'] or end_date.endswith('daysAgo') else end_date
            
            # Get current period data
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[
                    DateRange(start_date=current_start, end_date=current_end),
                    DateRange(start_date=prev_start_date, end_date=prev_end_date)
                ],
                dimensions=[Dimension(name="pageTitle"), Dimension(name="pagePath")],
                metrics=[Metric(name="screenPageViews")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                current_views = int(row.metric_values[0].value)
                previous_views = int(row.metric_values[1].value) if len(row.metric_values) > 1 else 0
                
                # Calculate percentage change
                if previous_views > 0:
                    percent_change = ((current_views - previous_views) / previous_views) * 100
                elif current_views > 0:
                    percent_change = 100.0  # New page
                else:
                    percent_change = 0.0
                
                result.append({
                    'title': row.dimension_values[0].value,
                    'path': row.dimension_values[1].value,
                    'pageviews': current_views,
                    'previousPageviews': previous_views,
                    'percentChange': round(percent_change, 1)
                })
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching top pages with trends: {e}", exc_info=True)
            return None
    
    def get_user_engagement(self, time_period='30days', use_cache=True):
        """
        Get user engagement metrics.
        
        Args:
            time_period: Time period string
            use_cache: Whether to use cached data
            
        Returns:
            dict: Engagement metrics (duration, session duration, bounce rate)
        """
        if not self.client:
            return None
        
        cache_key = self._get_cache_key('get_user_engagement', time_period)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                metrics=[
                    Metric(name="userEngagementDuration"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="bounceRate"),
                ],
            )
            
            response = self.client.run_report(request)
            
            if response.rows:
                row = response.rows[0]
                result = {
                    'engagementDuration': float(row.metric_values[0].value) / 60,  # Convert to minutes
                    'averageSessionDuration': float(row.metric_values[1].value) / 60,  # Convert to minutes
                    'bounceRate': float(row.metric_values[2].value),
                }
                
                if use_cache:
                    cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
                
                return result
            return None
            
        except Exception as e:
            logger.error(f"Error fetching user engagement: {e}", exc_info=True)
            return None
    
    def get_pageviews_by_path(self, page_path, time_period='30days', limit=1000, use_cache=False):
        """
        Get pageview details for a specific page path from GA4.
        
        Args:
            page_path: The page path to filter by (e.g., '/careers/tag/trending')
            time_period: Time period string
            limit: Maximum number of records to return
            use_cache: Whether to use cached data
            
        Returns:
            list: List of dicts with pageview details including date, source, device, etc.
        """
        if not self.client:
            return None
        
        cache_key = self._get_cache_key('get_pageviews_by_path', page_path, time_period, limit)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            # Create filter for page path
            path_filter = Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.EXACT,
                    value=page_path
                )
            )
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[
                    Dimension(name="date"),
                    Dimension(name="pageTitle"),
                    Dimension(name="pagePath"),
                    Dimension(name="sessionSource"),
                    Dimension(name="deviceCategory"),
                    Dimension(name="country"),
                ],
                metrics=[Metric(name="screenPageViews")],
                dimension_filter=FilterExpression(
                    filter=path_filter
                ),
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                date_str = row.dimension_values[0].value
                formatted_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                result.append({
                    'date': formatted_date,
                    'page_title': row.dimension_values[1].value,
                    'page_path': row.dimension_values[2].value,
                    'source': row.dimension_values[3].value or 'Direct',
                    'device': row.dimension_values[4].value or 'Unknown',
                    'country': row.dimension_values[5].value or 'Unknown',
                    'pageviews': int(row.metric_values[0].value),
                })
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching pageviews by path: {e}", exc_info=True)
            return None
    
    def get_all_page_paths(self, time_period='30days', limit=1000, use_cache=False):
        """
        Get all unique page paths from GA4 for autocomplete/dropdown.
        
        Args:
            time_period: Time period string
            limit: Maximum number of paths to return
            use_cache: Whether to use cached data
            
        Returns:
            list: List of unique page paths
        """
        if not self.client:
            return []
        
        cache_key = self._get_cache_key('get_all_page_paths', time_period, limit)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="pagePath")],
                metrics=[Metric(name="screenPageViews")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                path = row.dimension_values[0].value
                if path and path not in result:
                    result.append(path)
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching all page paths: {e}", exc_info=True)
            return []
    
    def get_entry_pages(self, time_period='30days', limit=10, use_cache=False):
        """
        Get top entry pages from GA4.
        
        Args:
            time_period: Time period string
            limit: Number of top entry pages to return
            use_cache: Whether to use cached data
            
        Returns:
            list: List of dicts with entry page path and session count
        """
        if not self.client:
            return []
        
        cache_key = self._get_cache_key('get_entry_pages', time_period, limit)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="landingPage")],
                metrics=[Metric(name="sessions")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                result.append({
                    'entry_page': row.dimension_values[0].value,
                    'count': int(row.metric_values[0].value)
                })
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching entry pages: {e}", exc_info=True)
            return []
    
    def get_exit_pages(self, time_period='30days', limit=10, use_cache=False):
        """
        Get top exit pages from GA4.
        Note: GA4 API doesn't have an 'exitPage' dimension directly.
        This method returns an empty list as exit pages need to be calculated
        from session data, which is not available in standard GA4 reports.
        
        Args:
            time_period: Time period string
            limit: Number of top exit pages to return
            use_cache: Whether to use cached data
            
        Returns:
            list: Empty list (exit pages not available via GA4 API)
        """
        if not self.client:
            return []
        
        # GA4 API doesn't support exitPage dimension
        # Exit pages need to be calculated from session-level data
        # which requires different API calls or data export
        logger.warning("Exit pages are not available via GA4 standard API. Use session data instead.")
        return []
    
    def get_sessions_by_filters(self, time_period='30days', source=None, country=None, device=None, entry_page=None, exit_page=None, limit=1000, use_cache=False):
        """
        Get session data from GA4 filtered by various parameters.
        
        Args:
            time_period: Time period string
            source: Filter by session source
            country: Filter by country
            device: Filter by device category
            entry_page: Filter by entry page
            exit_page: Filter by exit page
            limit: Maximum number of records to return
            use_cache: Whether to use cached data
            
        Returns:
            list: List of dicts with session data
        """
        if not self.client:
            return None
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            # Build dimensions
            dimensions = [
                Dimension(name="date"),
                Dimension(name="sessionSource"),
                Dimension(name="country"),
                Dimension(name="deviceCategory"),
                Dimension(name="landingPage"),
            ]
            
            # Build filters
            filters = []
            
            if source:
                # Handle direct traffic variations
                if source.lower() in ['(direct)', 'direct', '(not set)']:
                    source_filter = Filter(
                        field_name="sessionSource",
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.EXACT,
                            value="(direct)"
                        )
                    )
                    filters.append(source_filter)
                else:
                    source_filter = Filter(
                        field_name="sessionSource",
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.EXACT,
                            value=source
                        )
                    )
                    filters.append(source_filter)
            
            if country:
                country_filter = Filter(
                    field_name="country",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.EXACT,
                        value=country
                    )
                )
                filters.append(country_filter)
            
            if device:
                device_filter = Filter(
                    field_name="deviceCategory",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.EXACT,
                        value=device
                    )
                )
                filters.append(device_filter)
            
            if entry_page:
                entry_filter = Filter(
                    field_name="landingPage",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.EXACT,
                        value=entry_page
                    )
                )
                filters.append(entry_filter)
            
            # Note: Exit page filtering is not supported in GA4 aggregated reports
            # Exit pages are session-level and require different query structure
            # The exit_page parameter is accepted but won't be applied to GA4 query
            
            # Build filter expression
            dimension_filter = None
            if filters:
                if len(filters) == 1:
                    dimension_filter = FilterExpression(filter=filters[0])
                else:
                    # Combine filters with AND
                    dimension_filter = FilterExpression(
                        and_group=FilterExpression.FilterExpressionList(expressions=[FilterExpression(filter=f) for f in filters])
                    )
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=dimensions,
                metrics=[Metric(name="sessions"), Metric(name="screenPageViews")],
                dimension_filter=dimension_filter,
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                result.append({
                    'date': row.dimension_values[0].value,
                    'source': row.dimension_values[1].value or '(direct)',
                    'country': row.dimension_values[2].value or 'Unknown',
                    'device': row.dimension_values[3].value or 'Unknown',
                    'entry_page': row.dimension_values[4].value if len(row.dimension_values) > 4 else 'N/A',
                    'sessions': int(row.metric_values[0].value),
                    'pageviews': int(row.metric_values[1].value),
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching sessions by filters from GA4: {e}", exc_info=True)
            return None
    
    def get_sessions_with_client_ids(self, time_period='30days', limit=10000):
        """
        Fetch GA4 sessions with client IDs for linking with Django sessions.
        
        Args:
            time_period: Time period string ('today', 'yesterday', '7days', '30days', '90days')
            limit: Maximum number of records to return
            
        Returns:
            list: List of dicts with session data including client IDs
        """
        if not self.client:
            logger.warning("GA4 client not initialized")
            return None
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            # Build dimensions - include clientId for linking
            dimensions = [
                Dimension(name="date"),
                Dimension(name="clientId"),  # GA4 client ID
                Dimension(name="sessionId"),  # GA4 session ID
                Dimension(name="sessionSource"),
                Dimension(name="country"),
                Dimension(name="deviceCategory"),
                Dimension(name="landingPage"),
                Dimension(name="exitPage"),
            ]
            
            # Build metrics
            metrics = [
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
            ]
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=dimensions,
                metrics=metrics,
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                result.append({
                    'date': row.dimension_values[0].value,
                    'client_id': row.dimension_values[1].value if len(row.dimension_values) > 1 else None,
                    'session_id': row.dimension_values[2].value if len(row.dimension_values) > 2 else None,
                    'source': row.dimension_values[3].value if len(row.dimension_values) > 3 else '(direct)',
                    'country': row.dimension_values[4].value if len(row.dimension_values) > 4 else 'Unknown',
                    'device': row.dimension_values[5].value if len(row.dimension_values) > 5 else 'Unknown',
                    'entry_page': row.dimension_values[6].value if len(row.dimension_values) > 6 else 'N/A',
                    'exit_page': row.dimension_values[7].value if len(row.dimension_values) > 7 else None,
                    'sessions': int(row.metric_values[0].value) if len(row.metric_values) > 0 else 0,
                    'pageviews': int(row.metric_values[1].value) if len(row.metric_values) > 1 else 0,
                    'users': int(row.metric_values[2].value) if len(row.metric_values) > 2 else 0,
                })
            
            logger.info(f"Fetched {len(result)} sessions with client IDs from GA4")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching sessions with client IDs from GA4: {e}", exc_info=True)
            return None
    
    def sync_sessions_to_db(self, time_period='30days', link_users=True):
        """
        Sync GA4 session data to database (GA4Session model).
        Links GA4 sessions with Django user sessions via client ID matching.
        
        Args:
            time_period: Time period string
            link_users: Whether to attempt linking sessions to Django users
            
        Returns:
            dict: Sync statistics
        """
        from user_analytics.models import GA4Session, UserJourney
        from django.utils import timezone
        from datetime import datetime, timedelta
        from django.db import transaction
        
        if not self.client:
            logger.warning("GA4 client not initialized, cannot sync")
            return {'success': False, 'error': 'GA4 client not initialized'}
        
        try:
            # Fetch sessions from GA4
            ga4_sessions = self.get_sessions_with_client_ids(time_period=time_period)
            if not ga4_sessions:
                return {'success': False, 'error': 'No sessions fetched from GA4'}
            
            # Calculate date range for filtering existing records
            start_date, end_date = self._get_date_range(time_period)
            
            # Parse dates
            if start_date == 'today':
                start_date_obj = datetime.now().date()
            elif start_date == 'yesterday':
                start_date_obj = (datetime.now() - timedelta(days=1)).date()
            elif start_date.endswith('daysAgo'):
                days = int(start_date.replace('daysAgo', ''))
                start_date_obj = (datetime.now() - timedelta(days=days)).date()
            else:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            stats = {
                'total_fetched': len(ga4_sessions),
                'created': 0,
                'updated': 0,
                'linked_users': 0,
                'linked_sessions': 0,
            }
            
            with transaction.atomic():
                for ga4_data in ga4_sessions:
                    try:
                        # Parse date
                        date_str = ga4_data['date']
                        if len(date_str) == 8:  # Format: YYYYMMDD
                            session_date = datetime.strptime(date_str, '%Y%m%d').date()
                        else:
                            session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        
                        client_id = ga4_data.get('client_id')
                        if not client_id:
                            continue
                        
                        # Prepare defaults
                        # Note: synced_at has auto_now_add=True, so don't set it manually
                        # Note: updated has auto_now=True, so it will be set automatically
                        defaults = {
                            'ga4_session_id': ga4_data.get('session_id'),
                            'date': session_date,
                            'source': ga4_data.get('source') or '(direct)',
                            'country': ga4_data.get('country') or 'Unknown',
                            'device': ga4_data.get('device') or 'Unknown',
                            'entry_page': ga4_data.get('entry_page') or '',
                            'exit_page': ga4_data.get('exit_page'),
                            'sessions_count': ga4_data.get('sessions', 1),
                            'pageviews': ga4_data.get('pageviews', 0),
                            'users': ga4_data.get('users', 1),
                            # Don't set synced_at - it has auto_now_add=True
                            # For updates, we need to manually update synced_at
                        }
                        
                        # Try to link with Django session via client ID
                        django_session_id = None
                        user = None
                        
                        if link_users and client_id:
                            # Find UserJourney with matching GA4 client ID
                            journey = UserJourney.objects.filter(
                                ga4_client_id=client_id
                            ).order_by('-start_time').first()
                            
                            if journey:
                                django_session_id = journey.session_id
                                user = journey.user
                                stats['linked_sessions'] += 1
                                if user:
                                    stats['linked_users'] += 1
                        
                        defaults['django_session_id'] = django_session_id
                        defaults['user'] = user
                        
                        # Create or update GA4Session
                        # Use unique constraint fields for lookup
                        ga4_session, created = GA4Session.objects.update_or_create(
                            ga4_client_id=client_id,
                            date=session_date,
                            source=defaults['source'],
                            country=defaults['country'],
                            device=defaults['device'],
                            entry_page=defaults['entry_page'] or '',
                            defaults=defaults
                        )
                        
                        # Update synced_at for both new and existing records
                        # (auto_now_add only works on creation, so we update it manually)
                        if not created:
                            # For updates, manually update synced_at
                            GA4Session.objects.filter(id=ga4_session.id).update(synced_at=timezone.now())
                            stats['updated'] += 1
                        else:
                            stats['created'] += 1
                            
                    except Exception as e:
                        logger.error(f"Error syncing individual GA4 session: {e}", exc_info=True)
                        continue
            
            logger.info(f"GA4 sync completed: {stats}")
            return {'success': True, **stats}
            
        except Exception as e:
            logger.error(f"Error syncing GA4 sessions to DB: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

