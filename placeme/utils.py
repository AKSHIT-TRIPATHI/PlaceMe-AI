"""
utils.py — PlaceMe AI
Resume parsing + Gemini interview utilities.
"""

import os
import time
import json as _json
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from django.conf import settings

# ── Model chain ────────────────────────────────────────────────────────────
# Each entry is {"provider": "gemini"|"groq", "model": "<model_id>"}
# Tried in order — moves to next on quota/rate-limit error.

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
]

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Cap resume text at ~15 000 chars (~3 000 words) to avoid token exhaustion
RESUME_MAX_CHARS = 15_000


# ── Resume text extraction ─────────────────────────────────────────────────

def extract_text_from_file(file_path: str) -> str:
    if not file_path or not os.path.exists(file_path):
        return ""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            import pdfplumber
            parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        parts.append(t)
            return "\n".join(parts)
        elif ext in (".docx", ".doc"):
            from docx import Document
            doc = Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        print(f"[utils] resume parse error: {e}")
    return ""


def get_resume_text(session_obj) -> str:
    """
    Priority:
    1. InterviewPreferences resume (temp@username file — user uploaded on AI Interviews page)
    2. UserProfile resume (uploaded on Profile page)
    3. Empty string
    No files are copied — we read directly from the original locations.
    """
    # 1. Check InterviewPreferences resume (temp@username file)
    try:
        prefs = session_obj.user.interview_prefs
        if prefs.resume:
            text = extract_text_from_file(prefs.resume.path)
            if text.strip():
                return text[:RESUME_MAX_CHARS]
    except Exception:
        pass

    # 2. Fallback to profile resume
    try:
        profile = session_obj.user.profile
        if profile.resume:
            text = extract_text_from_file(profile.resume.path)
            if text.strip():
                return text[:RESUME_MAX_CHARS]
    except Exception:
        pass

    return ""


# ── Gemini helpers ─────────────────────────────────────────────────────────

def _gemini_client() -> genai.Client:
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in settings.py")
    return genai.Client(api_key=api_key)


# Keep _client as an alias so existing call sites don't break
def _client() -> genai.Client:
    return _gemini_client()


def _groq_generate(model: str, contents) -> str:
    """
    Call Groq API with the given model.
    `contents` can be either a plain string prompt or a list of
    [{role, text}] history dicts (same format as our chat_history).
    Returns the response text.
    """
    from groq import Groq

    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in settings.py")

    client = Groq(api_key=api_key)

    # Convert contents to Groq message format
    if isinstance(contents, str):
        messages = [{"role": "user", "content": contents}]
    elif isinstance(contents, list):
        messages = []
        for item in contents:
            # Handle both raw dicts {role, text} and types.Content objects
            if hasattr(item, "role") and hasattr(item, "parts"):
                # types.Content object
                role = "assistant" if item.role == "model" else "user"
                text = item.parts[0].text if item.parts else ""
            else:
                role = "assistant" if item.get("role") == "model" else "user"
                text = item.get("text", "")
            if text.strip():
                messages.append({"role": role, "content": text})
    else:
        messages = [{"role": "user", "content": str(contents)}]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2048,
        temperature=0.7,
    )
    return response.choices[0].message.content


def _generate_with_fallback(client: genai.Client, contents) -> tuple:
    """
    Try Gemini models first, then Groq models on quota exhaustion.
    Returns (model_used, response_text).
    Raises the last exception if all models are exhausted.
    """
    last_exc = None

    # ── Gemini models ──────────────────────────────────────────────────────
    for model_name in GEMINI_MODELS:
        try:
            resp = client.models.generate_content(model=model_name, contents=contents)
            return model_name, resp.text
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"[utils] Gemini {model_name} quota hit, trying next…")
                last_exc = e
                time.sleep(1)
                continue
            raise
        except Exception as e:
            print(f"[utils] Gemini {model_name} error: {e}, trying next…")
            last_exc = e
            continue

    # ── Groq fallback ──────────────────────────────────────────────────────
    groq_key = getattr(settings, "GROQ_API_KEY", "")
    if groq_key:
        for model_name in GROQ_MODELS:
            try:
                print(f"[utils] Falling back to Groq: {model_name}")
                text = _groq_generate(model_name, contents)
                return f"groq/{model_name}", text
            except Exception as e:
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    print(f"[utils] Groq {model_name} rate limited, trying next…")
                    last_exc = e
                    time.sleep(1)
                    continue
                print(f"[utils] Groq {model_name} error: {e}, trying next…")
                last_exc = e
                continue
    else:
        print("[utils] GROQ_API_KEY not set — skipping Groq fallback")

    raise last_exc or Exception("All AI providers exhausted")


def _history_to_contents(history: list) -> list:
    """Convert [{role, text}] → [types.Content], skipping empty messages."""
    result = []
    for msg in history:
        text = msg.get("text", "").strip()
        if not text:
            continue   # ← skip empty parts — Gemini rejects them with INVALID_ARGUMENT
        role = "model" if msg.get("role") == "model" else "user"
        result.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return result


# ── Answer classifier ──────────────────────────────────────────────────────

def classify_message(client: genai.Client, message: str, last_question: str) -> bool:
    """
    Returns True if the message is a genuine attempt to answer the question.
    Returns False for greetings, fillers, 'wait', 'ok', 'hi', off-topic chatter.
    """
    prompt = (
        f"You are a classifier. Output exactly one word: YES or NO.\n"
        f"Interview question: \"{last_question}\"\n"
        f"Candidate message: \"{message}\"\n"
        f"Is this a genuine attempt to answer the interview question? "
        f"YES = real answer (even if brief or partial). "
        f"NO = greeting, filler, 'wait', 'ok', 'hi', 'thanks', or off-topic.\n"
        f"Output only YES or NO."
    )
    try:
        _, result = _generate_with_fallback(client, prompt)
        return result.strip().upper().startswith("Y")
    except Exception:
        return True  # default to counting if classifier fails


def get_last_question(chat_history: list) -> str:
    """Return the most recent AI message text."""
    for msg in reversed(chat_history):
        if msg.get("role") == "model":
            return msg.get("text", "")
    return ""


# ── Interview initialisation ───────────────────────────────────────────────

def initialize_gemini_interview(session_obj, resume_text: str):
    """
    Build system prompt, call Gemini, return (ai_opening_text, chat_history).
    """
    pref_label  = dict(session_obj.PREF_CHOICES).get(session_obj.interview_preference, session_obj.interview_preference)
    tone_label  = dict(session_obj.TONE_CHOICES).get(session_obj.interviewer_tone,     session_obj.interviewer_tone)
    depth_label = dict(session_obj.DEPTH_CHOICES).get(session_obj.question_depth,      session_obj.question_depth)

    # Build context sections for the system prompt
    if resume_text.strip():
        resume_section = f"\n\n--- CANDIDATE RESUME ---\n{resume_text}\n--- END OF RESUME ---"
    else:
        # No resume on either page — fall back entirely to manually entered details
        manual_context = []
        if session_obj.target_roles:
            manual_context.append(f"Target roles: {session_obj.target_roles}")
        if session_obj.additional_skills:
            manual_context.append(f"Skills: {session_obj.additional_skills}")
        if manual_context:
            resume_section = (
                f"\n\n(No resume was uploaded. Use the following candidate-provided details to "
                f"generate relevant interview questions:\n" + "\n".join(manual_context) + ")"
            )
        else:
            resume_section = (
                f"\n\n(No resume or profile details provided. Ask general interview questions "
                f"relevant to the target role: {session_obj.target_roles or 'software engineering'}.)"
            )
    jd_section = (
        f"\n\n--- JOB DESCRIPTION ---\n{session_obj.job_description}\n--- END OF JD ---"
        if session_obj.job_description.strip()
        else ""
    )
    skills_section = (
        f"\n\nAdditional skills to assess: {session_obj.additional_skills}"
        if session_obj.additional_skills.strip()
        else ""
    )

    system_prompt = (
        f"You are an expert AI interviewer conducting a {pref_label} interview. "
        f"Your tone should be {tone_label}. "
        f"Ask questions at a {depth_label} depth. "
        f"The candidate is preparing for: {session_obj.target_roles or 'general software engineering'}. "
        f"Base your questions on the candidate's resume. "
        f"{'Align questions to the job description provided.' if session_obj.job_description.strip() else ''}"
        f"\n\nSTRICT RULES YOU MUST FOLLOW WITHOUT EXCEPTION:\n"
        f"1. Ask ONLY ONE question at a time.\n"
        f"2. Do NOT provide answers, hints, or evaluations mid-interview.\n"
        f"3. Ask exactly {session_obj.number_of_questions} interview questions in total.\n"
        f"4. NEVER close, conclude, or say goodbye on your own — ONLY close when explicitly instructed.\n"
        f"5. If the candidate sends a greeting, 'hi', 'ok', 'wait', or any non-answer, "
        f"acknowledge it briefly in a {tone_label} tone and then REPEAT the current unanswered question.\n"
        f"6. If the candidate's answer is off-topic or does not address the question, "
        f"point this out in a {tone_label} tone and ask them to address it.\n"
        f"7. Only move to the next question AFTER receiving a genuine answer to the current one.\n"
        f"8. After receiving the answer to your {session_obj.number_of_questions}th question, "
        f"simply wait — do NOT conclude. You will be explicitly told when to close.\n"
        f"{resume_section}{jd_section}{skills_section}"
        f"\n\nNow begin: greet the candidate warmly, introduce yourself as 'PlaceMe AI Interviewer', "
        f"and ask the first question."
    )

    client = _client()
    try:
        _, ai_text = _generate_with_fallback(client, system_prompt)
    except ClientError as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise Exception("The AI is at capacity. Please wait 30–60 seconds and try again.")
        raise

    history = [
        {"role": "user",  "text": system_prompt},
        {"role": "model", "text": ai_text},
    ]
    return ai_text, history


# ── Ongoing chat ───────────────────────────────────────────────────────────

def send_message_to_gemini(session_obj, user_message: str):
    """Send a user reply and return (ai_response_text, updated_history)."""
    user_message = user_message.strip()
    if not user_message:
        user_message = "..."   # prevent empty Part being sent to Gemini

    client   = _client()
    contents = _history_to_contents(session_obj.chat_history)
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    try:
        _, ai_text = _generate_with_fallback(client, contents)
    except ClientError as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise Exception("The AI is at capacity. Please wait 30 seconds and try again.")
        raise

    updated_history = session_obj.chat_history + [
        {"role": "user",  "text": user_message},
        {"role": "model", "text": ai_text},
    ]
    return ai_text, updated_history


# ── Score & feedback generation ────────────────────────────────────────────

def generate_score_and_feedback(session_obj) -> dict:
    """
    Analyse the completed interview transcript and return:
    {
      "score": <int 0-100>,
      "tech":    "<feedback string>",
      "coding":  "<feedback string>",
      "grammar": "<feedback string>"
    }
    Returns a safe fallback dict if Gemini fails.
    """
    # Build a readable transcript (skip system prompt at index 0)
    transcript_lines = []
    for msg in session_obj.chat_history[1:]:
        role = "Interviewer" if msg.get("role") == "model" else "Candidate"
        transcript_lines.append(f"{role}: {msg.get('text','')}")
    transcript = "\n\n".join(transcript_lines)

    n = session_obj.number_of_questions
    marks_per_q = round(100 / n) if n else 10

    prompt = f"""You are a strict but fair interview evaluator.

Below is the complete transcript of a {session_obj.get_interview_preference_display()} interview.
The interview had {n} questions worth {marks_per_q} marks each (total = 100).

Evaluate the candidate's responses and return a JSON object with EXACTLY these keys:
- "score": integer 0-100 (sum of marks earned across all answers)
- "tech": string — specific feedback on technical knowledge (2-3 sentences, mention weak areas)
- "coding": string — specific data structures / algorithms / coding topics to practise (2-3 sentences, be concrete e.g. "practise sliding window, binary search, hash maps")
- "grammar": string — feedback on communication clarity, grammar, and explanation style (2-3 sentences)
- "weak_areas": array of 3 to 5 short strings — concrete topics the candidate struggled with, suitable as tags (e.g. ["Binary Search", "System Design", "Time Complexity", "Communication Clarity"]). Each tag must be 1-4 words, specific, and actionable. Do NOT use generic words like "Technical", "Candidate", "Advanced", "Knowledge".

Rules:
- Be honest and constructive, not overly generous.
- Return ONLY the JSON object, no markdown fences, no extra text.

--- TRANSCRIPT START ---
{transcript[:8000]}
--- TRANSCRIPT END ---
"""

    client = _client()
    try:
        _, raw = _generate_with_fallback(client, prompt)
        # Strip any accidental markdown fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        import json as _json
        data = _json.loads(raw.strip())
        # Validate expected keys
        score = max(0, min(100, int(data.get("score", 50))))
        return {
            "score":      score,
            "tech":       str(data.get("tech",    "No technical feedback available.")),
            "coding":     str(data.get("coding",  "No coding feedback available.")),
            "grammar":    str(data.get("grammar", "No grammar feedback available.")),
            "weak_areas": [str(t) for t in data.get("weak_areas", []) if str(t).strip()][:5],
        }
    except Exception as e:
        print(f"[utils] scoring error: {e}")
        return {
            "score":      None,
            "tech":       "Could not generate feedback.",
            "coding":     "Could not generate feedback.",
            "grammar":    "Could not generate feedback.",
            "weak_areas": [],
        }
