from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        import users.signals  # noqa: F401 - ensure user_pdf folder created for new users
