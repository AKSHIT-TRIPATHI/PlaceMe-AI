from django.db import models
from django.contrib.auth.models import User


# ── Feedback ───────────────────────────────────────────────────────────────

class Feedback(models.Model):
    username   = models.CharField(max_length=150)
    name       = models.CharField(max_length=255, blank=True, default="")
    email      = models.EmailField()
    subject    = models.CharField(max_length=255, blank=True, default="")
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read    = models.BooleanField(default=False)

    class Meta:
        db_table = "feedback"
        ordering = ["-created_at"]

    def __str__(self):
        display = self.name or self.username
        return f"{display} (@{self.username}) — {self.subject or 'No subject'} ({self.created_at:%Y-%m-%d %H:%M})"


# ── UserProfile ────────────────────────────────────────────────────────────

EXPERIENCE_CHOICES = [
    ("fresher", "Fresher"),
    ("1-3",     "1–3 Years"),
    ("3-5",     "3–5 Years"),
    ("senior",  "Senior (5+ Years)"),
]

INTERVIEW_TYPE_CHOICES = [
    ("technical",  "Technical"),
    ("behavioral", "Behavioural"),
    ("mix",        "Mix of Both"),
]


def profile_pic_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"profile_pics/{instance.user.username}.{ext}"


def resume_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"resumes/{instance.user.username}.{ext}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Section 1: Basic Identity
    full_name   = models.CharField(max_length=255, blank=True, default="")
    headline    = models.CharField(max_length=255, blank=True, default="")
    profile_pic = models.ImageField(upload_to=profile_pic_path, blank=True, null=True)

    # Section 2: Resume
    resume = models.FileField(upload_to=resume_path, blank=True, null=True)

    # Section 3: Skills (comma-separated list)
    skills = models.TextField(blank=True, default="")

    # Section 4: Experience level
    experience_level = models.CharField(max_length=20, blank=True, default="",
                           choices=EXPERIENCE_CHOICES)

    # Section 5: Contact & Links
    phone            = models.CharField(max_length=30,  blank=True, default="")
    location_city    = models.CharField(max_length=100, blank=True, default="")
    location_country = models.CharField(max_length=100, blank=True, default="")
    linkedin         = models.URLField(blank=True, default="")
    github           = models.URLField(blank=True, default="")
    portfolio        = models.URLField(blank=True, default="")

    # Section 6: PlaceMe AI Settings
    target_roles   = models.CharField(max_length=255, blank=True, default="")
    interview_type = models.CharField(max_length=20,  blank=True, default="",
                         choices=INTERVIEW_TYPE_CHOICES)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profile"

    def __str__(self):
        return f"{self.user.username} — {self.full_name or 'No name set'}"

    def skills_list(self):
        """Return skills as a clean list, stripping blanks."""
        return [s.strip() for s in self.skills.split(",") if s.strip()]


# ── Education ──────────────────────────────────────────────────────────────

DEGREE_CHOICES = [
    ("10th",        "10th"),
    ("12th",        "12th"),
    ("diploma",     "Diploma"),
    ("bachelors",   "Bachelor's"),
    ("masters",     "Master's"),
    ("phd",         "PhD"),
    ("other",       "Other"),
]


class Education(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="educations")
    institution = models.CharField(max_length=255)
    degree      = models.CharField(max_length=20, choices=DEGREE_CHOICES)
    location    = models.CharField(max_length=255, blank=True, default="")
    from_year   = models.CharField(max_length=7,  blank=True, default="")  # e.g. "2020"
    to_year     = models.CharField(max_length=7,  blank=True, default="")  # e.g. "2024" or "Present"
    grade       = models.CharField(max_length=50, blank=True, default="")  # e.g. "8.5 CGPA" or "85%"
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "education"
        ordering = ["-from_year"]

    def __str__(self):
        return f"{self.user.username} — {self.get_degree_display()} @ {self.institution}"


# ── Project ────────────────────────────────────────────────────────────────

class Project(models.Model):
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    title           = models.CharField(max_length=255)
    completion_month = models.CharField(max_length=20, blank=True, default="")  # e.g. "March"
    completion_year  = models.CharField(max_length=4,  blank=True, default="")  # e.g. "2024"
    skills_used     = models.CharField(max_length=500, blank=True, default="")  # comma-separated
    description     = models.TextField(blank=True, default="")
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project"
        ordering = ["-completion_year", "-completion_month"]

    def __str__(self):
        return f"{self.user.username} — {self.title}"

    def skills_list(self):
        return [s.strip() for s in self.skills_used.split(",") if s.strip()]


# ── InterviewPreferences ───────────────────────────────────────────────────

def interview_resume_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"interview_resumes/temp@{instance.user.username}.{ext}"


class InterviewPreferences(models.Model):
    TONE_CHOICES = [
        ("friendly", "Friendly"),
        ("standard", "Standard"),
        ("strict",   "Strict"),
    ]
    DEPTH_CHOICES = [
        ("quickfire", "Quick-Fire"),
        ("deepdive",  "Deep-Dive Scenarios"),
    ]
    QUESTION_COUNT_CHOICES = [
        (5,  "5"),
        (10, "10"),
        (15, "15"),
        (20, "20"),
    ]

    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name="interview_prefs")
    target_roles     = models.CharField(max_length=255, blank=True, default="")
    extra_skills     = models.CharField(max_length=500, blank=True, default="")   # comma-separated
    job_description  = models.TextField(blank=True, default="")
    interview_type   = models.CharField(max_length=20,  blank=True, default="",
                           choices=INTERVIEW_TYPE_CHOICES)
    tone             = models.CharField(max_length=20,  blank=True, default="standard",
                           choices=TONE_CHOICES)
    depth            = models.CharField(max_length=20,  blank=True, default="quickfire",
                           choices=DEPTH_CHOICES)
    num_questions    = models.IntegerField(default=10)
    resume           = models.FileField(upload_to=interview_resume_path, blank=True, null=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interview_preferences"

    def __str__(self):
        return f"{self.user.username} — interview prefs"

    def extra_skills_list(self):
        return [s.strip() for s in self.extra_skills.split(",") if s.strip()]


# ── InterviewSession ───────────────────────────────────────────────────────

def session_resume_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"session_resumes/session_{instance.user.username}.{ext}"


class InterviewSession(models.Model):
    PREF_CHOICES = [
        ("technical",  "Technical"),
        ("behavioral", "Behavioural"),
        ("mix",        "Mix of Both"),
    ]
    TONE_CHOICES = [
        ("friendly", "Friendly"),
        ("standard", "Standard"),
        ("strict",   "Strict"),
    ]
    DEPTH_CHOICES = [
        ("quickfire", "Quick-Fire"),
        ("deepdive",  "Deep-Dive Scenarios"),
    ]
    NUM_CHOICES = [(5, "5"), (10, "10"), (15, "15"), (20, "20")]

    user                   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interview_sessions")
    target_roles           = models.CharField(max_length=255, blank=True, default="")
    additional_skills      = models.CharField(max_length=500, blank=True, default="")
    job_description        = models.TextField(blank=True, default="")
    interview_preference   = models.CharField(max_length=20, choices=PREF_CHOICES, default="mix")
    interviewer_tone       = models.CharField(max_length=20, choices=TONE_CHOICES, default="standard")
    question_depth         = models.CharField(max_length=20, choices=DEPTH_CHOICES, default="quickfire")
    number_of_questions    = models.IntegerField(choices=NUM_CHOICES, default=10)
    resume_file            = models.FileField(upload_to=session_resume_path, blank=True, null=True)
    chat_history           = models.JSONField(default=list)
    current_question_count = models.IntegerField(default=0)
    is_active              = models.BooleanField(default=True)
    score                  = models.IntegerField(null=True, blank=True)          # 0-100
    feedback               = models.JSONField(default=dict, blank=True)          # {tech, coding, grammar}
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "interview_session"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} — session #{self.id} ({self.created_at:%Y-%m-%d %H:%M})"


# ── UserReview ─────────────────────────────────────────────────────────────

class UserReview(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    name       = models.CharField(max_length=255)          # display name (can differ from username)
    role       = models.CharField(max_length=255, blank=True, default="")  # e.g. "Software Engineering"
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_review"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} (@{self.user.username}) — {self.created_at:%Y-%m-%d %H:%M}"


class Internship(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name="internships")
    company      = models.CharField(max_length=255)
    role         = models.CharField(max_length=255)
    location     = models.CharField(max_length=255, blank=True, default="")
    from_month   = models.CharField(max_length=20, blank=True, default="")
    from_year    = models.CharField(max_length=4,  blank=True, default="")
    to_month     = models.CharField(max_length=20, blank=True, default="")
    to_year      = models.CharField(max_length=4,  blank=True, default="")
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "internship"
        ordering = ["-from_year", "-from_month"]

    def __str__(self):
        return f"{self.user.username} — {self.role} @ {self.company}"

    def duration(self):
        start = f"{self.from_month} {self.from_year}".strip()
        end   = f"{self.to_month} {self.to_year}".strip() or "Present"
        return f"{start} – {end}"
