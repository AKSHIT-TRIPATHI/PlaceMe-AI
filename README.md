# PlaceMe AI

> AI-powered interview preparation platform — practice mock interviews, get scored, track progress, and sharpen coding skills.

PlaceMe AI is a full-stack Django web application built as a final capstone project. It helps job seekers prepare for technical and behavioural interviews through AI-generated resume-aware questions, real-time feedback, performance scoring, and an in-browser coding practice environment.

---

## Features

### 🤖 AI Interviews
- Configure interview type (Technical / Behavioural / Mix), tone, and question depth
- Upload a resume — the AI reads it and generates role-specific questions
- Live chat-based interview session powered by Google Gemini (with Groq as automatic fallback)
- Smart answer classification — filler messages like "wait" or "hi" are not counted as answers
- Auto-submit when the timer runs out or the user submits early
- Scored out of 100 at the end with detailed feedback on:
  - Technical Knowledge
  - Coding Areas to Practise
  - Grammar & Communication
- Structured weak-area tags aggregated across sessions (e.g. "Hash Maps", "System Design")

### 💻 Coding Practice
- In-browser code editor with line numbers, tab support, and starter templates
- Supports 15+ languages — Python, C++, Java, JavaScript, TypeScript, Rust, Go, C#, PHP, Ruby, Kotlin, Swift, Scala, Haskell, Lua, Perl, R
- Powered by [Wandbox](https://wandbox.org) — completely free, no API key needed
- Real-time output, stderr, and compilation error display

### 📊 Results
- Tracks all interview sessions with scores, question counts, and a day streak
- Average score stat card colour-coded by performance (green ≥75 / yellow ≥50 / red <50)
- Last 10 sessions with expandable transcripts (first 2 always visible, rest behind "View More")
- **📌 Last Session Feedback** tile — shows tech, coding, and grammar feedback from the most recent session
- **🎯 Top Weak Areas** tile — aggregates AI-generated topic tags across all sessions and surfaces the most repeated ones (e.g. "Binary Search mentioned 4×")

### 🌟 Community — Share Your Experience
- Dedicated "Share Your Experience" tile on the dashboard (Contact Us style — left info panel, right form)
- AJAX submit — no page reload, instant success state with "Share another" option
- Latest 3 reviews appear dynamically on the landing page Testimonials section
- Falls back to static placeholder cards if no reviews exist yet

### 👤 Profile
- Full candidate profile — identity, resume upload, skills, education, projects, internships
- Contact & links section (LinkedIn, GitHub, portfolio)
- Settings tabs — Contact & Links, PlaceMe AI preferences
- Dashboard "PlaceMe Resume" tile built live from profile data

### 🔐 Auth
- Sign up with email OTP verification — account is only created after the email is confirmed
- Unique username and email enforced at registration
- Password strength rules — min 8 chars, uppercase, lowercase, special character (enforced on signup and password reset)
- Sign in with username or email
- Password reset via OTP sent to email (styled HTML email)
- Dark / light theme toggle across all pages

### 🎨 UI / UX
- Dark glass-morphism design with radial gradient background
- Responsive — works on desktop and mobile
- Footer on all pages with contextual links
- Self-contained per-page CSS — no shared stylesheet between post-login pages

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2.4, Python 3.13 |
| Database | SQLite (local dev) |
| AI — Primary | Google Gemini API (`gemini-2.0-flash`) via `google-genai` |
| AI — Fallback | Groq API (`llama-3.3-70b-versatile`) via `groq` — auto-kicks in on Gemini quota exhaustion |
| Code Execution | Wandbox public API (no key needed) |
| Email | Gmail SMTP with App Password |
| Frontend | Vanilla HTML / CSS / JS — self-contained per-page stylesheets |
| File Storage | Django `MEDIA_ROOT` |

---

## AI Fallback Chain

When Gemini hits its daily quota, the system automatically falls back through this chain — no interruption to the interview:

```
1. gemini-2.0-flash        → quota hit? ↓
2. gemini-2.5-flash        → quota hit? ↓
3. gemini-2.0-flash-lite   → quota hit? ↓
4. groq/llama-3.3-70b      → rate limit? ↓
5. groq/llama-3.1-8b       → all failed → error shown to user
```

Both Gemini and Groq are free tier — daily limits reset at midnight.

---

## Getting Started

Follow these steps exactly. No prior Django experience needed.

### Prerequisites

Make sure you have the following installed on your machine:

- **Python 3.11 or higher** — download from https://www.python.org/downloads/
  - During installation, check **"Add Python to PATH"**
- **Git** — download from https://git-scm.com/downloads

Verify installation by opening a terminal and running:

```bash
python --version
git --version
```

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/PlaceMe_AI.git
cd PlaceMe_AI
```

> Replace `YOUR_USERNAME` with your actual GitHub username.

---

### Step 2 — Create a virtual environment

A virtual environment keeps project dependencies isolated from your system Python.

```bash
python -m venv venv
```

Now activate it:

- **Windows:**
  ```bash
  venv\Scripts\activate
  ```
- **Mac / Linux:**
  ```bash
  source venv/bin/activate
  ```

You should see `(venv)` appear at the start of your terminal line. Keep this active for all following steps.

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs Django, Gemini SDK, Groq SDK, PDF parsing libraries, and all other required packages.

---

### Step 4 — Configure your API keys

Open `PlaceMe_AI/settings.py` in any text editor and update the following values:

#### 4a — Gemini API Key (required for AI Interviews)

```python
GEMINI_API_KEY = 'your_gemini_api_key_here'
```

**How to get one (free, no credit card):**
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click **"Create API key"** → **"Create API key in new project"**
4. Copy the key and paste it above

#### 4b — Groq API Key (recommended — free fallback when Gemini quota runs out)

```python
GROQ_API_KEY = 'your_groq_api_key_here'
```

**How to get one (free, no credit card):**
1. Go to https://console.groq.com
2. Sign in and go to **API Keys**
3. Click **"Create API Key"**, copy it and paste above

> If left empty, the app still works using Gemini only. Groq is the safety net.

#### 4c — Gmail SMTP (required for OTP emails — signup verification + password reset)

```python
EMAIL_HOST_USER     = 'your_gmail_address@gmail.com'
EMAIL_HOST_PASSWORD = 'your_gmail_app_password'
```

**How to get a Gmail App Password (free):**
1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** if not already on
3. Go to **Security → 2-Step Verification → App passwords**
4. Select **Mail** → **Windows Computer** → click **Generate**
5. Copy the 16-character code and paste it as `EMAIL_HOST_PASSWORD`

> Use the App Password, NOT your real Gmail password.

#### 4d — Django Secret Key (required for production, optional for local)

The default secret key in `settings.py` is fine for local development.
For production, replace it with a new random key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

### Step 5 — Set up the database

Run Django's database migrations to create all the required tables:

```bash
python manage.py migrate
```

---

### Step 6 — Create the admin account

```bash
python manage.py createsuperuser
```

Follow the prompts to set a username, email, and password for the Django admin panel.

---

### Step 7 — Run the development server

```bash
python manage.py runserver
```

Open your browser and go to:

```
http://127.0.0.1:8000
```

You should see the PlaceMe AI landing page.

---

### Step 8 — Access the admin panel

Go to:

```
http://127.0.0.1:8000/admin
```

Log in with the superuser credentials you created in Step 6.

---

## Project Structure

```
PlaceMe_AI/
├── PlaceMe_AI/               # Django project config (settings, urls, wsgi)
├── placeme/                  # Main app
│   ├── static/placeme/
│   │   ├── css/              # Per-page self-contained CSS files
│   │   └── js/               # theme_toggle.js
│   ├── templates/placeme/    # HTML templates (one per page)
│   ├── models.py             # DB models — UserProfile, InterviewSession, UserReview, etc.
│   ├── views.py              # All view logic
│   ├── urls.py               # URL routing
│   ├── utils.py              # Gemini + Groq AI utilities, resume parsing, fallback chain
│   ├── backends.py           # Custom email/username auth backend
│   └── admin.py              # Admin panel registration
├── media/                    # User-uploaded files (profile pics, resumes)
├── requirements.txt
├── manage.py
└── README.md
```

---

## Common Issues

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Make sure your virtual environment is activated (`venv\Scripts\activate`) |
| Gemini `429 RESOURCE_EXHAUSTED` | Daily free quota hit — Groq fallback will kick in automatically if `GROQ_API_KEY` is set. Both reset at midnight. |
| Groq `rate_limit` error | Very rare — Groq's free tier is 14,400 req/day. If hit, wait a few minutes. |
| Email not sending on signup | Check your Gmail App Password is correct. Make sure 2FA is enabled on your Google account. |
| `gaierror` on email | Your network is blocking SMTP port 587 — try on a different network or hotspot. |
| Code execution not working | Wandbox may be temporarily down — check https://wandbox.org status. |
| Static files not loading | Do a hard refresh (Ctrl+Shift+R). Run `python manage.py collectstatic` if deploying. |
| OTP not arriving | Check spam folder. Gmail App Password may have expired — regenerate one. |

---

## Environment Variables (for deployment)

If deploying to a server, move secrets out of `settings.py` into environment variables:

```bash
DJANGO_SECRET_KEY=your_secret_key
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
```

And update `settings.py` to read them:

```python
import os
SECRET_KEY        = os.environ.get('DJANGO_SECRET_KEY')
GEMINI_API_KEY    = os.environ.get('GEMINI_API_KEY')
GROQ_API_KEY      = os.environ.get('GROQ_API_KEY')
EMAIL_HOST_USER   = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
```

---

## License

This project was built as a final capstone project. Feel free to use it as a reference or starting point.

---

*Built with Django + Google Gemini + Groq + Wandbox*
