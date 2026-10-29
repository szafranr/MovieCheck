"""Token TMDB w natywnym magazynie poświadczeń bieżącego użytkownika."""

import sys

SERVICE = "MovieCheck.TMDB"
ACCOUNT = "api-token"


class CredentialStoreError(Exception):
    pass


def native_backend():
    # Jawny wybór wyklucza magazyny tekstowe i wtyczki skonfigurowane poza aplikacją.
    if sys.platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring
        return WinVaultKeyring()
    if sys.platform == "darwin":
        from keyring.backends.macOS import Keyring
        return Keyring()
    raise CredentialStoreError("Zapamiętywanie tokenu jest dostępne na Windows i macOS.")


class TMDBTokenStore:
    def __init__(self, backend=None):
        self.backend = backend

    def _backend(self):
        if self.backend is None:
            self.backend = native_backend()
        return self.backend

    def load(self):
        try:
            return self._backend().get_password(SERVICE, ACCOUNT) or ""
        except Exception:
            raise CredentialStoreError("Nie można odczytać tokenu z systemowego magazynu poświadczeń. Możesz wpisać token na tę sesję.") from None

    def save(self, token):
        token = token.strip()
        if not token:
            raise CredentialStoreError("Wpisz token przed zapisaniem.")
        try:
            self._backend().set_password(SERVICE, ACCOUNT, token)
        except Exception:
            raise CredentialStoreError("Nie można zapisać tokenu w systemowym magazynie poświadczeń. Token nadal działa w tej sesji.") from None

    def delete(self):
        try:
            backend = self._backend()
            if backend.get_password(SERVICE, ACCOUNT) is not None:
                backend.delete_password(SERVICE, ACCOUNT)
        except Exception:
            raise CredentialStoreError("Nie można usunąć zapisanego tokenu. Spróbuj ponownie po odblokowaniu magazynu poświadczeń.") from None
