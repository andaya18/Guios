import os
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from guios.env import load_env_file


class LoadEnvFileTests(TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_loads_values_ignoring_comments_quotes_and_blank_lines(self):
        path = self.write('# comentario\n\nEMAIL_HOST=smtp.gmail.com\nDEFAULT_FROM_EMAIL="GUIOS PRO <a@b.com>"\nEMAIL_HOST_PASSWORD=\'abcd efgh\'\n')

        with mock.patch.dict(os.environ, {}, clear=True):
            loaded = load_env_file(path)
            self.assertEqual(os.environ["EMAIL_HOST"], "smtp.gmail.com")
            self.assertEqual(os.environ["DEFAULT_FROM_EMAIL"], "GUIOS PRO <a@b.com>")
            self.assertEqual(os.environ["EMAIL_HOST_PASSWORD"], "abcd efgh")
        self.assertEqual(loaded, ["EMAIL_HOST", "DEFAULT_FROM_EMAIL", "EMAIL_HOST_PASSWORD"])

    def test_real_environment_variables_win(self):
        path = self.write("EMAIL_HOST=desde-archivo\n")

        with mock.patch.dict(os.environ, {"EMAIL_HOST": "desde-sistema"}, clear=True):
            load_env_file(path)
            self.assertEqual(os.environ["EMAIL_HOST"], "desde-sistema")

    def test_missing_file_is_ignored(self):
        self.assertEqual(load_env_file(Path("no-existe.env")), [])

    def test_lines_without_equals_are_ignored(self):
        path = self.write("ESTO NO ES VALIDO\nOK=1\n")

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_env_file(path), ["OK"])
