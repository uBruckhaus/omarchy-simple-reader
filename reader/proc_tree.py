"""End a helper and everything it started, and reap all of it, before reporting it gone.

As a module: wait_reaped() and stop_descendants() for a process that is a child
subreaper. As a program (`proc_tree.py <argv…>`): runs argv as a child, relays its exit
code, and on SIGTERM (Cancel) or after argv exits ends and reaps every descendant left.
Stdlib only: setup runs it with the system Python, the reader with its own runtime.
"""
import ctypes
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def become_subreaper():
    """Orphaned descendants (also ones that left the process group with setsid) are
    re-parented to this process, so stop_descendants() finds and reaps all of them."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER
    except (OSError, AttributeError):
        return False


def direct_children():
    """PIDs whose parent is this process. Not yet reaped, so none of them can be reused."""
    me, result = os.getpid(), []
    for entry in os.listdir('/proc'):
        if not entry.isdigit():
            continue
        try:
            stat = (Path('/proc') / entry / 'stat').read_bytes()
            if int(stat[stat.rindex(b')') + 2:].split()[1]) == me:
                result.append(int(entry))
        except (OSError, ValueError, IndexError):
            continue
    return result


def wait_reaped(process, forget):
    """Waits for `process` without reaping it, then reaps it and calls forget() with
    SIGTERM blocked. A Cancel never sees a reaped leader still named as the helper, so a
    group id is only signalled while its leader keeps it from being reused."""
    while True:
        try:
            os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
            break
        except InterruptedError:
            continue
        except ChildProcessError:
            break
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    try:
        code = process.wait()
        forget()
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)
    return code


def stop_descendants(leader=None, grace=5.0):
    """Ends every descendant and returns once all of them are reaped: TERM to the
    unreaped `leader`'s group, `grace` seconds to exit, then SIGKILL generation by
    generation (descendants of a killed child are re-parented here). A process this user
    may not signal (a root package transaction) is waited for, not abandoned."""
    leader_alive = leader is not None
    if leader_alive:
        try:
            os.killpg(leader, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.monotonic() + grace
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == leader:
            leader_alive = False
        if pid == 0:
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
    while True:
        if leader_alive:
            try:
                os.killpg(leader, signal.SIGKILL)
            except OSError:
                pass
        for pid in direct_children():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            pid, _ = os.waitpid(-1, 0)
        except ChildProcessError:
            return
        if pid == leader:
            leader_alive = False


def main(argv):
    become_subreaper()
    state = {'child': None}

    def cancelled(*_):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child = state['child']
        stop_descendants(child.pid if child is not None else None)
        os._exit(130)

    signal.signal(signal.SIGTERM, cancelled)
    try:
        state['child'] = subprocess.Popen(argv, start_new_session=True)
    except OSError as error:
        print(error, file=sys.stderr, flush=True)
        return 127
    code = wait_reaped(state['child'], lambda: state.update(child=None))
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    stop_descendants(grace=1.0)  # anything the helper left behind
    return code if code >= 0 else 128 - code


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
