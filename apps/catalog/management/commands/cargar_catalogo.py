from django.core.management.base import BaseCommand, CommandError

from apps.catalog.services import CatalogDataError, load_catalog


class Command(BaseCommand):
    help = "Carga el catálogo inicial: 3 dimensiones, 18 factores, 61 subfactores y 2 versiones."

    def handle(self, *args, **options):
        try:
            result = load_catalog()
        except CatalogDataError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                "Catálogo cargado: {dimensions} dimensiones, {factors} factores, "
                "{subfactors} subfactores, {versions} versiones.".format(**result)
            )
        )
