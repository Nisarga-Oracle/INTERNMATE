from django import forms

from .models import DailyProgressEntry, InternProfile, MasterDataItem, Project


class DailyProgressEntryForm(forms.ModelForm):
    update_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Describe what changed"}),
    )

    class Meta:
        model = DailyProgressEntry
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
        widgets = {
            "log_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "expected_completion_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "task_description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "planned_work": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "actual_work": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "blocker_description": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "support_needed": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "remarks": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "task_name": forms.TextInput(attrs={"class": "form-control"}),
            "deliverable_link": forms.URLInput(attrs={"class": "form-control"}),
            "completion_percentage": forms.NumberInput(attrs={"min": 0, "max": 100, "class": "form-control"}),
            "time_spent_hours": forms.NumberInput(attrs={"min": 0, "step": "0.25", "class": "form-control"}),
            "workflow_state": forms.Select(attrs={"class": "form-select"}),
            "blocker_flag": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        role = kwargs.pop("role", None)
        super().__init__(*args, **kwargs)

        self.fields["intern_profile"].queryset = InternProfile.objects.select_related("user").order_by("intern_code")
        self.fields["project"].queryset = Project.objects.order_by("project_name")
        self.fields["task_type"].queryset = MasterDataItem.objects.filter(list_ref__name="Task Type", is_active=True)
        self.fields["priority"].queryset = MasterDataItem.objects.filter(list_ref__name="Priority", is_active=True)
        self.fields["final_owner"].queryset = MasterDataItem.objects.filter(list_ref__name="Final Owner", is_active=True)

        for name, field in self.fields.items():
            if name in {"blocker_flag", "log_date", "expected_completion_date", "workflow_state"}:
                continue
            if name in {"intern_profile", "project", "task_type", "priority", "final_owner"}:
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

        if role == "INTERN" and user:
            self.fields["intern_profile"].queryset = self.fields["intern_profile"].queryset.filter(user=user)
            self.fields["intern_profile"].empty_label = None
