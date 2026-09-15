from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import (
    AIUsageRecordViewSet,
    DailyProgressEntryViewSet,
    DepartmentViewSet,
    InternProfileViewSet,
    InternProjectAssignmentViewSet,
    MasterDataItemViewSet,
    MasterDataListViewSet,
    MentorReviewCommentViewSet,
    ProjectViewSet,
)
from .views import (
    daily_log_create_view,
    daily_log_detail_view,
    daily_log_update_view,
    daily_logs_view,
    daily_stats_view,
    dashboard_view,
)

router = DefaultRouter()
router.register("departments", DepartmentViewSet)
router.register("projects", ProjectViewSet)
router.register("interns", InternProfileViewSet)
router.register("intern-assignments", InternProjectAssignmentViewSet)
router.register("master-data-lists", MasterDataListViewSet)
router.register("master-data-items", MasterDataItemViewSet)
router.register("daily-logs", DailyProgressEntryViewSet, basename="daily-log")
router.register("ai-usage", AIUsageRecordViewSet)
router.register("review-comments", MentorReviewCommentViewSet)

urlpatterns = [
    path("dashboard/", dashboard_view, name="dashboard"),
    path("daily-logs/new/", daily_log_create_view, name="task-create-page"),
    path("daily-logs/<int:pk>/edit/", daily_log_update_view, name="task-edit-page"),
    path("daily-logs/<int:pk>/", daily_log_detail_view, name="task-detail-page"),
    path("daily-logs/", daily_logs_view, name="daily-logs-page"),
    path("daily-stats/", daily_stats_view, name="daily-stats-page"),
    path("api/", include(router.urls)),
]
