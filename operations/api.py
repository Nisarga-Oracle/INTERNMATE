from rest_framework import decorators, mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin, get_role

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
)
from .serializers import (
    AIUsageRecordSerializer,
    DailyProgressEntrySerializer,
    DepartmentSerializer,
    InternProfileSerializer,
    InternProjectAssignmentSerializer,
    MasterDataItemSerializer,
    MasterDataListSerializer,
    MentorReviewCommentSerializer,
    ProjectSerializer,
)
from .services import apply_workflow_action, can_edit_entry, visible_entries_for_user


class AdminWriteMixin:
    def get_permissions(self):
        if self.request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]


class DepartmentViewSet(AdminWriteMixin, viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


class ProjectViewSet(AdminWriteMixin, viewsets.ModelViewSet):
    queryset = Project.objects.select_related("department").all()
    serializer_class = ProjectSerializer


class InternProfileViewSet(AdminWriteMixin, viewsets.ModelViewSet):
    queryset = InternProfile.objects.select_related("user", "department", "mentor", "manager").all()
    serializer_class = InternProfileSerializer


class InternProjectAssignmentViewSet(AdminWriteMixin, viewsets.ModelViewSet):
    queryset = InternProjectAssignment.objects.select_related("intern_profile", "project").all()
    serializer_class = InternProjectAssignmentSerializer


class MasterDataListViewSet(AdminWriteMixin, viewsets.ModelViewSet):
    queryset = MasterDataList.objects.all()
    serializer_class = MasterDataListSerializer


class MasterDataItemViewSet(AdminWriteMixin, viewsets.ModelViewSet):
    queryset = MasterDataItem.objects.select_related("list_ref").all()
    serializer_class = MasterDataItemSerializer


class DailyProgressEntryViewSet(viewsets.ModelViewSet):
    serializer_class = DailyProgressEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return visible_entries_for_user(self.request.user)

    def perform_update(self, serializer):
        entry = self.get_object()
        if not can_edit_entry(self.request.user, entry):
            raise PermissionDenied("You are not allowed to edit this entry")
        serializer.save()

    @decorators.action(detail=True, methods=["post"])
    def workflow(self, request, pk=None):
        entry = self.get_object()
        action = request.data.get("action")
        if action not in {"DRAFT", "SUBMITTED", "REVIEWED", "REOPENED", "CLOSED"}:
            return Response({"detail": "Invalid workflow action"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            entry = apply_workflow_action(entry, action, request.user)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        comment_text = request.data.get("comment", "")
        if comment_text or action in {"REOPENED", "REVIEWED", "CLOSED"}:
            MentorReviewComment.objects.create(
                entry=entry,
                reviewer=request.user,
                action=action,
                comment_text=comment_text,
            )

        entry.updated_by = request.user
        entry.save()
        return Response(self.get_serializer(entry).data)


class AIUsageRecordViewSet(viewsets.ModelViewSet):
    queryset = AIUsageRecord.objects.select_related(
        "entry",
        "ai_tool",
        "ai_assistance_type",
        "output_usage",
        "human_review_status",
    ).all()
    serializer_class = AIUsageRecordSerializer
    permission_classes = [IsAuthenticated]


class MentorReviewCommentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = MentorReviewComment.objects.select_related("entry", "reviewer").all()
    serializer_class = MentorReviewCommentSerializer
    permission_classes = [IsAuthenticated]
