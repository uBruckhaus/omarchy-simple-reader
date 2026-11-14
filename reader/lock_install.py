"""Hash-locked pip installs into the reader's private Python runtimes.

Each runtime records which lock it was verified against: `<prefix>/.verified-<name>`
holds the SHA256 of `lock-<name>.txt`. A runtime counts as ready for a lock only with a
current marker; a runtime from an older release (or one changed by hand) is made again
from the system Python by rebuild(), never trusted because its modules import.
Stdlib only: setup runs it with the system Python, the installers with the runtime's.
"""
import hashlib
import os
from pathlib import Path
import shutil
import time

HERE = Path(__file__).resolve().parent
PIP = ('--disable-pip-version-check', '--require-hashes', '--only-binary=:all:', '--no-deps')
# Source packages without a CPython 3.14 wheel, built against lock-build.txt only.
EXTRA = {'japanese': ('--no-binary=mojimoji', '--no-binary=unidic-lite', '--no-build-isolation')}
NEEDS = {'japanese': ('build',)}


def lock_file(name):
    return HERE / f'lock-{name}.txt'


def digest(name):
    return hashlib.sha256(lock_file(name).read_bytes()).hexdigest()


def marker(prefix, name):
    return Path(prefix) / f'.verified-{name}'


def verified(prefix, name):
    try:
        return marker(prefix, name).read_text().strip() == digest(name)
    except OSError:
        return False


def install(python, prefix, name, run):
    """Installs every file of lock `name` (and the locks it needs) with its hash checked
    into a runtime made by rebuild(), then records the marker. `run(argv)` raises on failure."""
    for needed in NEEDS.get(name, ()):
        if not verified(prefix, needed):
            install(python, prefix, needed, run)
    marker(prefix, name).unlink(missing_ok=True)
    run([str(python), '-m', 'pip', 'install', *PIP, *EXTRA.get(name, ()), '--force-reinstall',
         '-r', str(lock_file(name))])
    complete(prefix, name)


def complete(prefix, name):
    marker(prefix, name).write_text(digest(name) + '\n')


def rebuild(prefix, name, run, base_python, backups):
    """A runtime without a current marker is never upgraded in place: it is moved aside
    and made again from `base_python` (the system Python, whose venv module also supplies
    pip), then lock `name` is installed into it. Nothing of the old runtime runs or stays
    importable. On failure the old runtime is put back; after success it is deleted."""
    prefix, old = Path(prefix), None
    base_python = Path(base_python).resolve()  # never an interpreter inside `prefix`
    if prefix.resolve() in base_python.parents:
        raise RuntimeError('Run setup with the system Python')
    if prefix.exists() or prefix.is_symlink():
        Path(backups).mkdir(parents=True, exist_ok=True)
        old = Path(backups) / f'{prefix.name}-{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}'
        os.rename(prefix, old)
    try:
        run([str(base_python), '-m', 'venv', str(prefix)])
        install(prefix / 'bin/python', prefix, name, run)
    except Exception:
        shutil.rmtree(prefix, ignore_errors=True)
        if old is not None:
            os.rename(old, prefix)
        raise
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)
