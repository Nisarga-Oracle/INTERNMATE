"""FastAPI implementation of the InternMate HTTP backend.

The application deliberately reads the existing SQLite schema during the migration
from Django. This preserves all existing InternMate data and the REST paths used
by the React client. The persistence layer can later be switched to Oracle ATP
without changing these HTTP contracts.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import Integer, bindparam, create_engine, inspect, text
from sqlalchemy.engine import RowMapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    for env_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in env_line and not env_line.lstrip().startswith("#"):
            env_key, env_value = env_line.split("=", 1)
            os.environ.setdefault(env_key.strip(), env_value.strip())
ORACLE_USER = os.getenv("INTERNMATE_ORACLE_USER", "LEARNING")
ORACLE_PASSWORD = os.getenv("INTERNMATE_ORACLE_PASSWORD")
ORACLE_DSN = os.getenv("INTERNMATE_ORACLE_DSN", "tecpdatp01_medium")
ORACLE_WALLET_DIR = os.getenv("INTERNMATE_ORACLE_WALLET_DIR", r"C:\Users\Nisarga\Documents\ATP_CREDENTIALS")
ORACLE_WALLET_PASSWORD = os.getenv("INTERNMATE_ORACLE_WALLET_PASSWORD")
DATABASE_MODE = os.getenv("INTERNMATE_DATABASE", "sqlite").lower()
if DATABASE_MODE == "sqlite":
    engine = create_engine(f"sqlite:///{PROJECT_ROOT / 'db.sqlite3'}", connect_args={"check_same_thread": False})
elif DATABASE_MODE == "oracle":
    if not ORACLE_PASSWORD:
        raise RuntimeError("INTERNMATE_ORACLE_PASSWORD must be configured before starting the InternMate API.")
    oracle_connect_args = {"user": ORACLE_USER, "password": ORACLE_PASSWORD, "dsn": ORACLE_DSN, "config_dir": ORACLE_WALLET_DIR, "wallet_location": ORACLE_WALLET_DIR}
    if ORACLE_WALLET_PASSWORD:
        oracle_connect_args["wallet_password"] = ORACLE_WALLET_PASSWORD
    engine = create_engine("oracle+oracledb://", connect_args=oracle_connect_args, pool_pre_ping=True)
else:
    raise RuntimeError("INTERNMATE_DATABASE must be either 'sqlite' or 'oracle'.")
security = HTTPBasic(auto_error=False)
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI(title="InternMate API", version="2.0.0")
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def as_dict(row: RowMapping | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: json_value(value) for key, value in row.items()}


def django_password_matches(raw_password: str, encoded: str) -> bool:
    """Validate the existing Django PBKDF2 hashes without importing Django."""
    try:
        algorithm, iterations, salt, stored = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        calculated = base64.b64encode(
            hashlib.pbkdf2_hmac("sha256", raw_password.encode(), salt.encode(), int(iterations))
        ).decode()
        return hmac.compare_digest(calculated, stored)
    except (TypeError, ValueError):
        return False


def django_password_hash(raw_password: str) -> str:
    """Create a Django-compatible PBKDF2 hash for website users."""
    salt = secrets.token_urlsafe(16)
    iterations = 1_200_000
    digest = base64.b64encode(
        hashlib.pbkdf2_hmac("sha256", raw_password.encode(), salt.encode(), iterations)
    ).decode()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def current_user(credentials: HTTPBasicCredentials | None = Depends(security)) -> dict[str, Any]:
    if not credentials:
        # The React login form handles a 401 itself.  Do not send a browser
        # Basic-auth challenge here, because it opens Chrome's native popup
        # instead of keeping authentication inside the InternMate screen.
        raise HTTPException(status_code=401, detail="Authentication required")
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """SELECT u.id, u.username, u.first_name, u.last_name, u.password, u.is_superuser,
                          COALESCE(p.role, 'INTERN') AS role
                   FROM auth_user u LEFT JOIN accounts_userprofile p ON p.user_id = u.id
                   WHERE u.username = :username AND u.is_active = 1"""
            ),
            {"username": credentials.username},
        ).mappings().first()
    if not row or not django_password_matches(credentials.password, row["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    user = as_dict(row) or {}
    if user["is_superuser"]:
        user["role"] = "ADMIN"
    return user


def visible_clause(user: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    # Shared intern-workspace mode: interns can view the full task directory
    # and choose the person whose progress is being updated.
    return "", {}


def entry_query(user: dict[str, Any], filters: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    filters = filters or {}
    where, params = visible_clause(user)
    clauses = ["1 = 1" + where]
    for key, column in {
        "intern_profile": "e.intern_profile_id",
        "project": "e.project_id",
        "workflow_state": "e.workflow_state",
        "blocker_flag": "e.blocker_flag",
    }.items():
        value = filters.get(key)
        if value not in (None, ""):
            clauses.append(f"{column} = :{key}")
            params[key] = int(value) if key in {"intern_profile", "project"} else value
    if filters.get("date_from"):
        clauses.append("e.log_date >= :date_from")
        params["date_from"] = filters["date_from"]
    if filters.get("date_to"):
        clauses.append("e.log_date <= :date_to")
        params["date_to"] = filters["date_to"]
    sql = """
        FROM operations_dailyprogressentry e
        JOIN operations_internprofile i ON i.id = e.intern_profile_id
        JOIN auth_user u ON u.id = i.user_id
        JOIN operations_project pr ON pr.id = e.project_id
        LEFT JOIN operations_masterdataitem owner ON owner.id = e.final_owner_id
        LEFT JOIN operations_aiusagerecord ai ON ai.entry_id = e.id
        LEFT JOIN operations_masterdataitem ai_tool ON ai_tool.id = ai.ai_tool_id
        WHERE """ + " AND ".join(clauses)
    return sql, params


def hide_hr_fields(entry: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    if user["role"] == "HR":
        for field in ("task_description", "planned_work", "actual_work", "blocker_description", "support_needed", "remarks", "deliverable_link"):
            entry.pop(field, None)
    return entry


class WorkflowAction(BaseModel):
    action: str
    comment: str = ""


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": "fastapi"}


@app.get("/api/daily-logs/")
def list_daily_logs(
    page: int = 1,
    intern_profile: int | None = None,
    project: int | None = None,
    workflow_state: str | None = None,
    blocker_flag: bool | None = None,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    tail, params = entry_query(user, {"intern_profile": intern_profile, "project": project, "workflow_state": workflow_state, "blocker_flag": blocker_flag})
    page_size, offset = 100, max(page - 1, 0) * 100
    select = """SELECT e.*, TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, '')) AS intern_name,
                        (SELECT TRIM(COALESCE(mu.first_name, '') || ' ' || COALESCE(mu.last_name, '')) FROM auth_user mu WHERE mu.id = i.mentor_id) AS mentor_name,
                        pr.project_name, owner.value AS final_owner,
                        ai_tool.value AS ai_tool,
                        COALESCE(ai.used_ai_flag, 0) AS used_ai_flag,
                        COALESCE(ai.estimated_time_saved_hours, 0) AS estimated_time_saved_hours"""
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) " + tail), params).scalar_one()
        pagination = " LIMIT :limit OFFSET :offset" if DATABASE_MODE == "sqlite" else " OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
        rows = conn.execute(text(select + tail + " ORDER BY e.log_date DESC, e.updated_at DESC" + pagination), {**params, "limit": page_size, "offset": offset}).mappings().all()
    results = [hide_hr_fields(as_dict(row) or {}, user) for row in rows]
    for entry in results:
        # Keep the UI date-only: Oracle serializes DATE values with midnight.
        raw_date = entry.get("log_date")
        if isinstance(raw_date, str):
            try:
                parsed = datetime.fromisoformat(raw_date)
                entry["log_date"] = f"{parsed.day:02d} {parsed.strftime('%B')} {parsed.year}"
            except ValueError:
                pass
    return {"count": count, "next": None if offset + page_size >= count else f"?page={page + 1}", "previous": None if page <= 1 else f"?page={page - 1}", "results": results}


@app.get("/api/daily-logs/{entry_id}/")
def get_daily_log(entry_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    tail, params = entry_query(user)
    params["entry_id"] = entry_id
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT e.*, TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, '')) AS intern_name,
                                         pr.project_name, owner.value AS final_owner """ + tail + " AND e.id = :entry_id"), params).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Daily log not found")
        data = as_dict(row) or {}
        dependencies = conn.execute(text("SELECT * FROM operations_taskdependency WHERE entry_id = :id"), {"id": entry_id}).mappings().all()
        ai_usage = conn.execute(text("SELECT * FROM operations_aiusagerecord WHERE entry_id = :id"), {"id": entry_id}).mappings().first()
        comments = conn.execute(text("SELECT * FROM operations_mentorreviewcomment WHERE entry_id = :id ORDER BY action_at DESC"), {"id": entry_id}).mappings().all()
    data.update({"dependencies": [as_dict(r) for r in dependencies], "ai_usage": as_dict(ai_usage), "review_comments": [as_dict(r) for r in comments]})
    return hide_hr_fields(data, user)


def paginated_table(table: str, page: int, user: dict[str, Any]) -> dict[str, Any]:
    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        pagination = " LIMIT :limit OFFSET :offset" if DATABASE_MODE == "sqlite" else " OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
        page_size, offset = 100, max(page - 1, 0) * 100
        rows = conn.execute(text(f"SELECT * FROM {table} ORDER BY id" + pagination), {"limit": page_size, "offset": offset}).mappings().all()
    return {"count": count, "next": None if offset + page_size >= count else f"?page={page + 1}", "previous": None if page <= 1 else f"?page={page - 1}", "results": [as_dict(row) for row in rows]}


@app.get("/api/interns/")
def list_interns(page: int = 1, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    conditions, params = "", {}
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT i.*, TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, '')) AS intern_name FROM operations_internprofile i JOIN auth_user u ON u.id = i.user_id" + conditions + " ORDER BY i.id"), params).mappings().all()
    return {"count": len(rows), "next": None, "previous": None, "results": [as_dict(row) for row in rows]}


@app.get("/api/projects/")
def list_projects(page: int = 1, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return paginated_table("operations_project", page, user)


@app.post("/api/daily-logs/{entry_id}/workflow/")
def workflow(entry_id: int, body: WorkflowAction, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    allowed = {"DRAFT", "SUBMITTED", "REVIEWED", "REOPENED", "CLOSED"}
    if body.action not in allowed:
        raise HTTPException(status_code=400, detail="Invalid workflow action")
    detail = get_daily_log(entry_id, user)
    if user["role"] not in {"ADMIN", "MENTOR", "INTERN"}:
        raise HTTPException(status_code=403, detail="You are not allowed to perform this workflow action")
    with engine.begin() as conn:
        conn.execute(text("UPDATE operations_dailyprogressentry SET workflow_state=:state, updated_by_id=:user_id, updated_at=CURRENT_TIMESTAMP WHERE id=:id"), {"state": body.action, "user_id": user["id"], "id": entry_id})
        if body.comment or body.action in {"REOPENED", "REVIEWED", "CLOSED"}:
            conn.execute(text("INSERT INTO operations_mentorreviewcomment (entry_id, reviewer_id, action, comment_text, action_at, created_at, updated_at) VALUES (:id,:user_id,:action,:comment,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"id": entry_id, "user_id": user["id"], "action": body.action, "comment": body.comment})
    return get_daily_log(entry_id, user)


@app.get("/reports/export/")
def export_reports(
    format: str = "csv",
    intern_profile: int | None = None,
    project: int | None = None,
    workflow_state: str | None = None,
    blocker_flag: bool | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    tail, params = entry_query(user, {"intern_profile": intern_profile, "project": project, "workflow_state": workflow_state, "blocker_flag": blocker_flag, "date_from": date_from, "date_to": date_to})
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT e.log_date AS log_date, TRIM(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) AS intern_name, pr.project_name AS project_name, e.task_name AS task_name, e.workflow_state AS workflow_state, e.completion_percentage AS completion, e.blocker_flag AS blocked, owner.value AS owner " + tail + " ORDER BY e.log_date DESC"), params).mappings().all()
    report_rows = [{"Date": str(r["log_date"]), "Intern": r["intern_name"], "Project": r["project_name"], "Task": r["task_name"], "Workflow": r["workflow_state"], "Completion %": r["completion"], "Blocked": "Yes" if r["blocked"] else "No", "Final Owner": r["owner"]} for r in rows]
    headers = ["Date", "Intern", "Project", "Task", "Workflow", "Completion %", "Blocked", "Final Owner"]
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader(); writer.writerows(report_rows)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="internmate_report.csv"'})
    if format == "xlsx":
        from openpyxl import Workbook
        workbook = Workbook(); sheet = workbook.active; sheet.title = "InternMate"
        sheet.append(headers)
        for row in report_rows:
            sheet.append([row.get(header, "") for header in headers])
        output = io.BytesIO(); workbook.save(output); output.seek(0)
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="internmate_report.xlsx"'})
    if format == "pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        output = io.BytesIO(); pdf = canvas.Canvas(output, pagesize=A4); y = 800
        pdf.setFont("Helvetica-Bold", 12); pdf.drawString(40, y, "InternMate Summary Report"); y -= 24
        pdf.setFont("Helvetica", 9)
        for row in report_rows[:50]:
            line = f"{row['Date']} | {row['Intern']} | {row['Project']} | {row['Completion %']}% | Blocked: {row['Blocked']}"
            pdf.drawString(40, y, line[:110]); y -= 14
            if y < 50:
                pdf.showPage(); y = 800; pdf.setFont("Helvetica", 9)
        pdf.save(); output.seek(0)
        return StreamingResponse(output, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="internmate_report.pdf"'})
    raise HTTPException(status_code=400, detail="Unsupported format")


@app.get("/")
def home() -> Response:
    """Serve the unchanged compiled React interface from FastAPI."""
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    return RedirectResponse("http://127.0.0.1:5173/")

# FastAPI CRUD and administration compatibility layer.
ADMIN_TABLES = {
    "departments": "operations_department",
    "projects": "operations_project",
    "interns": "operations_internprofile",
    "intern-assignments": "operations_internprojectassignment",
    "master-data-lists": "operations_masterdatalist",
    "master-data-items": "operations_masterdataitem",
    "ai-usage": "operations_aiusagerecord",
}

DEFAULT_MASTER_DATA = {
    "Task Type": ["Backend", "Frontend", "Testing", "Documentation"],
    "Priority": ["Low", "Medium", "High", "Critical"],
    "Completion Status": ["Not Started", "Initiated", "In Progress", "Near Completion", "Completed"],
    "Final Owner": ["Independent", "Joint"],
    "AI Tool": ["Codex", "ChatGPT", "Gemini", "Other"],
    "AI Assistance Type": ["General Assistance"],
    "Output Usage": ["Used"],
    "Human Review Status": ["Reviewed"],
}


def require_admin(user: dict[str, Any]) -> dict[str, Any]:
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    return user


def require_mentor(user: dict[str, Any]) -> dict[str, Any]:
    if user["role"] != "MENTOR":
        raise HTTPException(status_code=403, detail="Mentor access is required")
    return user


def writable_columns(table: str) -> set[str]:
    return {column["name"].lower() for column in inspect(engine).get_columns(table)} - {"id", "created_at", "updated_at"}


def insert_and_return_id(conn, table: str, values: dict[str, Any]) -> int:
    # Bind real Python dates to Oracle. Passing an ISO string makes Oracle use
    # its session date format and caused task saves to fail with ORA-01843.
    bind_values = dict(values)
    for field in ("log_date", "start_date", "end_date", "expected_completion_date", "internship_start_date", "internship_end_date", "assigned_from", "assigned_to"):
        value = bind_values.get(field)
        if isinstance(value, str) and value:
            try:
                bind_values[field] = date.fromisoformat(value[:10])
            except ValueError:
                pass
    for field in ("created_at", "updated_at"):
        value = bind_values.get(field)
        if isinstance(value, str) and value:
            try:
                bind_values[field] = datetime.fromisoformat(value)
            except ValueError:
                pass
    columns = list(bind_values)
    placeholders = ", ".join(f":{column}" for column in columns)
    if DATABASE_MODE == "sqlite":
        result = conn.execute(text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"), bind_values)
        return int(result.lastrowid)
    statement = text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id INTO :new_id").bindparams(bindparam("new_id", type_=Integer, isoutparam=True))
    result = conn.execute(statement, {**bind_values, "new_id": None})
    new_id = result.out_parameters["new_id"]
    # python-oracledb returns a one-item list for a DML RETURNING bind.
    if isinstance(new_id, (list, tuple)):
        new_id = new_id[0]
    return int(new_id)


def record_by_id(table: str, record_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT * FROM {table} WHERE id=:id"), {"id": record_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return as_dict(row) or {}


def write_record(table: str, payload: dict[str, Any], actor_id: int, record_id: int | None = None) -> dict[str, Any]:
    allowed = writable_columns(table)
    values = {key: value for key, value in payload.items() if key in allowed}
    if not values:
        raise HTTPException(status_code=400, detail="No writable fields were supplied")
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    if record_id is None:
        values.setdefault("created_at", now)
    values.setdefault("updated_at", now)
    with engine.begin() as conn:
        if record_id is None:
            new_id = insert_and_return_id(conn, table, values)
        else:
            assignments = ", ".join(f"{column}=:{column}" for column in values)
            conn.execute(text(f"UPDATE {table} SET {assignments} WHERE id=:id"), {**values, "id": record_id})
            new_id = record_id
    return record_by_id(table, int(new_id))


def find_or_create_id(conn, table: str, where: str, lookup: dict[str, Any], values: dict[str, Any]) -> int:
    record_id = conn.execute(text(f"SELECT id FROM {table} WHERE {where}"), lookup).scalar()
    return int(record_id) if record_id is not None else insert_and_return_id(conn, table, values)


@app.post("/api/setup/defaults/")
def initialize_workspace(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Create the smallest usable blank workspace for a fresh ATP deployment."""
    require_admin(user)
    now = datetime.now()
    with engine.begin() as conn:
        list_ids: dict[str, int] = {}
        for list_name, items in DEFAULT_MASTER_DATA.items():
            list_id = find_or_create_id(
                conn, "operations_masterdatalist", "name=:name", {"name": list_name},
                {"name": list_name, "description": f"InternMate {list_name}", "created_at": now, "updated_at": now},
            )
            list_ids[list_name] = list_id
            for display_order, value in enumerate(items, start=1):
                find_or_create_id(
                    conn, "operations_masterdataitem", "list_ref_id=:list_ref_id AND value=:value",
                    {"list_ref_id": list_id, "value": value},
                    {"list_ref_id": list_id, "value": value, "display_order": display_order, "is_active": 1, "created_at": now, "updated_at": now},
                )

        engineering_id = find_or_create_id(
            conn, "operations_department", "name=:name", {"name": "Engineering"},
            {"name": "Engineering", "created_at": now, "updated_at": now},
        )
        data_id = find_or_create_id(
            conn, "operations_department", "name=:name", {"name": "Data"},
            {"name": "Data", "created_at": now, "updated_at": now},
        )
        internmate_project = find_or_create_id(
            conn, "operations_project", "project_code=:project_code", {"project_code": "INTERNMATE"},
            {"project_code": "INTERNMATE", "project_name": "InternMate", "department_id": engineering_id, "status": "ACTIVE", "description": "Fresh ATP workspace", "created_at": now, "updated_at": now},
        )
        ai_project = find_or_create_id(
            conn, "operations_project", "project_code=:project_code", {"project_code": "AI-INSIGHTS"},
            {"project_code": "AI-INSIGHTS", "project_name": "AI Insights", "department_id": data_id, "status": "ACTIVE", "description": "Fresh ATP workspace", "created_at": now, "updated_at": now},
        )
        intern_specs = [(5, "INT-001", engineering_id, internmate_project), (6, "INT-002", engineering_id, internmate_project), (7, "INT-003", data_id, ai_project)]
        for user_id, intern_code, department_id, project_id in intern_specs:
            intern_id = find_or_create_id(
                conn, "operations_internprofile", "user_id=:user_id", {"user_id": user_id},
                {"user_id": user_id, "intern_code": intern_code, "department_id": department_id, "mentor_id": 3, "manager_id": 2, "internship_start_date": date.today(), "internship_end_date": date.today().replace(year=date.today().year + 1), "status": "ACTIVE", "created_at": now, "updated_at": now},
            )
            find_or_create_id(
                conn, "operations_internprojectassignment", "intern_profile_id=:intern_profile_id AND project_id=:project_id AND assigned_from=:assigned_from",
                {"intern_profile_id": intern_id, "project_id": project_id, "assigned_from": date.today()},
                {"intern_profile_id": intern_id, "project_id": project_id, "assigned_from": date.today(), "assigned_to": None, "is_primary": 1, "created_at": now, "updated_at": now},
            )
    return {"status": "initialized", "message": "Created starter departments, projects, intern profiles, and daily-log reference data."}


@app.get("/api/me/")
def current_profile(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {key: user[key] for key in ("id", "username", "first_name", "last_name", "role")}


def ensure_default_master_data(conn) -> None:
    """Create the dropdown values needed by mentor task assignment, only if absent."""
    now = datetime.now()
    for list_name, values in DEFAULT_MASTER_DATA.items():
        list_id = find_or_create_id(conn, "operations_masterdatalist", "name=:name", {"name": list_name}, {"name": list_name, "description": f"InternMate {list_name}", "created_at": now, "updated_at": now})
        for order, value in enumerate(values, start=1):
            find_or_create_id(conn, "operations_masterdataitem", "list_ref_id=:list_ref_id AND value=:value", {"list_ref_id": list_id, "value": value}, {"list_ref_id": list_id, "value": value, "display_order": order, "is_active": 1, "created_at": now, "updated_at": now})


def master_item_id(conn, list_name: str, value: str) -> int:
    item_id = conn.execute(text("""SELECT i.id FROM operations_masterdataitem i
        JOIN operations_masterdatalist l ON l.id=i.list_ref_id
        WHERE l.name=:list_name AND i.value=:value"""), {"list_name": list_name, "value": value}).scalar()
    if item_id is None:
        raise HTTPException(status_code=400, detail="Workspace reference data is missing. Ask the administrator to initialize the workspace.")
    return int(item_id)


def upsert_ai_usage(conn, entry_id: int, payload: dict[str, Any]) -> None:
    """Save the optional AI details submitted with an intern's task update."""
    if "ai_tool" not in payload and "estimated_time_saved_hours" not in payload:
        return

    selected_tool = str(payload.get("ai_tool", "")).strip()
    other_tool = str(payload.get("ai_other_platform", "")).strip()
    if selected_tool == "Other":
        selected_tool = other_tool
    if selected_tool and selected_tool not in {"Codex", "ChatGPT", "Gemini"} and len(selected_tool) > 100:
        raise HTTPException(status_code=400, detail="AI platform name must be 100 characters or fewer")

    try:
        time_saved = Decimal(str(payload.get("estimated_time_saved_hours", 0) or 0))
    except Exception as error:
        raise HTTPException(status_code=400, detail="Time saved must be a valid number") from error
    if time_saved < 0 or time_saved > Decimal("999.99"):
        raise HTTPException(status_code=400, detail="Time saved must be between 0 and 999.99 hours")

    if not selected_tool:
        # An explicit "No AI used" selection clears AI information for this task.
        conn.execute(text("DELETE FROM operations_aiusagerecord WHERE entry_id=:entry_id"), {"entry_id": entry_id})
        return

    ensure_default_master_data(conn)
    list_id = find_or_create_id(
        conn, "operations_masterdatalist", "name=:name", {"name": "AI Tool"},
        {"name": "AI Tool", "description": "InternMate AI Tool", "created_at": datetime.now(), "updated_at": datetime.now()},
    )
    tool_id = find_or_create_id(
        conn, "operations_masterdataitem", "list_ref_id=:list_ref_id AND value=:value",
        {"list_ref_id": list_id, "value": selected_tool},
        {"list_ref_id": list_id, "value": selected_tool, "display_order": 99, "is_active": 1, "created_at": datetime.now(), "updated_at": datetime.now()},
    )
    values = {
        "ai_tool_id": tool_id,
        "ai_assistance_type_id": master_item_id(conn, "AI Assistance Type", "General Assistance"),
        "ai_contribution_percentage": 0,
        "prompt_summary": other_tool if other_tool else " ",
        "output_usage_id": master_item_id(conn, "Output Usage", "Used"),
        "human_review_status_id": master_item_id(conn, "Human Review Status", "Reviewed"),
        "accuracy_helpfulness_rating": 0,
        "estimated_time_saved_hours": time_saved,
        "used_ai_flag": 1,
        "updated_at": datetime.now(),
    }
    existing_id = conn.execute(text("SELECT id FROM operations_aiusagerecord WHERE entry_id=:entry_id"), {"entry_id": entry_id}).scalar()
    if existing_id:
        conn.execute(text("UPDATE operations_aiusagerecord SET " + ", ".join(f"{key}=:{key}" for key in values) + " WHERE entry_id=:entry_id"), {**values, "entry_id": entry_id})
    else:
        insert_and_return_id(conn, "operations_aiusagerecord", {**values, "entry_id": entry_id, "created_at": datetime.now()})


def create_login_user(conn, payload: dict[str, Any], role: str) -> int:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and temporary password are required")
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    try:
        user_id = insert_and_return_id(conn, "auth_user", {
            "password": django_password_hash(password), "last_login": None, "is_superuser": 0,
            "username": username, "last_name": str(payload.get("last_name", "")).strip(),
            "email": str(payload.get("email", "")).strip(), "is_staff": 0, "is_active": 1,
            "date_joined": now, "first_name": str(payload.get("first_name", "")).strip(),
        })
        insert_and_return_id(conn, "accounts_userprofile", {"role": role, "user_id": user_id})
        return user_id
    except Exception as error:
        if "UNIQUE" in str(error).upper():
            raise HTTPException(status_code=400, detail="That username already exists") from error
        raise


@app.get("/api/admin/mentors/")
def admin_mentors(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT u.id, u.username, u.first_name, u.last_name, u.email,
            (SELECT COUNT(*) FROM operations_mentorprojectassignment a WHERE a.mentor_id=u.id) AS project_count,
            (SELECT COUNT(*) FROM operations_internprofile i WHERE i.mentor_id=u.id) AS intern_count
            FROM auth_user u JOIN accounts_userprofile p ON p.user_id=u.id
            WHERE p.role='MENTOR' AND u.is_active=1 ORDER BY u.first_name, u.username""")).mappings().all()
    return {"results": [as_dict(row) for row in rows]}


@app.post("/api/admin/mentors/", status_code=201)
def admin_create_mentor(payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    with engine.begin() as conn:
        mentor_id = create_login_user(conn, payload, "MENTOR")
    return record_by_id("auth_user", mentor_id)


@app.post("/api/admin/projects/", status_code=201)
def admin_create_project(payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    code, name = str(payload.get("project_code", "")).strip(), str(payload.get("project_name", "")).strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="Project code and project name are required")
    now = datetime.now()
    with engine.begin() as conn:
        department_id = find_or_create_id(conn, "operations_department", "name=:name", {"name": "InternMate"}, {"name": "InternMate", "created_at": now, "updated_at": now})
        project_id = insert_and_return_id(conn, "operations_project", {"project_code": code, "project_name": name, "description": str(payload.get("description", "")).strip() or " ", "department_id": department_id, "status": str(payload.get("status", "ACTIVE")).upper(), "start_date": payload.get("start_date") or None, "end_date": payload.get("end_date") or None, "created_at": now, "updated_at": now})
    return record_by_id("operations_project", project_id)


@app.post("/api/admin/project-mentors/", status_code=201)
def admin_assign_project_mentor(payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    mentor_id, project_id = int(payload.get("mentor_id", 0)), int(payload.get("project_id", 0))
    now = datetime.now()
    with engine.begin() as conn:
        mentor = conn.execute(text("""SELECT 1 FROM auth_user u JOIN accounts_userprofile p ON p.user_id=u.id
            WHERE u.id=:id AND p.role='MENTOR' AND u.is_active=1"""), {"id": mentor_id}).scalar()
        if not mentor:
            raise HTTPException(status_code=400, detail="Select an active mentor")
        assignment_id = find_or_create_id(conn, "operations_mentorprojectassignment", "mentor_id=:mentor_id AND project_id=:project_id", {"mentor_id": mentor_id, "project_id": project_id}, {"mentor_id": mentor_id, "project_id": project_id, "created_at": now, "updated_at": now})
    return {"id": assignment_id, "message": "Mentor assigned to project"}


@app.get("/api/mentor/projects/")
def mentor_projects(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_mentor(user)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT p.* FROM operations_project p WHERE p.status='ACTIVE' ORDER BY p.project_name")).mappings().all()
    return {"results": [as_dict(row) for row in rows]}


@app.post("/api/mentor/interns/", status_code=201)
def mentor_create_intern(payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_mentor(user)
    project_id = int(payload.get("project_id", 0))
    intern_code = str(payload.get("intern_code", "")).strip()
    if not intern_code:
        raise HTTPException(status_code=400, detail="Intern code is required")
    now = datetime.now()
    with engine.begin() as conn:
        project = conn.execute(text("""SELECT p.department_id FROM operations_project p
            JOIN operations_mentorprojectassignment a ON a.project_id=p.id
            WHERE p.id=:project_id AND a.mentor_id=:mentor_id"""), {"project_id": project_id, "mentor_id": user["id"]}).mappings().first()
        if not project:
            raise HTTPException(status_code=403, detail="Select one of your assigned projects")
        intern_user_id = create_login_user(conn, payload, "INTERN")
        intern_id = insert_and_return_id(conn, "operations_internprofile", {"intern_code": intern_code, "user_id": intern_user_id, "department_id": project["department_id"], "mentor_id": user["id"], "manager_id": user["id"], "internship_start_date": date.today(), "internship_end_date": date.today().replace(year=date.today().year + 1), "status": "ACTIVE", "created_at": now, "updated_at": now})
        insert_and_return_id(conn, "operations_internprojectassignment", {"intern_profile_id": intern_id, "project_id": project_id, "assigned_from": date.today(), "assigned_to": None, "is_primary": 1, "created_at": now, "updated_at": now})
    return record_by_id("operations_internprofile", intern_id)


@app.post("/api/mentor/tasks/", status_code=201)
def mentor_assign_task(payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_mentor(user)
    intern_id, project_id = int(payload.get("intern_profile_id", 0)), int(payload.get("project_id", 0))
    task_name = str(payload.get("task_name", "")).strip()
    if not task_name:
        raise HTTPException(status_code=400, detail="Task name is required")
    expected_completion = payload.get("expected_completion_date") or None
    if expected_completion:
        try:
            expected_date = date.fromisoformat(str(expected_completion)[:10])
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Expected completion must be a valid date") from error
        if expected_date < date.today():
            raise HTTPException(status_code=400, detail="Expected completion must be today or a future date")
    with engine.begin() as conn:
        ensure_default_master_data(conn)
        owns_intern = conn.execute(text("SELECT 1 FROM operations_internprofile WHERE id=:id"), {"id": intern_id}).scalar()
        owns_project = conn.execute(text("SELECT 1 FROM operations_project WHERE id=:project_id AND status='ACTIVE'"), {"project_id": project_id}).scalar()
        if not (owns_intern and owns_project):
            raise HTTPException(status_code=403, detail="Choose an active intern and project")
        # Serialize assignments for this intern.  Together with the exact-match
        # lookup below, this prevents a double-click (or a browser retry) from
        # creating more than one copy of the same task.
        lock_suffix = " FOR UPDATE" if engine.dialect.name == "oracle" else ""
        conn.execute(text(f"SELECT id FROM operations_internprofile WHERE id=:id{lock_suffix}"), {"id": intern_id})
        due_date_expression = "TRUNC(expected_completion_date)" if engine.dialect.name == "oracle" else "DATE(expected_completion_date)"
        duplicate_task_id = conn.execute(text("""
            SELECT MIN(id)
            FROM operations_dailyprogressentry
            WHERE intern_profile_id=:intern_id
              AND project_id=:project_id
              AND LOWER(TRIM(task_name))=:task_name
              AND created_by_id=:created_by_id
              AND ((expected_completion_date IS NULL AND :expected_completion_date IS NULL)
                   OR """ + due_date_expression + """=:expected_completion_date)
        """), {
            "intern_id": intern_id,
            "project_id": project_id,
            "task_name": task_name.lower(),
            "created_by_id": user["id"],
            "expected_completion_date": expected_date if expected_completion else None,
        }).scalar()
        if duplicate_task_id:
            return get_daily_log(int(duplicate_task_id), user)
        # Single-mentor workspace mode: selecting a project assigns that intern
        # to it automatically before their task is created.
        is_allocated = conn.execute(text("SELECT 1 FROM operations_internprojectassignment WHERE intern_profile_id=:intern_id AND project_id=:project_id"), {"intern_id": intern_id, "project_id": project_id}).scalar()
        if not is_allocated:
            insert_and_return_id(conn, "operations_internprojectassignment", {
                "intern_profile_id": intern_id, "project_id": project_id,
                "assigned_from": date.today(), "assigned_to": None, "is_primary": 0,
                "created_at": datetime.now(), "updated_at": datetime.now(),
            })
        priority = str(payload.get("priority", "Medium"))
        priority_id = master_item_id(conn, "Priority", priority)
        task_type_id = master_item_id(conn, "Task Type", str(payload.get("task_type", "Documentation")))
        final_owner_id = master_item_id(conn, "Final Owner", "Independent")
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        task_id = insert_and_return_id(conn, "operations_dailyprogressentry", {"log_date": date.today(), "task_name": task_name, "task_description": str(payload.get("task_description", "")).strip() or " ", "planned_work": str(payload.get("planned_work", "")).strip() or " ", "actual_work": "Not started", "completion_percentage": 0, "workflow_state": "DRAFT", "blocker_flag": 0, "blocker_description": " ", "support_needed": " ", "time_spent_hours": 0, "expected_completion_date": expected_completion, "deliverable_link": " ", "remarks": "Assigned by mentor", "on_time_completion_flag": 0, "created_by_id": user["id"], "updated_by_id": user["id"], "intern_profile_id": intern_id, "completion_status_id": master_item_id(conn, "Completion Status", "Not Started"), "final_owner_id": final_owner_id, "priority_id": priority_id, "task_type_id": task_type_id, "project_id": project_id, "created_at": now, "updated_at": now})
    return get_daily_log(task_id, user)


@app.get("/api/{resource}/")
def list_admin_resource(resource: str, page: int = 1, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    table = ADMIN_TABLES.get(resource)
    if not table:
        raise HTTPException(status_code=404, detail="Unknown resource")
    return paginated_table(table, page, user)


@app.get("/api/users/")
def list_users(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT u.id, u.username, u.first_name, u.last_name, u.email,
                                         u.is_active, COALESCE(p.role, 'INTERN') AS role
                                  FROM auth_user u LEFT JOIN accounts_userprofile p ON p.user_id = u.id
                                  ORDER BY u.id""")).mappings().all()
    return {"count": len(rows), "next": None, "previous": None, "results": [as_dict(row) for row in rows]}


@app.post("/api/users/", status_code=201)
def create_user(payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "INTERN")).upper()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if role != "MENTOR":
        raise HTTPException(status_code=400, detail="Invalid role")
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    try:
        with engine.begin() as conn:
            user_id = insert_and_return_id(conn, "auth_user", {
                "password": django_password_hash(password), "last_login": None,
                "is_superuser": 1 if role == "ADMIN" else 0, "username": username,
                "last_name": str(payload.get("last_name", "")).strip(),
                "email": str(payload.get("email", "")).strip(), "is_staff": 1 if role == "ADMIN" else 0,
                "is_active": 1, "date_joined": now, "first_name": str(payload.get("first_name", "")).strip(),
            })
            insert_and_return_id(conn, "accounts_userprofile", {"role": role, "user_id": user_id})
    except Exception as error:
        if "UNIQUE" in str(error).upper():
            raise HTTPException(status_code=400, detail="That username already exists") from error
        raise
    return record_by_id("auth_user", user_id)


def can_edit_entry(user: dict[str, Any], entry_id: int) -> bool:
    if user["role"] in {"ADMIN", "MENTOR", "INTERN"}:
        return True
    with engine.connect() as conn:
        row = conn.execute(text("SELECT e.created_by_id, i.user_id FROM operations_dailyprogressentry e JOIN operations_internprofile i ON i.id=e.intern_profile_id WHERE e.id=:id"), {"id": entry_id}).mappings().first()
    return bool(row and user["role"] == "INTERN" and (row["created_by_id"] == user["id"] or row["user_id"] == user["id"]))


def completion_status_id(percentage: int) -> int | None:
    label = "Not Started" if percentage == 0 else "Initiated" if percentage <= 30 else "In Progress" if percentage <= 70 else "Near Completion" if percentage <= 99 else "Completed"
    with engine.connect() as conn:
        return conn.execute(text("SELECT m.id FROM operations_masterdataitem m JOIN operations_masterdatalist l ON l.id=m.list_ref_id WHERE l.name='Completion Status' AND m.value=:label AND m.is_active=1"), {"label": label}).scalar()


def normalize_daily_log_text(values: dict[str, Any]) -> None:
    """Oracle treats an empty string as NULL; these ATP columns are NOT NULL."""
    for field in ("task_description", "planned_work", "actual_work", "blocker_description", "support_needed", "deliverable_link", "remarks"):
        if field in values and values[field] in (None, ""):
            values[field] = " "


@app.post("/api/daily-logs/", status_code=201)
def create_daily_log(payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["role"] not in {"ADMIN", "MENTOR", "INTERN"}:
        raise HTTPException(status_code=403, detail="You are not allowed to create daily logs")
    intern_id = payload.get("intern_profile_id", payload.get("intern_profile"))
    if user["role"] == "INTERN":
        with engine.connect() as conn:
            own = conn.execute(text("SELECT id FROM operations_internprofile WHERE user_id=:id"), {"id": user["id"]}).scalar()
        if int(intern_id or 0) != own:
            raise HTTPException(status_code=403, detail="Interns can create only their own logs")
    values = {key: value for key, value in payload.items() if key in writable_columns("operations_dailyprogressentry")}
    for alias in ("intern_profile", "project", "task_type", "priority", "completion_status", "final_owner"):
        if alias in values:
            values[f"{alias}_id"] = values.pop(alias)
    normalize_daily_log_text(values)
    values["created_by_id"] = user["id"]; values["updated_by_id"] = user["id"]
    values.setdefault("log_date", date.today().isoformat()); values.setdefault("workflow_state", "DRAFT")
    percentage = int(values.get("completion_percentage", 0)); values["completion_status_id"] = completion_status_id(percentage)
    now = datetime.now().isoformat(sep=" ", timespec="seconds"); values["created_at"] = now; values["updated_at"] = now
    with engine.begin() as conn:
        new_id = insert_and_return_id(conn, "operations_dailyprogressentry", values)
    return get_daily_log(new_id, user)


@app.put("/api/daily-logs/{entry_id}/")
@app.patch("/api/daily-logs/{entry_id}/")
def update_daily_log(entry_id: int, payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not can_edit_entry(user, entry_id):
        raise HTTPException(status_code=403, detail="You are not allowed to edit this entry")
    allowed = writable_columns("operations_dailyprogressentry")
    values = {key: value for key, value in payload.items() if key in allowed}
    if user["role"] == "INTERN":
        # Interns report progress; they cannot change the mentor's assignment.
        editable_by_intern = {"actual_work", "completion_percentage", "time_spent_hours", "blocker_flag", "blocker_description", "support_needed", "deliverable_link", "remarks", "workflow_state"}
        values = {key: value for key, value in values.items() if key in editable_by_intern}
    for alias in ("intern_profile", "project", "task_type", "priority", "completion_status", "final_owner"):
        if alias in values:
            values[f"{alias}_id"] = values.pop(alias)
    normalize_daily_log_text(values)
    if "completion_percentage" in values:
        values["completion_status_id"] = completion_status_id(int(values["completion_percentage"]))
    values["updated_by_id"] = user["id"]; values["updated_at"] = datetime.now()
    assignments = ", ".join(f"{key}=:{key}" for key in values)
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE operations_dailyprogressentry SET {assignments} WHERE id=:id"), {**values, "id": entry_id})
        upsert_ai_usage(conn, entry_id, payload)
    return get_daily_log(entry_id, user)


@app.delete("/api/daily-logs/{entry_id}/", status_code=204)
def delete_daily_log(entry_id: int, user: dict[str, Any] = Depends(current_user)) -> Response:
    if not can_edit_entry(user, entry_id):
        raise HTTPException(status_code=403, detail="You are not allowed to delete this entry")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM operations_dailyprogressentry WHERE id=:id"), {"id": entry_id})
    return Response(status_code=204)


ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf", "text/plain", "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@app.post("/api/daily-logs/{entry_id}/attachments/", status_code=201)
async def upload_task_attachment(entry_id: int, file: UploadFile = File(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Store an intern's supporting document in ATP, linked to its task."""
    if not can_edit_entry(user, entry_id):
        raise HTTPException(status_code=403, detail="You are not allowed to attach a file to this task")
    content = await file.read()
    if not file.filename or file.content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF, DOC/DOCX, XLS/XLSX, and TXT files are allowed")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Attachment must be 5 MB or smaller")
    now = datetime.now()
    with engine.begin() as conn:
        attachment_id = insert_and_return_id(conn, "operations_taskattachment", {
            "entry_id": entry_id, "original_filename": Path(file.filename).name,
            "content_type": file.content_type, "content_size": len(content), "content_blob": content,
            "created_by_id": user["id"], "created_at": now, "updated_at": now,
        })
    return {"id": attachment_id, "filename": Path(file.filename).name, "content_type": file.content_type, "size": len(content)}


@app.get("/api/daily-logs/{entry_id}/attachments/")
def list_task_attachments(entry_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not can_edit_entry(user, entry_id):
        raise HTTPException(status_code=403, detail="You are not allowed to view task attachments")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, original_filename, content_type, content_size, created_at FROM operations_taskattachment WHERE entry_id=:entry_id ORDER BY id DESC"), {"entry_id": entry_id}).mappings().all()
    return {"results": [as_dict(row) for row in rows]}


@app.get("/api/attachments/{attachment_id}/download")
def download_task_attachment(attachment_id: int, user: dict[str, Any] = Depends(current_user)) -> StreamingResponse:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT a.*, e.id AS entry_id FROM operations_taskattachment a JOIN operations_dailyprogressentry e ON e.id=a.entry_id WHERE a.id=:id"), {"id": attachment_id}).mappings().first()
    if not row or not can_edit_entry(user, int(row["entry_id"])):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return StreamingResponse(io.BytesIO(row["content_blob"]), media_type=row["content_type"], headers={"Content-Disposition": f'attachment; filename="{row["original_filename"]}"'})


# Register the generic admin CRUD routes after the concrete daily-log routes.
# FastAPI uses declaration order for equally matching routes, so this prevents
# /api/daily-logs/{id}/ from being mistaken for a generic admin resource.
@app.post("/api/{resource}/", status_code=201)
def create_admin_resource(resource: str, payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    table = ADMIN_TABLES.get(resource)
    if not table:
        raise HTTPException(status_code=404, detail="Unknown resource")
    require_admin(user)
    return write_record(table, payload, user["id"])


@app.get("/api/{resource}/{record_id}/")
def get_admin_resource(resource: str, record_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    table = ADMIN_TABLES.get(resource)
    if not table:
        raise HTTPException(status_code=404, detail="Unknown resource")
    return record_by_id(table, record_id)


@app.put("/api/{resource}/{record_id}/")
@app.patch("/api/{resource}/{record_id}/")
def update_admin_resource(resource: str, record_id: int, payload: dict[str, Any], user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    table = ADMIN_TABLES.get(resource)
    if not table:
        raise HTTPException(status_code=404, detail="Unknown resource")
    require_admin(user)
    return write_record(table, payload, user["id"], record_id)


@app.delete("/api/{resource}/{record_id}/", status_code=204)
def delete_admin_resource(resource: str, record_id: int, user: dict[str, Any] = Depends(current_user)) -> Response:
    table = ADMIN_TABLES.get(resource)
    if not table:
        raise HTTPException(status_code=404, detail="Unknown resource")
    require_admin(user)
    with engine.begin() as conn:
        result = conn.execute(text(f"DELETE FROM {table} WHERE id=:id"), {"id": record_id})
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Record not found")
    return Response(status_code=204)


@app.get("/{page_path:path}", include_in_schema=False)
def frontend_page(page_path: str) -> Response:
    """Keep legacy page URLs reachable while React is the active frontend."""
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build.")
