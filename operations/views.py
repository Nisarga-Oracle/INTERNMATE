import json

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.forms.models import model_to_dict
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserRole
from accounts.permissions import get_role

from .forms import DailyProgressEntryForm
from .models import (
    AIUsageRecord,
    AuditLog,
    DailyProgressEntry,
    InternProfile,
    MasterDataItem,
    MentorReviewComment,
    Project,
    TaskDependency,
)
from .services import can_view_entry, resolve_completion_status_item


def _build_query_string_without_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


def _apply_entry_filters(entries, request):
    intern_id = request.GET.get("intern", "").strip()
    project_id = request.GET.get("project", "").strip()
    workflow = request.GET.get("workflow", "").strip()
    blocked = request.GET.get("blocked", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if intern_id:
        entries = entries.filter(intern_profile_id=intern_id)
    if project_id:
        entries = entries.filter(project_id=project_id)
    if workflow:
        entries = entries.filter(workflow_state=workflow)
    if blocked == "yes":
        entries = entries.filter(blocker_flag=True)
    elif blocked == "no":
        entries = entries.filter(blocker_flag=False)
    if date_from:
        entries = entries.filter(log_date__gte=date_from)
    if date_to:
        entries = entries.filter(log_date__lte=date_to)

    return entries


def _item_or_none(list_name: str, value: str):
    return MasterDataItem.objects.filter(list_ref__name=list_name, value=value, is_active=True).first()


def _json_safe(data):
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def _snapshot_entry(entry: DailyProgressEntry):
    fields = [
        "log_date",
        "intern_profile",
        "project",
        "task_type",
        "task_name",
        "task_description",
        "priority",
        "planned_work",
        "actual_work",
        "completion_percentage",
        "workflow_state",
        "blocker_flag",
        "blocker_description",
        "support_needed",
        "time_spent_hours",
        "expected_completion_date",
        "deliverable_link",
        "final_owner",
        "remarks",
    ]
    return _json_safe(model_to_dict(entry, fields=fields))


def _extract_changed_fields(old_data: dict, new_data: dict):
    changed = {}
    for key in old_data.keys() | new_data.keys():
        if old_data.get(key) != new_data.get(key):
            changed[key] = {"from": old_data.get(key), "to": new_data.get(key)}
    return changed


def _can_edit_task(user, entry: DailyProgressEntry):
    role = get_role(user)
    if role == UserRole.ADMIN:
        return True
    if role == UserRole.MANAGER:
        return True
    if entry.created_by_id == user.id:
        return True
    if entry.intern_profile.user_id == user.id:
        return True
    return False


def _upsert_ai_usage(entry: DailyProgressEntry, request):
    used_ai = request.POST.get("used_ai_flag") == "on"
    ai_tool = _item_or_none("AI Tool", request.POST.get("ai_tool", ""))
    ai_assist = _item_or_none("AI Assistance Type", request.POST.get("ai_assistance_type", ""))
    output_usage = _item_or_none("Output Usage", request.POST.get("output_usage", ""))
    human_review = _item_or_none("Human Review Status", request.POST.get("human_review_status", ""))

    if not used_ai:
        ai_tool = _item_or_none("AI Tool", "None")
        output_usage = _item_or_none("Output Usage", "N/A")
        human_review = _item_or_none("Human Review Status", "N/A")
        ai_assist = ai_assist or _item_or_none("AI Assistance Type", "Documentation")

    AIUsageRecord.objects.update_or_create(
        entry=entry,
        defaults={
            "ai_tool": ai_tool or _item_or_none("AI Tool", "None"),
            "ai_assistance_type": ai_assist or _item_or_none("AI Assistance Type", "Documentation"),
            "ai_contribution_percentage": int(request.POST.get("ai_contribution_percentage") or 0),
            "prompt_summary": request.POST.get("prompt_summary", "").strip(),
            "output_usage": output_usage or _item_or_none("Output Usage", "N/A"),
            "human_review_status": human_review or _item_or_none("Human Review Status", "N/A"),
            "accuracy_helpfulness_rating": int(request.POST.get("accuracy_helpfulness_rating") or 0),
            "estimated_time_saved_hours": float(request.POST.get("estimated_time_saved_hours") or 0),
            "used_ai_flag": used_ai,
        },
    )


@login_required
def dashboard_view(request):
    entries = DailyProgressEntry.objects.select_related("intern_profile__user", "project", "final_owner")
    entries = _apply_entry_filters(entries, request)
    total = entries.count()
    completed = entries.filter(completion_percentage=100).count()
    blocked = entries.filter(blocker_flag=True).count()
    ai_assisted = entries.filter(ai_usage__used_ai_flag=True).count()

    kpis = {
        "total_tasks": total,
        "completed_tasks": completed,
        "blocked_tasks": blocked,
        "completion_rate": round((completed / total) * 100, 2) if total else 0,
        "avg_completion": round(entries.aggregate(avg=Avg("completion_percentage"))["avg"] or 0, 2),
        "ai_assisted_pct": round((ai_assisted / total) * 100, 2) if total else 0,
        "time_saved": float(entries.aggregate(saved=Sum("ai_usage__estimated_time_saved_hours"))["saved"] or 0),
    }

    recent_entries = entries.order_by("-updated_at")[:10]
    return render(
        request,
        "operations/dashboard.html",
        {
            "kpis": kpis,
            "recent_entries": recent_entries,
            "intern_options": InternProfile.objects.select_related("user").order_by("intern_code"),
            "project_options": Project.objects.order_by("project_name"),
            "selected": request.GET,
            "query_string": _build_query_string_without_page(request),
        },
    )


@login_required
def daily_logs_view(request):
    logs_qs = (
        DailyProgressEntry.objects.select_related("intern_profile__user", "project", "final_owner")
        .prefetch_related("dependencies")
        .order_by("-log_date", "-updated_at")
    )
    logs_qs = _apply_entry_filters(logs_qs, request)
    paginator = Paginator(logs_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    editable_entry_ids = {entry.id for entry in page_obj.object_list if _can_edit_task(request.user, entry)}
    return render(
        request,
        "operations/daily_logs.html",
        {
            "logs": page_obj.object_list,
            "editable_entry_ids": editable_entry_ids,
            "page_obj": page_obj,
            "intern_options": InternProfile.objects.select_related("user").order_by("intern_code"),
            "project_options": Project.objects.order_by("project_name"),
            "selected": request.GET,
            "query_string": _build_query_string_without_page(request),
        },
    )


@login_required
def daily_stats_view(request):
    entries = DailyProgressEntry.objects.all()
    entries = _apply_entry_filters(entries, request)
    grouped_qs = (
        entries.values("log_date")
        .annotate(
            tasks_logged=Count("id"),
            completed_tasks=Count("id", filter=Q(completion_percentage=100)),
            blocked_tasks=Count("id", filter=Q(blocker_flag=True)),
            average_completion=Avg("completion_percentage"),
            ai_assisted_tasks=Count("id", filter=Q(ai_usage__used_ai_flag=True)),
            time_spent=Sum("time_spent_hours"),
            time_saved=Sum("ai_usage__estimated_time_saved_hours"),
        )
        .order_by("-log_date")
    )
    paginator = Paginator(grouped_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    return render(
        request,
        "operations/daily_stats.html",
        {
            "stats": page_obj.object_list,
            "page_obj": page_obj,
            "intern_options": InternProfile.objects.select_related("user").order_by("intern_code"),
            "project_options": Project.objects.order_by("project_name"),
            "selected": request.GET,
            "query_string": _build_query_string_without_page(request),
        },
    )


@login_required
def daily_log_create_view(request):
    role = get_role(request.user)
    if role not in {UserRole.ADMIN, UserRole.MANAGER, UserRole.MENTOR, UserRole.INTERN}:
        return HttpResponseForbidden("You are not allowed to create daily logs.")

    form = DailyProgressEntryForm(request.POST or None, user=request.user, role=role)

    ai_tool_options = MasterDataItem.objects.filter(list_ref__name="AI Tool", is_active=True).order_by("display_order")
    ai_assist_options = MasterDataItem.objects.filter(
        list_ref__name="AI Assistance Type", is_active=True
    ).order_by("display_order")
    output_usage_options = MasterDataItem.objects.filter(
        list_ref__name="Output Usage", is_active=True
    ).order_by("display_order")
    human_review_options = MasterDataItem.objects.filter(
        list_ref__name="Human Review Status", is_active=True
    ).order_by("display_order")

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            entry = form.save(commit=False)
            entry.created_by = request.user
            entry.updated_by = request.user
            entry.completion_status = resolve_completion_status_item(entry.completion_percentage)
            entry.save()

            dependency_text = request.POST.get("dependency_text", "").strip()
            if dependency_text:
                TaskDependency.objects.create(entry=entry, dependency_text=dependency_text)

            _upsert_ai_usage(entry, request)

            messages.success(request, "Daily task logged successfully.")
            return redirect("task-detail-page", pk=entry.pk)

    return render(
        request,
        "operations/daily_log_form.html",
        {
            "form": form,
            "is_edit": False,
            "ai_tool_options": ai_tool_options,
            "ai_assist_options": ai_assist_options,
            "output_usage_options": output_usage_options,
            "human_review_options": human_review_options,
        },
    )


@login_required
def daily_log_detail_view(request, pk: int):
    entry = get_object_or_404(
        DailyProgressEntry.objects.select_related(
            "intern_profile__user",
            "project",
            "task_type",
            "priority",
            "final_owner",
            "completion_status",
        ).prefetch_related("dependencies", "review_comments__reviewer"),
        pk=pk,
    )
    if not can_view_entry(request.user, entry):
        return HttpResponseForbidden("You are not allowed to view this task.")

    return render(
        request,
        "operations/daily_log_detail.html",
        {
            "entry": entry,
            "ai_usage": getattr(entry, "ai_usage", None),
            "review_comments": entry.review_comments.order_by("-action_at"),
            "change_logs": AuditLog.objects.filter(
                entity_type="DailyProgressEntry",
                entity_id=entry.id,
            )
            .select_related("actor")
            .order_by("-created_at")[:50],
            "can_edit_task": _can_edit_task(request.user, entry),
        },
    )


@login_required
def daily_log_update_view(request, pk: int):
    entry = get_object_or_404(DailyProgressEntry, pk=pk)
    if not _can_edit_task(request.user, entry):
        return HttpResponseForbidden("You are not allowed to edit this task.")

    role = get_role(request.user)
    form = DailyProgressEntryForm(request.POST or None, instance=entry, user=request.user, role=role)

    ai_tool_options = MasterDataItem.objects.filter(list_ref__name="AI Tool", is_active=True).order_by("display_order")
    ai_assist_options = MasterDataItem.objects.filter(
        list_ref__name="AI Assistance Type", is_active=True
    ).order_by("display_order")
    output_usage_options = MasterDataItem.objects.filter(
        list_ref__name="Output Usage", is_active=True
    ).order_by("display_order")
    human_review_options = MasterDataItem.objects.filter(
        list_ref__name="Human Review Status", is_active=True
    ).order_by("display_order")

    if request.method == "POST" and form.is_valid():
        old_snapshot = _snapshot_entry(entry)
        with transaction.atomic():
            updated_entry = form.save(commit=False)
            updated_entry.updated_by = request.user
            updated_entry.completion_status = resolve_completion_status_item(updated_entry.completion_percentage)
            updated_entry.save()

            dependency_text = request.POST.get("dependency_text", "").strip()
            if dependency_text:
                dep = updated_entry.dependencies.first()
                if dep:
                    dep.dependency_text = dependency_text
                    dep.save(update_fields=["dependency_text", "updated_at"])
                else:
                    TaskDependency.objects.create(entry=updated_entry, dependency_text=dependency_text)

            _upsert_ai_usage(updated_entry, request)

            new_snapshot = _snapshot_entry(updated_entry)
            changed_fields = _extract_changed_fields(old_snapshot, new_snapshot)
            update_note = form.cleaned_data.get("update_note", "").strip()
            if update_note:
                changed_fields["_note"] = update_note

            if changed_fields:
                action_type = "intern_update" if role == UserRole.INTERN else "task_update"
                AuditLog.objects.create(
                    entity_type="DailyProgressEntry",
                    entity_id=updated_entry.id,
                    action_type=action_type,
                    actor=request.user,
                    old_value_json=old_snapshot,
                    new_value_json=changed_fields,
                )

            messages.success(request, "Task updated successfully.")
            return redirect("task-detail-page", pk=updated_entry.pk)

    ai_usage = getattr(entry, "ai_usage", None)
    dependency = entry.dependencies.first()
    return render(
        request,
        "operations/daily_log_form.html",
        {
            "form": form,
            "is_edit": True,
            "entry": entry,
            "ai_usage": ai_usage,
            "dependency_text": dependency.dependency_text if dependency else "",
            "ai_tool_options": ai_tool_options,
            "ai_assist_options": ai_assist_options,
            "output_usage_options": output_usage_options,
            "human_review_options": human_review_options,
        },
    )
