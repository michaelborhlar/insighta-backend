from django.urls import path, include

urlpatterns = [
    path("auth/", include("authentication.urls")),
    path("api/", include("profiles.urls")),
]
