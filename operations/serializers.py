from rest_framework import serializers

from accounts.models import UserRole
from accounts.permissions import get_role

from .models import (
    AIUsageRecord,
    DailyProgressEntry,
    Department,
    InternProfile,
    InternProjectAssignment,
    MasterDataItem,
    MasterDataList,
    MentorReviewComment,
    Project,
    TaskDependency,
)
from .services import resolve_completion_status_item


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = "__all__"


class InternProfileSerializer(serializers.ModelSerializer):
    intern_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = InternProfile
        fields = "__all__"


class InternProjectAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternProjectAssignment
        fields = "__all__"


class MasterDataListSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterDataList
        fields = "__all__"


class MasterDataItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterDataItem
        fields = "__all__"


class TaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskDependency
        fields = "__all__"


class AIUsageRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIUsageRecord
        fields = "__all__"


class MentorReviewCommentSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="reviewer.get_full_name", read_only=True)

    class Meta:
        model = MentorReviewComment
        fields = "__all__"


class DailyProgressEntrySerializer(serializers.ModelSerializer):
    dependencies = TaskDependencySerializer(many=True, read_only=True)
    ai_usage = AIUsageRecordSerializer(read_only=True)
    review_comments = MentorReviewCommentSerializer(many=True, read_only=True)
    intern_name = serializers.CharField(source="intern_profile.user.get_full_name", read_only=True)
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    is_on_hold = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = DailyProgressEntry
        fields = "__all__"

    def get_is_on_hold(self, obj):
        return obj.blocker_flag or obj.dependencies.filter(dependency_status="OPEN").exists()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and get_role(request.user) == UserRole.HR:
            for field in [
                "task_description",
                "planned_work",
                "actual_work",
                "blocker_description",
                "support_needed",
                "remarks",
                "deliverable_link",
            ]:
                data.pop(field, None)
        return data

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["created_by"] = request.user
        validated_data["updated_by"] = request.user
        validated_data["completion_status"] = resolve_completion_status_item(
            validated_data.get("completion_percentage", 0)
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context["request"]
        validated_data["updated_by"] = request.user
        completion_percentage = validated_data.get("completion_percentage")
        if completion_percentage is not None:
            validated_data["completion_status"] = resolve_completion_status_item(completion_percentage)
        return super().update(instance, validated_data)
