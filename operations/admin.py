from django.contrib import admin

from .models import (
    AIUsageRecord,
    AuditLog,
    DailyProgressEntry,
    Department,
    InternProfile,
    InternProjectAssignment,
    MasterDataItem,
    MasterDataList,
    MentorReviewComment,
    Project,
    SkillDomain,
    TaskDependency,
)


admin.site.register(Department)
admin.site.register(SkillDomain)
admin.site.register(Project)
admin.site.register(InternProfile)
admin.site.register(InternProjectAssignment)
admin.site.register(MasterDataList)
admin.site.register(MasterDataItem)
admin.site.register(TaskDependency)
admin.site.register(AIUsageRecord)
admin.site.register(MentorReviewComment)
admin.site.register(AuditLog)


@admin.register(DailyProgressEntry)
class DailyProgressEntryAdmin(admin.ModelAdmin):
    list_display = (
        "log_date",
        "intern_profile",
        "project",
        "task_name",
        "workflow_state",
        "completion_percentage",
        "blocker_flag",
    )
    list_filter = ("workflow_state", "blocker_flag", "log_date")
    search_fields = ("task_name", "intern_profile__intern_code", "intern_profile__user__username")
