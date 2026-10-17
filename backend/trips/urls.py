from django.urls import path

from trips import views

urlpatterns = [
    path("health/", views.health),
    path("geocode/", views.geocode),
    path("presets/", views.PresetList.as_view()),
    path("plans/", views.PlanList.as_view()),
    path("plans/<uuid:pk>/", views.PlanDetail.as_view()),
]
