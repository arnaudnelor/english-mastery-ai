# Roadmap

Status key: ✅ done · ⬜ planned

| Phase | Scope | Status |
|---|---|---|
| 1 | Architecture, requirements, interface design, technical foundation | ✅ |
| 2 | Desktop shell, database (with automatic migrations), dashboard, profile, settings, backup, logging, tests | ✅ |
| 3 | Grammar (20 topics, B2–C2, 88 exercises), Vocabulary (70 entries, SM-2 spaced repetition), Reading (8 texts), Writing tutor (9 genres) | ✅ |
| 4 | Listening Lab (6 recordings, 3 accents); Pronunciation Lab (sounds, minimal pairs, stress, shadowing, Whisper clarity check, Azure phoneme scoring) | ✅ |
| 5 | AI conversation: 19 modes, 4 personas, 3 accents, 4 correction modes, push-to-talk **and hands-free with barge-in**, session reports | ✅ |
| 6 | Video Academy: animated scenes; your own videos and YouTube embeds with synced subtitles, sentence replay, AI study packs | ✅ |
| 7 | IELTS Academic full mock (4 skills, timed, band estimates); Business, Finance & Academic track (7 specialisations) | ✅ |
| 8 | Placement test, learning path, weekly checks, analytics, history, search, bookmarks, reminders | ✅ |
| 9 | Windows scripts (start/stop/restart/LAN/firewall/auto-start/reminder), installer build, documentation, end-to-end browser tests | ✅ |

| 1.1 | TOEFL iBT 2026-format and Cambridge C1/C2 practice papers; exam-only IELTS passages and recordings; live setup check (AI model, correction engine, voice, Whisper, Azure, microphone); 24 grammar topics, 100 words, 11 texts, 9 recordings; browser preview | ✅ |

| 2.0 | Six CEFR levels with their own dashboards, units and level tests; Business English Academy (18 categories); A1–C2 placement test with sentence construction | ✅ |
| 2.1 | **Online academy**: registration, sign-in, sessions, email verification and recovery, roles and permissions, administrator portal (monitoring, reports, content, placement, settings, audit), automatic progress saving across devices, Postgres hosting | ✅ |

## Feature status in 2.1
| Module | Status |
|---|---|
| Learner academy, AI professor, placement, Business Academy, admin portal | **Operational** |
| Subscription plans (configurable in the portal) | **Configured, not activated** (nothing is sold or charged) |
| Online payments (Stripe / PayPal) | **Configured, not activated** (needs your provider account; keys can already be stored) |
| Teacher portal, classes, groups, organisations | **Architecture ready** (database tables, relationships, roles and permissions in place and tested; no screens yet) |

## Activation roadmap for commercial features
1. **Teachers (≈1–2 weeks):** teacher invitation and approval screens. These reuse the inactive `teacher` role, `teacher_profiles` and the `classes.manage` permission. A teacher dashboard would show their classes' learners, using the existing per-learner statistics filtered by `enrolments`. Next come homework and feedback (`assignments`), then scheduling and attendance (`class_sessions`, `attendance`).
2. **Classes and groups (≈1 week):** create and edit classes (level, objectives, schedule, capacity), enrol learners, and add a class dashboard that aggregates the learner statistics already computed. Groups add announcements and group assignments.
3. **Organisations (≈1 week):** organisation admin role, seat limits (`organizations.seat_limit`), organisation-scoped reports. This needs a filter on `users.organization_id` in the admin queries, which the data model supports.
4. **Subscriptions and payments (≈1–2 weeks once you have a Stripe account):**
   - Stripe Checkout (hosted page, so cards never touch our servers), with webhooks that write `subscriptions`, `payments` and `invoices`.
   - Plan-based feature gating from `subscription_plans.features`/`limits`.
   - Trial, renewal, cancellation, upgrade and downgrade handled by Stripe Billing.
   - Failed-payment and renewal notifications via the existing notification and email services.
   - **Needs from you:** a Stripe account (business details and bank account), your prices, and your decision on taxes (GST/QST registration).
5. **Scaling:** move the API to a paid Render instance ($7/month, no sleeping) and Neon Launch when traffic grows. Use Redis for rate limiting when running more than one instance. Move media to object storage (Cloudflare R2 or Neon object storage) beyond about 500 MB of uploads.

## Ideas for future versions
- A second practice paper for each exam, and adaptive TOEFL routing.
- More original content: 20+ listening recordings, 20+ reading texts, a second IELTS mock.
- Streaming speech-to-speech conversation (lower latency than the current transcribe → reply → speak loop).
- Custom vocabulary cards created from video study packs and reading.
- Code-signed installer and auto-update.
