"""Conversation modes and the AI teacher persona."""
from __future__ import annotations

from ..providers.llm import ChatMessage

MODES: dict[str, dict] = {
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
        f"The learner is around CEFR {level}. Speak naturally at a slightly higher level than theirs, "
        "introducing useful C1/C2 vocabulary and idioms in context.\n"
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
