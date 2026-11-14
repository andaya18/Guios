from django.core.management.base import BaseCommand

from apps.literature.services import compute


class Command(BaseCommand):
    help = "Calcula la importancia sugerida con IA (o respaldo) y la guarda con su trazabilidad."

    def add_arguments(self, parser):
        parser.add_argument("--forzar", action="store_true", help="Recalcula aunque exista un resultado de IA guardado.")

    def handle(self, *args, **options):
        run = compute(force=options["forzar"])
        origin = "IA" if run.origin == "ia" else f"RESPALDO ({run.error})"
        self.stdout.write(f"Origen: {origin} · modelo: {run.model or '-'} · hash: {run.corpus_hash[:12]}")
        for row in run.factors.select_related("factor"):
            detail = f"TC={row.tc} r={row.r} IL={row.il}" if row.il else "sin cálculo"
            flag = "  ≠ respaldo" if row.differs_from_fallback else ""
            self.stdout.write(f"  {row.factor.name}: IS={row.value} ({detail}){flag}")
