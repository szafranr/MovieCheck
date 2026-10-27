#!/bin/sh
set -eu
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
    if [ -e .venv ]; then
        printf '%s\n' 'Katalog .venv nie zawiera środowiska dla macOS. Zmień jego nazwę i uruchom skrypt ponownie.' >&2
        exit 1
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        printf '%s\n' 'Zainstaluj Python 3.11 lub nowszy i uruchom skrypt ponownie.' >&2
        exit 1
    fi
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
        printf '%s\n' 'Polecenie python3 musi wskazywać Python 3.11 lub nowszy.' >&2
        exit 1
    fi
    printf '%s\n' 'Tworzenie lokalnego środowiska .venv…'
    python3 -m venv .venv
fi

if ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    printf '%s\n' 'Środowisko .venv wymaga Pythona 3.11 lub nowszego. Zmień nazwę starego .venv i uruchom skrypt ponownie.' >&2
    exit 1
fi

fingerprint=$(cksum pyproject.toml moviecheck/__init__.py)
stamp=.venv/.moviecheck-install.stamp
if [ "$fingerprint" != "$(cat "$stamp" 2>/dev/null || true)" ] || ! .venv/bin/python -c 'import PySide6, httpx, bs4, jinja2' >/dev/null 2>&1; then
    printf '%s\n' 'Instalowanie zależności MovieCheck (pierwsza instalacja wymaga Internetu)…'
    if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
        .venv/bin/python -m ensurepip --upgrade
    fi
    .venv/bin/python -m pip install -e .
    printf '%s\n' "$fingerprint" > "$stamp"
fi
exec .venv/bin/python -m moviecheck "$@"
