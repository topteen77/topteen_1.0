"""
Structured admin navigation for TopTeen.

Splits the admin into two primary hubs:
  - Website & platform configuration
  - Day-to-day operations and content management

Links are permission-aware and searchable so staff do not hunt through the flat app list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional
import re

from django.apps import apps
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import NoReverseMatch, path, reverse

from core import choices


LinkBuilder = Callable[[HttpRequest], Optional[dict]]


@dataclass
class HubLink:
    label: str
    description: str = ""
    url_name: str = ""
    url: str = ""
    url_kwargs: dict = field(default_factory=dict)
    staff_only: bool = False
    superuser_only: bool = False
    app_label: str = ""
    model_name: str = ""

    def resolve(self, request: HttpRequest) -> Optional[dict]:
        if self.superuser_only and not request.user.is_superuser:
            return None
        if self.staff_only and not request.user.is_staff:
            return None

        if self.app_label and self.model_name:
            if not _user_can_access_model(request, self.app_label, self.model_name):
                return None
            try:
                url = reverse(
                    f"admin:{self.app_label}_{self.model_name.lower()}_changelist"
                )
            except NoReverseMatch:
                return None
        elif self.url_name:
            try:
                url = reverse(self.url_name, kwargs=self.url_kwargs or None)
            except NoReverseMatch:
                return None
        elif self.url:
            url = self.url
        else:
            return None

        return {
            "label": self.label,
            "description": self.description,
            "url": url,
            "search_text": f"{self.label} {self.description}".lower(),
        }


@dataclass
class HubSection:
    title: str
    description: str
    links: list[HubLink] = field(default_factory=list)
    instruction: str = ""

    def resolve(self, request: HttpRequest) -> Optional[dict]:
        resolved = []
        for link in self.links:
            item = link.resolve(request)
            if item:
                resolved.append(item)
        if not resolved:
            return None
        section_id = section_slug(self.title)
        return {
            "title": self.title,
            "description": self.description,
            "instruction": self.instruction,
            "section_id": section_id,
            "links": resolved,
        }


def section_slug(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    return re.sub(r"[-\s]+", "-", slug).strip("-")


def _user_can_access_model(request: HttpRequest, app_label: str, model_name: str) -> bool:
    if request.user.is_superuser:
        return True
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return False
    if model is None:
        return False
    opts = model._meta
    return request.user.has_perm(f"{opts.app_label}.view_{opts.model_name}") or request.user.has_perm(
        f"{opts.app_label}.change_{opts.model_name}"
    )


def _named(label: str, url_name: str, description: str = "", **kwargs) -> HubLink:
    return HubLink(label=label, url_name=url_name, description=description, **kwargs)


def _model(label: str, app_label: str, model_name: str, description: str = "") -> HubLink:
    return HubLink(
        label=label,
        app_label=app_label,
        model_name=model_name,
        description=description,
    )


def _external(label: str, url: str, description: str = "", **kwargs) -> HubLink:
    return HubLink(label=label, url=url, description=description, **kwargs)


CONFIGURATION_SECTIONS: list[HubSection] = [
    HubSection(
        title="AI tokens & freemium",
        description="Sellable AI packs, USD→INR pricing, role free quotas, wallets, and billing.",
        instruction=(
            "1) Open “Shop display (rate & notes)” to set USD→INR and hide "
            "“Current rate” / conversion notes on /ai-tokens/. "
            "2) Edit LLM token packages (use-case lines buyers see). "
            "3) Set monthly free tokens per role. "
            "4) Use admin grants / wallets for one-off top-ups. "
            "5) Open AI Cost / LLM Billing for spend vs pack sales."
        ),
        links=[
            _named(
                "Shop display (rate & notes)",
                "admin:core_configuration_llm_shop_display",
                "Hide Current rate / conversion notes on /ai-tokens/; set USD→INR and price visibility.",
            ),
            _named("AI Cost / LLM Billing", "admin:core_configuration_llm_billing", "Token usage and estimated provider spend vs pack sales."),
            _model("LLM token packages", "core", "LLMTokenPackage", "Spark/Boost/Power packs — buyer use cases + USD price."),
            _model("LLM pricing settings", "core", "LLMPricingSettings", "Same FX + show/hide toggles (model record)."),
            _model("LLM role quotas", "core", "LLMRoleQuotaDefault", "Default monthly free tokens per role (student, staff, …)."),
            _model(
                "AI feature quotas",
                "core",
                "AIFeatureQuotaSettings",
                "Student/parent limits: resume free tier, AI Counselor & Chat-with-page caps.",
            ),
            _model("User AI feature usage", "core", "UserAIFeatureUsage", "Per-user feature counters and purchase bonuses."),
            _model("LLM admin grants", "core", "LLMAdminGrant", "Manually grant AI tokens to any user."),
            _model("User LLM wallets", "core", "UserLLMWallet", "Per-user AI token balances."),
            _model("LLM package payments", "core", "LLMTokenPackagePayment", "Token pack purchase records."),
            _model("LLM usage logs", "core", "LLMUsageLog", "Per-call token and cost ledger."),
            _model("LLM wallet ledger", "core", "LLMWalletLedger", "Credits and debits for every wallet change."),
        ],
    ),
    HubSection(
        title="Website & branding",
        description="Global switches, language bar, and public-facing site content settings.",
        instruction="Start with Core website settings and Language bar. Use Configuration keys only for advanced toggles.",
        links=[
            _named("Core website settings", "admin:core_configuration_website_settings", "Feature toggles for the public site."),
            _named("Language bar settings", "admin:core_configuration_language_bar_settings", "Languages shown in the header selector."),
            _model("Configuration keys", "core", "Configuration", "Advanced key-value platform settings."),
            _model("Common FAQs", "core", "CommonFAQ", "FAQ entries shown across the website."),
            _model("Stories", "core", "Stories", "Success stories and testimonials."),
            _model("Reviews", "core", "Review", "User reviews displayed on the site."),
        ],
    ),
    HubSection(
        title="Voice to text settings",
        description="Site-wide microphone speech-to-text for Notebook, login fields, profile voice bar, and notes.",
        instruction=(
            "Choose Disabled, Browser speech (free Chrome/Edge), or OpenAI gpt-4o-mini-transcribe "
            "(cloud; needs OPENAI_API_KEY; works on iPhone). Changes apply immediately."
        ),
        links=[
            _named(
                "Voice-to-text mode",
                "admin:core_configuration_voice_to_text_settings",
                "Switch off / browser Web Speech / OpenAI cloud transcription.",
            ),
        ],
    ),
    HubSection(
        title="Student dashboard & gamification",
        description="Dashboard stats, student IDs, and reward mechanics.",
        instruction="Set student ID prefixes first, then tune level bands, points, trophies, and streaks on one screen each.",
        links=[
            _named("Dashboard statistics", "admin:core_configuration_dashboard_statistics", "Aggregated dashboard counters."),
            _named("Student ID settings", "admin:core_configuration_student_id_settings", "Student and school ID prefixes."),
            _model("Dashboard level bands", "gamification", "DashboardLevelBand", "XP level thresholds."),
            _model("Dashboard point rules", "gamification", "DashboardPointRule", "Points awarded per action."),
            _model("Dashboard trophies", "gamification", "DashboardTrophyDefinition", "Achievement trophies."),
            _model("Dashboard streak config", "gamification", "DashboardStreakConfig", "Login streak rewards."),
        ],
    ),
    HubSection(
        title="Assessments & reports",
        description="Psychometric, aptitude, and assessment report configuration.",
        instruction="Use the report settings pages for display rules. Open individual assessment models only when editing test content.",
        links=[
            _named("Psychometric test settings", "admin:core_configuration_psychometric_settings", "Central test and psychometric options."),
            _named("Class 10 aptitude report settings", "admin:core_configuration_class10_aptitude_report_settings", "Stream display and Class 10 report options."),
            _named("Class 12 aptitude report settings", "admin:core_configuration_class12_aptitude_report_settings", "Consolidated Class 12 report options."),
            _model("Class 10 report guidance", "app", "Class10ReportGuidanceSettings", "Premium stream guidance copy."),
            _model("Class 10 premium streams", "app", "Class10PremiumStream", "Stream tiers for Class 10 guidance."),
            _model("Four pillars assessments", "core", "FourPillarsAssessment", "Four pillars test definitions."),
            _model("Four pillars scoring guides", "core", "FourPillarsAssessmentScoringGuide", "Scoring rules per assessment."),
            _model("Aptitude improvement plans", "app", "AptitudeImprovementPlan", "Post-report improvement content."),
            _model("Class 12 consolidated reports", "app", "Class12AptitudeConsolidatedReport", "Uploaded consolidated report data."),
        ],
    ),
    HubSection(
        title="SEO & static pages",
        description="Page content, SEO metadata, indexing rules, and the SEO dashboard.",
        instruction="Prefer the SEO dashboard for page copy and meta tags. Use Static pages and Page SEO here for bulk admin edits.",
        links=[
            _external("SEO dashboard (CMS)", "/seo-dashboard/", "Visual editor for page content and SEO.", staff_only=True),
            _model("Static pages", "core", "StaticPage", "CMS static page records."),
            _model("Page SEO", "core", "PageSEO", "Meta titles, descriptions, and keywords."),
            _model("URL index rules", "core", "URLIndexRule", "Robots/indexing rules per URL pattern."),
            _model("Generated pages", "core", "GeneratedPage", "Auto-generated landing pages."),
            _model("Scanned URLs", "core", "ScannedURL", "URLs discovered by the SEO scanner."),
        ],
    ),
    HubSection(
        title="Communications & notifications",
        description="Email templates, OTP logs, and in-app notification setup.",
        instruction="Edit templates here; view Communication logs to audit what was sent.",
        links=[
            _model("SMS settings", "communication", "SmsSettings", "SMS provider, credentials, From numbers, sandbox test, enable/disable."),
            _model("WhatsApp settings", "communication", "WhatsAppSettings", "WhatsApp provider, approved templates, sandbox test, enable/disable."),
            _model("Email message templates", "communication", "EmailMessageTemplate", "Transactional email content."),
            _model("Notification type config", "notifications", "NotificationTypeConfig", "Which notifications are enabled."),
            _model("Notification templates", "notifications", "NotificationMessageTemplate", "In-app notification copy."),
            _model("Communication logs", "communication", "CommunicationLog", "Sent email/SMS history."),
        ],
    ),
    HubSection(
        title="Integrations & system",
        description="AI, invoices, course mindmaps, demo data, and resume tools.",
        instruction="One listing per integration area — open only the tool you need to configure.",
        links=[
            _model("Course mindmap config", "course_mindmap", "CourseMindmapConfig", "Mindmap placement and visibility."),
            _model("Resume V2 AI settings", "users", "ResumeV2AISettings", "AI provider options for resume builder."),
            _model("Invoice configuration", "invoices", "InvoiceConfiguration", "GST, numbering, and invoice defaults."),
            _model("Demo dataset config", "demo_data", "DemoDatasetConfig", "Demo account seeding options."),
            _model("Resume HTML templates", "users", "ResumeStudioHtmlTemplate", "Resume studio layout templates."),
            _model("Forum AI features", "forum", "AIFeature", "Forum AI capability toggles."),
            _external(
                "AI tokens & freemium (all tools)",
                "/admin/hub/configuration/#ai-tokens-freemium",
                "Packages, quotas, wallets, FX rate, and AI billing.",
            ),
        ],
    ),
    HubSection(
        title="Geography & reference data",
        description="Countries, states, and cities used across the platform.",
        instruction="Manage geography in order: Countries → States → Cities. All CRUD for location data lives in these three lists.",
        links=[
            _model("Countries", "core", "Country", "Country list."),
            _model("States", "core", "State", "State / province list."),
            _model("Cities", "core", "City", "City list."),
        ],
    ),
]

# Dedicated Education Loan hub (sidebar + /admin/hub/education-loan/)
EDUCATION_LOAN_SECTIONS: list[HubSection] = [
    HubSection(
        title="Loan team",
        description="Create and manage Loan Managers and Executives for the Loan Desk PWA.",
        instruction="Open Loan team for one list with Add Manager / Add Executive. Edit and enable/disable inline via AJAX.",
        links=[
            _named(
                "Loan team",
                "admin:hub_education_loan_team",
                "CRUD list: add manager/executive, edit, enable/disable. Shows role and name.",
            ),
        ],
    ),
    HubSection(
        title="Enquiries & follow-up",
        description="Parent education loan leads, callbacks, and internal remarks.",
        instruction="Open applications for lead follow assignment and status. Remarks are the activity timeline from Loan Desk.",
        links=[
            _model(
                "Loan applications / leads",
                "users",
                "EducationLoanApplication",
                "Parent calculator drafts and submitted enquiries.",
            ),
            _model(
                "Loan remarks",
                "users",
                "EducationLoanRemark",
                "Internal follow-up notes from the loan team.",
            ),
            _external(
                "Open Loan Desk PWA",
                "/loan-desk/?queue=new",
                "Queues: New, Pending, Today follow-ups, Qualified / Not qualified, bank handoff.",
                staff_only=True,
            ),
            _external(
                "Hard delete ALL enquiries",
                "/admin/users/educationloanapplication/hard-delete-all/",
                "Permanently wipe all loan enquiries, remarks, and login tokens (confirmation required).",
                staff_only=True,
            ),
        ],
    ),
    HubSection(
        title="Loan settings",
        description="Ops emails, PWA toggle, CRM handoff, client email templates.",
        instruction="Set manager report emails and notify flags in Ops settings. CRM is optional outbound sync. Email templates can also be managed in Loan Desk by managers.",
        links=[
            _model(
                "Loan ops settings",
                "users",
                "EducationLoanOpsSettings",
                "PWA, enquiry notify, daily report emails, reminders.",
            ),
            _model(
                "Bank API settings",
                "users",
                "EducationLoanCRMSettings",
                "Bank API URL, HTTP method, and parameters with {{variable}} placeholders.",
            ),
            _model(
                "Client email templates",
                "users",
                "EducationLoanClientEmailTemplate",
                "Reusable subject/body templates for Loan Desk → client emails.",
            ),
            _external(
                "Manage templates in Loan Desk",
                "/loan-desk/email-templates/",
                "Manager UI to create and edit client email templates.",
                staff_only=True,
            ),
        ],
    ),
]

OPERATIONS_SECTIONS: list[HubSection] = [
    HubSection(
        title="Users & accounts",
        description="Students, staff, and profiles.",
        instruction="Use Users for account CRUD. Profiles and calendars are linked records — edit from the user change page when possible. Education loan tools live under the Education Loan hub.",
        links=[
            _model("Users", "users", "User", "All registered users and staff accounts."),
            _model("User profiles", "users", "UserProfile", "Extended profile data."),
            _model("User calendars", "users", "UserCalender", "Student calendar entries."),
            _model("Counselors", "counselor", "Counselor", "Counselor accounts and assignments."),
        ],
    ),
    HubSection(
        title="Careers & vocational content",
        description="Career library, clusters, skills, and vocational pathways.",
        instruction="Careers is the main entry point. Use categories and FAQs only when structuring or extending career pages.",
        links=[
            _model("Careers", "careers", "Career", "Career detail pages."),
            _model("Career clusters", "careers", "CareerCluster", "Cluster groupings."),
            _model("Career FAQs", "careers", "CareerFAQ", "Per-career FAQ content."),
            _model("Vocational courses", "core", "VocationalCourse", "Vocational course pages."),
            _model("Vocational categories", "core", "VocationalCourseCategory", "Vocational course groupings."),
            _model("Entrance test prep exams", "core", "EntranceTestPrepExam", "Test prep exam content."),
            _model("Entrance test prep categories", "core", "EntranceTestPrepCategory", "Test prep categories."),
            _model("Extracurricular activities", "core", "ExtracurricularActivity", "Activity listings."),
            _model("Ebooks", "core", "Ebook", "Downloadable ebook resources."),
            _model("Entrance exams", "entrance_exams", "EntranceExam", "Entrance exam reference data."),
        ],
    ),
    HubSection(
        title="Courses & learning",
        description="SkillLab, counselor courses, mindmaps, and aptitude tests.",
        instruction="SkillLab courses and Counselor courses are separate products. Mindmap tools include generate → preview → configure workflow.",
        links=[
            _model("SkillLab courses", "skilllab", "SkillLabCourse", "Online skill courses."),
            _model("International online courses", "skilllab", "InternationalOnlineCourse", "International course catalog."),
            _model("Counselor courses", "counselor", "CounselorCourse", "Guided counselor learning paths."),
            _model("Course mindmap generations", "course_mindmap", "CourseMindmapGeneration", "Generate and preview mindmaps."),
            _model("Course mindmap data", "course_mindmap", "CourseMindmapData", "Published mindmap nodes."),
            _model("Aptitude tests (app)", "app", "Category", "Legacy aptitude test categories."),
            _model("Post-matric tests", "app_post_matric", "Test", "Post-matric assessment tests."),
            _model("Post-matric mappings", "app_post_matric", "ClusterMapping", "Cluster and role mappings."),
        ],
    ),
    HubSection(
        title="Institutes & schools",
        description="School accounts, classes, students, and institute billing.",
        instruction="Start at Institutes, then classes/sections, then student management for a given school.",
        links=[
            _model("Institutes", "institute", "Institute", "Partner school accounts."),
            _model("Classes & sections", "institute", "ClassAndSection", "School class structure."),
            _model("Student management", "institute", "StudentManagement", "Institute-linked students."),
            _model("Institute discount coupons", "institute", "InstituteDiscountCoupon", "Promotional coupons."),
            _model("Institute tie-up orders", "institute", "InstituteTieUpOrder", "Institute purchase orders."),
        ],
    ),
    HubSection(
        title="Commerce & payments",
        description="Payments, invoices, and psychometric purchases.",
        instruction="Payments lists all transactions. Use course-specific payment models only for refunds or reconciliation.",
        links=[
            _model("Payments", "payments", "Payment", "All payment transactions."),
            _model("Invoices", "invoices", "Invoice", "Generated invoices."),
            _model("SkillLab course payments", "skilllab", "SkilllabCoursePayment", "Course purchase records."),
            _model("Psychometric payments", "psychometric_tests", "PsychometricTestPayment", "Test purchase records."),
        ],
    ),
    HubSection(
        title="Leads, CRM & counselling",
        description="Inbound leads, contacts, sessions, and follow-ups.",
        instruction="Leads and Contacts are inbound enquiries. Counselling sessions and follow-ups track active pipeline work.",
        links=[
            _model("Leads (core)", "core", "Lead", "Marketing and enquiry leads."),
            _model("Contacts", "core", "Contact", "Contact form submissions."),
            _model("Counselling sessions", "core", "CounsellingSession", "Booked counselling sessions."),
            _model("Analytics leads", "user_analytics", "Lead", "Tracked marketing leads."),
            _model("Follow-up statuses", "counselor", "FollowUpStatus", "Counselor follow-up pipeline."),
            _model("Career battle fights", "core", "CareerBattleFight", "Career battle game sessions."),
        ],
    ),
    HubSection(
        title="Analytics, forum & logs",
        description="Usage analytics, forum moderation, and system logs.",
        instruction="Open the analytics dashboard for reports. Use forum queries/responses for moderation; API logs for debugging.",
        links=[
            _external("User analytics dashboard", "", "Business and admin analytics.", staff_only=True),
            _model("User activity", "user_analytics", "UserActivity", "Raw activity events."),
            _model("User journeys", "user_analytics", "UserJourney", "Session journey records."),
            _model("Forum queries", "forum", "Query", "Student forum questions."),
            _model("Forum responses", "forum", "Response", "Answers and moderator replies."),
            _model("API logs", "core", "APILog", "External API call log."),
        ],
    ),
    HubSection(
        title="TopTeen CMS & media",
        description="Legacy content manager and file uploads.",
        instruction="TopTeen Admin and Blog CMS are full visual editors. S3 uploads is the shared media library for admin assets.",
        links=[
            _external("TopTeen Admin dashboard", "", "Full CMS for careers, colleges, blogs, and more.", staff_only=True),
            _external("Blog CMS", "", "Manage blog posts and categories.", staff_only=True),
            _model("S3 file uploads", "core", "S3FileUpload", "Uploaded media library."),
            _model("Blog subscriptions", "blog", "SubscriptionEmail", "Newsletter subscribers."),
        ],
    ),
]


def _resolve_external_urls(request: HttpRequest, sections: list[HubSection]) -> list[HubSection]:
    """Fill in dynamic external URLs that depend on url namespaces."""
    analytics_url = ""
    topteenadmin_url = ""
    blog_cms_url = ""
    try:
        if request.user.is_superuser:
            analytics_url = reverse("user_analytics:admin_dashboard")
        elif request.user.is_staff:
            analytics_url = reverse("user_analytics:business_dashboard")
    except NoReverseMatch:
        pass
    try:
        topteenadmin_url = reverse("topteenadmin:topteendashboard")
    except NoReverseMatch:
        pass
    try:
        blog_cms_url = reverse("topteenadminmanaged:bloglist")
    except NoReverseMatch:
        pass

    patched: list[HubSection] = []
    for section in sections:
        new_links = []
        for link in section.links:
            if link.label == "User analytics dashboard" and analytics_url:
                new_links.append(HubLink(label=link.label, url=analytics_url, description=link.description, staff_only=True))
            elif link.label == "TopTeen Admin dashboard" and topteenadmin_url:
                new_links.append(HubLink(label=link.label, url=topteenadmin_url, description=link.description, staff_only=True))
            elif link.label == "Blog CMS" and blog_cms_url:
                new_links.append(HubLink(label=link.label, url=blog_cms_url, description=link.description, staff_only=True))
            else:
                new_links.append(link)
        patched.append(
            HubSection(
                title=section.title,
                description=section.description,
                instruction=section.instruction,
                links=new_links,
            )
        )
    return patched


def resolve_hub_sections(request: HttpRequest, sections: list[HubSection]) -> list[dict]:
    sections = _resolve_external_urls(request, sections)
    resolved = []
    for section in sections:
        data = section.resolve(request)
        if data:
            resolved.append(data)
    return resolved


def count_hub_links(sections: list[dict]) -> int:
    return sum(len(section["links"]) for section in sections)


def _normalize_path(path: str) -> str:
    path = path.split("?")[0].rstrip("/") or "/"
    return path


def _iter_hub_link_entries(request: HttpRequest):
    zone_map = (
        ("configuration", CONFIGURATION_SECTIONS, "admin:hub_configuration", "Configuration"),
        ("operations", OPERATIONS_SECTIONS, "admin:hub_operations", "Operations"),
        ("education_loan", EDUCATION_LOAN_SECTIONS, "admin:hub_education_loan", "Education Loan"),
    )
    for zone, sections_source, hub_name, zone_label in zone_map:
        for section in resolve_hub_sections(request, sections_source):
            hub_url = reverse(hub_name)
            section_url = f"{hub_url}#{section['section_id']}"
            for link in section["links"]:
                yield {
                    "zone": zone,
                    "zone_label": zone_label,
                    "hub_url": hub_url,
                    "section": section,
                    "section_url": section_url,
                    "link": link,
                    "path": _normalize_path(link["url"]),
                }


def resolve_you_are_here(request: HttpRequest) -> Optional[dict]:
    if not getattr(request, "user", None) or not request.user.is_staff:
        return None
    current = _normalize_path(request.path)
    if current in (
        "/admin",
        "/admin/hub/configuration",
        "/admin/hub/operations",
        "/admin/hub/education-loan",
    ):
        return None

    best = None
    best_len = -1
    for entry in _iter_hub_link_entries(request):
        link_path = entry["path"]
        if not link_path.startswith("/"):
            continue
        if current == link_path or current.startswith(link_path + "/"):
            if len(link_path) > best_len:
                best_len = len(link_path)
                best = entry
    if not best:
        return None
    return {
        "zone": best["zone"],
        "zone_label": best["zone_label"],
        "hub_url": best["hub_url"],
        "section_title": best["section"]["title"],
        "section_id": best["section"]["section_id"],
        "section_url": best["section_url"],
        "page_label": best["link"]["label"],
        "page_url": best["link"]["url"],
    }


def get_sidebar_nav(request: HttpRequest) -> dict:
    path = _normalize_path(request.path)
    active = "home"
    if path.startswith("/admin/hub/configuration"):
        active = "configuration"
    elif path.startswith("/admin/hub/operations"):
        active = "operations"
    elif path.startswith("/admin/hub/education-loan"):
        active = "education_loan"
    else:
        here = resolve_you_are_here(request)
        if here:
            active = here["zone"]

    config_sections = resolve_hub_sections(request, CONFIGURATION_SECTIONS)
    ops_sections = resolve_hub_sections(request, OPERATIONS_SECTIONS)
    loan_sections = resolve_hub_sections(request, EDUCATION_LOAN_SECTIONS)
    loan_links = []
    for section in loan_sections:
        for link in section.get("links") or []:
            loan_links.append(link)

    return {
        "sidebar_active": active,
        "sidebar_you_are_here": resolve_you_are_here(request),
        "sidebar_config_sections": config_sections,
        "sidebar_ops_sections": ops_sections,
        "sidebar_loan_sections": loan_sections,
        "sidebar_loan_links": loan_links,
    }


def get_admin_home_context(request: HttpRequest) -> dict:
    configuration_sections = resolve_hub_sections(request, CONFIGURATION_SECTIONS)
    operations_sections = resolve_hub_sections(request, OPERATIONS_SECTIONS)
    education_loan_sections = resolve_hub_sections(request, EDUCATION_LOAN_SECTIONS)
    return {
        "hub_configuration_sections": configuration_sections,
        "hub_operations_sections": operations_sections,
        "hub_education_loan_sections": education_loan_sections,
        "hub_configuration_count": count_hub_links(configuration_sections),
        "hub_operations_count": count_hub_links(operations_sections),
        "hub_education_loan_count": count_hub_links(education_loan_sections),
    }


def _hub_context(request: HttpRequest, zone: str, title: str, intro: str, sections: list[dict], sibling: dict) -> dict:
    return {
        "title": title,
        "hub_zone": zone,
        "hub_intro": intro,
        "hub_sections": sections,
        "hub_link_count": count_hub_links(sections),
        "hub_sibling": sibling,
        **get_admin_home_context(request),
    }


@staff_member_required
def configuration_hub_view(request: HttpRequest) -> HttpResponse:
    sections = resolve_hub_sections(request, CONFIGURATION_SECTIONS)
    sibling = {
        "label": "Operations & content",
        "url": reverse("admin:hub_operations"),
        "description": "Users, courses, payments, institutes, and daily workflows.",
        "count": count_hub_links(resolve_hub_sections(request, OPERATIONS_SECTIONS)),
    }
    context = _hub_context(
        request,
        zone="configuration",
        title="Website & platform configuration",
        intro="Tune how the TopTeen website behaves. Changes here affect features, copy, SEO, and integrations — not day-to-day user records.",
        sections=sections,
        sibling=sibling,
    )
    context.update(admin.site.each_context(request))
    return render(request, "admin/hub/zone.html", context)


@staff_member_required
def operations_hub_view(request: HttpRequest) -> HttpResponse:
    sections = resolve_hub_sections(request, OPERATIONS_SECTIONS)
    sibling = {
        "label": "Education Loan",
        "url": reverse("admin:hub_education_loan"),
        "description": "Loan team, enquiries, Loan Desk PWA, and loan settings.",
        "count": count_hub_links(resolve_hub_sections(request, EDUCATION_LOAN_SECTIONS)),
    }
    context = _hub_context(
        request,
        zone="operations",
        title="Operations & content management",
        intro="Manage users, content, institutes, payments, and support workflows. For site-wide toggles and SEO, use the configuration hub. Education loan tools are in the Education Loan hub.",
        sections=sections,
        sibling=sibling,
    )
    context.update(admin.site.each_context(request))
    return render(request, "admin/hub/zone.html", context)


@staff_member_required
def education_loan_hub_view(request: HttpRequest) -> HttpResponse:
    sections = resolve_hub_sections(request, EDUCATION_LOAN_SECTIONS)
    sibling = {
        "label": "Operations & content",
        "url": reverse("admin:hub_operations"),
        "description": "Users, courses, payments, institutes, and daily workflows.",
        "count": count_hub_links(resolve_hub_sections(request, OPERATIONS_SECTIONS)),
    }
    context = _hub_context(
        request,
        zone="education_loan",
        title="Education Loan",
        intro="Manage loan team accounts, parent enquiries, follow-ups, Loan Desk PWA, and loan ops/CRM settings — all in one place.",
        sections=sections,
        sibling=sibling,
    )
    context.update(admin.site.each_context(request))
    return render(request, "admin/hub/zone.html", context)


def register_admin_hub_urls() -> None:
    """Attach hub routes to the default admin site (idempotent)."""
    if getattr(admin.site, "_topteen_hub_urls_registered", False):
        return

    original_get_urls = admin.site.get_urls

    def get_urls():
        from django.shortcuts import redirect as dj_redirect

        from loan_desk.admin_views import (
            loan_team_get_api,
            loan_team_list_view,
            loan_team_save_api,
            loan_team_toggle_api,
        )

        def _redirect_team(request):
            return dj_redirect("admin:hub_education_loan_team")

        custom = [
            path(
                "hub/configuration/",
                admin.site.admin_view(configuration_hub_view),
                name="hub_configuration",
            ),
            path(
                "hub/operations/",
                admin.site.admin_view(operations_hub_view),
                name="hub_operations",
            ),
            path(
                "hub/education-loan/",
                admin.site.admin_view(education_loan_hub_view),
                name="hub_education_loan",
            ),
            path(
                "hub/education-loan/team/",
                admin.site.admin_view(loan_team_list_view),
                name="hub_education_loan_team",
            ),
            path(
                "hub/education-loan/team/save/",
                admin.site.admin_view(loan_team_save_api),
                name="hub_education_loan_team_save",
            ),
            path(
                "hub/education-loan/team/<int:user_id>/",
                admin.site.admin_view(loan_team_get_api),
                name="hub_education_loan_team_get",
            ),
            path(
                "hub/education-loan/team/<int:user_id>/toggle/",
                admin.site.admin_view(loan_team_toggle_api),
                name="hub_education_loan_team_toggle",
            ),
            path(
                "hub/education-loan/add-manager/",
                admin.site.admin_view(_redirect_team),
                name="hub_education_loan_add_manager",
            ),
            path(
                "hub/education-loan/add-executive/",
                admin.site.admin_view(_redirect_team),
                name="hub_education_loan_add_executive",
            ),
        ]
        return custom + original_get_urls()

    admin.site.get_urls = get_urls

    original_index = admin.site.index

    def index(request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(get_admin_home_context(request))
        return original_index(request, extra_context)

    admin.site.index = index

    original_each_context = admin.site.each_context

    def each_context(request):
        context = original_each_context(request)
        if getattr(request, "user", None) and request.user.is_authenticated and request.user.is_staff:
            context.update(get_sidebar_nav(request))
            context.update(get_admin_home_context(request))
        return context

    admin.site.each_context = each_context
    admin.site._topteen_hub_urls_registered = True
