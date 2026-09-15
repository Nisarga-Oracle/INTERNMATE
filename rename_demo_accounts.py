"""Rename the existing ATP demo accounts to human-friendly login names."""
from sqlalchemy import text
from backend.app.main import engine

RENAMES = {
    "demo_mentor_ava": ("arjun", "Arjun", "Rao"), "demo_mentor_arjun": ("krishna", "Krishna", "Mehta"),
    "demo_intern_01": ("ananya", "Ananya", "Shah"), "demo_intern_02": ("vikram", "Vikram", "Nair"), "demo_intern_03": ("priya", "Priya", "Iyer"),
    "demo_intern_04": ("rohan", "Rohan", "Kapoor"), "demo_intern_05": ("sneha", "Sneha", "Reddy"), "demo_intern_06": ("kunal", "Kunal", "Joshi"),
    "demo_intern_07": ("meera", "Meera", "Das"), "demo_intern_08": ("aditya", "Aditya", "Sinha"), "demo_intern_09": ("kavya", "Kavya", "Menon"),
    "demo_intern_10": ("ishaan", "Ishaan", "Verma"),
}

with engine.begin() as conn:
    for old, (new, first, last) in RENAMES.items():
        current = conn.execute(text("SELECT id FROM auth_user WHERE username=:old"), {"old": old}).scalar()
        occupied = conn.execute(text("SELECT id FROM auth_user WHERE username=:new"), {"new": new}).scalar()
        if current and occupied:
            raise RuntimeError(f"Cannot rename {old}: username {new} is already in use")
        if current:
            conn.execute(text("UPDATE auth_user SET username=:new, first_name=:first, last_name=:last, email=:email WHERE id=:id"), {"new": new, "first": first, "last": last, "email": f"{new}@internmate.demo", "id": current})
    conn.execute(text("UPDATE auth_user SET first_name='Arjun', last_name='Rao' WHERE username='arjun'"))
    conn.execute(text("UPDATE auth_user SET first_name='Krishna', last_name='Mehta' WHERE username='krishna'"))
print("Demo account names renamed successfully.")
