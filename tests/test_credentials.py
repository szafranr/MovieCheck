import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QLineEdit
from moviecheck.app import MainWindow
from moviecheck.credentials import ACCOUNT, SERVICE, CredentialStoreError, TMDBTokenStore
from moviecheck.tmdb import TMDBProvider


class MemoryBackend:
    def __init__(self):
        self.values = {}
    def get_password(self, service, account):
        return self.values.get((service, account))
    def set_password(self, service, account, value):
        self.values[(service, account)] = value
    def delete_password(self, service, account):
        del self.values[(service, account)]


class CredentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"TMDB_READ_ACCESS_TOKEN": "", "TMDB_API_KEY": ""})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.backend = MemoryBackend()

    def window(self):
        window = MainWindow(token_store=TMDBTokenStore(self.backend))
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window

    def test_save_restart_update_and_forget_token(self):
        first = self.window()
        first.tmdb_token.setText("fixture-private-token")
        first.save_token_button.click()
        self.assertEqual(self.backend.values, {(SERVICE, ACCOUNT): "fixture-private-token"})
        first.close()
        second = self.window()
        self.assertEqual(second.tmdb_token.text(), "fixture-private-token")
        self.assertEqual(second.tmdb_token.echoMode(), QLineEdit.EchoMode.Password)
        self.assertNotIn("fixture-private-token", second.token_status.text())
        second.tmdb_token.setText("replaced-fixture")
        second.save_token_button.click()
        second.forget_token_button.click()
        self.assertEqual(self.backend.values, {})
        self.assertEqual(second.tmdb_token.text(), "")
        self.assertEqual(self.window().tmdb_token.text(), "")

    def test_search_saves_changed_token_and_session_survives_save_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "lista.txt"
            source.write_text("Movie.2020.mkv", encoding="utf-8")
            window = self.window()
            window.load_source(source)
            window.tmdb_token.setText("session-fixture")
            with patch("moviecheck.app.SearchWorker") as worker:
                window.start_all()
                self.assertEqual(self.backend.values[(SERVICE, ACCOUNT)], "session-fixture")
                self.assertEqual(worker.call_args.kwargs["tmdb_credential"], "session-fixture")
                worker.return_value.start.assert_called_once()
            window.worker = None
            window.set_busy(False)
            window.tmdb_token.setText("new-session-fixture")
            with patch.object(self.backend, "set_password", side_effect=RuntimeError("new-session-fixture")), patch("moviecheck.app.SearchWorker") as worker:
                window.start_all()
                self.assertEqual(worker.call_args.kwargs["tmdb_credential"], "new-session-fixture")
                worker.return_value.start.assert_called_once()
            window.worker = None
            self.assertNotIn("new-session-fixture", window.token_status.text())
            self.assertIn("tej sesji", window.token_status.text())

    def test_locked_store_does_not_clear_input_or_claim_success(self):
        store = Mock()
        store.load.side_effect = CredentialStoreError("Magazyn zablokowany")
        store.delete.side_effect = CredentialStoreError("Nie można usunąć")
        window = MainWindow(token_store=store)
        try:
            self.assertIn("zablokowany", window.token_status.text())
            window.tmdb_token.setText("session-fixture")
            window.forget_token_button.click()
            self.assertEqual(window.tmdb_token.text(), "session-fixture")
            self.assertNotIn("Usunięto", window.token_status.text())
        finally:
            window.close()

    def test_native_errors_are_sanitized_and_empty_save_is_rejected(self):
        backend = Mock()
        for operation in ("get_password", "set_password", "delete_password"):
            getattr(backend, operation).side_effect = RuntimeError("secret-in-backend-error")
        store = TMDBTokenStore(backend)
        for action in (store.load, lambda: store.save("secret-in-backend-error"), store.delete):
            with self.assertRaises(CredentialStoreError) as caught:
                action()
            self.assertNotIn("secret-in-backend-error", str(caught.exception))
        with self.assertRaisesRegex(CredentialStoreError, "Wpisz"):
            store.save("  ")

    def test_environment_overrides_saved_token_and_empty_field_disables_tmdb(self):
        self.backend.set_password(SERVICE, ACCOUNT, "saved-fixture")
        with patch.dict(os.environ, {"TMDB_READ_ACCESS_TOKEN": "environment-fixture"}):
            window = self.window()
            self.assertEqual(window.tmdb_token.text(), "environment-fixture")
            window.forget_token_button.click()
            self.assertEqual(window.tmdb_token.text(), "")
            cache = Mock()
            provider = TMDBProvider(cache, credential="")
            try:
                self.assertEqual(provider.credential, "")
            finally:
                provider.close()
