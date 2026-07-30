from django.urls import path

from loan_desk import views

app_name = "loan_desk"

urlpatterns = [
    path("manifest.json", views.loan_desk_manifest, name="manifest"),
    path("service-worker.js", views.loan_desk_service_worker, name="service_worker"),
    path("login/", views.LoanDeskLoginView.as_view(), name="login"),
    path("logout/", views.LoanDeskLogoutView.as_view(), name="logout"),
    path("instant/<str:token>/", views.LoanDeskInstantLoginView.as_view(), name="instant_login"),
    path("", views.LoanDeskHomeView.as_view(), name="home"),
    path("applications/<int:pk>/", views.LoanDeskDetailView.as_view(), name="detail"),
]
