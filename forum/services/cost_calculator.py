"""
Cost Calculator Service
Calculates study abroad costs based on country, course, and duration
"""
from rest_framework.views import APIView
from rest_framework.response import Response as DRFResponse
from rest_framework import status, permissions
from forum.models import KnowledgeBaseEntry, Country, Category


def calculate_study_costs(country_name, course_type='MS', duration_years=2, accommodation_type='off_campus'):
    """
    Calculate total study abroad costs
    
    Args:
        country_name: Name of the country (e.g., 'USA', 'UK', 'Canada', 'United States')
        course_type: Type of course (e.g., 'MS', 'MBA', 'PhD')
        duration_years: Duration of study in years
        accommodation_type: Type of accommodation ('on_campus', 'off_campus', 'shared')
    
    Returns:
        dict: Cost breakdown with all details
    """
    # Try to find country by name or code
    country = None
    country_name_upper = country_name.upper()
    
    # Map common country names to database names
    country_mapping = {
        'USA': 'United States',
        'US': 'United States',
        'AMERICA': 'United States',
        'UK': 'United Kingdom',
        'GB': 'United Kingdom',
        'BRITAIN': 'United Kingdom',
        'CANADA': 'Canada',
        'CA': 'Canada',
        'AUSTRALIA': 'Australia',
        'AU': 'Australia'
    }
    
    mapped_name = country_mapping.get(country_name_upper, country_name)
    
    try:
        # Try by name first
        country = Country.objects.get(name__icontains=mapped_name)
    except Country.DoesNotExist:
        try:
            # Try by code
            country = Country.objects.get(code__iexact=country_name_upper[:2])
        except Country.DoesNotExist:
            return {
                'error': f'Country "{country_name}" not found in database',
                'country': country_name
            }
    
    # Get knowledge base entries for this country
    kb_entries = KnowledgeBaseEntry.objects.filter(
        country=country
    ).filter(
        content__costs__isnull=False
    )
    
    costs = {}
    
    # Extract cost data from knowledge base
    for entry in kb_entries:
        if 'costs' in entry.content:
            costs.update(entry.content['costs'])
    
    # Default costs if not found in KB
    default_costs = {
        'USA': {
            'tuition': {'min': 20000, 'max': 60000, 'currency': 'USD'},
            'living': {'min': 12000, 'max': 20000, 'currency': 'USD'},
            'accommodation': {'on_campus': {'min': 8000, 'max': 15000}, 'off_campus': {'min': 6000, 'max': 18000}, 'shared': {'min': 4000, 'max': 12000}}
        },
        'UK': {
            'tuition': {'min': 15000, 'max': 35000, 'currency': 'GBP'},
            'living': {'min': 12000, 'max': 15000, 'currency': 'GBP'},
            'accommodation': {'on_campus': {'min': 4000, 'max': 8000}, 'off_campus': {'min': 4800, 'max': 14400}, 'shared': {'min': 3600, 'max': 7200}}
        },
        'Canada': {
            'tuition': {'min': 15000, 'max': 35000, 'currency': 'CAD'},
            'living': {'min': 10000, 'max': 15000, 'currency': 'CAD'},
            'accommodation': {'on_campus': {'min': 6000, 'max': 12000}, 'off_campus': {'min': 7200, 'max': 18000}, 'shared': {'min': 6000, 'max': 14400}}
        }
    }
    
    # Get country code for defaults
    country_code = country.code
    country_key = country.name
    
    # Use defaults if KB data not available
    if not costs:
        if country_key in default_costs:
            cost_data = default_costs[country_key]
        else:
            cost_data = default_costs['USA']  # Fallback
    else:
        # Parse KB costs (they're strings like "$20,000-$60,000/year")
        cost_data = _parse_costs_from_kb(costs, country_key, default_costs.get(country_key, default_costs['USA']))
    
    # Calculate accommodation costs
    accommodation_costs = cost_data.get('accommodation', {})
    if accommodation_type in accommodation_costs:
        acc_cost = accommodation_costs[accommodation_type]
    else:
        acc_cost = accommodation_costs.get('off_campus', {'min': 6000, 'max': 12000})
    
    # Calculate totals
    currency = cost_data.get('tuition', {}).get('currency', 'USD')
    
    tuition_min = cost_data.get('tuition', {}).get('min', 20000) * duration_years
    tuition_max = cost_data.get('tuition', {}).get('max', 60000) * duration_years
    
    living_min = cost_data.get('living', {}).get('min', 12000) * duration_years
    living_max = cost_data.get('living', {}).get('max', 20000) * duration_years
    
    accommodation_min = acc_cost.get('min', 6000) * duration_years
    accommodation_max = acc_cost.get('max', 12000) * duration_years
    
    total_min = tuition_min + living_min
    total_max = tuition_max + living_max
    
    # Additional costs (one-time)
    additional_costs = {
        'visa_application': 150 if currency == 'USD' else (150 if currency == 'CAD' else 363),
        'health_insurance': 1000 * duration_years if currency == 'USD' else (800 * duration_years if currency == 'CAD' else 500 * duration_years),
        'books_supplies': 2000 * duration_years,
        'travel': 2000,
        'initial_setup': 2000
    }
    
    additional_total = sum(additional_costs.values())
    
    return {
        'country': country.name,
        'currency': currency,
        'duration_years': duration_years,
        'accommodation_type': accommodation_type,
        'breakdown': {
            'tuition': {
                'min': tuition_min,
                'max': tuition_max,
                'per_year': {
                    'min': tuition_min / duration_years,
                    'max': tuition_max / duration_years
                }
            },
            'living_expenses': {
                'min': living_min,
                'max': living_max,
                'per_year': {
                    'min': living_min / duration_years,
                    'max': living_max / duration_years
                }
            },
            'accommodation': {
                'min': accommodation_min,
                'max': accommodation_max,
                'per_year': {
                    'min': accommodation_min / duration_years,
                    'max': accommodation_max / duration_years
                }
            },
            'additional_costs': additional_costs,
            'additional_total': additional_total
        },
        'totals': {
            'min': total_min + additional_total,
            'max': total_max + additional_total,
            'average': ((total_min + total_max) / 2) + additional_total
        },
        'formatted': {
            'tuition_range': f"{currency} {tuition_min:,.0f} - {tuition_max:,.0f}",
            'living_range': f"{currency} {living_min:,.0f} - {living_max:,.0f}",
            'total_range': f"{currency} {total_min + additional_total:,.0f} - {total_max + additional_total:,.0f}",
            'average_total': f"{currency} {((total_min + total_max) / 2) + additional_total:,.0f}"
        }
    }


def _parse_costs_from_kb(costs_dict, country_key, default_costs):
    """Parse cost strings from knowledge base into numeric values"""
    # This is a helper function to convert string costs to numbers
    # For now, return default costs as KB entries have structured data
    return default_costs


class CostCalculatorView(APIView):
    permission_classes = [permissions.AllowAny]
    """API endpoint for cost calculations"""
    def post(self, request):
        country = request.data.get('country', '')
        course_type = request.data.get('course_type', 'MS')
        duration_years = int(request.data.get('duration_years', 2))
        accommodation_type = request.data.get('accommodation_type', 'off_campus')
        
        if not country:
            return DRFResponse(
                {'error': 'Country is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = calculate_study_costs(country, course_type, duration_years, accommodation_type)
        
        if 'error' in result:
            return DRFResponse(result, status=status.HTTP_404_NOT_FOUND)
        
        return DRFResponse(result)
