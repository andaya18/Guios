from django.core.management.base import BaseCommand

from apps.literature.services import load_literature


class Command(BaseCommand):
    help = "Carga los documentos y citas 2020-2025 de la Tabla 14 (idempotente)."

    def handle(self, *args, **options):
        documents, citations = load_literature()
        self.stdout.write(self.style.SUCCESS(f"Literatura cargada: {documents} documentos, {citations} citas."))
