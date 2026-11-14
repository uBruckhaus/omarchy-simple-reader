"""Hash-locked pip installs into the reader's private Python runtimes.

Each runtime records which lock it was verified against: `<prefix>/.verified-<name>`
holds the SHA256 of `lock-<name>.txt`. A runtime counts as ready for a lock only with a
current marker, so a runtime from an older release (or one changed by hand) is rebuilt
from the lock's exact files once, instead of being trusted because its modules import.
Stdlib only: setup runs it with the system Python, the installers with the runtime's.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

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


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def locked_packages(name):
    names = set()
    for line in lock_file(name).read_text().splitlines():
        match = re.match(r'([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?==', line)
        if match:
            names.add(normalize(match.group(1)))
    return names


def install(python, prefix, name, run, mark=True):
    """Installs every file of lock `name` (and the locks it needs) with its hash checked,
    replacing what the runtime had, then records the marker (unless mark=False: the
    caller records it with complete() once the runtime is also pruned). `run(argv)` raises
    on failure."""
    for needed in NEEDS.get(name, ()):
        if not verified(prefix, needed):
            install(python, prefix, needed, run)
    marker(prefix, name).unlink(missing_ok=True)
    run([str(python), '-m', 'pip', 'install', *PIP, *EXTRA.get(name, ()), '--force-reinstall',
         '-r', str(lock_file(name))])
    if mark:
        complete(prefix, name)


def complete(prefix, name):
    marker(prefix, name).write_text(digest(name) + '\n')


def rebuild(python, prefix, name, run, keep_locks):
    """The runtime's own lock: install, prune, and only then record it as verified, so an
    interrupted run is redone in full next time."""
    install(python, prefix, name, run, mark=False)
    prune(python, prefix, run, keep_locks, current=name)
    complete(prefix, name)


def prune(python, prefix, run, keep_locks, current=None):
    """Removes every distribution that no verified lock in `keep_locks` lists (pip itself
    stays), so nothing unverified from an older runtime remains importable. `current` is
    the lock just installed, whose marker is written only after this."""
    allowed = {'pip'} | (locked_packages(current) if current else set())
    for name in keep_locks:
        if name == current:
            continue
        if verified(prefix, name):
            allowed |= locked_packages(name)
        else:
            marker(prefix, name).unlink(missing_ok=True)
    listing = subprocess.run([str(python), '-m', 'pip', 'list', '--disable-pip-version-check', '--format=json'],
                             capture_output=True, text=True, timeout=120, check=True).stdout
    extra = sorted(item['name'] for item in json.loads(listing)[:5000]
                   if isinstance(item, dict) and isinstance(item.get('name'), str) and normalize(item['name']) not in allowed)
    if extra:
        run([str(python), '-m', 'pip', 'uninstall', '--disable-pip-version-check', '-y', *extra])
