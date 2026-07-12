from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django import forms
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
import random
import string



class SignupForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    password1 = forms.CharField(widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(widget=forms.PasswordInput, required=True)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password1(self):
        import re
        password = self.cleaned_data.get("password1", "")
        
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
        
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError("Password must contain at least one lowercase letter.")
        
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise forms.ValidationError("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>).")
        
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned


def landing(request):
    from .models import UserReview
    latest_reviews = UserReview.objects.select_related("user").order_by("-created_at")[:3]
    return render(request, "placeme/landing.html", {"latest_reviews": latest_reviews})



@require_http_methods(["GET", "POST"])
def signup(request):
    # ── Step 1: show form / validate details / send OTP ──────────────────
    if request.method == "GET":
        return render(request, "placeme/signup.html")

    # ── POST: figure out which step we're on ──────────────────────────────

    # Step 2: user submitted OTP → create account
    if "verify_otp" in request.POST:
        stored_otp = request.session.get("signup_otp")
        pending    = request.session.get("signup_pending")  # {username, email, password}

        entered_otp = request.POST.get("otp", "").strip()

        def otp_err(msg):
            return render(request, "placeme/signup.html", {
                "otp_sent": True,
                "email":    pending.get("email", "") if pending else "",
                "error":    msg,
            })

        if not stored_otp or not pending:
            return otp_err("Session expired. Please start over.")

        if entered_otp != stored_otp:
            return otp_err("Incorrect code. Please try again.")

        # OTP correct — create the account now
        user = User.objects.create_user(
            username=pending["username"],
            email=pending["email"],
            password=pending["password"],
        )
        # Clean up session
        for k in ("signup_otp", "signup_pending"):
            request.session.pop(k, None)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("dashboard")

    # Step 1: validate form details → send OTP
    form = SignupForm(request.POST)
    if not form.is_valid():
        return render(request, "placeme/signup.html", {"form": form})

    username = form.cleaned_data["username"]
    email    = form.cleaned_data["email"]
    password = form.cleaned_data["password1"]

    # Generate OTP and stash pending data in session
    otp = "".join(random.choices(string.digits, k=4))
    request.session["signup_otp"]     = otp
    request.session["signup_pending"] = {
        "username": username,
        "email":    email,
        "password": password,
    }

    # Send OTP email
    body = render_to_string("placeme/signup_verification_email.html", {
        "username": username,
        "otp":      otp,
    })

    try:
        send_mail(
            subject="Verify your PlaceMe AI account",
            message=f"Hi {username},\n\nYour email verification code is: {otp}\n\nEnter this code to complete your registration.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=body,
            fail_silently=False,
        )
    except Exception as e:
        print(f"[signup] email send failed: {e}")
        # Clear session so user isn't stuck
        for k in ("signup_otp", "signup_pending"):
            request.session.pop(k, None)
        form = SignupForm(request.POST)
        return render(request, "placeme/signup.html", {
            "form":  form,
            "error": f"Could not send verification email: {e}. Please check your email address and try again.",
        })

    return render(request, "placeme/signup.html", {
        "otp_sent": True,
        "email":    email,
    })




@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Accepts username OR email + password.
    Uses EmailOrUsernameBackend registered in AUTHENTICATION_BACKENDS.
    """
    error = None

    if request.method == "POST":
        from django.contrib.auth import authenticate as auth_authenticate
        username_or_email = request.POST.get("username", "").strip()
        password          = request.POST.get("password", "")

        user = auth_authenticate(request, username=username_or_email, password=password)

        if user is not None:
            login(request, user)
            if user.is_staff:
                return redirect("/admin/")
            return redirect("dashboard")
        else:
            error = "Invalid username/email or password."

    return render(request, "placeme/login.html", {"error": error})


@login_required
def dashboard(request):
    if request.user.is_staff:
        return redirect("/admin/")
    from .models import UserProfile, Education, Project, Internship, UserReview
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    latest_reviews = UserReview.objects.select_related("user").order_by("-created_at")[:3]
    ctx = {
        "p":             profile_obj,
        "educations":    Education.objects.filter(user=request.user),
        "projects":      Project.objects.filter(user=request.user),
        "internships":   Internship.objects.filter(user=request.user),
        "latest_reviews": latest_reviews,
    }
    return render(request, "placeme/dashboard.html", ctx)


@login_required
def results(request):
    from .models import InterviewSession
    from datetime import date, timedelta
    from collections import Counter

    all_sessions = InterviewSession.objects.filter(user=request.user).order_by("-created_at")

    # Stats use ALL sessions
    total_sessions     = all_sessions.count()
    completed_sessions = all_sessions.filter(is_active=False).count()
    total_questions    = sum(s.current_question_count for s in all_sessions)

    # Average score (only scored sessions)
    scored = [s.score for s in all_sessions if s.score is not None]
    avg_score = round(sum(scored) / len(scored)) if scored else None

    # Streak — consecutive calendar days with at least one completed session
    completed_dates = sorted(set(
        s.created_at.date()
        for s in all_sessions
        if not s.is_active
    ), reverse=True)

    streak = 0
    if completed_dates:
        check = date.today()
        for d in completed_dates:
            if d == check or d == check - timedelta(days=1):
                streak += 1
                check = d - timedelta(days=1)
            else:
                break

    # Last session feedback (most recent session that has feedback)
    last_feedback_session = None
    for s in all_sessions:
        if s.feedback and (s.feedback.get("tech") or s.feedback.get("coding") or s.feedback.get("grammar")):
            last_feedback_session = s
            break

    # Top weak areas — aggregate structured tags from feedback.weak_areas across ALL sessions
    from collections import Counter
    tag_counter = Counter()
    for s in all_sessions:
        fb = s.feedback or {}
        for tag in fb.get("weak_areas", []):
            tag = tag.strip()
            if tag:
                tag_counter[tag] += 1

    # Top 6 tags by frequency
    weak_areas = tag_counter.most_common(6)

    # Only last 10 sessions shown in the tile
    sessions = all_sessions[:10]

    ctx = {
        "sessions":              sessions,
        "total_sessions":        total_sessions,
        "completed_sessions":    completed_sessions,
        "total_questions":       total_questions,
        "streak":                streak,
        "avg_score":             avg_score,
        "last_feedback_session": last_feedback_session,
        "weak_areas":            weak_areas,
    }
    return render(request, "placeme/results.html", ctx)

@login_required
def coding_practice(request):
    return render(request, "placeme/coding_practice.html")


@login_required
@require_http_methods(["POST"])
def piston_run(request):
    """Proxy code execution to Wandbox API — completely free, no API key needed."""
    import json
    import requests as req
    from django.http import JsonResponse

    WANDBOX_URL = "https://wandbox.org/api/compile.json"

    # Language → best Wandbox compiler string
    LANG_MAP = {
        "python":     "cpython-3.12.7",
        "cpp":        "gcc-head",
        "c":          "gcc-head-c",
        "java":       "openjdk-jdk-22+36",
        "javascript": "nodejs-20.17.0",
        "typescript": "typescript-5.6.2",
        "rust":       "rust-1.82.0",
        "go":         "go-1.23.2",
        "csharp":     "mono-6.12.0.199",
        "php":        "php-8.3.12",
        "ruby":       "ruby-4.0.2",
        "kotlin":     "kotlin-2.0.21",
        "swift":      "swift-6.0.1",
        "scala":      "scala-3.5.1",
        "haskell":    "ghc-9.10.1",
        "lua":        "lua-5.4.7",
        "perl":       "perl-5.42.0",
        "r":          "r-4.4.1",
    }

    try:
        body        = json.loads(request.body)
        language    = body.get("language", "python").strip().lower()
        source_code = body.get("source_code", "").strip()
        stdin       = body.get("stdin", "")

        if not source_code:
            return JsonResponse({"error": "No code provided."}, status=400)
        if len(source_code) > 200_000:
            return JsonResponse({"error": "Code too large (max 200 KB)."}, status=400)

        compiler = LANG_MAP.get(language, "cpython-3.12.7")

        payload = {
            "compiler": compiler,
            "code":     source_code,
            "stdin":    stdin,
        }

        resp = req.post(
            WANDBOX_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=20
        )
        resp.raise_for_status()
        data = resp.json()

        return JsonResponse({
            "stdout":  data.get("program_output", ""),
            "stderr":  data.get("program_error", ""),
            "compile": data.get("compiler_error", ""),
            "code":    int(data.get("status", "0") or "0"),
        })

    except req.Timeout:
        return JsonResponse({"error": "Execution timed out. Please try again."}, status=504)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
@require_http_methods(["GET", "POST"])
def ai_interviews(request):
    from .models import InterviewPreferences, UserProfile
    from django.core.files.base import ContentFile
    import os

    prefs, _ = InterviewPreferences.objects.get_or_create(user=request.user)

    # Pre-fill target_roles and interview_type from profile if prefs are empty
    if not prefs.target_roles or not prefs.interview_type:
        try:
            profile_obj = UserProfile.objects.get(user=request.user)
            if not prefs.target_roles:
                prefs.target_roles = profile_obj.target_roles
            if not prefs.interview_type:
                prefs.interview_type = profile_obj.interview_type
        except UserProfile.DoesNotExist:
            pass

    if request.method == "POST":
        action = request.POST.get("action", "save")

        if action == "reset":
            # Delete resume file from disk if present
            if prefs.resume:
                try:
                    if os.path.exists(prefs.resume.path):
                        os.remove(prefs.resume.path)
                except Exception:
                    pass
            prefs.delete()
            return redirect("ai_interviews")

        # save or start — both save preferences first
        prefs.target_roles    = request.POST.get("target_roles",   "").strip()
        prefs.extra_skills    = request.POST.get("extra_skills",   "").strip()
        prefs.job_description = request.POST.get("job_description","").strip()
        prefs.interview_type  = request.POST.get("interview_type", "").strip()
        prefs.tone            = request.POST.get("tone",           "standard").strip()
        prefs.depth           = request.POST.get("depth",          "quickfire").strip()
        try:
            prefs.num_questions = int(request.POST.get("num_questions", 10))
        except ValueError:
            prefs.num_questions = 10

        # Handle resume delete
        if request.POST.get("delete_resume") == "1" and prefs.resume:
            try:
                if os.path.exists(prefs.resume.path):
                    os.remove(prefs.resume.path)
            except Exception:
                pass
            prefs.resume = None

        prefs.save()

        # Handle resume upload
        if "resume" in request.FILES:
            resume_file = request.FILES["resume"]
            ext      = os.path.splitext(resume_file.name)[1].lower()
            new_name = f"temp@{request.user.username}{ext}"
            if prefs.resume:
                try:
                    if os.path.exists(prefs.resume.path):
                        os.remove(prefs.resume.path)
                except Exception:
                    pass
            content = ContentFile(resume_file.read(), name=new_name)
            prefs.resume.save(new_name, content, save=True)

        if action == "start":
            # ── Start live interview session ───────────────────────────────
            from .models import InterviewSession
            from .utils import get_resume_text, initialize_gemini_interview
            from django.core.files.base import ContentFile as CF
            import os as _os

            # Create session record first (need pk for resume path)
            session = InterviewSession.objects.create(
                user                 = request.user,
                target_roles         = prefs.target_roles,
                additional_skills    = prefs.extra_skills,
                job_description      = prefs.job_description,
                interview_preference = prefs.interview_type or "mix",
                interviewer_tone     = prefs.tone,
                question_depth       = prefs.depth,
                number_of_questions  = prefs.num_questions,
            )

            # No resume copy — get_resume_text() will read from prefs.resume or profile resume directly

            # Extract resume text & call Gemini
            resume_text = get_resume_text(session)
            try:
                ai_text, history = initialize_gemini_interview(session, resume_text)
                session.chat_history = history
                session.save()
                return redirect("interview_chat", session_id=session.id)
            except Exception as e:
                session.delete()
                return render(request, "placeme/ai_interviews.html", {
                    "prefs": prefs,
                    "error": f"Could not start session: {e}",
                    "interview_choices": [
                        ("technical",  "Technical"),
                        ("behavioral", "Behavioural"),
                        ("mix",        "Mix of Both"),
                    ],
                    "tone_choices": [
                        ("friendly", "😊 Friendly"),
                        ("standard", "🎯 Standard"),
                        ("strict",   "⚡ Strict"),
                    ],
                    "depth_choices": [
                        ("quickfire", "⚡ Quick-Fire"),
                        ("deepdive",  "🔍 Deep-Dive Scenarios"),
                    ],
                    "question_counts": [5, 10, 15, 20],
                })

        return redirect("/ai-interviews/?saved=1")

    ctx = {
        "prefs": prefs,
        "interview_choices": [
            ("technical",  "Technical"),
            ("behavioral", "Behavioural"),
            ("mix",        "Mix of Both"),
        ],
        "tone_choices": [
            ("friendly", "😊 Friendly"),
            ("standard", "🎯 Standard"),
            ("strict",   "⚡ Strict"),
        ],
        "depth_choices": [
            ("quickfire", "⚡ Quick-Fire"),
            ("deepdive",  "🔍 Deep-Dive Scenarios"),
        ],
        "question_counts": [5, 10, 15, 20],
    }
    return render(request, "placeme/ai_interviews.html", ctx)


@login_required
@require_http_methods(["GET", "POST"])
def contact_us(request):
    if request.method == "POST":
        name    = request.POST.get("name", "").strip()
        email   = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()

        # Basic validation
        errors = {}
        if not name:
            errors["name"] = "Please enter your name."
        if not email:
            errors["email"] = "Please enter your email."
        if not message:
            errors["message"] = "Please enter a message."

        if errors:
            return render(request, "placeme/contact_us.html", {
                "errors":  errors,
                "name":    name,
                "email":   email,
                "subject": subject,
                "message": message,
            })

        # Use logged-in username if available, else form name
        username = request.user.username if request.user.is_authenticated else name

        from .models import Feedback
        Feedback.objects.create(
            username=username,
            name=name,
            email=email,
            subject=subject,
            message=message,
        )

        return render(request, "placeme/contact_us.html", {"success": True})

    return render(request, "placeme/contact_us.html")


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    from .models import UserProfile, Education, Project, Internship
    from django.core.files.base import ContentFile
    import os

    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    action = request.POST.get("action", "save_profile")

    if request.method == "POST":

        # ── Save main profile ─────────────────────────────────────────────
        if action == "save_profile":
            profile_obj.full_name        = request.POST.get("full_name",        "").strip()
            profile_obj.headline         = request.POST.get("headline",         "").strip()
            profile_obj.skills           = request.POST.get("skills",           "").strip()
            profile_obj.experience_level = request.POST.get("experience_level", "").strip()
            profile_obj.phone            = request.POST.get("phone",            "").strip()
            profile_obj.location_city    = request.POST.get("location_city",    "").strip()
            profile_obj.location_country = request.POST.get("location_country", "").strip()
            profile_obj.linkedin         = request.POST.get("linkedin",         "").strip()
            profile_obj.github           = request.POST.get("github",           "").strip()
            profile_obj.portfolio        = request.POST.get("portfolio",        "").strip()
            profile_obj.target_roles     = request.POST.get("target_roles",     "").strip()
            profile_obj.interview_type   = request.POST.get("interview_type",   "").strip()

            if request.POST.get("delete_resume") == "1" and profile_obj.resume:
                try:
                    if os.path.exists(profile_obj.resume.path):
                        os.remove(profile_obj.resume.path)
                except Exception:
                    pass
                profile_obj.resume = None

            profile_obj.save()

            if "profile_pic" in request.FILES:
                pic_file = request.FILES["profile_pic"]
                ext      = os.path.splitext(pic_file.name)[1].lower()
                new_name = f"{request.user.username}{ext}"
                if profile_obj.profile_pic:
                    try:
                        if os.path.exists(profile_obj.profile_pic.path):
                            os.remove(profile_obj.profile_pic.path)
                    except Exception:
                        pass
                content = ContentFile(pic_file.read(), name=new_name)
                profile_obj.profile_pic.save(new_name, content, save=True)

            if "resume" in request.FILES:
                resume_file = request.FILES["resume"]
                ext         = os.path.splitext(resume_file.name)[1].lower()
                new_name    = f"{request.user.username}{ext}"
                if profile_obj.resume:
                    try:
                        if os.path.exists(profile_obj.resume.path):
                            os.remove(profile_obj.resume.path)
                    except Exception:
                        pass
                content = ContentFile(resume_file.read(), name=new_name)
                profile_obj.resume.save(new_name, content, save=True)

            return redirect("/profile/?saved=1")

        # ── Add education ─────────────────────────────────────────────────
        if action == "add_education":
            institution = request.POST.get("edu_institution", "").strip()
            if institution:
                Education.objects.create(
                    user        = request.user,
                    institution = institution,
                    degree      = request.POST.get("edu_degree",    "").strip(),
                    location    = request.POST.get("edu_location",  "").strip(),
                    from_year   = request.POST.get("edu_from_year", "").strip(),
                    to_year     = request.POST.get("edu_to_year",   "").strip(),
                    grade       = request.POST.get("edu_grade",     "").strip(),
                )
            return redirect("/profile/#education")

        # ── Delete education ──────────────────────────────────────────────
        if action == "delete_education":
            edu_id = request.POST.get("edu_id")
            Education.objects.filter(id=edu_id, user=request.user).delete()
            return redirect("/profile/#education")

        # ── Edit education ────────────────────────────────────────────────
        if action == "edit_education":
            edu_id = request.POST.get("edu_id")
            edu = Education.objects.filter(id=edu_id, user=request.user).first()
            if edu:
                edu.institution = request.POST.get("edu_institution", "").strip()
                edu.degree      = request.POST.get("edu_degree",      "").strip()
                edu.location    = request.POST.get("edu_location",    "").strip()
                edu.from_year   = request.POST.get("edu_from_year",   "").strip()
                edu.to_year     = request.POST.get("edu_to_year",     "").strip()
                edu.grade       = request.POST.get("edu_grade",       "").strip()
                edu.save()
            return redirect("/profile/#education")

        # ── Add project ───────────────────────────────────────────────────
        if action == "add_project":
            title = request.POST.get("proj_title", "").strip()
            if title:
                Project.objects.create(
                    user             = request.user,
                    title            = title,
                    completion_month = request.POST.get("proj_month",       "").strip(),
                    completion_year  = request.POST.get("proj_year",        "").strip(),
                    skills_used      = request.POST.get("proj_skills",      "").strip(),
                    description      = request.POST.get("proj_description", "").strip(),
                )
            return redirect("/profile/#projects")

        # ── Delete project ────────────────────────────────────────────────
        if action == "delete_project":
            proj_id = request.POST.get("proj_id")
            Project.objects.filter(id=proj_id, user=request.user).delete()
            return redirect("/profile/#projects")

        # ── Edit project ──────────────────────────────────────────────────
        if action == "edit_project":
            proj_id = request.POST.get("proj_id")
            proj = Project.objects.filter(id=proj_id, user=request.user).first()
            if proj:
                proj.title            = request.POST.get("proj_title",       "").strip()
                proj.completion_month = request.POST.get("proj_month",       "").strip()
                proj.completion_year  = request.POST.get("proj_year",        "").strip()
                proj.skills_used      = request.POST.get("proj_skills",      "").strip()
                proj.description      = request.POST.get("proj_description", "").strip()
                proj.save()
            return redirect("/profile/#projects")

        # ── Add internship ────────────────────────────────────────────────
        if action == "add_internship":
            company = request.POST.get("int_company", "").strip()
            if company:
                Internship.objects.create(
                    user        = request.user,
                    company     = company,
                    role        = request.POST.get("int_role",       "").strip(),
                    location    = request.POST.get("int_location",   "").strip(),
                    from_month  = request.POST.get("int_from_month", "").strip(),
                    from_year   = request.POST.get("int_from_year",  "").strip(),
                    to_month    = request.POST.get("int_to_month",   "").strip(),
                    to_year     = request.POST.get("int_to_year",    "").strip(),
                )
            return redirect("/profile/#internships")

        # ── Delete internship ─────────────────────────────────────────────
        if action == "delete_internship":
            int_id = request.POST.get("int_id")
            Internship.objects.filter(id=int_id, user=request.user).delete()
            return redirect("/profile/#internships")

        # ── Edit internship ───────────────────────────────────────────────
        if action == "edit_internship":
            int_id = request.POST.get("int_id")
            intern = Internship.objects.filter(id=int_id, user=request.user).first()
            if intern:
                intern.company    = request.POST.get("int_company",    "").strip()
                intern.role       = request.POST.get("int_role",       "").strip()
                intern.location   = request.POST.get("int_location",   "").strip()
                intern.from_month = request.POST.get("int_from_month", "").strip()
                intern.from_year  = request.POST.get("int_from_year",  "").strip()
                intern.to_month   = request.POST.get("int_to_month",   "").strip()
                intern.to_year    = request.POST.get("int_to_year",    "").strip()
                intern.save()
            return redirect("/profile/#internships")

        return redirect("profile")

    # ── GET ───────────────────────────────────────────────────────────────
    ctx = {
        "p":            profile_obj,
        "educations":   Education.objects.filter(user=request.user),
        "projects":     Project.objects.filter(user=request.user),
        "internships":  Internship.objects.filter(user=request.user),
        "degree_choices": [
            ("10th",      "10th"),
            ("12th",      "12th"),
            ("diploma",   "Diploma"),
            ("bachelors", "Bachelor's"),
            ("masters",   "Master's"),
            ("phd",       "PhD"),
            ("other",     "Other"),
        ],
        "month_choices": [
            "January","February","March","April","May","June",
            "July","August","September","October","November","December",
        ],
        "year_choices": [str(y) for y in range(2030, 1979, -1)],
        "experience_choices": [
            ("fresher", "Fresher"),
            ("1-3",     "1–3 Years"),
            ("3-5",     "3–5 Years"),
            ("senior",  "Senior (5+ Years)"),
        ],
        "interview_choices": [
            ("technical",  "Technical"),
            ("behavioral", "Behavioural"),
            ("mix",        "Mix of Both"),
        ],
    }
    return render(request, "placeme/profile.html", ctx)



@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("landing")


# ---------------------------------------------------------------------------
# Interview chat page
# ---------------------------------------------------------------------------

@login_required
def interview_chat(request, session_id):
    from .models import InterviewSession
    try:
        session = InterviewSession.objects.get(id=session_id, user=request.user)
    except InterviewSession.DoesNotExist:
        return redirect("ai_interviews")

    # Build display-friendly chat history (skip the system prompt at index 0)
    display_history = []
    raw = session.chat_history
    # raw[0] = system prompt (user role), raw[1] = AI opening (model role)
    # From index 1 onwards: alternate model/user/model/user...
    for msg in raw[1:]:   # skip system prompt
        display_history.append({
            "role": msg.get("role"),
            "text": msg.get("text", ""),
        })

    # Timer: 3 minutes per question
    total_seconds = session.number_of_questions * 3 * 60

    ctx = {
        "session":         session,
        "display_history": display_history,
        "total_seconds":   total_seconds,
    }
    return render(request, "placeme/interview_chat.html", ctx)


# ---------------------------------------------------------------------------
# AJAX message endpoint
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def messages_api(request, session_id):
    import json
    from django.http import JsonResponse
    from .models import InterviewSession
    from .utils import send_message_to_gemini, classify_message, get_last_question, _client

    try:
        session = InterviewSession.objects.get(id=session_id, user=request.user)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "Session not found."}, status=404)

    # If already fully scored, just return the existing score
    if not session.is_active and session.score is not None:
        return JsonResponse({
            "message":     "",
            "is_finished": True,
            "score":       session.score,
            "feedback":    session.feedback,
        })

    try:
        body         = json.loads(request.body)
        user_message = body.get("message", "").strip()
    except (json.JSONDecodeError, AttributeError):
        user_message = request.POST.get("message", "").strip()

    if not user_message:
        return JsonResponse({"error": "Empty message."}, status=400)

    # If already fully scored, just return the existing score — no need to call Gemini again
    if not session.is_active and session.score is not None:
        return JsonResponse({
            "message":     "",
            "is_finished": True,
            "score":       session.score,
            "feedback":    session.feedback,
        })

    # If session is inactive but not yet scored (edge case), fall through to score it
    if not session.is_active or session.current_question_count >= session.number_of_questions or \
       "submitted the interview early" in user_message or "time has expired" in user_message:

        wrap_prompt = (
            "The candidate has submitted their interview. "
            "Please give a brief, warm closing message. "
            "Do NOT ask any more questions."
        )
        try:
            ai_text, updated_history = send_message_to_gemini(session, wrap_prompt)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

        session.chat_history = updated_history
        session.is_active    = False
        session.save()

        # Generate score and feedback for early/time-up submissions too
        from .utils import generate_score_and_feedback
        result = generate_score_and_feedback(session)
        session.score    = result["score"]
        session.feedback = {
            "tech":       result["tech"],
            "coding":     result["coding"],
            "grammar":    result["grammar"],
            "weak_areas": result.get("weak_areas", []),
        }
        session.save()

        return JsonResponse({
            "message":     ai_text,
            "is_finished": True,
            "score":       result["score"],
            "feedback":    session.feedback,
        })

    # ── Classify: is this a real answer or filler? ────────────────────────
    client        = _client()
    last_question = get_last_question(session.chat_history)
    is_real_answer = classify_message(client, user_message, last_question)

    # Send message to AI (it will respond appropriately either way)
    try:
        ai_text, updated_history = send_message_to_gemini(session, user_message)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    session.chat_history = updated_history

    # Only increment counter for genuine answers
    if is_real_answer:
        session.current_question_count += 1

    # Wrap up AFTER the last genuine answer has been received
    if is_real_answer and session.current_question_count >= session.number_of_questions:
        wrap_prompt = (
            f"The candidate has now genuinely answered all {session.number_of_questions} interview questions. "
            f"Please give a brief, warm, professional closing message to conclude the interview. "
            f"Do NOT ask any more questions under any circumstances."
        )
        try:
            closing_text, updated_history = send_message_to_gemini(session, wrap_prompt)
            session.chat_history = updated_history
            session.is_active    = False
            session.save()

            # Generate score and feedback
            from .utils import generate_score_and_feedback
            result = generate_score_and_feedback(session)
            session.score    = result["score"]
            session.feedback = {
                "tech":       result["tech"],
                "coding":     result["coding"],
                "grammar":    result["grammar"],
                "weak_areas": result.get("weak_areas", []),
            }
            session.save()

            combined = f"{ai_text}\n\n{closing_text}"
            return JsonResponse({
                "message":     combined,
                "is_finished": True,
                "score":       result["score"],
                "feedback":    session.feedback,
            })
        except Exception:
            session.is_active = False
            session.save()
            return JsonResponse({"message": ai_text, "is_finished": True})

    session.save()
    return JsonResponse({
        "message":     ai_text,
        "is_finished": False,
        "q_count":     session.current_question_count,
        "q_total":     session.number_of_questions,
    })


# ---------------------------------------------------------------------------
# Forgot password — handles both email-link flow and OTP flow
# ---------------------------------------------------------------------------

def _lookup_user(username_email):
    """Return a User by username or email, or None if not found."""
    username_email = username_email.strip()
    try:
        return User.objects.get(username=username_email)
    except User.DoesNotExist:
        pass
    try:
        return User.objects.get(email=username_email)
    except User.DoesNotExist:
        return None


@require_http_methods(["GET", "POST"])
def forgot_password_view(request):
    if request.method == "GET":
        return render(request, "placeme/forgot_password.html")

    username_email = request.POST.get("username_email", "").strip()

    # ── Flow 1: generate OTP, email it, redirect to entry form ───────────
    if "send_reset_link" in request.POST:
        user = _lookup_user(username_email)
        if user is None:
            return render(request, "placeme/forgot_password.html", {
                "error": "No account found with that username or email."
            })

        # Generate OTP and store in session (same mechanism as OTP flow)
        otp = "".join(random.choices(string.digits, k=4))
        request.session["reset_otp"]     = otp
        request.session["reset_user_id"] = user.id

        # Email the OTP
        body = render_to_string("placeme/password_reset_email.html", {
            "user":      user,
            "otp":       otp,
            "site_name": getattr(settings, "SITE_NAME", "PlaceMe AI"),
        })

        send_mail(
            subject=f"Your {getattr(settings, 'SITE_NAME', 'PlaceMe AI')} password reset code",
            message=f"Hi {user.username}, your password reset code is: {otp}",  # plain-text fallback
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=body,
            fail_silently=False,
        )

        # Redirect to OTP entry form — otp NOT shown on screen
        return render(request, "placeme/forgot_password.html", {
            "otp_sent":        True,
            "otp_via_email":   True,   # hides the on-screen OTP box
            "username_email":  username_email,
        })

    # ── Flow 2 step 2: verify OTP + set new password ───────────────────────
    if "reset_password" in request.POST:
        stored_otp = request.session.get("reset_otp")
        user_id    = request.session.get("reset_user_id")
        entered_otp      = request.POST.get("otp", "").strip()
        new_password     = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        def otp_error(msg):
            return render(request, "placeme/forgot_password.html", {
                "otp_sent":       True,
                "otp_via_email":  True,
                "username_email": username_email,
                "error":          msg,
            })

        if not stored_otp or not user_id:
            return otp_error("Session expired. Please start over.")

        if entered_otp != stored_otp:
            return otp_error("Incorrect OTP. Please try again.")

        if not new_password:
            return otp_error("Please enter a new password.")

        if new_password != confirm_password:
            return otp_error("Passwords do not match.")

        import re
        if len(new_password) < 8:
            return otp_error("Password must be at least 8 characters long.")
        if not re.search(r'[a-z]', new_password):
            return otp_error("Password must contain at least one lowercase letter.")
        if not re.search(r'[A-Z]', new_password):
            return otp_error("Password must contain at least one uppercase letter.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            return otp_error("Password must contain at least one special character.")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return otp_error("Account not found. Please start over.")

        user.set_password(new_password)
        user.save()

        # Clean up session
        del request.session["reset_otp"]
        del request.session["reset_user_id"]

        return redirect("login")

    # Fallback — unknown POST action
    return render(request, "placeme/forgot_password.html")


# ---------------------------------------------------------------------------
# Password reset confirm — validates email link token, sets new password
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def password_reset_confirm_view(request, uidb64, token):
    # Decode uid and validate token
    try:
        uid  = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid = user is not None and default_token_generator.check_token(user, token)

    if request.method == "GET":
        return render(request, "placeme/password_reset_confirm.html", {
            "validlink": valid,
        })

    # POST — set the new password
    if not valid:
        return render(request, "placeme/password_reset_confirm.html", {
            "validlink": False,
        })

    new_password     = request.POST.get("new_password", "")
    confirm_password = request.POST.get("confirm_password", "")

    if not new_password:
        return render(request, "placeme/password_reset_confirm.html", {
            "validlink": True,
            "error": "Please enter a new password.",
        })

    if new_password != confirm_password:
        return render(request, "placeme/password_reset_confirm.html", {
            "validlink": True,
            "error": "Passwords do not match.",
        })

    import re
    if len(new_password) < 8:
        return render(request, "placeme/password_reset_confirm.html", {"validlink": True, "error": "Password must be at least 8 characters long."})
    if not re.search(r'[a-z]', new_password):
        return render(request, "placeme/password_reset_confirm.html", {"validlink": True, "error": "Password must contain at least one lowercase letter."})
    if not re.search(r'[A-Z]', new_password):
        return render(request, "placeme/password_reset_confirm.html", {"validlink": True, "error": "Password must contain at least one uppercase letter."})
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
        return render(request, "placeme/password_reset_confirm.html", {"validlink": True, "error": "Password must contain at least one special character."})

    user.set_password(new_password)
    user.save()

    return redirect("login")







# ---------------------------------------------------------------------------
# User reviews — submit + fetch
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def submit_review(request):
    import json
    from django.http import JsonResponse
    from .models import UserReview

    name    = request.POST.get("name", "").strip()
    role    = request.POST.get("role", "").strip()
    message = request.POST.get("message", "").strip()

    if not name:
        return JsonResponse({"success": False, "error": "Please enter your name."}, status=400)
    if not message:
        return JsonResponse({"success": False, "error": "Please enter your experience."}, status=400)

    review = UserReview.objects.create(
        user    = request.user,
        name    = name,
        role    = role,
        message = message,
    )

    return JsonResponse({
        "success": True,
        "review": {
            "id":         review.id,
            "name":       review.name,
            "role":       review.role,
            "message":    review.message,
            "created_at": review.created_at.strftime("%d %b %Y"),
        }
    })


def get_reviews(request):
    """Public endpoint — returns latest 3 reviews as JSON for landing page polling."""
    from django.http import JsonResponse
    from .models import UserReview

    reviews = UserReview.objects.select_related("user").order_by("-created_at")[:3]
    data = [
        {
            "id":         r.id,
            "name":       r.name,
            "role":       r.role or "Candidate",
            "message":    r.message,
            "created_at": r.created_at.strftime("%d %b %Y"),
        }
        for r in reviews
    ]
    return JsonResponse({"success": True, "reviews": data})
