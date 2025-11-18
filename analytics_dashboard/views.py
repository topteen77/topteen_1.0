from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    OrderBy,
    Filter,
    FilterExpression,
)
import json
import logging
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

# GA4 Configuration
KEY_FILE_LOCATION = './media/upload/demoproject.json'
PROPERTY_ID = 'properties/493379109'

def get_analytics_client():
    """Create and return a GA4 client with proper credentials"""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            KEY_FILE_LOCATION,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        client = BetaAnalyticsDataClient(credentials=credentials)
        return client
    except Exception as e:
        logger.error(f"Error creating GA4 client: {e}")
        return None

def get_user_metrics(time_period='30days'):
    """Get user metrics for the specified time period"""
    client = get_analytics_client()
    if not client:
        return None
    
    try:
        # Set date range based on time period
        if time_period == 'today':
            start_date = "today"
            end_date = "today"
        elif time_period == 'yesterday':
            start_date = "yesterday"
            end_date = "yesterday"
        elif time_period == '7days':
            start_date = "7daysAgo"
            end_date = "today"
        elif time_period == '30days':
            start_date = "30daysAgo"
            end_date = "today"
        elif time_period == '90days':
            start_date = "90daysAgo"
            end_date = "today"
        else:
            # Default to 30 days
            start_date = "30daysAgo"
            end_date = "today"
        
        request = RunReportRequest(
            property=PROPERTY_ID,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name="date")],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="newUsers"),
                Metric(name="engagedSessions"),
                Metric(name="screenPageViews"),
                Metric(name="conversions"),  # Added conversion tracking
                Metric(name="totalRevenue"),  # Added revenue tracking
            ],
            order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
        )
        
        response = client.run_report(request)
        
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
            # Convert YYYYMMDD to a readable format
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
            
        return result
    except Exception as e:
        logger.error(f"Error fetching user metrics: {e}")
        return None

def get_device_breakdown(time_period='30days'):
    """Get user breakdown by device category"""
    client = get_analytics_client()
    if not client:
        return None
    
    try:
        # Set date range based on time period
        if time_period == 'today':
            start_date = "today"
            end_date = "today"
        elif time_period == 'yesterday':
            start_date = "yesterday"
            end_date = "yesterday"
        elif time_period == '7days':
            start_date = "7daysAgo"
            end_date = "today"
        elif time_period == '30days':
            start_date = "30daysAgo"
            end_date = "today"
        elif time_period == '90days':
            start_date = "90daysAgo"
            end_date = "today"
        else:
            # Default to 30 days
            start_date = "30daysAgo"
            end_date = "today"
            
        request = RunReportRequest(
            property=PROPERTY_ID,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[Metric(name="activeUsers")],
        )
        
        response = client.run_report(request)
        
        result = {
            'devices': [],
            'users': []
        }
        
        for row in response.rows:
            result['devices'].append(row.dimension_values[0].value)
            result['users'].append(int(row.metric_values[0].value))
            
        return result
    except Exception as e:
        logger.error(f"Error fetching device breakdown: {e}")
        return None

def get_top_pages(time_period='30days'):
    """Get top pages by pageviews"""
    client = get_analytics_client()
    if not client:
        return None
    
    try:
        # Set date range based on time period
        if time_period == 'today':
            start_date = "today"
            end_date = "today"
        elif time_period == 'yesterday':
            start_date = "yesterday"
            end_date = "yesterday"
        elif time_period == '7days':
            start_date = "7daysAgo"
            end_date = "today"
        elif time_period == '30days':
            start_date = "30daysAgo"
            end_date = "today"
        elif time_period == '90days':
            start_date = "90daysAgo"
            end_date = "today"
        else:
            # Default to 30 days
            start_date = "30daysAgo"
            end_date = "today"
            
        request = RunReportRequest(
            property=PROPERTY_ID,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name="pageTitle"), Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews")],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
            limit=10
        )
        
        response = client.run_report(request)
        
        result = []
        
        for row in response.rows:
            result.append({
                'title': row.dimension_values[0].value,
                'path': row.dimension_values[1].value,
                'pageviews': int(row.metric_values[0].value)
            })
            
        return result
    except Exception as e:
        logger.error(f"Error fetching top pages: {e}")
        return None

def get_user_engagement(time_period='30days'):
    """Get user engagement metrics"""
    client = get_analytics_client()
    if not client:
        return None
    
    try:
        # Set date range based on time period
        if time_period == 'today':
            start_date = "today"
            end_date = "today"
        elif time_period == 'yesterday':
            start_date = "yesterday"
            end_date = "yesterday"
        elif time_period == '7days':
            start_date = "7daysAgo"
            end_date = "today"
        elif time_period == '30days':
            start_date = "30daysAgo"
            end_date = "today"
        elif time_period == '90days':
            start_date = "90daysAgo"
            end_date = "today"
        else:
            # Default to 30 days
            start_date = "30daysAgo"
            end_date = "today"
            
        request = RunReportRequest(
            property=PROPERTY_ID,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="userEngagementDuration"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
            ],
        )
        
        response = client.run_report(request)
        
        if response.rows:
            row = response.rows[0]
            return {
                'engagementDuration': float(row.metric_values[0].value) / 60,  # Convert to minutes
                'averageSessionDuration': float(row.metric_values[1].value) / 60,  # Convert to minutes
                'bounceRate': float(row.metric_values[2].value),
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching user engagement: {e}")
        return None

def get_traffic_sources(time_period='30days'):
    """Get traffic source breakdown"""
    client = get_analytics_client()
    if not client:
        return None
    
    try:
        # Set date range based on time period
        if time_period == 'today':
            start_date = "today"
            end_date = "today"
        elif time_period == 'yesterday':
            start_date = "yesterday"
            end_date = "yesterday"
        elif time_period == '7days':
            start_date = "7daysAgo"
            end_date = "today"
        elif time_period == '30days':
            start_date = "30daysAgo"
            end_date = "today"
        elif time_period == '90days':
            start_date = "90daysAgo"
            end_date = "today"
        else:
            # Default to 30 days
            start_date = "30daysAgo"
            end_date = "today"
            
        request = RunReportRequest(
            property=PROPERTY_ID,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name="sessionSource")],
            metrics=[Metric(name="sessions")],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
            limit=10
        )
        
        response = client.run_report(request)
        
        result = {
            'sources': [],
            'sessions': []
        }
        
        for row in response.rows:
            result['sources'].append(row.dimension_values[0].value)
            result['sessions'].append(int(row.metric_values[0].value))
            
        return result
    except Exception as e:
        logger.error(f"Error fetching traffic sources: {e}")
        return None

def get_real_time_users():
    """Get real-time active users"""
    client = get_analytics_client()
    if not client:
        return None
    
    try:
        from google.analytics.data_v1beta.types import RunRealtimeReportRequest
        
        request = RunRealtimeReportRequest(
            property=PROPERTY_ID,
            metrics=[Metric(name="activeUsers")]
        )
        
        response = client.run_realtime_report(request)
        
        if response.rows:
            return int(response.rows[0].metric_values[0].value)
        return 0
    except Exception as e:
        logger.error(f"Error fetching real-time users: {e}")
        return None
    

def dashboard(request):
    """Main dashboard view"""
    # Get time period from request, default to 30 days
    time_period = request.GET.get('period', '30days')
    
    # Get all the required metrics
    user_metrics = get_user_metrics(time_period)
    device_breakdown = get_device_breakdown(time_period)
    top_pages = get_top_pages(time_period)
    engagement = get_user_engagement(time_period)
    traffic_sources = get_traffic_sources(time_period)
    real_time_users = get_real_time_users()
    
    # Calculate summary metrics
    summary = {
        'totalUsers': sum(user_metrics['activeUsers']) if user_metrics else 0,
        'totalSessions': sum(user_metrics['sessions']) if user_metrics else 0,
        'totalPageviews': sum(user_metrics['screenPageViews']) if user_metrics else 0,
        'newUsers': sum(user_metrics['newUsers']) if user_metrics else 0,
        'totalConversions': sum(user_metrics['conversions']) if user_metrics else 0,
        'totalRevenue': sum(user_metrics['revenue']) if user_metrics else 0,
        'realTimeUsers': real_time_users or 0,
    }
    
    # Format the time period for display
    display_period = {
        'today': 'Today',
        'yesterday': 'Yesterday',
        '7days': 'Last 7 Days',
        '30days': 'Last 30 Days',
        '90days': 'Last 90 Days',
    }.get(time_period, 'Last 30 Days')
    
    context = {
        'user_metrics': json.dumps(user_metrics) if user_metrics else None,
        'device_breakdown': json.dumps(device_breakdown) if device_breakdown else None,
        'traffic_sources': json.dumps(traffic_sources) if traffic_sources else None,
        'top_pages': top_pages,
        'engagement': engagement,
        'summary': summary,
        'time_period': time_period,
        'display_period': display_period,
    }
    
    return render(request, 'analytics_dashboard.html', context)

@csrf_exempt
def update_dashboard_data(request):
    """AJAX endpoint to update dashboard data"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            time_period = data.get('period', '30days')
            
            user_metrics = get_user_metrics(time_period)
            device_breakdown = get_device_breakdown(time_period)
            top_pages = get_top_pages(time_period)
            engagement = get_user_engagement(time_period)
            traffic_sources = get_traffic_sources(time_period)
            real_time_users = get_real_time_users()
            
            # Calculate summary metrics
            summary = {
                'totalUsers': sum(user_metrics['activeUsers']) if user_metrics else 0,
                'totalSessions': sum(user_metrics['sessions']) if user_metrics else 0,
                'totalPageviews': sum(user_metrics['screenPageViews']) if user_metrics else 0,
                'newUsers': sum(user_metrics['newUsers']) if user_metrics else 0,
                'totalConversions': sum(user_metrics['conversions']) if user_metrics else 0,
                'totalRevenue': sum(user_metrics['revenue']) if user_metrics else 0,
                'realTimeUsers': real_time_users or 0,
            }
            
            return JsonResponse({
                'user_metrics': user_metrics,
                'device_breakdown': device_breakdown,
                'traffic_sources': traffic_sources,
                'top_pages': top_pages,
                'engagement': engagement,
                'summary': summary,
            })
        except Exception as e:
            logger.error(f"Error updating dashboard data: {e}")
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def get_real_time_data(request):
    """AJAX endpoint to get real-time data"""
    try:
        real_time_users = get_real_time_users()
        real_time_pages = get_recent_page_views()

        return JsonResponse({
            'realTimeUsers': real_time_users or 0,
            'realTimePages': real_time_pages or [],
            'isRealTime': bool(real_time_pages and len(real_time_pages) > 0)
        })
    except Exception as e:
        logger.error(f"Error in get_real_time_data: {e}", exc_info=True)
        return JsonResponse({
            'error': str(e),
            'c': 0,
            'realTimePages': []
        })
def get_recent_page_views():
    """Get page views from the last hour as a fallback for real-time data"""
    client = get_analytics_client()
    if not client:
        return None
    
    try:
        # Calculate dates for last hour
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d')
        
        request = RunReportRequest(
            property=PROPERTY_ID,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="pageLocation"),
                Dimension(name="pageTitle"),
                Dimension(name="dateHourMinute")
            ],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="screenPageViews")
            ],
            order_bys=[
                OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="dateHourMinute"), desc=True)
            ],
            limit=10
        )
        
        response = client.run_report(request)
        
        result = []
        
        for row in response.rows:
            result.append({
                'path': row.dimension_values[0].value or '/',
                'title': row.dimension_values[1].value or 'Unknown',
                'views': int(row.metric_values[0].value),
                'pageviews': int(row.metric_values[1].value)
            })
        print(f"Recent page views fetched: {result}")
        if not result:
            logger.info("No recent page views found")
            return None
        return result
    except Exception as e:
        logger.error(f"Error fetching recent page views: {e}")
        return None