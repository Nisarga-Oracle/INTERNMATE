import csv
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Sum
from django.http import HttpResponse
from django.shortcuts import render
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from operations.models import DailyProgressEntry, InternProfile, Project


def _build_query_string_without_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


def _apply_report_filters(entries, request):
    intern_id = request.GET.get("intern", "").strip()
    project_id = request.GET.get("project", "").strip()
    blocked = request.GET.get("blocked", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if intern_id:
        entries = entries.filter(intern_profile_id=intern_id)
    if project_id:
        entries = entries.filter(project_id=project_id)
    if blocked == "yes":
        entries = entries.filter(blocker_flag=True)
    elif blocked == "no":
        entries = entries.filter(blocker_flag=False)
    if date_from:
        entries = entries.filter(log_date__gte=date_from)
    if date_to:
        entries = entries.filter(log_date__lte=date_to)

    return entries


@login_required
def reports_view(request):
    filtered_entries = _apply_report_filters(DailyProgressEntry.objects.all(), request)
    rows = []
    for intern in InternProfile.objects.select_related("user").order_by("intern_code"):
        code = intern.intern_code
        name = intern.user.get_full_name() or intern.user.username
        intern_entries = filtered_entries.filter(intern_profile__intern_code=code)
        rows.append(
            {
                "code": code,
                "name": name,
                "total_tasks": intern_entries.count(),
                "completed_tasks": intern_entries.filter(completion_percentage=100).count(),
                "blocked_tasks": intern_entries.filter(blocker_flag=True).count(),
                "avg_completion": round(intern_entries.aggregate(avg=Avg("completion_percentage"))["avg"] or 0, 2),
                "time_saved": float(
                    intern_entries.aggregate(saved=Sum("ai_usage__estimated_time_saved_hours"))["saved"] or 0
                ),
            }
        )

    paginator = Paginator(rows, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    return render(
        request,
        "reporting/reports.html",
        {
            "rows": page_obj.object_list,
            "page_obj": page_obj,
            "intern_options": InternProfile.objects.select_related("user").order_by("intern_code"),
            "project_options": Project.objects.order_by("project_name"),
            "selected": request.GET,
            "query_string": _build_query_string_without_page(request),
        },
    )


def _report_rows():
    entries = DailyProgressEntry.objects.select_related("intern_profile__user", "project", "final_owner")
    for e in entries:
        yield {
            "Date": e.log_date.isoformat(),
            "Intern": e.intern_profile.user.get_full_name() or e.intern_profile.user.username,
            "Project": e.project.project_name,
            "Task": e.task_name,
            "Workflow": e.workflow_state,
            "Completion %": e.completion_percentage,
            "Blocked": "Yes" if e.blocker_flag else "No",
            "Final Owner": e.final_owner.value,
        }


@login_required
def export_reports(request):
    export_format = request.GET.get("format", "csv")
    filtered_entries = _apply_report_filters(
        DailyProgressEntry.objects.select_related("intern_profile__user", "project", "final_owner"),
        request,
    )
    rows = list(_report_rows()) if not request.GET else [
        {
            "Date": e.log_date.isoformat(),
            "Intern": e.intern_profile.user.get_full_name() or e.intern_profile.user.username,
            "Project": e.project.project_name,
            "Task": e.task_name,
            "Workflow": e.workflow_state,
            "Completion %": e.completion_percentage,
            "Blocked": "Yes" if e.blocker_flag else "No",
            "Final Owner": e.final_owner.value,
        }
        for e in filtered_entries
    ]

    if export_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="internmate_report.csv"'
        if rows:
            writer = csv.DictWriter(response, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return response

    if export_format == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "InternMate"
        if rows:
            headers = list(rows[0].keys())
            ws.append(headers)
            for row in rows:
                ws.append([row.get(h, "") for h in headers])

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="internmate_report.xlsx"'
        return response

    if export_format == "pdf":
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        y = 800
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, "InternMate Summary Report")
        y -= 24
        pdf.setFont("Helvetica", 9)
        for row in rows[:50]:
            line = (
                f"{row['Date']} | {row['Intern']} | {row['Project']} | "
                f"{row['Completion %']}% | Blocked: {row['Blocked']}"
            )
            pdf.drawString(40, y, line[:110])
            y -= 14
            if y < 50:
                pdf.showPage()
                y = 800
                pdf.setFont("Helvetica", 9)

        pdf.save()
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="internmate_report.pdf"'
        return response

    return HttpResponse("Unsupported format", status=400)
