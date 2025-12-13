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

