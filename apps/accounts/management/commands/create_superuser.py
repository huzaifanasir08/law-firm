import os
from django.core.management.base import BaseCommand
from decouple import config
from apps.accounts.models import User, UserRole


class Command(BaseCommand):
    help = "Create a default superuser with role=SUPER_ADMIN if one does not exist"

    def handle(self, *args, **kwargs):
        email = config("DJANGO_SUPERUSER_EMAIL", default="admin@lawfirm.com")
        password = config("DJANGO_SUPERUSER_PASSWORD", default="Admin@123456")
        name = config("DJANGO_SUPERUSER_NAME", default="Super Admin")

        if not email or not password:
            self.stdout.write("Superuser email or password not configured, skipping.")
            return

        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(f"Superuser '{email}' already exists, skipping.")
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            name=name,
            role=UserRole.SUPER_ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"Superuser '{email}' created successfully with role SUPER_ADMIN."))
