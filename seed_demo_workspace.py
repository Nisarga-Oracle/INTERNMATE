"""Create safe, repeatable demonstration data for the InternMate ATP workspace.

Run from the project root with the same .env that the FastAPI app uses.
Existing records are preserved; the script only creates missing demo records.
"""
from datetime import date, datetime

from sqlalchemy import text

from backend.app.main import (
    django_password_hash,
    engine,
    ensure_default_master_data,
    find_or_create_id,
    insert_and_return_id,
    master_item_id,
)


PASSWORD = "Demo@1234"
MENTORS = [("arjun", "Arjun", "Rao"), ("krishna", "Krishna", "Mehta")]
INTERNS = [
    ("ananya", "Ananya", "Shah"), ("vikram", "Vikram", "Nair"),
    ("priya", "Priya", "Iyer"), ("rohan", "Rohan", "Kapoor"),
    ("sneha", "Sneha", "Reddy"), ("kunal", "Kunal", "Joshi"),
    ("meera", "Meera", "Das"), ("aditya", "Aditya", "Sinha"),
    ("kavya", "Kavya", "Menon"), ("ishaan", "Ishaan", "Verma"),
]


def user_id(conn, username, first, last, role):
    existing = conn.execute(text("SELECT id FROM auth_user WHERE username=:username"), {"username": username}).scalar()
    if existing:
        return int(existing)
    now = datetime.now()
    uid = insert_and_return_id(conn, "auth_user", {
        "password": django_password_hash(PASSWORD), "last_login": None, "is_superuser": 0,
        "username": username, "last_name": last, "email": f"{username}@internmate.demo",
        "is_staff": 0, "is_active": 1, "date_joined": now, "first_name": first,
    })
    insert_and_return_id(conn, "accounts_userprofile", {"role": role, "user_id": uid})
    return uid


def main():
    now = datetime.now()
    with engine.begin() as conn:
        ensure_default_master_data(conn)
        department_id = find_or_create_id(conn, "operations_department", "name=:name", {"name": "InternMate Demo"}, {"name": "InternMate Demo", "created_at": now, "updated_at": now})
        projects = []
        for code, name in [("DEMO-PORTAL", "Intern Portal Refresh"), ("DEMO-ANALYTICS", "Progress Analytics")]:
            pid = conn.execute(text("SELECT id FROM operations_project WHERE project_code=:code"), {"code": code}).scalar()
            if not pid:
                pid = insert_and_return_id(conn, "operations_project", {"project_code": code, "project_name": name, "description": "Demo project created for local role testing.", "department_id": department_id, "status": "ACTIVE", "created_at": now, "updated_at": now})
            projects.append(int(pid))

        mentor_ids = [user_id(conn, username, first, last, "MENTOR") for username, first, last in MENTORS]
        for mentor_id, project_id in zip(mentor_ids, projects):
            find_or_create_id(conn, "operations_mentorprojectassignment", "mentor_id=:mentor_id AND project_id=:project_id", {"mentor_id": mentor_id, "project_id": project_id}, {"mentor_id": mentor_id, "project_id": project_id, "created_at": now, "updated_at": now})

        for index, (username, first, last) in enumerate(INTERNS, start=1):
            mentor_id, project_id = mentor_ids[(index - 1) % 2], projects[(index - 1) % 2]
            uid = user_id(conn, username, first, last, "INTERN")
            intern_code = f"DEMO-{index:03d}"
            iid = conn.execute(text("SELECT id FROM operations_internprofile WHERE user_id=:user_id"), {"user_id": uid}).scalar()
            if not iid:
                iid = insert_and_return_id(conn, "operations_internprofile", {"intern_code": intern_code, "internship_start_date": date.today(), "internship_end_date": date(date.today().year + 1, date.today().month, date.today().day), "status": "ACTIVE", "department_id": department_id, "manager_id": mentor_id, "mentor_id": mentor_id, "user_id": uid, "created_at": now, "updated_at": now})
            find_or_create_id(conn, "operations_internprojectassignment", "intern_profile_id=:intern_id AND project_id=:project_id", {"intern_id": iid, "project_id": project_id}, {"intern_profile_id": iid, "project_id": project_id, "assigned_from": date.today(), "assigned_to": None, "is_primary": 1, "created_at": now, "updated_at": now})
            has_task = conn.execute(text("SELECT 1 FROM operations_dailyprogressentry WHERE intern_profile_id=:intern_id"), {"intern_id": iid}).scalar()
            if not has_task:
                priority_id = master_item_id(conn, "Priority", "Medium")
                task_type_id = master_item_id(conn, "Task Type", "Documentation")
                owner_id = master_item_id(conn, "Final Owner", "Independent")
                status_id = master_item_id(conn, "Completion Status", "Not Started")
                insert_and_return_id(conn, "operations_dailyprogressentry", {"log_date": date.today(), "task_name": f"Complete onboarding task {index}", "task_description": "Review the assigned project and document your first update.", "planned_work": "Review requirements and prepare a concise status update.", "actual_work": "Not started", "completion_percentage": 0, "workflow_state": "DRAFT", "blocker_flag": 0, "blocker_description": " ", "support_needed": " ", "time_spent_hours": 0, "expected_completion_date": date.today(), "deliverable_link": " ", "remarks": "Demo task assigned by mentor", "on_time_completion_flag": 0, "created_by_id": mentor_id, "updated_by_id": mentor_id, "intern_profile_id": iid, "completion_status_id": status_id, "final_owner_id": owner_id, "priority_id": priority_id, "task_type_id": task_type_id, "project_id": project_id, "created_at": now, "updated_at": now})
    print("Demo workspace ready: 2 mentors, 10 interns, 2 projects, and one task per intern.")
    print("Demo mentors/interns use password: Demo@1234")


if __name__ == "__main__":
    main()
