# InternMate Phase 1 Review and Architecture Proposal

Date: 2026-04-21
Status: Draft for Approval (No code generated)

## 1. Requirements Review

### Product Goal
InternMate should function as an intern support workspace with operational visibility for mentors, managers, and HR. It must balance intern enablement with accountable execution and reporting.

### Core Capability Coverage
- Intern/project profile management
- Daily progress logging with task-level detail
- Responsible AI usage capture per task
- Review workflow with mentor feedback
- Rule-driven status automation and data validation
- Master-data driven dropdown configuration
- KPI dashboard and daily stats
- Search/filter/export for operational reports
- Role-based access control (RBAC)
- Auditability and extensible architecture

### Constraints/Direction Confirmed
- Backend: Django (Python)
- UI: HTML/CSS/Bootstrap/JS
- DB: SQLite first, portable to PostgreSQL/MySQL
- REST APIs required for key entities and dashboard data
- OCI GenAI Digital Guide Worker must be optional/pluggable

## 2. Gaps, Assumptions, and Risks

### Assumptions
- Each intern has one primary mentor and one manager at a time.
- Interns can log tasks across multiple projects in Phase 1.
- Manager has global visibility across all intern progress.
- Workflow transitions are rule-driven (not fully configurable in admin initially).
- AI prompt/query capture stores summary only, not raw sensitive prompts by default.
- Exports are generated on-demand, not scheduled in Phase 1.

### Gaps / Open Areas
- Review SLA expectations (example: mentor review within 24 hours).
- Data retention and archival policy for internship cycles.
- PDF format expectations (summary-only vs full detailed printable report).

### Risks
- KPI ambiguity may produce inconsistent metrics if logic is not approved first.
- AI contribution percentages may be self-reported and prone to inconsistency.
- Overly restrictive workflow can reduce intern usability.
- Export-to-PDF complexity can delay Phase 1 if rich formatting is required.
- Role overlap (Mentor vs Manager vs HR) can create permission edge cases.

## 3. Proposed Information Architecture

### Main Areas
- Dashboard
- Daily Logs
- Interns
- Projects
- Reviews
- Reports & Exports
- Master Data
- Administration

### Navigation Model
- Intern view: Dashboard, My Daily Logs, My Tasks, AI Usage Summary
- Mentor/Manager view: Team Dashboard, Review Queue, Blockers, Reports
- HR view: Portfolio Dashboard, Progress Reports, Export Center (summary-only visibility)
- Admin view: Full platform + master data + users/roles

## 4. Proposed Data Model (Schema Outline)

### Core Entities
- User (Django auth user; extended by profile/role mapping)
- Role (Admin, MentorManager, HR, Intern)
- Department
- SkillDomain
- Project
- InternProfile
- InternProjectAssignment
- DailyProgressEntry
- TaskDependency
- MentorReviewComment
- AIUsageRecord
- MasterDataList (generic list metadata)
- MasterDataItem (list items for dropdowns)
- AuditLog

### Key Table-Level Design
1. `intern_profile`
- id (PK)
- user_id (FK -> auth_user, unique)
- intern_code (unique)
- full_name
- email
- department_id (FK)
- mentor_user_id (FK -> auth_user)
- manager_user_id (FK -> auth_user)
- internship_start_date
- internship_end_date
- status (Active/Completed/On Hold)

2. `project`
- id
- project_code (unique)
- project_name
- department_id
- status
- description

3. `intern_project_assignment`
- id
- intern_profile_id
- project_id
- is_primary
- assigned_from
- assigned_to (nullable)

4. `daily_progress_entry`
- id
- log_date
- intern_profile_id
- project_id
- task_type_id (master data)
- task_name
- task_description
- priority_id (master data)
- planned_work
- actual_work
- completion_percentage (0-100)
- completion_status_id (master data, can be auto-derived)
- workflow_state_id (Draft/Submitted/Reviewed/Reopened/Closed)
- blocker_flag (bool)
- blocker_description
- support_needed
- time_spent_hours (decimal)
- expected_completion_date
- deliverable_link
- final_owner_id (master data: Independent, Joint)
- remarks
- on_time_completion_flag (bool, computed/store-on-save)
- created_by
- updated_by
- created_at
- updated_at

5. `task_dependency`
- id
- entry_id (FK -> daily_progress_entry)
- dependency_text
- dependency_status

6. `ai_usage_record`
- id
- entry_id (1:1 with daily_progress_entry)
- ai_tool_id (master data)
- ai_assistance_type_id (master data, allow multi-select via bridge table in Phase 2; single in Phase 1)
- ai_contribution_percentage (0-100)
- prompt_summary
- output_usage_id (master data)
- human_review_status_id (master data)
- accuracy_helpfulness_rating (1-5)
- estimated_time_saved_hours (decimal)
- used_ai_flag (bool)

7. `mentor_review_comment`
- id
- entry_id
- reviewer_user_id
- action (Submitted/Reviewed/Reopened/Closed/Comment)
- comment_text
- action_at

8. `audit_log`
- id
- entity_type
- entity_id
- action_type (create/update/delete/state_change/export/login)
- actor_user_id
- old_value_json
- new_value_json
- timestamp

## 5. Workflow Design

### Lifecycle States
- Draft -> Submitted -> Reviewed -> Closed
- Reopened is reachable from Reviewed/Closed and returns to Submitted after intern update

### Transition Rules
- Intern: can update workflow state on own entries across all states
- Mentor/Manager: can review and can always reopen tasks from any state
- Admin: can perform all transitions
- HR: read/report access only with summary-only visibility (no state mutation in Phase 1)

### Review Mechanics
- Mandatory mentor comment when marking Reopened
- Optional comment when Reviewed
- Close action requires completion_percentage = 100 (or explicit override permission for Admin)

## 6. Business Rules and Validation

### Completion Mapping (Auto)
- 0 -> Not Started
- 1-30 -> Initiated
- 31-70 -> In Progress
- 71-99 -> Near Completion
- 100 -> Completed

### Validation Rules
- completion_percentage in [0,100]
- time_spent_hours >= 0
- expected_completion_date cannot be before log_date unless override reason provided
- if blocker_flag = true, blocker_description is required
- if used_ai_flag = false, AI detail fields must be null/N/A compatible
- if used_ai_flag = true, ai_tool and assistance_type required
- deliverable_link must be valid URL when provided
- intern can modify only own entries unless Admin/Mentor role
- workflow transitions must follow allowed state matrix

### Derived Flags
- `is_overdue`: expected_completion_date < today AND completion_percentage < 100 (calendar-day logic for Phase 1)
- `is_on_time`: completion_percentage = 100 AND updated_at::date <= expected_completion_date
- `is_blocked`: blocker_flag = true

## 7. KPI Definitions (Pre-Implementation Logic)

All KPIs scoped by active filters (date range, intern, project, etc).

- Total Tasks = count(daily_progress_entry)
- Completed Tasks = count(entries where completion_percentage = 100)
- Blocked Tasks = count(entries where blocker_flag = true)
- On Hold Tasks = count(entries where blocker_flag = true OR there is unresolved dependency on others)
- Not Started Tasks = count(entries where completion_percentage = 0)
- Task Completion Rate = Completed Tasks / Total Tasks * 100
- Average Completion % = avg(completion_percentage)
- On-Time Completion % = count(completed & is_on_time=true) / Completed Tasks * 100
- AI-Assisted Task % = count(entries where used_ai_flag=true) / Total Tasks * 100
- Average AI Contribution % = avg(ai_contribution_percentage where used_ai_flag=true)
- Human Review Compliance % = count(ai_used entries with human_review_status in {Yes, Partial}) / count(ai_used entries) * 100
- Independent Task % = count(entries with final_owner = Independent) / Total Tasks * 100
- Joint Ownership % = count(entries with final_owner = Joint) / Total Tasks * 100
- Estimated Time Saved = sum(estimated_time_saved_hours where used_ai_flag=true)
- Daily Trend = per-day aggregates of total, completed, blocked, avg completion, time spent, time saved

## 8. API Design Outline (REST)

### Auth and Session
- POST `/api/auth/login`
- POST `/api/auth/logout`
- GET `/api/auth/me`

### Master Data
- GET `/api/master-data/{list_name}`
- POST `/api/master-data/{list_name}` (Admin)
- PUT `/api/master-data/items/{id}` (Admin)

### Interns and Projects
- GET `/api/interns`
- POST `/api/interns` (Admin)
- GET `/api/interns/{id}`
- GET `/api/projects`
- POST `/api/projects` (Admin)

### Daily Progress
- GET `/api/daily-logs`
- POST `/api/daily-logs`
- GET `/api/daily-logs/{id}`
- PUT `/api/daily-logs/{id}`
- POST `/api/daily-logs/{id}/submit`
- POST `/api/daily-logs/{id}/review`
- POST `/api/daily-logs/{id}/reopen`
- POST `/api/daily-logs/{id}/close`

### AI Assistive Guide (Pluggable)
- POST `/api/daily-logs/{id}/digital-guide/suggest`
- Service interface: `DigitalGuideService.generate_guidance(context)` with providers:
  - `MockDigitalGuideService` (default/local)
  - `OciGenAiDigitalGuideService` (optional)

### Dashboard & Reports
- GET `/api/dashboard/kpis`
- GET `/api/dashboard/daily-stats`
- GET `/api/reports/intern-summary`
- GET `/api/reports/project-summary`
- GET `/api/reports/export?format=csv|xlsx|pdf`

## 9. UI/UX Design Outline

### Common Application Layout
- Common responsive application shell across all screens
- **Header** with application name/logo, global search, notifications, user profile menu, and quick action buttons
- **Sidebar navigation menu** with role-based access and active page highlighting
- **Footer** with version, help/support, and internal use notice
- Breadcrumbs for inner pages
- Collapsible sidebar for tablet and mobile
- Mobile-friendly hamburger navigation for small screens

### Dashboard
- KPI summary cards row at top with quick visual indicators
- Sticky filter panel for date range, intern, project, department, and status
- Task status distribution chart
- AI usage insights chart
- Blocker / overdue spotlight widget
- Daily productivity trend chart
- Intern and project ranking tables
- Recent activity / latest updates section
- Upcoming deadlines and attention-needed widget
- Card-based responsive layout that stacks cleanly on tablet/mobile

### Daily Log Screen
- Quick-add log button prominently placed
- Searchable and filterable table with sorting, pagination, and export options
- Status chips, progress bars, and blocker indicators
- Row highlight for blocked, overdue, or review-pending entries
- Inline row actions by role such as submit, review, reopen, close, and comment
- On smaller screens, table should transform into responsive card/list view
- Sticky action bar for common actions and filters
- Empty state and loading state support

### Entry Form
- Sectioned form layout with clear grouping:
  - Task Details
  - Work Details
  - AI Usage
  - Dependencies / Blockers
  - Review / Remarks
- Guided hints, helper text, and tooltips for intern clarity
- Smart input controls such as dropdowns, date pickers, autocomplete, and text areas
- Inline validation with clear error messages
- Required fields clearly marked
- Sticky save, submit, and cancel actions
- Optional draft save support for partially completed entries
- Optional **Digital Guide Worker** panel for assistive suggestions only
- Digital Guide Worker should appear as a contextual side panel or collapsible helper area, not interrupting form flow

### Reusable UI Components
- Shared header, sidebar, and footer across all pages
- Reusable KPI cards, status badges, filter panels, data tables, modal dialogs, toast notifications, and confirmation popups
- Standardized page title and action header section
- Consistent spacing, typography, icons, and color usage throughout the application

### Responsive and Accessibility Standards
- Mobile-first responsive design
- Desktop, tablet, and mobile optimized layouts
- Keyboard-friendly navigation
- Accessible labels, contrast, and form interactions
- Do not rely only on color for status indication
- Use clean whitespace, modern cards, subtle borders, and professional enterprise styling

## 10. CRUD Flow Summary

1. Intern creates Draft daily log
2. System validates and auto-maps completion status
3. Intern submits entry
4. Mentor reviews and comments
5. Mentor marks Reviewed or Reopened
6. Intern updates and resubmits if reopened
7. Mentor/Admin closes when complete
8. Dashboard and reports refresh from filtered aggregates

## 11. Phased Implementation Roadmap

### Phase 0: Foundations
- Project scaffolding, env config, auth, role model, base layout
- Master data framework
- Audit logging utilities

### Phase 0 Test & UAT Gate
What I will verify:
- Django project boots reliably; migrations run clean on fresh DB
- Authentication works for seeded users; session/login/logout flow is stable
- Role mapping and baseline permission guards are enforced
- Master data CRUD works for Admin and is blocked for non-Admin
- Audit log entries are captured for create/update/delete events

What you should verify for UAT acceptance:
- Login experience is smooth for each role type
- Admin screens and master data setup feel understandable
- Naming and terminology match your business language
- Basic navigation/layout is acceptable for intern and mentor usage
- You approve baseline role visibility and access boundaries

### Phase 1: Core Logging + Workflow
- Intern/project management
- Daily progress CRUD + validations + workflow transitions
- Mentor review comments
- Basic dashboard KPIs (table/cards)

### Phase 1 Test & UAT Gate
What I will verify:
- Intern/project CRUD, assignment logic, and data integrity
- Daily log validations (required fields, percentage ranges, blocker rules)
- Workflow transitions respect role/state matrix
- Auto completion-status mapping works for all percentage bands
- Mentor review comments and reopen/close actions persist correctly
- KPI cards (total/completed/blocked/not started/avg %) match DB calculations

What you should verify for UAT acceptance:
- Daily logging flow is practical for interns in real usage
- Mentor review workflow reflects your operational process
- Blocker/support fields provide enough signal for follow-up
- KPI summaries align with your manual expectation on sample data
- Draft/submitted/reviewed/reopened/closed behavior is acceptable

### Phase 2: AI Usage + Digital Guide Integration Layer
- AI usage capture enhancements
- Pluggable guide service with mock provider
- OCI provider adapter interface (feature flag)

### Phase 2 Test & UAT Gate
What I will verify:
- AI usage fields validate correctly for AI-used vs non-AI tasks
- AI contribution/time-saved calculations aggregate correctly in KPIs
- Digital Guide mock provider returns structured guidance safely
- Feature flag cleanly enables/disables OCI adapter path
- Failure handling works when provider is unavailable (graceful fallback)

What you should verify for UAT acceptance:
- AI usage tracking is clear and not burdensome for interns
- Responsible AI fields satisfy your governance expectations
- Guide suggestions are assistive (not autonomous) and useful
- Reported AI metrics are meaningful for mentor/manager reviews
- You approve wording/disclaimers for AI guidance output

### Phase 3: Reporting + Exports + Charts
- Advanced filters
- CSV/XLSX/PDF exports
- Trend charts and intern/project summaries

### Phase 3 Test & UAT Gate
What I will verify:
- All filter combinations return correct scoped datasets
- Export parity: CSV/XLSX/PDF reflects currently filtered records
- Dashboard trend charts match underlying aggregates by date
- Intern-wise and project-wise summaries compute consistently
- Large-result exports handle pagination/timeout constraints safely

What you should verify for UAT acceptance:
- Reports answer operational questions for mentors/managers/HR
- Export formats are usable in your downstream review workflows
- Chart readability and labels are business-friendly
- Daily stats page reflects expected day-level numbers
- You approve report layouts/content for stakeholder sharing

### Phase 4: Hardening
- Permission refinements
- Performance optimization
- Postgres compatibility checks
- Test coverage and release readiness

### Phase 4 Test & UAT Gate
What I will verify:
- Full RBAC regression across all endpoints and UI actions
- Auditability and traceability checks for critical state changes
- Security basics (input validation, authorization checks, error handling)
- Performance sanity checks on list/dashboard/report endpoints
- DB portability validation (SQLite -> PostgreSQL compatibility)
- End-to-end regression suite passes for core intern-to-review flows

What you should verify for UAT acceptance:
- Platform is stable for day-to-day usage with realistic team data
- Role boundaries and visibility are acceptable to HR/management
- KPI/report outputs are trusted for decision-making
- No critical UX blockers remain for intern adoption
- You approve production-readiness for pilot rollout

## 11A. UAT Sign-Off Template (Per Phase)

Use this checklist at the end of each phase:
- Scope delivered matches agreed phase items
- Test evidence shared (key scenarios + outcomes)
- Known issues documented with severity and workaround
- No blocker/critical defects open for that phase scope
- Business owner sign-off captured (Approved / Approved with conditions / Rework)

## 12. Clarifications Needed Before Code Generation

1. None blocking. Phase 1 uses simple defaults:
- PDF export: minimal summary-first layout
- AI prompt handling: store prompt/query summary only (no raw prompt retention by default)
- Overdue logic: calendar-day based (no weekend/holiday exclusion)

## 12A. Confirmed Decisions

1. Workflow state: intern can update workflow state on own tasks.
2. Reopen authority: mentor or manager can always reopen tasks.
3. Final Owner values: `Independent` and `Joint` only.
4. Multi-project logging in Phase 1: allowed.
5. On Hold Tasks KPI: blocked tasks or tasks with unresolved dependencies on others.
6. AI assistance type in Phase 1: single-select.
7. Manager visibility: manager can view all interns' progress.
8. HR visibility: summaries only.
9. Overdue logic in Phase 1: calendar-day based.
10. PDF export in Phase 1: minimal summary-first format.
11. AI prompt compliance in Phase 1: summary-only capture, avoid raw prompt storage.

## 13. Future Enhancements (Post-Phase 1)

- Goal planning and weekly sprint view for interns
- Notification system (email/in-app) for blockers and pending reviews
- SLA tracking for mentor response time
- Skill progression analytics from task taxonomy
- Conversational assistant for search/reporting (RBAC-aware)
- MCP-compatible integration endpoints
- MCP auth hardening plan:
- Phase 2 (local/dev baseline): MCP server to InternMate API can use Basic Auth with dedicated service credentials.
- Later phase (production-ready): enforce stronger auth for client-to-MCP and MCP-to-API (token/OAuth/JWT-based), credential rotation, and audit expansion for MCP calls.

## 14. Approval Gate

No code has been generated.  
Please approve or adjust this design baseline. After approval, implementation can begin phase-by-phase.
