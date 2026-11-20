"""The AI correction engine.

Takes a learner utterance (typed or transcribed), optional objective speech
metrics, and returns structured, categorised feedback produced by the LLM.
Nothing here is canned: every correction is generated from the learner's
actual words.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from ..providers.llm import ChatMessage, LLMProvider, ProviderError

CATEGORIES = ("grammar", "vocabulary", "naturalness", "pronunciation", "fluency")


class Issue(BaseModel):
    category: str
    original: str
    corrected: str
    explanation: str
    pattern: str = Field(default="", description="short reusable label for tracking")
    explanation_fr: str | None = None


class Feedback(BaseModel):
    corrected_sentence: str
    is_correct: bool
    issues: list[Issue] = []
    advanced_alternative: str | None = None
    repeat_prompt: str | None = None
    fluency_note: str | None = None
    score: float = Field(ge=0, le=1, default=1.0)


SYSTEM = """You are an expert English professor and examiner (CEFR, IELTS, Cambridge) \
helping a {native}-speaking learner move from {level} toward {target}.

Analyse ONLY the learner's latest utterance. Return strict JSON, no prose:
{{
  "corrected_sentence": str,          // the whole utterance, minimally corrected
  "is_correct": bool,                 // true if no real errors (style tips allowed)
  "issues": [{{
     "category": "grammar"|"vocabulary"|"naturalness"|"pronunciation"|"fluency",
     "original": str,                 // exact fragment the learner said
     "corrected": str,
     "explanation": str,              // one or two sentences, why
     "pattern": str,                  // short label, e.g. "be + lexical verb (*am agree)"
     "explanation_fr": str|null       // French explanation if requested, else null
  }}],
  "advanced_alternative": str|null,   // a more sophisticated C1/C2 phrasing
  "repeat_prompt": str|null,          // ask learner to repeat the key corrected sentence
  "fluency_note": str|null,           // based on the speech metrics if provided
  "score": float                      // 0..1 overall accuracy & naturalness
}}

Rules:
- Distinguish grammar (form), vocabulary (wrong word/collocation), and naturalness \
(grammatical but unidiomatic, e.g. French calques like "I have 30 years").
- Do not invent errors. Accept valid regional variants (US/UK/Canadian).
- Utterances come from speech-to-text: ignore missing punctuation and capitalisation.
- Only report "pronunciation" if the transcript itself shows evidence (e.g. a likely \
mis-recognised word). Never claim phoneme-level analysis you cannot do.
- Base "fluency" only on the supplied metrics (pauses, fillers, words per minute).
- French explanations: {french}.
"""


def analyse_utterance(
    llm: LLMProvider,
    utterance: str,
    *,
    context: list[ChatMessage] | None = None,
    level: str = "B2",
    target: str = "C1",
    native: str = "French",
    french: bool = False,
    speech_metrics: dict | None = None,
) -> Feedback:
    msgs = [
        ChatMessage(
            "system",
            SYSTEM.format(
                native=native,
                level=level,
                target=target,
                french="provide them" if french else "set to null",
            ),
        )
    ]
    if context:
        recent = "\n".join(f"{m.role.upper()}: {m.content}" for m in context[-6:])
        msgs.append(ChatMessage("user", f"Conversation so far (for context only):\n{recent}"))
        msgs.append(ChatMessage("assistant", "Understood. Send the utterance to analyse."))
    body = f"Learner utterance:\n\"\"\"{utterance}\"\"\""
    if speech_metrics:
        body += f"\n\nObjective speech metrics: {speech_metrics}"
    msgs.append(ChatMessage("user", body))

    data = llm.chat_json(msgs)
    try:
        fb = Feedback.model_validate(data)
    except ValidationError as exc:
        raise ProviderError(f"Correction response had unexpected shape: {exc}") from exc
    fb.issues = [i for i in fb.issues if i.category in CATEGORIES]
    return fb
