from django.urls import path, include
from rest_framework.routers import DefaultRouter
from forum import views
from forum.services.cost_calculator import CostCalculatorView

app_name = 'forum'

router = DefaultRouter()
router.register(r'queries', views.QueryViewSet, basename='query')

urlpatterns = [
    path('', views.index, name='index'),
    path('api/', include(router.urls)),
    path('api/categories/', views.CategoryListView.as_view(), name='categories'),
    path('api/countries/', views.CountryListView.as_view(), name='countries'),
    path('api/statistics/', views.StatisticsView.as_view(), name='statistics'),
    path('api/user-progress/', views.UserProgressView.as_view(), name='user-progress'),
    path('api/popular-queries/', views.PopularQueriesView.as_view(), name='popular-queries'),
    path('api/trending/', views.TrendingQueriesView.as_view(), name='trending'),
    path('api/ai-features/', views.AIFeaturesView.as_view(), name='ai-features'),
    path('api/ai-capabilities/', views.AICapabilitiesView.as_view(), name='ai-capabilities'),
    path('api/calculate-costs/', CostCalculatorView.as_view(), name='calculate-costs'),
]
