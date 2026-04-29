from django.urls import path
from profiles import views

urlpatterns = [
    path("profiles", views.list_profiles, name="profile-list"),
    path("profiles/search", views.search_profiles, name="profile-search"),
    path("profiles/export", views.export_profiles, name="profile-export"),
    path("profiles/<str:profile_id>", views.get_profile, name="profile-detail"),
    path("profiles/", views.create_profile, name="profile-create"),  # POST only
]
