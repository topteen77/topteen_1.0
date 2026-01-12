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
            time_period: One of 'today', 'yesterday', '7days', '30days', '90days'
            
        Returns:
            tuple: (start_date, end_date) as strings
        """
        date_map = {
            'today': ('today', 'today'),
            'yesterday': ('yesterday', 'yesterday'),
            '7days': ('7daysAgo', 'today'),
            '30days': ('30daysAgo', 'today'),
            '90days': ('90daysAgo', 'today'),
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
        
        Returns:
            dict: {'total': int, 'new': int, 'returning': int}
        """
        if not self.client:
            return None
        
        try:
            from google.analytics.data_v1beta.types import RunRealtimeReportRequest
            
            # Get total active users
            request = RunRealtimeReportRequest(
                property=self.property_id,
                dimensions=[Dimension(name="newVsReturning")],
                metrics=[Metric(name="activeUsers")]
            )
            
            response = self.client.run_realtime_report(request)
            
            result = {'total': 0, 'new': 0, 'returning': 0}
            
            if response.rows:
                for row in response.rows:
                    user_type = row.dimension_values[0].value
                    count = int(row.metric_values[0].value)
                    result['total'] += count
                    
                    if user_type == 'new':
                        result['new'] = count
                    elif user_type == 'returning':
                        result['returning'] = count
            
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
            days_diff = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days
            prev_end_date = start_date
            prev_start_date = (datetime.strptime(prev_end_date, '%Y-%m-%d') - timedelta(days=days_diff)).strftime('%Y-%m-%d')
            
            # Get current period data
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[
                    DateRange(start_date=start_date, end_date=end_date),
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
        
        Args:
            time_period: Time period string
            limit: Number of top exit pages to return
            use_cache: Whether to use cached data
            
        Returns:
            list: List of dicts with exit page path and session count
        """
        if not self.client:
            return []
        
        cache_key = self._get_cache_key('get_exit_pages', time_period, limit)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        try:
            start_date, end_date = self._get_date_range(time_period)
            
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="exitPage")],
                metrics=[Metric(name="sessions")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                limit=limit
            )
            
            response = self.client.run_report(request)
            
            result = []
            for row in response.rows:
                exit_page = row.dimension_values[0].value
                if exit_page:  # Only include non-empty exit pages
                    result.append({
                        'exit_page': exit_page,
                        'count': int(row.metric_values[0].value)
                    })
            
            if use_cache:
                cache.set(cache_key, result, GA4_CACHE_TIMEOUT)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching exit pages: {e}", exc_info=True)
            return []

