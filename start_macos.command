#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
    printf '%s\n' 'Najpierw przygotuj środowisko zgodnie z README.md.'
    exit 1
fi
exec .venv/bin/python -m moviecheck
