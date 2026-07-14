from django.contrib import admin
from .models import Feedback, UserProfile, Education, Project, Internship, InterviewPreferences, InterviewSession


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display    = ("name", "username", "email", "subject", "created_at", "is_read")
    list_filter     = ("is_read", "created_at")
    search_fields   = ("name", "username", "email", "subject", "message")
    readonly_fields = ("name", "username", "email", "subject", "message", "created_at")
    ordering        = ("-created_at",)
    actions = ["mark_as_read"]

    @admin.action(description="Mark selected messages as read")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display    = ("user", "full_name", "headline", "experience_level",
                       "location_city", "location_country", "updated_at")
    list_filter     = ("experience_level", "interview_type")
    search_fields   = ("user__username", "full_name", "skills", "target_roles")
    readonly_fields = ("updated_at",)
    fieldsets = (
        ("Account",           {"fields": ("user",)}),
        ("Basic Identity",    {"fields": ("full_name", "headline", "profile_pic")}),
        ("Resume",            {"fields": ("resume",)}),
        ("Skills",            {"fields": ("skills",)}),
        ("Experience",        {"fields": ("experience_level",)}),
        ("Contact & Links",   {"fields": ("phone", "location_city", "location_country",
                                           "linkedin", "github", "portfolio")}),
        ("PlaceMe AI",        {"fields": ("target_roles", "interview_type")}),
        ("Meta",              {"fields": ("updated_at",)}),
    )


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display  = ("user", "institution", "degree", "from_year", "to_year",
                     "grade", "location", "created_at")
    list_filter   = ("degree",)
    search_fields = ("user__username", "institution", "location")
    ordering      = ("-created_at",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ("user", "title", "completion_month", "completion_year",
                     "skills_used", "created_at")
    search_fields = ("user__username", "title", "skills_used")
    ordering      = ("-created_at",)


@admin.register(Internship)
class InternshipAdmin(admin.ModelAdmin):
    list_display  = ("user", "company", "role", "location",
                     "from_month", "from_year", "to_month", "to_year", "created_at")
    search_fields = ("user__username", "company", "role", "location")
    ordering      = ("-created_at",)


@admin.register(InterviewPreferences)
class InterviewPreferencesAdmin(admin.ModelAdmin):
    list_display  = ("user", "target_roles", "interview_type", "tone",
                     "depth", "num_questions", "updated_at")
    list_filter   = ("interview_type", "tone", "depth", "num_questions")
    search_fields = ("user__username", "target_roles", "extra_skills")
    readonly_fields = ("updated_at",)


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display   = ("user", "interview_preference", "interviewer_tone",
                      "question_depth", "number_of_questions",
                      "current_question_count", "is_active", "created_at")
    list_filter    = ("interview_preference", "interviewer_tone", "is_active")
    search_fields  = ("user__username", "target_roles")
    readonly_fields = ("chat_history", "created_at")
    ordering       = ("-created_at",)
