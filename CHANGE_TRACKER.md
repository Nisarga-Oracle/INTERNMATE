# InternMate Change Tracker

Use this file to log meaningful project changes over time.

## Format

Date: YYYY-MM-DD
Type: Added | Changed | Fixed | Removed | Docs | Chore
Summary: One-line description
Files: file/path1, file/path2
Details:
- What changed
- Why it changed

---

## Entries

Date: 2026-04-21
Type: Chore
Summary: Initialized project repository and added change tracker
Files: CHANGE_TRACKER.md
Details:
- Initialized Git repository for InternMate
- Added a reusable template for tracking future updates

Date: 2026-04-21
Type: Docs
Summary: Added Phase 1 review and architecture proposal for InternMate
Files: mock_design/phase1_review_and_architecture.md, CHANGE_TRACKER.md
Details:
- Documented requirements review, assumptions, risks, architecture, schema, workflows, APIs, KPI logic, and phased roadmap
- Captured open clarification questions and explicit approval gate before code generation

Date: 2026-04-21
Type: Docs
Summary: Added test and UAT acceptance gates after each implementation phase
Files: mock_design/phase1_review_and_architecture.md, CHANGE_TRACKER.md
Details:
- Added phase-wise verification responsibilities (engineering checks and business UAT checks)
- Added reusable UAT sign-off template for each phase completion gate

Date: 2026-04-21
Type: Docs
Summary: Updated workflow and final owner decisions in architecture baseline
Files: mock_design/phase1_review_and_architecture.md, CHANGE_TRACKER.md
Details:
- Captured confirmed workflow behavior that intern can update workflow state and mentor/manager can always reopen
- Locked Final Owner values to Independent and Joint and adjusted pending clarification list

Date: 2026-04-21
Type: Docs
Summary: Captured additional scope clarifications and reduced pre-build blockers
Files: mock_design/phase1_review_and_architecture.md, CHANGE_TRACKER.md
Details:
- Updated baseline for multi-project Phase 1 support, On Hold KPI logic, manager global visibility, HR summary-only access, and single-select AI assistance type
- Trimmed open clarifications to PDF expectations, AI prompt compliance policy, and overdue logic decision

Date: 2026-04-21
Type: Docs
Summary: Locked simple Phase 1 defaults for overdue, PDF export, and AI prompt handling
Files: mock_design/phase1_review_and_architecture.md, CHANGE_TRACKER.md
Details:
- Set overdue logic to calendar-day based for Phase 1
- Set PDF export to minimal summary-first format for Phase 1
- Set AI prompt handling to summary-only capture without raw prompt retention by default

Date: 2026-04-21
Type: Docs
Summary: Added multi-page HTML mockup set for UI approval before build
Files: mock_design/mockup_html_design_v1, CHANGE_TRACKER.md
Details:
- Created static page mockups for dashboard, logs, forms, review queue, reports, master data, and HR summary view
- Added shared styles and navigation shell to validate full design and layout flow prior to implementation

Date: 2026-04-23
Type: Added
Summary: Built Django Phase 0/1 baseline application with RBAC-aware models, APIs, pages, and exports
Files: internmate/*, accounts/*, operations/*, reporting/*, templates/*, requirements.txt, README.md, CHANGE_TRACKER.md
Details:
- Implemented Django + DRF project scaffold with SQLite, authentication routes, role profiles, and core domain models
- Added daily log workflow, AI usage tracking, review comments, audit logging, dashboard/daily stats/reports pages, and CSV/XLSX/PDF exports
- Added seed command for local test users/master data and validated setup with migrations, seed run, and Django checks

Date: 2026-04-23
Type: Changed
Summary: Upgraded common layout UX, added modern landing/login experience, and expanded mock backend data
Files: templates/base.html, templates/accounts/*, static/app.css, accounts/*, internmate/urls.py, operations/management/commands/seed_baseline.py, operations/signals.py, README.md, CHANGE_TRACKER.md
Details:
- Introduced shared responsive header/menu/footer across application pages using a common base template and global stylesheet
- Added modern InternMate landing and login pages with banner content, platform value messaging, and role test credential guidance
- Expanded seed data to include realistic daily logs, blockers/dependencies, AI usage records, and mentor review comments for verification

Date: 2026-04-23
Type: Fixed
Summary: Resolved root URL redirect loop by moving dashboard route off root path
Files: operations/urls.py, CHANGE_TRACKER.md
Details:
- Changed dashboard route from `/` to `/dashboard/` to avoid collision with landing route at root
- Verified landing and login pages return 200 and dashboard correctly redirects to login when unauthenticated

Date: 2026-04-23
Type: Changed
Summary: Upgraded application UX with modern visual system and refreshed page layouts
Files: static/app.css, templates/base.html, templates/operations/*, templates/reporting/reports.html, CHANGE_TRACKER.md
Details:
- Introduced modern typography, richer color system, sticky header polish, gradient KPI cards, pill badges, and improved table surfaces
- Refreshed Dashboard, Daily Logs, Daily Stats, and Reports templates with cleaner hierarchy and better responsive behavior
- Preserved existing backend behavior while improving readability and usability across desktop and mobile

Date: 2026-04-23
Type: Changed
Summary: Applied Oracle Redwood-inspired visual refinement across shared application shell and pages
Files: static/app.css, templates/base.html, templates/operations/*, templates/reporting/reports.html, CHANGE_TRACKER.md
Details:
- Aligned UI tone with Redwood-inspired enterprise style using cleaner neutrals, subtle elevation, compact chips, structured table surfaces, and calmer gradients
- Improved responsive navigation and page headers to create consistent cross-page hierarchy
- Kept existing functionality intact while updating component aesthetics for a more polished enterprise UX

Date: 2026-04-23
Type: Changed
Summary: Added 50-record mock dataset and server-side pagination for table views
Files: operations/management/commands/seed_baseline.py, operations/views.py, reporting/views.py, templates/operations/daily_logs.html, templates/operations/daily_stats.html, templates/reporting/reports.html, CHANGE_TRACKER.md
Details:
- Updated seed command to generate 50 deterministic seeded daily log records with AI usage, blockers, dependencies, and mentor comments
- Added Django paginator support to Daily Logs, Daily Stats, and Reports views
- Added page navigation controls (Previous/Next + page indicator) to corresponding table templates

Date: 2026-04-23
Type: Changed
Summary: Added column filter controls to all data tables with filter-aware pagination
Files: operations/views.py, reporting/views.py, templates/operations/dashboard.html, templates/operations/daily_logs.html, templates/operations/daily_stats.html, templates/reporting/reports.html, CHANGE_TRACKER.md
Details:
- Added GET-based table filters for intern, project, workflow, blocked state, and date range across dashboard/logs/stats/reports
- Wired backend queryset filtering for each table view and preserved filters across paginated pages
- Added reset actions per table to quickly clear filter state

Date: 2026-04-23
Type: Added
Summary: Added UI task logging page and dedicated task details page
Files: operations/forms.py, operations/views.py, operations/urls.py, templates/operations/daily_log_form.html, templates/operations/daily_log_detail.html, templates/operations/daily_logs.html, templates/operations/dashboard.html, templates/base.html, CHANGE_TRACKER.md
Details:
- Added role-allowed daily task logging UI (Intern/Mentor/Manager/Admin) with task, workflow, blocker, dependency, and AI usage capture sections
- Added full task details page with work summary, dependency/blocker section, AI usage details, and review timeline
- Linked task rows to details view and added quick `+ Log Task` action from daily logs page

Date: 2026-04-23
Type: Changed
Summary: Added global `+ Log Task` action visibility for Manager and Mentor (and other task-logging roles)
Files: templates/base.html, CHANGE_TRACKER.md
Details:
- Added header-level quick action button to open the task logging form from any page
- Kept HR excluded from task creation entry points per summary/reporting-focused role behavior

Date: 2026-04-23
Type: Changed
Summary: Added task edit workflow with strict role-based edit permissions and JIRA-style intern update logs
Files: operations/views.py, operations/forms.py, operations/urls.py, operations/signals.py, templates/operations/daily_logs.html, templates/operations/daily_log_form.html, templates/operations/daily_log_detail.html, CHANGE_TRACKER.md
Details:
- Added editable task form and update route; edit is allowed only for admin, manager, task owner, and assigned intern
- Added structured change logging on task updates with field-level deltas and optional update notes, highlighted for intern updates
- Added task detail actions and change-log display panel to review update history similarly to ticket activity trails

Date: 2026-04-23
Type: Docs
Summary: Added timeline tracking workbook for prompts, design, and build progress
Files: TimelinesPromptTracking/timeline_tracking.xlsx, CHANGE_TRACKER.md
Details:
- Created Excel timeline with milestone chronology, summary metrics, and phase tracker view
- Captured prompts/design/build events from repository change history for audit and review

Date: 2026-04-23
Type: Docs
Summary: Expanded timeline workbook with detailed suggestion/input agreements, phase feature catalog, and effort tracking
Files: TimelinesPromptTracking/timeline_tracking.xlsx, CHANGE_TRACKER.md
Details:
- Added comprehensive traceability of user suggestions, assistant clarification asks, and final design agreements
- Added detailed feature list by phase with scope/status and implementation artifacts
- Added per-capability effort timeline with estimated duration windows and completion notes

Date: 2026-04-23
Type: Changed
Summary: Phase 1 closure pass completed for task page routing, edit governance, and regression tests
Files: operations/urls.py, operations/views.py, operations/forms.py, operations/tests.py, templates/base.html, templates/operations/dashboard.html, templates/operations/daily_logs.html, templates/operations/daily_log_form.html, templates/operations/daily_log_detail.html, mock_design/phase1_closure_report.md, CHANGE_TRACKER.md
Details:
- Resolved task details route-name conflict with DRF so task links always open HTML details pages
- Enforced edit access policy (admin/manager/owner/assigned intern) and retained JIRA-style update logs for intern edits
- Added and passed operations test suite for key Phase 1 behaviors and produced closure report with validation evidence

Date: 2026-04-23
Type: Docs
Summary: Added structured Excel unit-test proof report with traceability and signoff sheet
Files: TimelinesPromptTracking/unit_test_proof_report_2026-04-23.xlsx, TimelinesPromptTracking/phase1_test_results_2026-04-23.txt, CHANGE_TRACKER.md
Details:
- Generated test-proof workbook with execution summary, detailed test-case evidence, requirement traceability, and signoff section
- Linked all records to captured command output log for audit verification

Date: 2026-04-23
Type: Docs
Summary: Prepared Oracle hackathon submission PPT for InterMate Digital Worker using official template format
Files: TimelinesPromptTracking/InterMate_Digital_Worker_Submission_FY26_v1.pptx, CHANGE_TRACKER.md
Details:
- Populated required template slides with concise messaging from architecture/design decisions and implemented application features
- Included problem statement, digital worker flow, architecture, role usage model, responsible AI controls, and demo summary with Codex + MCP positioning

Date: 2026-04-24
Type: Docs
Summary: Executed API-to-UI verification run and captured structured evidence report
Files: TimelinesPromptTracking/api_ui_verification_report_2026-04-24.json, CHANGE_TRACKER.md
Details:
- Tested API read endpoints and key write flows (department, project, daily log, workflow action, AI usage) using authenticated admin context
- Verified API-created task visibility in UI list and task detail pages for manager role

Date: 2026-04-24
Type: Docs
Summary: Completed role-based API verification for Intern and Mentor using GET and PUT with Nisarga test scenario
Files: TimelinesPromptTracking/role_api_verification_intern_nisarga_2026-04-24.json, TimelinesPromptTracking/role_api_verification_intern_nisarga_2026-04-24.xlsx, CHANGE_TRACKER.md
Details:
- Ensured test data context for intern Nisarga Angadi under mentor Gaurav Mahna on project AIDOC with task TDD Diagram updation
- Validated GET list/detail and PUT update on /api/daily-logs/ for both INTERN and MENTOR roles with passing status codes
- Captured structured machine-readable JSON and Excel evidence for UAT verification without deleting any records

Date: 2026-04-24
Type: Added
Summary: Introduced HTTP MCP server integration for Codex CLI with InternMate-prefixed tools
Files: mcp_server/server.py, mcp_server/internmate_client.py, mcp_server/README.md, internmate/settings.py, requirements.txt, README.md, CHANGE_TRACKER.md
Details:
- Added MCP server module exposing `InternMate_get_daily_logs`, `InternMate_get_task`, `InternMate_update_task`, `InternMate_list_interns`, and `InternMate_list_projects`
- Implemented API client bridge from MCP tools to existing Django REST endpoints with Basic Auth and structured error responses
- Enabled DRF BasicAuthentication for local MCP-to-API access and documented Codex CLI HTTP transport setup
- Kept destructive operations out of MCP v1 (no delete tool)

Date: 2026-04-24
Type: Changed
Summary: Refreshed `/accounts/` landing page branding and digital workflow section with leadership terminology and improved layout
Files: templates/accounts/landing.html, static/app.css, CHANGE_TRACKER.md
Details:
- Updated hero branding to `Digital Worker - InternMate` and refreshed platform highlights wording
- Replaced the digital worker section with a near 1:1 styled adaptation of `mock_design/internmate_digital_worker_flow_static_html.html`
- Replaced `HR` terminology with `Leadership` across landing-page messaging and role cards
- Increased Codex strip action-label text size for readability and tuned outcomes panel height/spacing to use available vertical space
- Updated top action button labels to `Login` and `Admin Login` as requested

Date: 2026-04-24
Type: Added
Summary: Added CODEX CLI setup guide page and linked it in landing and main navigation
Files: accounts/views.py, accounts/urls.py, templates/accounts/codex_cli_guide.html, templates/accounts/landing.html, templates/base.html, CHANGE_TRACKER.md
Details:
- Added new page `How to Guide for CODEX CLI Setup` at `/accounts/codex-cli-guide/`
- Added guide link on `/accounts/` landing page
- Added `CODEX CLI Guide` item in authenticated top navigation menu
- Kept guide-page actions focused to `Back to Accounts` and `Login` as requested
