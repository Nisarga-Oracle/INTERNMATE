from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserProfile, UserRole
from operations.models import (
    AIUsageRecord,
    Department,
    DailyProgressEntry,
    DependencyStatus,
    InternProfile,
    InternProjectAssignment,
    MasterDataItem,
    MasterDataList,
    MentorReviewComment,
    Project,
    TaskDependency,
    WorkflowState,
)
from operations.services import calculate_completion_status_label


class Command(BaseCommand):
    help = "Seed baseline data for local testing"

    def handle(self, *args, **options):
        User = get_user_model()

        users = {
            "admin": ("Admin", "User", UserRole.ADMIN),
            "manager": ("Maya", "Manager", UserRole.MANAGER),
            "mentor": ("Mohan", "Mentor", UserRole.MENTOR),
            "hr": ("Hema", "HR", UserRole.HR),
            "intern1": ("Riya", "Sharma", UserRole.INTERN),
            "intern2": ("Karan", "Patel", UserRole.INTERN),
            "intern3": ("Neha", "Gupta", UserRole.INTERN),
        }

        created_users = {}
        for username, (first, last, role) in users.items():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@internmate.local"},
            )
            if created:
                user.set_password("pass1234")
                user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
            created_users[username] = user

        created_users["admin"].is_staff = True
        created_users["admin"].is_superuser = True
        created_users["admin"].save()

        eng, _ = Department.objects.get_or_create(name="Engineering")
        data, _ = Department.objects.get_or_create(name="Data")

        project_1, _ = Project.objects.get_or_create(
            project_code="INTERNMATE",
            defaults={"project_name": "InternMate", "department": eng},
        )
        project_2, _ = Project.objects.get_or_create(
            project_code="AI-INSIGHTS",
            defaults={"project_name": "AI Insights", "department": data},
        )

        intern_1, _ = InternProfile.objects.get_or_create(
            user=created_users["intern1"],
            defaults={
                "intern_code": "INT-001",
                "department": eng,
                "mentor": created_users["mentor"],
                "manager": created_users["manager"],
                "internship_start_date": "2026-04-01",
                "internship_end_date": "2026-07-01",
            },
        )
        intern_2, _ = InternProfile.objects.get_or_create(
            user=created_users["intern2"],
            defaults={
                "intern_code": "INT-002",
                "department": eng,
                "mentor": created_users["mentor"],
                "manager": created_users["manager"],
                "internship_start_date": "2026-04-01",
                "internship_end_date": "2026-07-01",
            },
        )
        intern_3, _ = InternProfile.objects.get_or_create(
            user=created_users["intern3"],
            defaults={
                "intern_code": "INT-003",
                "department": data,
                "mentor": created_users["mentor"],
                "manager": created_users["manager"],
                "internship_start_date": "2026-04-01",
                "internship_end_date": "2026-07-01",
            },
        )

        InternProjectAssignment.objects.get_or_create(
            intern_profile=intern_1,
            project=project_1,
            assigned_from="2026-04-01",
            defaults={"is_primary": True},
        )
        InternProjectAssignment.objects.get_or_create(
            intern_profile=intern_1,
            project=project_2,
            assigned_from="2026-04-10",
            defaults={"is_primary": False},
        )
        InternProjectAssignment.objects.get_or_create(
            intern_profile=intern_2,
            project=project_1,
            assigned_from="2026-04-01",
            defaults={"is_primary": True},
        )
        InternProjectAssignment.objects.get_or_create(
            intern_profile=intern_3,
            project=project_2,
            assigned_from="2026-04-01",
            defaults={"is_primary": True},
        )

        master_data = {
            "Task Type": ["Backend", "Frontend", "Testing", "Documentation"],
            "Priority": ["Low", "Medium", "High", "Critical"],
            "Completion Status": ["Not Started", "Initiated", "In Progress", "Near Completion", "Completed"],
            "AI Tool": ["None", "ChatGPT", "Codex", "Copilot", "OCI GenAI", "Other"],
            "AI Assistance Type": [
                "Brainstorming",
                "Drafting",
                "Summarization",
                "Coding",
                "Debugging",
                "Review",
                "Documentation",
                "Research Support",
            ],
            "Output Usage": ["As-Is", "Modified", "Reworked", "Rejected", "N/A"],
            "Human Review Status": ["Yes", "No", "Partial", "N/A"],
            "Final Owner": ["Independent", "Joint"],
        }

        for list_name, values in master_data.items():
            list_ref, _ = MasterDataList.objects.get_or_create(name=list_name)
            for idx, value in enumerate(values, start=1):
                MasterDataItem.objects.get_or_create(
                    list_ref=list_ref,
                    value=value,
                    defaults={"display_order": idx},
                )

        def item(list_name: str, value: str):
            return MasterDataItem.objects.get(list_ref__name=list_name, value=value)

        # Reset only previously seeded records to keep command repeatable and predictable.
        DailyProgressEntry.objects.filter(task_name__startswith="Seed Task ").delete()

        today = date.today()
        interns = [intern_1, intern_2, intern_3]
        projects = [project_1, project_2]
        task_types = ["Backend", "Frontend", "Testing", "Documentation"]
        priorities = ["Low", "Medium", "High", "Critical"]
        ai_tools = ["ChatGPT", "Codex", "Copilot", "OCI GenAI", "Other"]
        ai_assist = [
            "Brainstorming",
            "Drafting",
            "Summarization",
            "Coding",
            "Debugging",
            "Review",
            "Documentation",
            "Research Support",
        ]
        completions = [0, 15, 25, 38, 52, 67, 79, 88, 95, 100]

        for i in range(50):
            intern = interns[i % len(interns)]
            actor = intern.user
            project = projects[i % len(projects)]
            completion = completions[i % len(completions)]
            task_type = task_types[i % len(task_types)]
            priority = priorities[i % len(priorities)]
            blocker_flag = (i % 8 == 0) or (i % 13 == 0)
            used_ai = i % 4 != 0

            if completion == 100:
                workflow_state = WorkflowState.CLOSED if i % 2 == 0 else WorkflowState.REVIEWED
            elif blocker_flag:
                workflow_state = WorkflowState.REOPENED if i % 2 == 0 else WorkflowState.SUBMITTED
            else:
                workflow_state = WorkflowState.SUBMITTED if i % 3 else WorkflowState.DRAFT

            expected_completion_date = today - timedelta(days=(i % 7) - 2)
            completion_label = calculate_completion_status_label(completion)
            task_name = f"Seed Task {i + 1:02d} - {task_type}"

            entry = DailyProgressEntry.objects.create(
                log_date=today - timedelta(days=i % 20),
                intern_profile=intern,
                project=project,
                task_type=item("Task Type", task_type),
                task_name=task_name,
                task_description=f"Seeded task description for {task_type.lower()} verification scenario {i + 1}.",
                priority=item("Priority", priority),
                planned_work=f"Planned work for task {i + 1}",
                actual_work=f"Actual progress notes for task {i + 1}",
                completion_percentage=completion,
                completion_status=item("Completion Status", completion_label),
                workflow_state=workflow_state,
                blocker_flag=blocker_flag,
                blocker_description=(
                    "Dependency pending from external team." if blocker_flag else ""
                ),
                support_needed=(
                    "Need mentor support to unblock dependency." if blocker_flag else ""
                ),
                time_spent_hours=2 + (i % 6),
                expected_completion_date=expected_completion_date,
                final_owner=item("Final Owner", "Joint" if i % 3 == 0 else "Independent"),
                remarks="Seeded record for pagination and KPI validation.",
                created_by=actor,
                updated_by=actor,
            )

            if blocker_flag and i % 2 == 0:
                TaskDependency.objects.create(
                    entry=entry,
                    dependency_text="Waiting for required input from another team",
                    dependency_status=DependencyStatus.OPEN,
                )

            ai_tool_value = ai_tools[i % len(ai_tools)] if used_ai else "None"
            ai_assist_value = ai_assist[i % len(ai_assist)]
            human_review = "Yes" if i % 3 == 0 else "Partial" if i % 3 == 1 else "No"

            AIUsageRecord.objects.create(
                entry=entry,
                ai_tool=item("AI Tool", ai_tool_value),
                ai_assistance_type=item("AI Assistance Type", ai_assist_value),
                ai_contribution_percentage=0 if not used_ai else 20 + (i % 6) * 10,
                prompt_summary="Seeded prompt summary for validation use only.",
                output_usage=item("Output Usage", "N/A" if not used_ai else "Modified"),
                human_review_status=item("Human Review Status", "N/A" if not used_ai else human_review),
                accuracy_helpfulness_rating=0 if not used_ai else 3 + (i % 3),
                estimated_time_saved_hours=0 if not used_ai else round(0.5 + (i % 5) * 0.4, 2),
                used_ai_flag=used_ai,
            )

            if workflow_state in {WorkflowState.REVIEWED, WorkflowState.REOPENED, WorkflowState.CLOSED}:
                MentorReviewComment.objects.create(
                    entry=entry,
                    reviewer=created_users["mentor"],
                    action=workflow_state,
                    comment_text="Seeded mentor review comment.",
                )

        self.stdout.write(self.style.SUCCESS("Seed complete. Generated 50 seeded records. Password: pass1234"))
