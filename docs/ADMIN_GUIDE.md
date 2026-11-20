# Administrator guide

## First sign-in (once)
1. Open the academy: https://arnaudnelor.github.io/english-mastery-ai/
2. On the sign-in page, click **create the Super Administrator account**.
3. Enter the **setup code** you were given, your name, email and a password (10+ characters, letters and a number).
4. You arrive in the **Administrator portal**. The setup code stops working once this account exists.

Afterwards, sign in normally. Administrators are taken to the portal; **Learner view** (bottom left) shows the academy as a learner sees it.

## Switch on the AI professor (free)
Open **AI, email & status** and get a free key at https://aistudio.google.com/apikey. Paste it with "Google Gemini" selected, click **Save key**, then **Run live tests**. The key is encrypted on the server and is never shown to learners.

## Email (optional, free)
Without email, learners register and sign in immediately. When someone forgets their password, open their page in **Learners** and use **Create password-reset link**, then send them the link.

To send emails automatically:
1. Create a free Brevo account and confirm your sender address in Brevo.
2. Create an API key under Brevo › SMTP & API.
3. Paste it in **AI, email & status** with "Brevo" selected.
4. Tell the developer which sender address to set as `EMA_MAIL_FROM` (Render › Environment).

Email confirmation then becomes mandatory for new accounts (Platform settings › "Automatic").

## Daily work
- **Overview:** learner counts (total, active, inactive, new), lessons completed, hours, average performance, CEFR distribution, Business English enrolments, placement statistics, recent activity, and learners who need attention.
- **Learners:** search by name or email and filter by level or status. Each learner's page shows scores per skill, placement results, weaknesses, 12-week history, assessments, completed lessons and recent activity. It also has the account actions: activate, deactivate, suspend, confirm email, reset link and role.
- **Reports & exports:** learners, weekly and monthly usage, course completion, CEFR distribution and assessments. Filter by date, level, course or learner, and export to Excel, CSV or PDF. Each learner page also has an individual PDF report.
- **Lessons:** create lessons with exercises; edit, unpublish or hide built-in lessons, and restore the original at any time.
- **Levels & curriculum:** rename levels, edit their objectives, add or reorder units, and place lessons, readings, recordings, media, vocabulary sets, AI conversations and writing tasks. Lessons can only go into their own level, and each activity appears only once.
- **Audio & video:** upload files (25 MB maximum) or add YouTube links, with subtitles (.srt/.vtt), a transcript and comprehension questions. Then add them to a level as an "Audio / video" activity.
- **Placement test:** edit, add and remove questions, choose the reading and listening sections, and set the level threshold and the pass mark for level tests.
- **Administrators & roles:** invite administrators and choose what the Administrator role may do.
- **Platform settings:** registration open or closed, email confirmation, session length, lockout, the inactivity threshold and notifications.
- **Audit log:** who did what, and when.
- **Plans & expansion:** draft subscription plans (prices, trials, features, limits), revenue figures (they stay at zero until payments are activated) and the status of each future module.

## Backups
The database provider (Neon) keeps automatic restore points. **AI, email & status › Download a backup now** gives you a JSON copy of all records; password hashes and keys are excluded.
