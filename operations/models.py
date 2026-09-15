from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Department(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class SkillDomain(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class ProjectStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ON_HOLD = "ON_HOLD", "On Hold"
    COMPLETED = "COMPLETED", "Completed"


class Project(TimestampedModel):
    project_code = models.CharField(max_length=40, unique=True)
    project_name = models.CharField(max_length=255)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.ACTIVE)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["project_name"]

    def __str__(self):
        return f"{self.project_name} ({self.project_code})"


class InternStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    ON_HOLD = "ON_HOLD", "On Hold"


class InternProfile(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    intern_code = models.CharField(max_length=40, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mentored_interns"
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="managed_interns"
    )
    internship_start_date = models.DateField()
    internship_end_date = models.DateField()
    status = models.CharField(max_length=20, choices=InternStatus.choices, default=InternStatus.ACTIVE)
    skills = models.ManyToManyField(SkillDomain, blank=True)

    class Meta:
        ordering = ["intern_code"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.intern_code})"


class InternProjectAssignment(TimestampedModel):
    intern_profile = models.ForeignKey(InternProfile, on_delete=models.CASCADE, related_name="project_assignments")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="intern_assignments")
    is_primary = models.BooleanField(default=False)
    assigned_from = models.DateField()
    assigned_to = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("intern_profile", "project", "assigned_from")

    def __str__(self):
        return f"{self.intern_profile} -> {self.project}"


class MasterDataList(TimestampedModel):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class MasterDataItem(TimestampedModel):
    list_ref = models.ForeignKey(MasterDataList, on_delete=models.CASCADE, related_name="items")
    value = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("list_ref", "value")
        ordering = ["list_ref", "display_order", "value"]

    def __str__(self):
        return f"{self.list_ref.name}: {self.value}"


class WorkflowState(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    REVIEWED = "REVIEWED", "Reviewed"
    REOPENED = "REOPENED", "Reopened"
    CLOSED = "CLOSED", "Closed"


class DailyProgressEntry(TimestampedModel):
    log_date = models.DateField(default=timezone.localdate)
    intern_profile = models.ForeignKey(InternProfile, on_delete=models.PROTECT, related_name="daily_logs")
    project = models.ForeignKey(Project, on_delete=models.PROTECT)

    task_type = models.ForeignKey(MasterDataItem, on_delete=models.PROTECT, related_name="task_type_entries")
    task_name = models.CharField(max_length=255)
    task_description = models.TextField()
    priority = models.ForeignKey(MasterDataItem, on_delete=models.PROTECT, related_name="priority_entries")

    planned_work = models.TextField(blank=True)
    actual_work = models.TextField(blank=True)
    completion_percentage = models.PositiveSmallIntegerField(default=0)
    completion_status = models.ForeignKey(
        MasterDataItem,
        on_delete=models.PROTECT,
        related_name="completion_status_entries",
        null=True,
        blank=True,
    )
    workflow_state = models.CharField(max_length=20, choices=WorkflowState.choices, default=WorkflowState.DRAFT)

    blocker_flag = models.BooleanField(default=False)
    blocker_description = models.TextField(blank=True)
    support_needed = models.TextField(blank=True)
    time_spent_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    expected_completion_date = models.DateField(null=True, blank=True)
    deliverable_link = models.URLField(blank=True)

    final_owner = models.ForeignKey(MasterDataItem, on_delete=models.PROTECT, related_name="final_owner_entries")
    remarks = models.TextField(blank=True)
    on_time_completion_flag = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_daily_logs",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_daily_logs",
    )

    class Meta:
        ordering = ["-log_date", "-updated_at"]

    def __str__(self):
        return f"{self.log_date} | {self.intern_profile} | {self.task_name}"

    @property
    def is_overdue(self):
        if not self.expected_completion_date:
            return False
        return self.expected_completion_date < timezone.localdate() and self.completion_percentage < 100

    def clean(self):
        if self.completion_percentage > 100:
            raise ValidationError({"completion_percentage": "Completion percentage must be <= 100"})
        if self.expected_completion_date and self.expected_completion_date < self.log_date:
            raise ValidationError(
                {"expected_completion_date": "Expected completion date cannot be before log date"}
            )
        if self.blocker_flag and not self.blocker_description.strip():
            raise ValidationError({"blocker_description": "Blocker description is required when blocked"})

    def save(self, *args, **kwargs):
        # Calendar-day overdue logic for Phase 1.
        self.on_time_completion_flag = bool(
            self.completion_percentage == 100
            and self.expected_completion_date
            and timezone.localdate() <= self.expected_completion_date
        )
        super().save(*args, **kwargs)


class DependencyStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED = "RESOLVED", "Resolved"


class TaskDependency(TimestampedModel):
    entry = models.ForeignKey(DailyProgressEntry, on_delete=models.CASCADE, related_name="dependencies")
    dependency_text = models.CharField(max_length=255)
    dependency_status = models.CharField(max_length=20, choices=DependencyStatus.choices, default=DependencyStatus.OPEN)

    def __str__(self):
        return f"{self.entry_id}: {self.dependency_text}"


class AIUsageRecord(TimestampedModel):
    entry = models.OneToOneField(DailyProgressEntry, on_delete=models.CASCADE, related_name="ai_usage")
    ai_tool = models.ForeignKey(MasterDataItem, on_delete=models.PROTECT, related_name="ai_tool_entries")
    ai_assistance_type = models.ForeignKey(
        MasterDataItem,
        on_delete=models.PROTECT,
        related_name="ai_assistance_entries",
    )
    ai_contribution_percentage = models.PositiveSmallIntegerField(default=0)
    prompt_summary = models.TextField(blank=True)
    output_usage = models.ForeignKey(MasterDataItem, on_delete=models.PROTECT, related_name="output_usage_entries")
    human_review_status = models.ForeignKey(
        MasterDataItem,
        on_delete=models.PROTECT,
        related_name="human_review_entries",
    )
    accuracy_helpfulness_rating = models.PositiveSmallIntegerField(default=0)
    estimated_time_saved_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    used_ai_flag = models.BooleanField(default=False)

    def clean(self):
        if self.ai_contribution_percentage > 100:
            raise ValidationError({"ai_contribution_percentage": "AI contribution must be <= 100"})

    def __str__(self):
        return f"AI usage for entry {self.entry_id}"


class MentorReviewComment(TimestampedModel):
    entry = models.ForeignKey(DailyProgressEntry, on_delete=models.CASCADE, related_name="review_comments")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=20, choices=WorkflowState.choices)
    comment_text = models.TextField(blank=True)
    action_at = models.DateTimeField(default=timezone.now)


class AuditLog(TimestampedModel):
    entity_type = models.CharField(max_length=80)
    entity_id = models.PositiveBigIntegerField()
    action_type = models.CharField(max_length=30)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    old_value_json = models.JSONField(default=dict, blank=True)
    new_value_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
