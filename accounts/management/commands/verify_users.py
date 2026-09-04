from django.core.management.base import BaseCommand
from accounts.models import User

class Command(BaseCommand):
    help = "Mark users as email-verified so they can log in without requiring SMTP activation"

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help="Specific username to verify (default: all unverified users)"
        )

    def handle(self, *args, **options):
        username = options.get('username')
        if username:
            users = User.objects.filter(username=username)
            if not users.exists():
                self.stderr.write(self.style.ERROR(f"User '{username}' not found."))
                return
            count = users.update(email_verify=True)
            self.stdout.write(self.style.SUCCESS(f"Successfully verified user '{username}'."))
        else:
            unverified = User.objects.filter(email_verify=False)
            count = unverified.count()
            unverified.update(email_verify=True)
            self.stdout.write(self.style.SUCCESS(f"Successfully verified {count} user(s). All users can now log in without SMTP issues."))

