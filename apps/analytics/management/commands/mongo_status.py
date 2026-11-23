from django.core.management.base import BaseCommand
from database.migrations.migration_runner import MongoMigrationRunner

class Command(BaseCommand):
    help = "Displays migration status for MongoDB database."

    def handle(self, *args, **options):
        runner = MongoMigrationRunner()
        runner.status()
