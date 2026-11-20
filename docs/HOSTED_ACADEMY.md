# Hosted academy: architecture

The same code base runs in two modes:

| | Desktop app (`EMA_MODE=local`, default) | Online academy (`EMA_MODE=server`) |
|---|---|---|
| Users | one learner on one computer | many learners and administrators, each with an account |
| Database | SQLite file | PostgreSQL (Neon) |
| Front end | served by the backend or Electron | GitHub Pages (`VITE_HOSTED=1`), talking to the API over HTTPS |
| API keys | Windows Credential Manager | environment variables or **encrypted** in the database (admin portal) |

## Components
- **Web app**: React + TypeScript + Tailwind. It is built by GitHub Actions (`.github/workflows/pages.yml`) and published to GitHub Pages at the existing URL.
- **API**: FastAPI on a Render web service (`render.yaml`). Every push to `main` redeploys it automatically.
- **Database**: Neon Postgres (free plan: 1 GB, no expiry). Schema changes run automatically on start: new tables are created, and new columns are added by a forward-only migration in `app/db.py`.
- **Email**: Brevo (free, 300 emails a day) or SMTP. Until one is configured, emails are recorded in `email_outbox` as `not_configured`, and the admin portal offers manual alternatives.
- **AI**: Gemini, OpenAI or Anthropic, chosen in the admin portal. Keys never reach browsers.

## Security
- Passwords are hashed with scrypt (N=2^14, r=8, p=1, 16-byte salt) and must have at least 10 characters with letters and a digit.
- Sessions use opaque random bearer tokens; only a SHA-256 of each token is stored. They expire after 30 days by default (configurable) and can be revoked: sign out, sign out everywhere, changing the password, or an administrator suspending the account all revoke them.
- Email-verification and password-reset tokens are single-use and hashed. They expire after 48 h (verification), 2 h (self-service reset) and 72 h (administrator-issued reset).
- Rate limits apply to registration, login, verification, reset and setup, with a per-user API limit of 600 requests a minute. An account locks for 15 minutes after N failed sign-ins (configurable), and administrators are notified.
- Every `/api/*` call except the sign-in and recovery endpoints needs a valid session, enforced by middleware in `app/main.py`. `/api/admin/*`, API keys, backups and self-tests also need an administrator role. Each admin endpoint then checks a fine-grained permission (`app/deps.require`).
- **Data isolation:** every learner query is scoped to the signed-in user's profile (`deps.current_profile`). Records looked up by ID are checked for ownership. Tests prove that learner B can't read learner A's conversation or mistakes.
- Responses include `X-Content-Type-Options`, `X-Frame-Options: DENY` and `Referrer-Policy`, and API responses add `Cache-Control: no-store`. The front end sets a Content-Security-Policy restricted to its own origin and the API origin.
- Spreadsheet exports neutralise formula injection. Uploads are limited by type and size (25 MB), and PDFs are checked by signature.
- An audit log records sign-ins, lockouts, every administrator action, exports, key changes and backups.
- Privacy (PIPEDA / Québec Law 25): the privacy notice requires consent at registration. Learners can download a PDF report and a full JSON export, and can delete their account themselves.

## Roles and permissions
Tables: `roles`, `permissions`, `role_permissions`. The super administrator always holds every permission. The administrator's permissions are editable in the portal. The teacher role exists but is inactive. Learners hold no administrative permission. Permission codes are listed in `app/services/platform.py`.

## Data model (main tables)
- **Accounts:** `users`, `roles`, `permissions`, `role_permissions`, `auth_sessions`, `account_tokens`, `audit_logs`, `notifications`, `email_outbox`.
- **Learning:** `profiles` (one per user), `activity_log`, `lesson_progress`, `study_time`, `assessment_results`, `mistakes`, `vocab_cards`, `conversations`/`messages`, `exam_attempts`, `bookmarks`, `video_items`.
- **Content management:** `content_lessons` holds admin-created lessons, and edits or unpublishing of built-in ones. `content_documents` holds edited copies of the curriculum and placement test. `media_assets` holds audio, video and PDF files, with subtitles and questions.
- **Configuration:** `platform_settings`, `platform_secrets` (Fernet-encrypted with a key derived from `EMA_SECRET_KEY`).
- **Expansion foundations:**
  - `organizations`, `teacher_profiles`, `courses`, `classes`, `teacher_assignments`, `learner_groups`, `group_courses`, `enrolments`, `assignments`, `class_sessions`, `attendance`
  - `subscription_plans`, `subscriptions` (belonging to a user or an organisation), `payments`, `invoices`
  - `users.organization_id` makes organisation-level isolation possible.

## Progress saving
Every answer, review, writing submission, conversation turn and test is written to the database when it happens. `lesson_progress` is updated after each activity, and `study_time` comes from heartbeats sent while the tab is visible. The web app shows *Saving… / Saved successfully / Unable to save — retrying*.

Writes that are safe to repeat (answers, reviews, visits, heartbeats, profile changes) are retried with backoff. If the server can't be reached, they are kept in the browser and sent when the connection returns. Progress belongs to the account, so it is restored on any device.

## API versioning
Every endpoint is available as `/api/...` and as the stable alias `/api/v1/...`. Future breaking changes will use `/api/v2`.

## Environment variables (Render)
| Variable | Purpose |
|---|---|
| `EMA_MODE=server` | enables accounts, the admin portal and server guards |
| `EMA_DATABASE_URL` | Neon connection string |
| `EMA_SECRET_KEY` | generated by Render; encrypts stored API keys (do not change it once keys are saved) |
| `EMA_ADMIN_SETUP_CODE` | one-time code that creates the first Super Administrator |
| `EMA_CORS_ORIGINS` | `https://arnaudnelor.github.io` |
| `EMA_PUBLIC_APP_URL` | `https://arnaudnelor.github.io/english-mastery-ai/` (used in email links) |
| `EMA_MAIL_FROM`, `EMA_MAIL_FROM_NAME` | sender address for Brevo/SMTP (optional) |
| `GEMINI_API_KEY`, `OPENAI_API_KEY`, `BREVO_API_KEY`… | optional; keys can also be saved in the admin portal |

## Tests
- `backend/tests/test_server.py`: 15 end-to-end API scenarios covering accounts, isolation, lockout, verification and reset, admin monitoring, reports in three formats, content management, placement configuration, media, settings and secrets, roles, backups, privacy, and the expansion relationships. They run on SQLite and on PostgreSQL (`EMA_TEST_PG=...`).
- `.github/workflows/tests.yml` runs the whole suite on every push, on both databases.
