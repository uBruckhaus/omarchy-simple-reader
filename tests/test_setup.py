import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import setup_backend as setup
import bridge


class SetupTests(unittest.TestCase):
    def test_selected_language_only_requires_its_ocr_data(self):
        with patch.object(setup, 'DATA', Path('/nonexistent-screen-narrator-test')), patch('setup_backend.shutil.which', return_value='/usr/bin/tool'), patch('setup_backend.subprocess.run') as run:
            run.return_value.stdout = 'eng'
            self.assertEqual(setup.missing_packages('en'), [])
            self.assertEqual(setup.missing_packages('de'), ['tesseract-data-deu'])
            self.assertEqual(setup.missing_packages('fr'), ['tesseract-data-fra'])
            self.assertEqual(setup.missing_packages('zh'), ['tesseract-data-chi_sim'])

    def test_language_without_kokoro_installs_piper(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); data = base / 'data'; source = base / 'source'
            (source / 'reader').mkdir(parents=True)
            with patch.object(setup, 'DATA', data), patch.object(setup, 'UNIT', base / 'ocrvox.service'), patch.object(setup, 'ROOT', source), patch.object(setup, 'missing_packages', return_value=[]), patch.object(setup, 'runtime_ready', return_value=True), patch.object(setup, 'report'), patch.object(setup, 'install_launcher'), patch.object(setup, 'run') as run, patch('install_piper.install') as piper:
                setup.install('nl')
            piper.assert_called_once()
            self.assertEqual(piper.call_args.args[1], 'nl')
            self.assertFalse(any('install_kokoro.py' in str(c.args[0]) for c in run.call_args_list))

    def test_ocr_language_can_differ_from_voice_language(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / 'source/reader').mkdir(parents=True)
            with patch.object(setup, 'DATA', base / 'data'), patch.object(setup, 'UNIT', base / 'ocrvox.service'), patch.object(setup, 'ROOT', base / 'source'), patch.object(setup, 'missing_packages', return_value=[]) as missing, patch.object(setup, 'runtime_ready', return_value=True), patch.object(setup, 'report'), patch.object(setup, 'install_launcher'), patch.object(setup, 'run'):
                setup.install('en', backend_only=True, ocr_language='de')
            missing.assert_called_once_with('de')
        with self.assertRaises(ValueError):
            setup.install('en', ocr_language='xx')
        with self.assertRaises(ValueError):
            bridge.request({'command': 'setup', 'language': 'en', 'ocr_language': '../de'})

    def test_unknown_language_is_rejected(self):
        for value in ('xx', '../de', 'de\n', None):
            with self.assertRaises(ValueError):
                setup.install(value)
            with self.assertRaises(ValueError):
                bridge.request({'command': 'setup', 'language': value})

    def test_interrupted_setup_is_retryable(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / 'progress.json'
            state.write_text(json.dumps(dict(busy=True, pid=12345)))
            with patch.object(setup, 'PROGRESS', state), patch.object(setup, 'setup_pid', return_value=False):
                self.assertFalse(setup.setup_state()['busy'])
                self.assertEqual(setup.setup_state()['phase'], 'error')

    def test_cancel_reaps_every_descendant_before_releasing_setup(self):
        # A helper that ignores TERM starts a grandchild that leaves the process group
        # (setsid) and ignores TERM too; cancel must end and reap both before setup exits.
        import os, signal, subprocess, sys, textwrap, time
        root = Path(setup.__file__).resolve().parent
        with tempfile.TemporaryDirectory() as folder:
            pids = Path(folder) / 'pids'
            helper = textwrap.dedent(f"""
                import os, signal, subprocess, sys, time
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                g = subprocess.Popen([sys.executable, '-c', 'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'],
                                     start_new_session=True)
                open({str(pids)!r}, 'w').write(f'{{os.getpid()}} {{g.pid}}')
                print('started', flush=True)
                time.sleep(60)
            """)
            harness = textwrap.dedent(f"""
                import signal, sys
                from pathlib import Path
                sys.path.insert(0, {str(root)!r})
                import setup_backend as s
                s.DATA = Path({folder!r}); s.PROGRESS = s.DATA / 'progress.json'
                assert s.become_subreaper()
                signal.signal(signal.SIGTERM, s.interrupted)
                s.run([sys.executable, '-c', {helper!r}], stream=True)
            """)
            proc = subprocess.Popen([sys.executable, '-c', harness], stdout=subprocess.PIPE, text=True)
            deadline = time.monotonic() + 10
            while not (pids.exists() and len(pids.read_text().split()) == 2) and time.monotonic() < deadline:
                time.sleep(0.05)
            helper_pid, grandchild = map(int, pids.read_text().split())
            proc.send_signal(signal.SIGTERM)
            start = time.monotonic()
            self.assertEqual(proc.wait(timeout=20), 130)
            proc.stdout.close()
            self.assertGreaterEqual(time.monotonic() - start, 4)  # TERM grace first
            for pid in (helper_pid, grandchild):
                self.assertFalse(Path(f'/proc/{pid}').exists(), pid)   # dead and reaped
            state = json.loads((Path(folder) / 'progress.json').read_text())
            self.assertEqual((state['phase'], state['busy']), ('cancelled', False))

    def test_unknown_service_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / 'data'
            unit = Path(folder) / 'ocrvox.service'
            unit.write_text('[Service]\nExecStart=/unrelated/program\n')
            with patch.object(setup, 'DATA', data), patch.object(setup, 'UNIT', unit), patch.object(setup, 'report'), patch.object(setup, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'unmanaged'):
                    setup.install('en')
                run.assert_not_called()
            self.assertIn('/unrelated/program', unit.read_text())

    def test_legacy_service_gets_runtime_update_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); data = base / 'data'; source = base / 'source'
            (data / 'app').mkdir(parents=True); (source / 'reader').mkdir(parents=True)
            (data / 'app/reader.py').write_text('old runtime')
            (source / 'reader/reader.py').write_text('new runtime')
            (source / 'reader/lock-base.txt').write_text('locked')
            (source / 'reader/notes.txt').write_text('not copied')
            unit = base / 'ocrvox.service'
            original = 'Description=Simple Reader local OCR and speech\nExecStart=%h/.local/bin/ocrvox\n'
            unit.write_text(original)
            with patch.object(setup, 'DATA', data), patch.object(setup, 'UNIT', unit), patch.object(setup, 'ROOT', source), patch.object(setup, 'missing_packages', return_value=[]), patch.object(setup, 'runtime_ready', return_value=True), patch.object(setup, 'report'), patch.object(setup, 'install_launcher'), patch.object(setup, 'run') as run:
                setup.install('de', backend_only=True)
            self.assertEqual((data / 'app/reader.py').read_text(), 'new runtime')
            # The installers in app/ find their hash locks next to them.
            self.assertEqual((data / 'app/lock-base.txt').read_text(), 'locked')
            self.assertFalse((data / 'app/notes.txt').exists())
            backups = list((data / 'backups').iterdir())
            self.assertEqual((backups[0] / 'reader.py').read_text(), 'old runtime')
            self.assertEqual(unit.read_text(), original)
            self.assertIn('kindle-reader/app/reader.py', (base / 'ocrvox.service.d/read-aloud-runtime.conf').read_text())
            calls = [c.args[0] for c in run.call_args_list]
            self.assertIn(['systemctl', '--user', 'daemon-reload'], calls)
            self.assertIn(['systemctl', '--user', 'start', 'ocrvox.service'], calls)

    def test_upgrade_keeps_custom_qwen_model_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); data = base / 'data'; source = base / 'source'
            (data / 'app').mkdir(parents=True); (source / 'reader').mkdir(parents=True)
            unit = base / 'ocrvox.service'
            unit.write_text('# Managed by ubruckhaus.simple-reader\n')
            (base / 'ocrvox.service.d').mkdir()
            override = base / 'ocrvox.service.d/read-aloud-runtime.conf'
            override.write_text('[Service]\nEnvironment=QWEN_TTS_MODEL_DIR=/models/qwen\nEnvironment=OTHER=1\n')
            with patch.object(setup, 'DATA', data), patch.object(setup, 'UNIT', unit), patch.object(setup, 'ROOT', source), patch.object(setup, 'missing_packages', return_value=[]), patch.object(setup, 'runtime_ready', return_value=True), patch.object(setup, 'report'), patch.object(setup, 'install_launcher'), patch.object(setup, 'run'):
                setup.install('de', backend_only=True)
            text = override.read_text()
            self.assertIn('Environment=QWEN_TTS_MODEL_DIR=/models/qwen\n', text)
            self.assertNotIn('OTHER=1', text)
            self.assertNotIn('/mnt/', text)

    def test_first_use_status_works_without_backend(self):
        with patch.object(bridge, 'setup_state', return_value={'busy': False}), patch.object(bridge, 'runtime_ready', return_value=False), patch.object(bridge, 'readiness', return_value={'backend_ready': False, 'missing_packages': ['mpv']}), patch('bridge.Path.exists', return_value=False), patch('bridge.Path.read_text', side_effect=OSError):
            state = bridge.request({'command': 'status'})
            self.assertFalse(state['backend_ready'])
            self.assertFalse(state['enabled'])
            self.assertEqual(state['missing_packages'], ['mpv'])

    def test_invalid_setup_language_does_not_spawn(self):
        with patch.object(bridge, 'setup_state', return_value={'busy': False}), patch('bridge.subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):
                bridge.request({'command': 'setup', 'language': '--bad-option'})
            spawn.assert_not_called()

    def test_package_transaction_cannot_be_cancelled(self):
        with patch.object(bridge, 'setup_state', return_value={'busy': True, 'phase': 'packages'}), patch('bridge.os.kill') as kill:
            with self.assertRaisesRegex(ValueError, 'transaction'):
                bridge.request({'command': 'cancel-setup'})
            kill.assert_not_called()

    def test_startup_waits_for_connect_not_stale_socket_file(self):
        with patch('bridge.socket.socket') as socket, patch('bridge.subprocess.run') as start, patch('bridge.time.sleep'):
            client = socket.return_value.__enter__.return_value
            client.connect.side_effect = [ConnectionRefusedError(), None]
            client.recv.return_value = b'{"enabled":false}\n'
            self.assertFalse(bridge.socket_request({'command': 'status'})['enabled'])
            self.assertEqual(client.connect.call_count, 2)
            start.assert_called_once()

    def test_launcher_actions_use_updated_runtime_and_preserve_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            backup = home / 'backup'; backup.mkdir()
            desktop = home / '.local/share/applications/simple-reader.desktop'
            desktop.parent.mkdir(parents=True)
            desktop.write_text('old entry')
            launcher = home / '.local/bin/simple-reader'
            launcher.parent.mkdir(parents=True)
            launcher.write_text('old launcher')
            with patch('setup_backend.Path.home', return_value=home), patch.object(setup, 'DATA', home / 'data'):
                setup.install_launcher(backup)
            self.assertEqual((backup / 'simple-reader.desktop').read_text(), 'old entry')
            self.assertEqual((backup / 'simple-reader').read_text(), 'old launcher')
            self.assertIn('data/app/reader.py', launcher.read_text())
            self.assertNotIn('Work/KindleReader', launcher.read_text())
            self.assertTrue(launcher.stat().st_mode & 0o100)
            text = desktop.read_text()
            for command in ('toggle', 'on', 'off'):
                self.assertIn('Exec=simple-reader ' + command, text)
            self.assertIn('Name=Screen Narrator', text)


class ClipboardTests(unittest.TestCase):
    """Text fields never read the clipboard; explicit paste reads it bounded."""

    def test_bounded_runner_stops_endless_and_silent_helpers(self):
        import time
        self.assertEqual(bridge.run_bounded(['printf', 'ok'], 100, 3), (0, b'ok'))
        with self.assertRaises(ValueError):
            bridge.run_bounded(['yes'], 64 * 1024, 5)                 # streaming owner
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            bridge.run_bounded(['sleep', '30'], 1024, 1)             # owner that never answers
        self.assertLess(time.monotonic() - start, 4)

    def test_every_pip_install_takes_hashed_files_from_a_lock(self):
        import re
        root = Path(setup.__file__).resolve().parent
        sources = [root / 'setup_backend.py', *sorted((root / 'reader').glob('*.py'))]
        sites = 0
        for path in sources:
            if path.name.startswith('test_'):
                continue
            text = path.read_text()
            for match in re.finditer(r"'pip', 'install'(.{0,400}?)\]", text, re.S):
                sites += 1
                call = match.group(1)
                self.assertTrue('--require-hashes' in call or '*LOCKED' in call, (path.name, call))
                self.assertTrue('--no-deps' in call or '*LOCKED' in call, (path.name, call))
                self.assertIn('lock-', call, (path.name, call))
        self.assertEqual(sites, 6)  # base, Kokoro deps, build tools, Japanese, translator, Piper
        self.assertEqual(setup.LOCKED, ('--require-hashes', '--only-binary=:all:', '--no-deps'))

    def test_lock_files_pin_every_package_with_hashes(self):
        import re
        locks = sorted((Path(setup.__file__).resolve().parent / 'reader').glob('lock-*.txt'))
        self.assertEqual([path.name for path in locks],
                         ['lock-base.txt', 'lock-build.txt', 'lock-japanese.txt', 'lock-nllb.txt', 'lock-piper.txt'])
        for path in locks:
            entries = re.split(r'\n(?=\S)', '\n'.join(line for line in path.read_text().splitlines()
                                                      if line.strip() and not line.startswith('#')))
            self.assertTrue(entries)
            for entry in entries:
                self.assertRegex(entry, r'^[a-z0-9][a-z0-9._-]*(\[[a-z0-9,]+\])?==[0-9][^ ;]* ', (path.name, entry))
                self.assertRegex(entry, r'--hash=sha256:[0-9a-f]{64}', (path.name, entry))
                self.assertNotRegex(entry, r'(https?:|git\+|file:|-e )', (path.name, entry))

    def test_paste_reads_plain_text_only_and_cleans_it(self):
        def fake(args, limit, timeout):
            if '--list-types' in args:
                return 0, b'image/png\ntext/plain;charset=utf-8\n'
            self.assertEqual(args[-1], 'text/plain;charset=utf-8')
            self.assertLessEqual(limit, 8 * 1024)
            self.assertLessEqual(timeout, 2)
            return 0, b'sk-token\r\n\x1b[31mred'
        with patch('bridge.run_bounded', side_effect=fake):
            self.assertEqual(bridge.request({'command': 'paste'}), {'clipboard': 'sk-token[31mred'})

    def test_paste_without_text_or_too_large(self):
        with patch('bridge.run_bounded', return_value=(0, b'image/png\n')):
            self.assertEqual(bridge.read_clipboard(), {'clipboard': ''})
        with patch('bridge.run_bounded', return_value=(1, b'')):
            self.assertEqual(bridge.read_clipboard(), {'clipboard': ''})   # empty clipboard
        calls = iter([(0, b'text/plain\n')])
        def too_large(args, limit, timeout):
            if '--list-types' in args:
                return next(calls)
            raise ValueError('too large')
        with patch('bridge.run_bounded', side_effect=too_large), self.assertRaisesRegex(ValueError, '8 KiB'):
            bridge.read_clipboard()

    def test_no_qt_text_inputs_in_the_shell_ui(self):
        import re
        root = Path(__file__).resolve().parent.parent
        for qml in list(root.glob('*.qml')) + list((root / 'native').rglob('*.qml')):
            code = re.sub(r'//[^\n]*', '', qml.read_text())
            for pattern in (r'\bTextInput\s*\{', r'\bTextEdit\s*\{', r'\bTextArea\s*\{', r'QQC\.TextField', r'editable:\s*true'):
                self.assertIsNone(re.search(pattern, code), f'{qml.name}: {pattern}')
