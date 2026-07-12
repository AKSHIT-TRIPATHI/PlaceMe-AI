from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("results/", views.results, name="results"),
    path("coding-practice/", views.coding_practice, name="coding_practice"),
    path("coding-practice/run/", views.piston_run, name="piston_run"),
    path("ai-interviews/", views.ai_interviews, name="ai_interviews"),
    path("ai-interviews/chat/<int:session_id>/", views.interview_chat, name="interview_chat"),
    path("ai-interviews/chat/<int:session_id>/message/", views.messages_api, name="messages_api"),
    path("contact-us/", views.contact_us, name="contact_us"),
    path("profile/", views.profile, name="profile"),

    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),

    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("password_reset_confirm/<uidb64>/<token>/", views.password_reset_confirm_view, name="password_reset_confirm"),

    path("reviews/submit/", views.submit_review, name="submit_review"),
    path("reviews/latest/", views.get_reviews,   name="get_reviews"),
]


