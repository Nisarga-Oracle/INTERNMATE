from django.urls import path

from .views import export_reports, reports_view

urlpatterns = [
    path("", reports_view, name="reports-page"),
    path("export/", export_reports, name="reports-export"),
]
