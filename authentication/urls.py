from django.urls import path
from authentication import views

urlpatterns = [
    path("github/", views.github_authorize, name="github-authorize"),
    path("github/callback/", views.github_callback, name="github-callback"),
    path("refresh/", views.refresh_token_view, name="token-refresh"),
    path("logout/", views.logout_view, name="logout"),
    path("whoami/", views.whoami_view, name="whoami"),
]
