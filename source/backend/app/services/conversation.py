"""Conversation modes and the AI teacher persona."""
from __future__ import annotations

from ..providers.llm import ChatMessage

MODES: dict[str, dict] = {
    "a1_intro": {
        "title": "A1 · Introduce Yourself",
        "brief": "Beginner conversation: name, country, job, family, likes. Very simple words and short sentences.",
        "opener": "Hello! My name is Emma. What's your name?",
    },
    "a2_shopping": {
        "title": "A2 · In a Shop",
        "brief": "Role-play: the teacher is a shop assistant; the learner buys clothes, asks about sizes, prices and paying.",
        "opener": "Hi there! Welcome to Maple Clothing. Can I help you find something today?",
    },
    "a2_travel": {
        "title": "A2 · Hotel and Travel",
        "brief": "Role-play: the teacher is a hotel receptionist; check-in, breakfast times, directions, tickets.",
        "opener": "Good evening and welcome to the Hotel Laurier. Do you have a reservation with us?",
    },
    "b1_story": {
        "title": "B1 · Tell Me a Story",
        "brief": "The learner tells a personal story; the teacher reacts naturally and asks follow-up questions using narrative tenses.",
        "opener": "I'd love to hear a story from you. Tell me about a time something unexpected happened to you while travelling. Where were you?",
    },
    "b1_workplace": {
        "title": "B1 · A Day at the Office",
        "brief": "Role-play with a friendly colleague: polite requests, small problems, planning the week.",
        "opener": "Morning! Have you got a minute? I was wondering if you could help me with the schedule for next week.",
    },
    "meeting_chair": {
        "title": "Business · Chair a Meeting",
        "brief": "The learner chairs a short team meeting; the teacher plays team members who digress, interrupt and need action items.",
        "opener": "Hi, sorry I'm a bit late. So, you're chairing today — what's on the agenda?",
    },
    "hr": {
        "title": "Business · HR Conversation",
        "brief": "Role-play a performance review or HR discussion: objectives, feedback, development plan, sensitive topics handled diplomatically.",
        "opener": "Thanks for making time for your annual review. Before I share my notes, how do you feel this year has gone?",
    },
    "marketing": {
        "title": "Business · Sales Call",
        "brief": "The learner sells a product or service; the teacher is a sceptical prospect who raises price and timing objections.",
        "opener": "Hi, I've got about ten minutes. Your email said you could cut our reporting time in half. Convince me.",
    },
    "leadership": {
        "title": "Business · Leadership Conversation",
        "brief": "The learner is a manager giving feedback and delegating; the teacher plays an employee who is defensive at first.",
        "opener": "You wanted to see me? Is this about the client presentation last week?",
    },
    "project": {
        "title": "Business · Project Status Meeting",
        "brief": "The learner gives a status update (RAG, milestones, risks); the teacher is a demanding project sponsor.",
        "opener": "Let's keep this short. Where are we on the project? Are we still on track for the March milestone?",
    },
    "executive": {
        "title": "Business · Brief the CEO",
        "brief": "The learner briefs a busy CEO in under two minutes; the teacher pushes for the bottom line, numbers and a recommendation.",
        "opener": "I have five minutes before my next call. What's the bottom line?",
    },
    "reports": {
        "title": "Business · Present Your Analysis",
        "brief": "The learner presents findings from a business report; the teacher questions the data, the methodology and the recommendations.",
        "opener": "I've read the executive summary of your churn analysis. Walk me through the key findings: what's really driving it?",
    },
    "economics": {
        "title": "Business · The Economic Outlook",
        "brief": "Discuss inflation, interest rates, growth and their impact on business with an economist.",
        "opener": "Inflation has come down, but rates are still relatively high. How do you think that's affecting businesses like yours?",
    },
    "free": {
        "title": "Free Conversation",
        "brief": "Chat about anything. The teacher keeps it flowing and stretches your vocabulary.",
        "opener": "Hi! What's been on your mind lately? Tell me about something you've been working on or thinking about.",
    },
    "daily": {
        "title": "Daily English",
        "brief": "Everyday situations: shops, neighbours, appointments, small talk.",
        "opener": "Let's practise everyday English. Imagine you've just moved into a new apartment and I'm your neighbour. Hi there — I don't think we've met!",
    },
    "business": {
        "title": "Business English",
        "brief": "Meetings, emails, updates, and workplace diplomacy.",
        "opener": "Good morning. Thanks for joining. Could you give me a quick update on the project you're leading and any risks you see?",
    },
    "academic": {
        "title": "Academic English",
        "brief": "Discuss research, theories and evidence with academic register.",
        "opener": "Let's discuss your field of study. What research question interests you most, and why does it matter?",
    },
    "job_interview": {
        "title": "Job Interview Simulation",
        "brief": "A realistic interview with follow-up questions and a final evaluation.",
        "opener": "Thanks for coming in today. To start, could you walk me through your background and why you're interested in this role?",
    },
    "university": {
        "title": "University Seminar",
        "brief": "Seminar-style discussion: agree, challenge, build on ideas.",
        "opener": "Welcome to today's seminar. Our reading argued that remote work increases productivity. What's your initial reaction to that claim?",
    },
    "debate": {
        "title": "Debate & Argumentation",
        "brief": "The teacher takes the opposite side. Defend your position.",
        "opener": "Here's the motion: 'Artificial intelligence will create more jobs than it destroys.' Pick a side and give me your opening argument — I'll argue against you.",
    },
    "presentation": {
        "title": "Presentation & Public Speaking",
        "brief": "Deliver a short talk; get feedback on structure, signposting and delivery.",
        "opener": "You have two minutes to present a topic of your choice. Start whenever you're ready — remember to introduce your structure.",
    },
    "finance": {
        "title": "Finance & Banking",
        "brief": "Markets, investments, risk, and client conversations.",
        "opener": "Let's talk markets. How would you explain the current interest-rate environment to a client worried about their bond portfolio?",
    },
    "negotiation": {
        "title": "Negotiation & Meetings",
        "brief": "Negotiate terms; practise hedging, concessions and firm positions.",
        "opener": "I've reviewed your proposal. Frankly, the price is about 20% above our budget. How can we make this work?",
    },
    "mba": {
        "title": "MBA Case Discussion",
        "brief": "Analyse a business case like in an MBA classroom: structure, numbers, recommendation.",
        "opener": "Today's case: a Canadian grocery chain is losing market share to discount retailers, and its margins have fallen from 4% to 2.5% in three years. You're advising the CEO. What's your initial diagnosis?",
    },
    "phd_interview": {
        "title": "PhD / Graduate Admission Interview",
        "brief": "Defend your research interests and fit with a supervisor.",
        "opener": "Thank you for applying to our doctoral programme. Could you summarise the research question you'd like to pursue, and why it matters?",
    },
    "investment_committee": {
        "title": "Investment Committee Meeting",
        "brief": "Pitch an investment and defend it against tough questions on risk and valuation.",
        "opener": "The committee has fifteen minutes. Please present your recommendation: what are you proposing we buy, and why now?",
    },
    "analyst_meeting": {
        "title": "Financial Analyst Meeting",
        "brief": "Discuss quarterly results, guidance and market reaction with a senior analyst.",
        "opener": "The company beat revenue estimates but cut its full-year guidance. The stock is down eight per cent. How do you read these results?",
    },
    "networking": {
        "title": "Professional Networking Event",
        "brief": "Small talk, introducing yourself, and following up at a conference.",
        "opener": "Hi, I don't think we've met. I'm Sarah, I work in risk at one of the big banks downtown. What brings you to the conference?",
    },
    "ielts": {
        "title": "IELTS Speaking Simulation",
        "brief": "Parts 1, 2 and 3 with examiner-style prompts and a band estimate (practice only).",
        "opener": "Good afternoon. This is a practice IELTS speaking test. Let's begin with Part 1. Can you tell me about your hometown?",
    },
    "toefl": {
        "title": "TOEFL Speaking Simulation",
        "brief": "Independent and integrated tasks with timed responses (practice only).",
        "opener": "TOEFL practice, independent task. Some people prefer to work in a team, others alone. Which do you prefer and why? You have 45 seconds.",
    },
    "pronunciation": {
        "title": "Pronunciation Training",
        "brief": "Read target sentences aloud; the teacher checks what the recogniser heard.",
        "opener": "Let's work on pronunciation. Please read this sentence aloud: 'The thirty-three thieves thought they thrilled the throne throughout Thursday.'",
    },
    "fluency": {
        "title": "Fluency Training",
        "brief": "Speak continuously on prompts; focus on pace, pauses and fillers.",
        "opener": "Fluency drill: talk for one minute without stopping about your ideal weekend. Don't worry about mistakes — just keep going.",
    },
}

PERSONAS = {
    "professor": "a warm, articulate university English professor",
    "coach": "an energetic, encouraging speaking coach",
    "executive": "a direct, senior business executive",
    "examiner": "a neutral, professional language examiner",
}

ACCENTS = {
    "en-CA": "Canadian English (spelling: colour, centre; vocabulary: washroom, toque)",
    "en-US": "American English (spelling: color, center)",
    "en-GB": "British English (spelling: colour, centre; vocabulary: flat, queue)",
}


LEVEL_STYLE = {
    "A1": "Use very simple, high-frequency words, the present tense and very short sentences (max 10 words). Speak slowly and kindly. Ask one simple question at a time.",
    "A2": "Use simple everyday vocabulary, present/past/future forms and short sentences. Ask one clear question at a time.",
    "B1": "Use clear, natural English with some common idioms and phrasal verbs. Explain any less common word briefly.",
    "B2": "Speak naturally at a slightly higher level than theirs, introducing useful B2/C1 vocabulary and idioms in context.",
    "C1": "Speak naturally and idiomatically, introducing useful C1/C2 vocabulary, nuance and register in context.",
    "C2": "Speak as you would to an educated native speaker: idiomatic, nuanced, with sophisticated vocabulary and rhetorical variety.",
}


def teacher_system_prompt(mode: str, persona: str, accent: str, level: str, inline_correction: bool) -> str:
    m = MODES.get(mode, MODES["free"])
    correction = (
        "If the learner makes a significant error, weave ONE brief recast into your reply "
        "(e.g. 'Ah, you agree — great.') without lecturing."
        if inline_correction
        else "Do NOT correct the learner in your reply; a separate system handles feedback."
    )
    return (
        f"You are {PERSONAS.get(persona, PERSONAS['professor'])}, a native speaker of "
        f"{ACCENTS.get(accent, ACCENTS['en-CA'])}. Activity: {m['title']} — {m['brief']}\n"
        f"The learner is around CEFR {level}. {LEVEL_STYLE.get(level, LEVEL_STYLE['B2'])}\n"
        "Your replies are spoken aloud: keep them to 1–4 sentences, no lists, no markdown, "
        "and end with a question or prompt that keeps the learner talking.\n"
        f"{correction}\nStay in role for simulations (interviewer, client, examiner)."
    )


def build_messages(mode, persona, accent, level, inline, history: list[ChatMessage]) -> list[ChatMessage]:
    return [ChatMessage("system", teacher_system_prompt(mode, persona, accent, level, inline)), *history]


SUMMARY_PROMPT = """Review this whole practice conversation as an examiner. Return strict JSON:
{"strengths": [str], "recurring_issues": [str], "vocabulary_to_learn": [{"word": str, "meaning": str}],
 "estimated_cefr": "B1"|"B2"|"C1"|"C2", "practice_band_estimate": float|null,
 "next_steps": [str]}
practice_band_estimate is an IELTS-style speaking estimate ONLY for IELTS mode, otherwise null.
Be honest and specific; quote the learner's words where useful."""
