from datetime import date

from sqlalchemy import text

from backend.app.main import engine

with engine.begin() as conn:
    conn.execute(
        text("""UPDATE operations_dailyprogressentry
                 SET log_date=:log_date, expected_completion_date=:due_date
                 WHERE task_name LIKE 'Complete onboarding task %'"""),
        {"log_date": date(2026, 7, 1), "due_date": date(2026, 7, 8)},
    )
print("Demo task dates set to July 1, 2026.")
