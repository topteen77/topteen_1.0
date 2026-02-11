"""
Load demo data for Olympiad: demo user, one published exam, MCQ questions, and registration.
Use this to test the full flow: login -> list exams -> register/start -> take exam -> submit -> view results.

Usage:
  python manage.py load_olympiad_demo
  python manage.py load_olympiad_demo --no-register   # do not register demo user (test Register button)
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core import choices
from olympiad.models import (
    OlympiadExam,
    OlympiadQuestion,
    OlympiadExamQuestionSet,
    OlympiadRegistration,
)

# Markers for remove_olympiad_demo to find and remove only demo data
DEMO_USER_EMAIL = "olympiad_demo@topteen.demo"
DEMO_USER_PASSWORD = "demo1234"
DEMO_EXAM_NAME = "NSEO Demo Exam – Class 8"


class Command(BaseCommand):
    help = "Load Olympiad demo data: demo user, published exam with MCQs, optional registration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-register",
            action="store_true",
            help="Do not register the demo user for the exam (so you can test Register button).",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        skip_register = options["no_register"]

        # Use complete() to allow finding existing demo user even if soft-deleted
        existing_user = User.objects.complete().filter(email=DEMO_USER_EMAIL).first()
        if existing_user:
            self.stdout.write(f"Demo user already exists: {DEMO_USER_EMAIL}")
            demo_user = existing_user
            if not demo_user.is_active:
                demo_user.is_active = True
                demo_user.object_status = choices.ObjectStatus.ACTIVE
                demo_user.save()
                self.stdout.write("Reactivated demo user.")
        else:
            demo_user = User.objects.create_user(
                email=DEMO_USER_EMAIL,
                name="Olympiad Demo Student",
                password=DEMO_USER_PASSWORD,
            )
            demo_user.user_type = choices.UserType.STUDENT
            demo_user.object_status = choices.ObjectStatus.ACTIVE
            demo_user.save()
            self.stdout.write(self.style.SUCCESS(f"Created demo user: {DEMO_USER_EMAIL}"))

        # Exam (single demo exam)
        exam = OlympiadExam.objects.filter(name=DEMO_EXAM_NAME).first()
        if not exam:
            exam = OlympiadExam.objects.create(
                name=DEMO_EXAM_NAME,
                level=1,
                class_level=8,
                duration_minutes=15,
                total_marks=5,
                is_published=True,
                status="published",
                instructions="This is a demo exam. Answer the MCQs and submit.",
            )
            self.stdout.write(self.style.SUCCESS(f"Created demo exam: {exam.name}"))
        else:
            if not exam.is_published or exam.status not in ("published", "ongoing"):
                exam.is_published = True
                exam.status = "published"
                exam.save()
            self.stdout.write(f"Using existing demo exam: {exam.name}")

        # Demo MCQ questions (option id 'a', 'b', 'c', 'd'; correct_answer is option_id for scoring)
        demo_questions_data = [
            {
                "content": {"text": "What is the capital of India?"},
                "options": [
                    {"id": "a", "text": "Mumbai"},
                    {"id": "b", "text": "New Delhi"},
                    {"id": "c", "text": "Kolkata"},
                    {"id": "d", "text": "Chennai"},
                ],
                "correct_answer": "b",
            },
            {
                "content": {"text": "Which planet is known as the Red Planet?"},
                "options": [
                    {"id": "a", "text": "Venus"},
                    {"id": "b", "text": "Mars"},
                    {"id": "c", "text": "Jupiter"},
                    {"id": "d", "text": "Saturn"},
                ],
                "correct_answer": "b",
            },
            {
                "content": {"text": "How many continents are there on Earth?"},
                "options": [
                    {"id": "a", "text": "Five"},
                    {"id": "b", "text": "Six"},
                    {"id": "c", "text": "Seven"},
                    {"id": "d", "text": "Eight"},
                ],
                "correct_answer": "c",
            },
            {
                "content": {"text": "Which gas do plants absorb from the air for photosynthesis?"},
                "options": [
                    {"id": "a", "text": "Oxygen"},
                    {"id": "b", "text": "Nitrogen"},
                    {"id": "c", "text": "Carbon dioxide"},
                    {"id": "d", "text": "Hydrogen"},
                ],
                "correct_answer": "c",
            },
            {
                "content": {"text": "What is 7 × 8?"},
                "options": [
                    {"id": "a", "text": "54"},
                    {"id": "b", "text": "56"},
                    {"id": "c", "text": "58"},
                    {"id": "d", "text": "64"},
                ],
                "correct_answer": "b",
            },
        ]

        created_questions = 0
        for order, qdata in enumerate(demo_questions_data, start=1):
            # Create question without exam FK; we link via ExamQuestionSet
            existing = OlympiadQuestion.objects.filter(
                content__text=qdata["content"]["text"],
                object_status=choices.ObjectStatus.ACTIVE,
            ).first()
            if existing:
                q = existing
            else:
                q = OlympiadQuestion.objects.create(
                    question_type="mcq",
                    content=qdata["content"],
                    options=qdata["options"],
                    correct_answer=qdata["correct_answer"],
                    marks=1,
                    order=order,
                )
                created_questions += 1

            # Link to demo exam via set (if not already)
            if not OlympiadExamQuestionSet.objects.filter(exam=exam, question=q).exists():
                OlympiadExamQuestionSet.objects.create(exam=exam, question=q, order=order)

        if created_questions:
            self.stdout.write(self.style.SUCCESS(f"Created {created_questions} new demo question(s)."))

        if not skip_register:
            reg, created = OlympiadRegistration.objects.get_or_create(
                user=demo_user,
                exam=exam,
                defaults={
                    "registration_type": "individual",
                    "payment_status": "completed",
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS("Registered demo user for the exam."))
            else:
                reg.payment_status = "completed"
                reg.save(update_fields=["payment_status"])
                self.stdout.write("Demo user was already registered; ensured payment completed.")
        else:
            self.stdout.write("Skipped registration (--no-register). You can test Register on the list page.")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo data loaded. To test:"))
        self.stdout.write(f"  1. Run server: python manage.py runserver")
        self.stdout.write(f"  2. Open: http://localhost:8000/user/login/")
        self.stdout.write(f"  3. Login: {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")
        self.stdout.write(f"  4. Go to: http://localhost:8000/olympiad/")
        self.stdout.write(f"  5. Click 'Start exam' (or 'Register' if you used --no-register), take exam, submit, then view My Results.")
        self.stdout.write("")
        self.stdout.write("To remove demo data: python manage.py remove_olympiad_demo")
