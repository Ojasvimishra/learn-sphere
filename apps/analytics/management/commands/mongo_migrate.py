from django.core.management.base import BaseCommand
from database.migrations.migration_runner import MongoMigrationRunner

class Command(BaseCommand):
    help = "Applies all pending MongoDB schema and index migrations."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Checking and running MongoDB migrations..."))
        runner = MongoMigrationRunner()
        results = runner.run_migrations()
        runner.status()
        if results.get("status") == "success":
            self.stdout.write(self.style.SUCCESS(f"Done! {len(results.get('executed', []))} migration(s) applied."))
        else:
            self.stdout.write(self.style.ERROR(f"Migration error: {results.get('error')}"))
