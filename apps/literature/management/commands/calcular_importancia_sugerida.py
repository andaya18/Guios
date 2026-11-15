import time

from django.core.management.base import BaseCommand

from apps.literature.services import compute


class Command(BaseCommand):
    help = (
        "Calcula la importancia sugerida con IA (o respaldo) y la guarda con su trazabilidad. "
        "Si la API corta por cuota, espera y continúa: lo ya verificado queda guardado."
    )

    def add_arguments(self, parser):
        parser.add_argument("--forzar", action="store_true", help="Recalcula aunque exista un resultado de IA guardado.")
        parser.add_argument("--reintentos", type=int, default=10, help="Reintentos cuando la API corta por cuota (por defecto 10).")
        parser.add_argument("--espera", type=int, default=65, help="Segundos de espera entre reintentos (por defecto 65).")

    def handle(self, *args, **options):
        run = compute(force=options["forzar"])
        attempts = 0
        # Free-tier quotas reset every minute; already verified documents are cached, so each retry resumes.
        while run.origin != "ia" and run.error.startswith("quota") and attempts < options["reintentos"]:
            attempts += 1
            self.stdout.write(f"Cuota de la API alcanzada; reintento {attempts} de {options['reintentos']} en {options['espera']} s...")
            time.sleep(options["espera"])
            run = compute()
        self.report(run)

    def report(self, run):
        origin = "IA" if run.origin == "ia" else f"RESPALDO ({run.error})"
        self.stdout.write(f"Origen: {origin} · modelo: {run.model or '-'} · hash: {run.corpus_hash[:12]}")
        for row in run.factors.select_related("factor"):
            detail = f"TC={row.tc} r={row.r} IL={row.il}" if row.il else "sin cálculo"
            flag = "  ≠ respaldo" if row.differs_from_fallback else ""
            self.stdout.write(f"  {row.factor.name}: IS={row.value} ({detail}){flag}")
