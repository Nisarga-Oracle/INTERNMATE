-- InternMate demo workspace for Oracle ATP / Database Actions.
-- Safe to run more than once. Existing demo records are reused, not duplicated.
-- Prerequisite: run add_mentor_project_assignment.sql once if that table does not exist.
-- Existing admin account is used. Demo mentor and intern password: Demo@1234

DECLARE
  v_dept_id       NUMBER;
  v_project_a     NUMBER;
  v_project_b     NUMBER;
  v_mentor_a      NUMBER;
  v_mentor_b      NUMBER;
  v_intern_user   NUMBER;
  v_intern_id     NUMBER;
  v_priority_id   NUMBER;
  v_task_type_id  NUMBER;
  v_owner_id      NUMBER;
  v_status_id     NUMBER;
  v_now           TIMESTAMP := SYSTIMESTAMP;
  -- Django PBKDF2 hash for the password Demo@1234.
  v_password      VARCHAR2(255) := 'pbkdf2_sha256$1200000$HObmQND6Ru8LsHfJ76wJ_A$CDM56OcQzHQsS6WR+mIrXOxujMFQ2laBSUFsudR6wvE=';

  PROCEDURE ensure_user(p_username VARCHAR2, p_first VARCHAR2, p_last VARCHAR2, p_role VARCHAR2, p_user_id OUT NUMBER) IS
  BEGIN
    BEGIN
      SELECT id INTO p_user_id FROM internmate.auth_user WHERE username = p_username;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      INSERT INTO internmate.auth_user
        (password, last_login, is_superuser, username, last_name, email, is_staff, is_active, date_joined, first_name)
      VALUES
        (v_password, NULL, 0, p_username, p_last, p_username || '@internmate.demo', 0, 1, v_now, p_first)
      RETURNING id INTO p_user_id;
      INSERT INTO internmate.accounts_userprofile (role, user_id) VALUES (p_role, p_user_id);
    END;
  END;

  PROCEDURE ensure_project(p_code VARCHAR2, p_name VARCHAR2, p_project_id OUT NUMBER) IS
  BEGIN
    BEGIN
      SELECT id INTO p_project_id FROM internmate.operations_project WHERE project_code = p_code;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      INSERT INTO internmate.operations_project
        (created_at, updated_at, project_code, project_name, status, description, department_id)
      VALUES
        (v_now, v_now, p_code, p_name, 'ACTIVE', 'Demo project for InternMate role testing.', v_dept_id)
      RETURNING id INTO p_project_id;
    END;
  END;

  PROCEDURE ensure_intern(p_number NUMBER, p_username VARCHAR2, p_first VARCHAR2, p_last VARCHAR2, p_mentor_id NUMBER, p_project_id NUMBER) IS
    v_code VARCHAR2(40) := 'DEMO-' || LPAD(p_number, 3, '0');
    v_task_exists NUMBER;
  BEGIN
    ensure_user(p_username, p_first, p_last, 'INTERN', v_intern_user);
    BEGIN
      SELECT id INTO v_intern_id FROM internmate.operations_internprofile WHERE user_id = v_intern_user;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      INSERT INTO internmate.operations_internprofile
        (created_at, updated_at, intern_code, internship_start_date, internship_end_date, status, department_id, manager_id, mentor_id, user_id)
      VALUES
        (v_now, v_now, v_code, TRUNC(SYSDATE), ADD_MONTHS(TRUNC(SYSDATE), 12), 'ACTIVE', v_dept_id, p_mentor_id, p_mentor_id, v_intern_user)
      RETURNING id INTO v_intern_id;
    END;
    MERGE INTO internmate.operations_internprojectassignment target
    USING (SELECT v_intern_id intern_profile_id, p_project_id project_id FROM dual) source
    ON (target.intern_profile_id = source.intern_profile_id AND target.project_id = source.project_id)
    WHEN NOT MATCHED THEN INSERT (created_at, updated_at, is_primary, assigned_from, assigned_to, intern_profile_id, project_id)
      VALUES (v_now, v_now, 1, TRUNC(SYSDATE), NULL, source.intern_profile_id, source.project_id);
    SELECT COUNT(*) INTO v_task_exists FROM internmate.operations_dailyprogressentry WHERE intern_profile_id = v_intern_id AND task_name = 'Complete onboarding task ' || p_number;
    IF v_task_exists = 0 THEN
      INSERT INTO internmate.operations_dailyprogressentry
        (created_at, updated_at, log_date, task_name, task_description, planned_work, actual_work, completion_percentage, workflow_state,
         blocker_flag, blocker_description, support_needed, time_spent_hours, expected_completion_date, deliverable_link, remarks,
         on_time_completion_flag, created_by_id, updated_by_id, intern_profile_id, completion_status_id, final_owner_id, priority_id, task_type_id, project_id)
      VALUES
        (v_now, v_now, TRUNC(SYSDATE), 'Complete onboarding task ' || p_number,
         'Review the assigned project and document your first update.', 'Review requirements and prepare a concise status update.',
         'Not started', 0, 'DRAFT', 0, ' ', ' ', 0, TRUNC(SYSDATE) + 7, ' ', 'Demo task assigned by mentor', 0,
         p_mentor_id, p_mentor_id, v_intern_id, v_status_id, v_owner_id, v_priority_id, v_task_type_id, p_project_id);
    END IF;
  END;
BEGIN
  BEGIN
    SELECT id INTO v_dept_id FROM internmate.operations_department WHERE name = 'InternMate Demo';
  EXCEPTION WHEN NO_DATA_FOUND THEN
    INSERT INTO internmate.operations_department (created_at, updated_at, name) VALUES (v_now, v_now, 'InternMate Demo') RETURNING id INTO v_dept_id;
  END;

  ensure_project('DEMO-PORTAL', 'Intern Portal Refresh', v_project_a);
  ensure_project('DEMO-ANALYTICS', 'Progress Analytics', v_project_b);
  ensure_user('arjun', 'Arjun', 'Rao', 'MENTOR', v_mentor_a);
  ensure_user('krishna', 'Krishna', 'Mehta', 'MENTOR', v_mentor_b);

  MERGE INTO internmate.operations_mentorprojectassignment target
  USING (SELECT v_mentor_a mentor_id, v_project_a project_id FROM dual) source
  ON (target.mentor_id = source.mentor_id AND target.project_id = source.project_id)
  WHEN NOT MATCHED THEN INSERT (created_at, updated_at, mentor_id, project_id) VALUES (v_now, v_now, source.mentor_id, source.project_id);
  MERGE INTO internmate.operations_mentorprojectassignment target
  USING (SELECT v_mentor_b mentor_id, v_project_b project_id FROM dual) source
  ON (target.mentor_id = source.mentor_id AND target.project_id = source.project_id)
  WHEN NOT MATCHED THEN INSERT (created_at, updated_at, mentor_id, project_id) VALUES (v_now, v_now, source.mentor_id, source.project_id);

  SELECT i.id INTO v_priority_id FROM internmate.operations_masterdataitem i JOIN internmate.operations_masterdatalist l ON l.id=i.list_ref_id WHERE l.name='Priority' AND i.value='Medium';
  SELECT i.id INTO v_task_type_id FROM internmate.operations_masterdataitem i JOIN internmate.operations_masterdatalist l ON l.id=i.list_ref_id WHERE l.name='Task Type' AND i.value='Documentation';
  SELECT i.id INTO v_owner_id FROM internmate.operations_masterdataitem i JOIN internmate.operations_masterdatalist l ON l.id=i.list_ref_id WHERE l.name='Final Owner' AND i.value='Independent';
  SELECT i.id INTO v_status_id FROM internmate.operations_masterdataitem i JOIN internmate.operations_masterdatalist l ON l.id=i.list_ref_id WHERE l.name='Completion Status' AND i.value='Not Started';

  ensure_intern(1,  'ananya', 'Ananya', 'Shah',   v_mentor_a, v_project_a);
  ensure_intern(2,  'vikram', 'Vikram', 'Nair',   v_mentor_b, v_project_b);
  ensure_intern(3,  'priya', 'Priya', 'Iyer',    v_mentor_a, v_project_a);
  ensure_intern(4,  'rohan', 'Rohan', 'Kapoor',  v_mentor_b, v_project_b);
  ensure_intern(5,  'sneha', 'Sneha', 'Reddy',   v_mentor_a, v_project_a);
  ensure_intern(6,  'kunal', 'Kunal', 'Joshi',   v_mentor_b, v_project_b);
  ensure_intern(7,  'meera', 'Meera', 'Das',     v_mentor_a, v_project_a);
  ensure_intern(8,  'aditya', 'Aditya', 'Sinha',  v_mentor_b, v_project_b);
  ensure_intern(9,  'kavya', 'Kavya', 'Menon',   v_mentor_a, v_project_a);
  ensure_intern(10, 'ishaan', 'Ishaan', 'Verma',  v_mentor_b, v_project_b);
  COMMIT;
END;
/

SELECT p.role, u.username, u.first_name, u.last_name
FROM internmate.auth_user u JOIN internmate.accounts_userprofile p ON p.user_id=u.id
WHERE u.username LIKE 'demo_%' OR p.role='ADMIN'
ORDER BY p.role, u.username;

SELECT p.project_code, p.project_name, m.username AS mentor, COUNT(i.id) AS intern_count, COUNT(t.id) AS starter_task_count
FROM internmate.operations_project p
LEFT JOIN internmate.operations_mentorprojectassignment ma ON ma.project_id=p.id
LEFT JOIN internmate.auth_user m ON m.id=ma.mentor_id
LEFT JOIN internmate.operations_internprojectassignment ia ON ia.project_id=p.id
LEFT JOIN internmate.operations_internprofile i ON i.id=ia.intern_profile_id
LEFT JOIN internmate.operations_dailyprogressentry t ON t.intern_profile_id=i.id
WHERE p.project_code LIKE 'DEMO-%'
GROUP BY p.project_code, p.project_name, m.username
ORDER BY p.project_code;
