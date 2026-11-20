def les(ref): return {"kind": "lesson", "ref": ref}
def rd(ref): return {"kind": "reading", "ref": ref}
def ls(ref): return {"kind": "listening", "ref": ref}
def voc(level, title): return {"kind": "vocab", "ref": f"level:{level}", "title": title}
def vdom(domain, title): return {"kind": "vocab", "ref": f"domain:{domain}", "title": title}
def conv(mode, title): return {"kind": "conversation", "ref": mode, "title": title}
def wr(key, genre, title, task): return {"kind": "writing", "ref": key, "genre": genre, "title": title, "task": task}
def pron(title): return {"kind": "pronunciation", "ref": "pronunciation", "title": title}
def soon(title): return {"kind": "soon", "ref": "", "title": title}

LEVELS = [
 {"code": "A1", "name": "Beginner", "description": "Understand and use everyday expressions, introduce yourself and ask simple questions.",
  "units": [
   {"title": "Unit 1 · First Steps", "items": [les("a1-alphabet"), les("a1-greetings"), les("a1-to-be"), pron("Sounds of English: the alphabet and vowels")]},
   {"title": "Unit 2 · Everyday Life", "items": [les("a1-numbers-dates"), les("a1-present-simple"), voc("A1", "A1 core vocabulary (20 words)"), rd("a1-my-day")]},
   {"title": "Unit 3 · Building Sentences", "items": [les("a1-word-order"), les("a1-questions"), les("a1-present-continuous"), ls("a1-cafe-order")]},
   {"title": "Unit 4 · Communicate", "items": [conv("a1_intro", "Conversation: introduce yourself"), wr("a1-about-me", "short_text", "Writing: all about me", "Write 6–8 sentences about yourself: your name, where you live, your job or studies, your family and what you like doing.")]},
  ]},
 {"code": "A2", "name": "Elementary", "description": "Handle shopping, travel and everyday situations; talk about the past and future plans.",
  "units": [
   {"title": "Unit 1 · Talking About the Past", "items": [les("a2-past-simple"), rd("a2-weekend-quebec"), voc("A2", "A2 everyday vocabulary (20 words)")]},
   {"title": "Unit 2 · Plans and Comparisons", "items": [les("a2-future"), les("a2-comparatives"), les("a2-modals")]},
   {"title": "Unit 3 · Shopping and Travel", "items": [les("a2-shopping"), les("a2-travel"), ls("a2-hotel-directions"), conv("a2_shopping", "Role-play: in a shop"), conv("a2_travel", "Role-play: at the hotel and the station")]},
   {"title": "Unit 4 · Everyday Communication", "items": [les("a2-everyday-communication"), wr("a2-email-friend", "short_text", "Writing: an email to a friend", "Write an email (80–100 words) to a friend about your last weekend and invite them to do something next Saturday.")]},
  ]},
 {"code": "B1", "name": "Intermediate", "description": "Deal with most situations at work and while travelling, tell stories and give opinions.",
  "units": [
   {"title": "Unit 1 · Tenses in Context", "items": [les("present-perfect-vs-past-simple"), les("b1-past-perfect"), les("b1-narrative-tenses"), les("future-forms")]},
   {"title": "Unit 2 · Conditions and Phrasal Verbs", "items": [les("conditionals-mixed"), les("b1-phrasal-verbs"), voc("B1", "B1 vocabulary and false friends (20 words)")]},
   {"title": "Unit 3 · Natural English", "items": [les("b1-idioms"), les("b1-storytelling"), ls("coffee-shop-catchup"), conv("b1_story", "Speaking: tell a story")]},
   {"title": "Unit 4 · At Work", "items": [les("b1-professional-communication"), conv("b1_workplace", "Role-play: a day at the office"), rd("online-learning-lessons")]},
   {"title": "Unit 5 · Writing and Fluency", "items": [les("b1-paragraphs"), wr("b1-paragraph", "paragraph", "Writing: a structured paragraph", "Write one well-structured paragraph (120–150 words): 'The advantages of learning a language online.' Use a topic sentence, two supporting ideas with examples, and a concluding sentence."), conv("fluency", "Fluency drill: one minute without stopping")]},
  ]},
 {"code": "B2", "name": "Upper Intermediate", "description": "Interact fluently with native speakers, argue a point of view and understand complex texts.",
  "units": [
   {"title": "Unit 1 · Advanced Structures", "items": [les("passive-voice"), les("causative"), les("reported-speech"), les("relative-clauses")]},
   {"title": "Unit 2 · Complex Sentences", "items": [les("gerunds-infinitives"), les("articles"), les("quantifiers"), les("subject-verb-agreement"), les("punctuation")]},
   {"title": "Unit 3 · Vocabulary in Use", "items": [les("b2-collocations"), les("prepositions-collocations"), voc("B2", "B2 vocabulary set")]},
   {"title": "Unit 4 · Reading and Listening", "items": [rd("four-day-week"), rd("the-last-train"), ls("b2-debate-cars-downtown")]},
   {"title": "Unit 5 · Debates and Essays", "items": [les("b2-debating"), conv("debate", "Debate with the AI professor"), conv("presentation", "Give a short presentation"), wr("b2-essay", "essay", "Writing: opinion essay", "Write an opinion essay (250 words): 'Should private cars be banned from city centres?' Present both sides and give your own view.")]},
  ]},
 {"code": "C1", "name": "Advanced", "description": "Express yourself fluently and precisely in academic and professional settings.",
  "units": [
   {"title": "Unit 1 · Sophisticated Grammar", "items": [les("inversion-emphasis"), les("cleft-sentences"), les("participle-clauses"), les("noun-clauses")]},
   {"title": "Unit 2 · Nuance and Stance", "items": [les("modals-deduction"), les("subjunctive"), les("future-in-the-past"), les("hedging"), les("discourse-markers")]},
   {"title": "Unit 3 · Advanced Vocabulary and Idioms", "items": [les("c1-advanced-idioms"), voc("C1", "C1 academic and professional vocabulary")]},
   {"title": "Unit 4 · Critical Reading and Complex Listening", "items": [rd("algorithmic-hiring"), rd("sleep-memory-research"), ls("news-housing"), ls("panel-growth-climate")]},
   {"title": "Unit 5 · Presenting, Negotiating, Debating", "items": [les("c1-presentation-language"), les("c1-negotiation-language"), conv("academic", "Academic discussion"), conv("negotiation", "Negotiation simulation"), pron("Advanced pronunciation: stress, rhythm and intonation")]},
   {"title": "Unit 6 · Academic Writing", "items": [wr("c1-academic-essay", "essay", "Writing: academic essay", "Write an academic essay (300 words): 'To what extent should algorithms be used in hiring decisions?' Use hedging, evidence and a clear line of argument.")]},
  ]},
 {"code": "C2", "name": "Proficiency", "description": "Understand virtually everything and express subtle shades of meaning with near-native precision.",
  "units": [
   {"title": "Unit 1 · Near-Native Grammar", "items": [les("nominalisation"), les("ellipsis-substitution")]},
   {"title": "Unit 2 · Precision and Subtlety", "items": [les("c2-near-synonyms"), voc("C2", "C2 sophisticated vocabulary")]},
   {"title": "Unit 3 · Literary and Academic Texts", "items": [rd("in-praise-of-boredom"), rd("translation-and-power"), rd("on-clarity"), soon("Research paper analysis (coming soon)")]},
   {"title": "Unit 4 · Native-Level Listening", "items": [ls("podcast-ai-work"), ls("radio-nudging")]},
   {"title": "Unit 5 · Rhetoric and Argumentation", "items": [les("c2-rhetoric"), conv("phd_interview", "Academic discussion: doctoral interview"), wr("c2-argument", "essay", "Writing: nuanced argument", "Write a nuanced argumentative essay (350 words): 'Clarity is a moral obligation for experts.' Concede, qualify and use at least two rhetorical devices."), wr("c2-summary", "summary", "Writing: précis", "Summarise 'Translation and Power' in exactly 120 words, preserving the author's stance.")]},
  ]},
]

BUSINESS = [
 {"id": "communication", "title": "Business Communication", "icon": "💬", "level": "B1–B2", "items": [les("biz-communication"), vdom("business", "Business vocabulary"), conv("business", "Workplace update with your manager")]},
 {"id": "meetings", "title": "Professional Meetings", "icon": "🗓️", "level": "B2", "items": [les("biz-meetings"), ls("budget-meeting"), conv("meeting_chair", "Chair a meeting"), wr("biz-minutes", "minutes", "Write the minutes", "Write the minutes of the budget meeting you listened to: attendees, decisions and action items.")]},
 {"id": "negotiation", "title": "Business Negotiation", "icon": "🤝", "level": "C1", "items": [les("biz-negotiation"), conv("negotiation", "Supplier negotiation")]},
 {"id": "presentations", "title": "Corporate Presentations", "icon": "📊", "level": "B2–C1", "items": [les("biz-presentations"), conv("presentation", "Present your quarterly results")]},
 {"id": "writing", "title": "Business Writing", "icon": "✍️", "level": "B2", "items": [les("biz-writing"), conv("business", "Discuss your draft with your manager"), wr("biz-proposal", "proposal", "Write a proposal", "Write a one-page proposal recommending a four-day work week pilot for your team.")]},
 {"id": "emails", "title": "Professional Emails", "icon": "📧", "level": "B1–B2", "items": [les("biz-emails"), conv("networking", "Follow up by phone after your email"), wr("biz-email", "email", "Write a professional email", "Write to a client to apologise for a delayed delivery, explain the cause and propose a solution.")]},
 {"id": "leadership", "title": "Leadership and Management", "icon": "🧭", "level": "C1", "items": [les("biz-leadership"), vdom("leadership", "Leadership vocabulary"), vdom("management", "Management vocabulary"), conv("leadership", "Give feedback to a team member")]},
 {"id": "hr", "title": "Human Resources", "icon": "👥", "level": "B2", "items": [les("biz-hr"), conv("hr", "HR conversation: performance review")]},
 {"id": "marketing", "title": "Marketing and Sales", "icon": "📣", "level": "B2", "items": [les("biz-marketing-sales"), rd("pricing-psychology"), conv("marketing", "Sales call with a prospect")]},
 {"id": "corporate-finance", "title": "Corporate Finance", "icon": "💼", "level": "C1", "items": [les("biz-corporate-finance"), rd("esg-quarterly-report"), vdom("finance", "Finance vocabulary"), conv("investment_committee", "Investment committee")]},
 {"id": "banking", "title": "Banking and Investment", "icon": "🏦", "level": "B2", "items": [les("biz-banking-investment"), ls("bank-account"), vdom("banking", "Banking vocabulary"), vdom("investment", "Investment vocabulary"), conv("finance", "Client meeting with a bank advisor")]},
 {"id": "markets", "title": "Financial Markets", "icon": "📈", "level": "C1", "items": [les("biz-financial-markets"), ls("lecture-behavioural-finance"), vdom("risk management", "Risk management vocabulary"), conv("analyst_meeting", "Analyst meeting")]},
 {"id": "economics", "title": "Economics", "icon": "🌐", "level": "B2–C1", "items": [les("biz-economics"), rd("central-banks-inflation"), vdom("economics", "Economics vocabulary"), conv("economics", "Discuss the economic outlook")]},
 {"id": "projects", "title": "Project Management", "icon": "🗂️", "level": "B2", "items": [les("biz-project-management"), vdom("project management", "Project management vocabulary"), conv("project", "Project status meeting")]},
 {"id": "interviews", "title": "Business Interviews", "icon": "🎯", "level": "B2–C1", "items": [les("biz-interviews"), ls("job-interview-analyst"), conv("job_interview", "Job interview simulation"), wr("biz-cover-letter", "cover_letter", "Write a cover letter", "Write a cover letter for a financial analyst role at a Canadian bank.")]},
 {"id": "networking", "title": "Professional Networking", "icon": "🔗", "level": "B1–B2", "items": [les("biz-networking"), conv("networking", "Networking event")]},
 {"id": "executive", "title": "Executive Communication", "icon": "🏛️", "level": "C1–C2", "items": [les("biz-executive"), conv("executive", "Brief the CEO"), conv("mba", "MBA case discussion")]},
 {"id": "reports", "title": "Business Reports and Analysis", "icon": "📑", "level": "C1", "items": [les("biz-reports"), wr("biz-report", "report", "Write an executive summary", "Write an executive summary (200 words) of a report on rising customer churn, with three recommendations."), conv("reports", "Present your analysis")]},
]

CURRICULUM = {"levels": LEVELS, "business": BUSINESS}
