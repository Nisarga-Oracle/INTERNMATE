from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from operations.models import AIUsageRecord, AuditLog, DailyProgressEntry, InternProfile, MasterDataItem, Project


class Phase1ClosureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_baseline")
        User = get_user_model()
        cls.users = {u.username: u for u in User.objects.all()}

        cls.intern1 = InternProfile.objects.get(user=cls.users["intern1"])
        cls.intern2 = InternProfile.objects.get(user=cls.users["intern2"])
        cls.project = Project.objects.get(project_code="INTERNMATE")

        def item(list_name, value):
            return MasterDataItem.objects.get(list_ref__name=list_name, value=value)

        cls.task_type = item("Task Type", "Backend")
        cls.priority = item("Priority", "High")
        cls.final_owner = item("Final Owner", "Joint")
        cls.ai_tool = item("AI Tool", "Codex")
        cls.ai_assist = item("AI Assistance Type", "Debugging")
        cls.output_usage = item("Output Usage", "Modified")
        cls.human_review = item("Human Review Status", "Yes")

        cls.permission_entry = DailyProgressEntry.objects.create(
            log_date=date.today(),
            intern_profile=cls.intern1,
            project=cls.project,
            task_type=cls.task_type,
            task_name="Permission Matrix Task",
            task_description="Permission matrix validation task.",
            priority=cls.priority,
            planned_work="Plan",
            actual_work="Do",
            completion_percentage=40,
            workflow_state="SUBMITTED",
            blocker_flag=False,
            blocker_description="",
            support_needed="",
            time_spent_hours=2,
            expected_completion_date=date.today() + timedelta(days=1),
            final_owner=cls.final_owner,
            remarks="",
            created_by=cls.users["mentor"],
            updated_by=cls.users["mentor"],
        )
        AIUsageRecord.objects.update_or_create(
            entry=cls.permission_entry,
            defaults={
                "ai_tool": cls.ai_tool,
                "ai_assistance_type": cls.ai_assist,
                "ai_contribution_percentage": 30,
                "prompt_summary": "Seed",
                "output_usage": cls.output_usage,
                "human_review_status": cls.human_review,
                "accuracy_helpfulness_rating": 4,
                "estimated_time_saved_hours": 1.0,
                "used_ai_flag": True,
            },
        )

    def _login(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password="pass1234"))

    def _entry_payload(self, entry):
        return {
            "log_date": entry.log_date.isoformat(),
            "intern_profile": entry.intern_profile_id,
            "project": entry.project_id,
            "task_type": entry.task_type_id,
            "task_name": entry.task_name,
            "task_description": entry.task_description,
            "priority": entry.priority_id,
            "planned_work": entry.planned_work,
            "actual_work": entry.actual_work,
            "completion_percentage": entry.completion_percentage,
            "workflow_state": entry.workflow_state,
            "blocker_flag": "on" if entry.blocker_flag else "",
            "blocker_description": entry.blocker_description,
            "support_needed": entry.support_needed,
            "time_spent_hours": str(entry.time_spent_hours),
            "expected_completion_date": entry.expected_completion_date.isoformat()
            if entry.expected_completion_date
            else "",
            "deliverable_link": entry.deliverable_link,
            "final_owner": entry.final_owner_id,
            "remarks": entry.remarks,
            "dependency_text": "Updated dependency",
            "used_ai_flag": "on",
            "ai_tool": "Codex",
            "ai_assistance_type": "Debugging",
            "ai_contribution_percentage": "40",
            "output_usage": "Modified",
            "human_review_status": "Yes",
            "accuracy_helpfulness_rating": "4",
            "estimated_time_saved_hours": "1.2",
            "prompt_summary": "Updated prompt summary",
        }

    def test_daily_log_create_access_for_allowed_roles(self):
        url = reverse("task-create-page")
        for username in ["admin", "manager", "mentor", "intern1"]:
            self._login(username)
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, msg=f"{username} should access create form")

        self._login("hr")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_create_task_for_any_intern(self):
        self._login("manager")
        url = reverse("task-create-page")
        payload = {
            "log_date": date.today().isoformat(),
            "intern_profile": self.intern2.id,
            "project": self.project.id,
            "task_type": self.task_type.id,
            "task_name": "Manager Assigned Task",
            "task_description": "Assigned by manager to intern2",
            "priority": self.priority.id,
            "planned_work": "Plan",
            "actual_work": "Actual",
            "completion_percentage": 25,
            "workflow_state": "SUBMITTED",
            "blocker_description": "",
            "support_needed": "",
            "time_spent_hours": "1.5",
            "expected_completion_date": (date.today() + timedelta(days=2)).isoformat(),
            "final_owner": self.final_owner.id,
            "remarks": "Create test",
            "dependency_text": "",
            "ai_tool": "Codex",
            "ai_assistance_type": "Debugging",
            "ai_contribution_percentage": "20",
            "output_usage": "Modified",
            "human_review_status": "Yes",
            "accuracy_helpfulness_rating": "4",
            "estimated_time_saved_hours": "0.8",
            "prompt_summary": "Create test prompt summary",
            "used_ai_flag": "on",
        }
        resp = self.client.post(url, data=payload, follow=False)
        self.assertEqual(resp.status_code, 302)

        created = DailyProgressEntry.objects.get(task_name="Manager Assigned Task")
        self.assertEqual(created.intern_profile_id, self.intern2.id)
        self.assertEqual(created.created_by_id, self.users["manager"].id)

    def test_edit_permission_matrix(self):
        url = reverse("task-edit-page", kwargs={"pk": self.permission_entry.id})

        for username in ["admin", "manager", "mentor", "intern1"]:
            self._login(username)
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, msg=f"{username} should edit this task")

        for username in ["intern2", "hr"]:
            self._login(username)
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, msg=f"{username} should not edit this task")

    def test_intern_update_creates_jira_style_change_log(self):
        self._login("intern1")
        url = reverse("task-edit-page", kwargs={"pk": self.permission_entry.id})
        payload = self._entry_payload(self.permission_entry)
        payload["actual_work"] = "Updated by assigned intern"
        payload["update_note"] = "Updated progress and actual work details."

        resp = self.client.post(url, data=payload, follow=False)
        self.assertEqual(resp.status_code, 302)

        logs = AuditLog.objects.filter(
            entity_type="DailyProgressEntry",
            entity_id=self.permission_entry.id,
            action_type="intern_update",
            actor=self.users["intern1"],
        )
        self.assertTrue(logs.exists())
        self.assertIn("_note", logs.first().new_value_json)

    def test_task_details_is_html_page_not_api_redirect(self):
        self._login("manager")
        url = reverse("task-detail-page", kwargs={"pk": self.permission_entry.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Task Details")
        self.assertContains(resp, "Change Log")

    def test_daily_logs_filters_and_pagination_preserve_query(self):
        self._login("manager")
        url = reverse("daily-logs-page")
        resp = self.client.get(
            url,
            {
                "intern": str(self.intern1.id),
                "project": str(self.project.id),
                "blocked": "no",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="intern"')
        self.assertContains(resp, "INT-001")
        self.assertContains(resp, "InternMate")
