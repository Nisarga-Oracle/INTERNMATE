from django.urls import path

from .views import codex_cli_guide_view, landing_view, login_view, logout_view

urlpatterns = [
    path("", landing_view, name="landing"),
    path("codex-cli-guide/", codex_cli_guide_view, name="codex-cli-guide"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
]
