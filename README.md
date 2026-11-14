# Screen Narrator

*Formerly Simple Reader.* The plugin ID `ubruckhaus.simple-reader`, the `simple-reader` command and all data paths are unchanged.

Read any window, PDF or Kindle page aloud — and, if you like, **translate it first**. Screen Narrator recognizes the text of the active window with local OCR and speaks it with a local voice in 51 languages. Turn on **Translate before reading** to read, say, an English page and hear it in Spanish: translation runs offline with NLLB-200 or through your own llama.cpp, LM Studio or Ollama server. The reader service is included; voices and the translator are downloaded on request.

Click the headphones bar icon for ▶ Start / ❚❚ Pause / ■ Stop, a reading speed slider (0.60×–2.00×) right under them and three collapsible groups: **Reading** (text language, PDF, Kindle and area options), **Voice** (provider, voice, audio output) and **Translation** (off by default). Right-click the icon to start or stop reading directly; the icon turns the theme's green while reading. When something is missing, the popup names the one next step and a **Set up automatically** button installs it. Settings save immediately. Closing the popup leaves narration running; Stop ends it. User Manual opens integrated guidance. Existing reader shortcuts remain available; installation does not replace any desktop shortcuts.

The bridge uses only a private local Unix socket and Python standard library. Native Omarchy components are under `native/` with the upstream license. Removing this widget does not remove the reader or its preferences.


## Install

Install and enable the plugin on Omarchy Quattro:

```sh
omarchy plugin add https://github.com/uBruckhaus/omarchy-simple-reader.git
omarchy plugin enable ubruckhaus.simple-reader
```

Open the headphones widget and **Add / manage speech providers…**. Choose your
reading language and Kokoro or Piper, then install the voice. Then choose **Test provider
voice → Use provider**, focus your text window and press **▶ Start** (or right-click the bar icon; right-click again stops).

The main panel keeps the active provider, voice and audio output visible. Provider
setup stays separate from active settings until you test and activate it. Reading
options expand PDF, Kindle, following, highlighting and area controls. Advanced contains
manual files and maintenance. See [MANUAL.md](MANUAL.md) for the full setup flow.

The **Panel** group sets how the popup itself looks and the F12 key:

- **Corners:** *Like windows (… px)* (the default) follows Hyprland's window rounding (`decoration:rounding`, as the shell reads it), *Slightly rounded (6 px)*, *Rounded (12 px)* or *Square*. It rounds the popup's frame, its cards and manual sections, buttons, drop-downs and their lists, text fields, switches and tool tips (frame, cards, lists and tool tips at the full radius, buttons, drop-downs and fields at most 8 px; switches round, or square in *Square*). The reading-speed slider is the shell's own and keeps its round track and knob; the bar icon and the reading highlight keep their own look.
- **F12 saves a screenshot** (on by default), see *F12: a screenshot of the popup* below.

Both are stored in the widget's own entry in `~/.config/omarchy/shell.json` (`"corners"`, and `"screenshotKey": false` when switched off); the defaults are stored as no key. The reading settings stay with the reader service as before.

**51 languages.** Kokoro speaks English, German, Spanish, French, Italian, Portuguese,
Hindi, Japanese and Chinese (about 330–354 MB plus runtime packages; Japanese adds a
270 MB pronunciation dictionary). Piper covers the other languages with one voice each (60–122 MB plus a separate pinned runtime). Setup
installs the matching Tesseract OCR data. The popup defaults to your desktop locale. Progress, retry and cancellation
are built in; system package transactions request authorization and cannot be
cancelled from the popup. Setup does not start narration or add shortcuts.

Existing managed reader installations are upgraded with a backup of runtime and service files
in `~/.local/share/kindle-reader/backups/`. Settings, credentials, voices and models are retained.
An unrelated, unmanaged `ocrvox.service` is preserved and setup reports the conflict.
The existing plugin ID and data paths remain compatible with Simple Reader installations.

For terminal setup, `bash ~/.config/omarchy/plugins/ubruckhaus.simple-reader/setup.sh --language fr`
performs the same guided installation (any two-letter code from the language list;
Piper is chosen automatically when Kokoro has no voice for it). `--backend-only` installs or upgrades the backend without
downloading or selecting a voice.

## What setup installs and changes

Nothing is installed when the plugin is added. Setup runs only when you press **Set up now**,
**Set up automatically**, an install button, or `setup.sh`:

- **System packages** (`pkexec pacman -S --needed`), only those missing from a fixed list: `grim`,
  `slurp`, `imagemagick`, `tesseract`, `mpv`, `wtype`, `quickshell`, `hyprland`, `libpulse` and
  `tesseract-data-<language>` for the chosen text language. Authorization is requested each time.
- **User service** `~/.config/systemd/user/ocrvox.service` with the drop-in
  `ocrvox.service.d/read-aloud-runtime.conf`; setup stops, reloads and starts only this unit
  (`systemctl --user`). An existing unit not created by this plugin is left untouched.
- **Private Python runtimes** under `~/.local/share/kindle-reader` (`venv`, `piper-runtime`) with pinned
  packages, the `~/.local/bin/simple-reader` launcher and `~/.local/share/applications/simple-reader.desktop`.
  Replaced files are backed up in `~/.local/share/kindle-reader/backups/`.
- **Downloads**, all from pinned revisions and checked with SHA256 before use: Kokoro models (GitHub
  release `model-files-v1.0`, Hugging Face `Godelaune/Kokoro-82M-ONNX-German-Martin`), Piper voices
  (`rhasspy/piper-voices`) and, only if you choose it, the offline translator
  (`OpenNMT/nllb-200-distilled-1.3B-ct2-int8`, CC-BY-NC 4.0, non-commercial use only).
- **Network while reading**: none by default. Only a speech or translation server you configure is
  contacted (HTTPS, or HTTP on this computer only); it receives the recognized text.



Press **Stop** before removing the widget:

```sh
omarchy plugin disable ubruckhaus.simple-reader
omarchy plugin remove ubruckhaus.simple-reader
```

Removing the widget preserves reader settings, models and an existing reader service. To stop the backend too, run `systemctl --user stop ocrvox.service`. For a backend installed by this plugin, its files are `~/.local/share/kindle-reader/app` and `~/.config/systemd/user/ocrvox.service`; remove those only if you no longer use the reader. Do not remove a pre-existing service belonging to another reader installation.

## Privacy and lifecycle

OCR and local speech stay on your machine. Screenshots and generated audio use a private runtime directory and are cleaned when reading stops. The window focused when reading starts stays the book until reading stops, the book is closed or **Read again** / **Read active window** picks the focused window instead; you can work in other windows meanwhile, even over it. Screenshots of the book are taken from the window itself (`grim -T`), so windows over it are not read and the highlight stays visible while pages are checked; only a selected reading area is captured from the screen. The reader optionally follows page changes and can highlight the passage being read (the highlight shows while the book has focus). Automatic page turning presses Right arrow for Kindle, or the next-page key `n` for PDF viewers, only while the book has the keyboard focus. One `hyprctl eval` checks inside Hyprland that the book is the focused window and that no layer surface accepts keyboard input (a launcher, menu or shell panel), then sends the key with `hl.dsp.send_shortcut` without naming a window: Hyprland does not move the keyboard focus for it, so the book is never told which keys are held in another app. While another window has the focus, the session is locked, the book's workspace is not on screen or such a layer is open, the turn waits (**Waiting for the reading window**) and happens as soon as the book has the focus again. If the screen locks in the few milliseconds between the reader's lock check and the key, that one key reaches the lock screen instead of the book. Reading the rest of a page goes on in the background either way. Closing the popup leaves narration running; Stop cancels reader-owned work and playback. Online speech sends recognized text to your chosen HTTPS provider after Start, as described below.

### F12: a screenshot of the popup, with a note

While the popup is open, **F12** (without Ctrl, Shift, Alt or Super) saves a picture of the popup, for telling what is wrong with it:

- **Only on F12.** Nothing is captured at any other time, and only the popup itself: Qt draws the popup's own content into the picture (`grabToImage`). No screen capture tool runs, nothing else on the screen (not the book you are reading) is in it, and nothing is uploaded or sent anywhere. The reader service is not involved.
- **Where:** `~/Pictures/Screen Narrator/screen-narrator-<date>-<time>.png` (the pictures folder from `~/.config/user-dirs.dirs` when it is set there). The popup then names the file and asks **What is wrong? (optional)**; **Enter** or **Done** saves the text next to the picture as a `.txt` with the same name (at most 4000 characters; no text, no file), **Esc** skips it, and closing the popup keeps what was typed.
- **Private files:** the folder is made `0700` when missing and only used when it is a real folder (not a link) of yours that no one else can write to; pictures and notes are new `0600` files, never written through a link or over an existing file (`-2`, `-3` … are added instead), and a picture that cannot be written completely is removed again.
- **How:** the popup first writes the picture into its own folder `$XDG_RUNTIME_DIR/ubruckhaus.simple-reader-shot/` (`0700`, in memory; used only when `$XDG_RUNTIME_DIR` is a real folder of yours that no one else can write to, and every folder above it one that no other account can change, since Qt writes the picture there by name; a picture left there by a save that never ran is removed when the panel loads, or before the next screenshot, once it is two minutes old). `shot_save.py` (Python standard library, system `python3`) is then started with a fixed argument list, never through a shell: `cleanup <plugin id>` (when the panel loads), `prepare <plugin id>`, `save <picture> "Screen Narrator"` (checks that the picture is a regular file of yours in that folder, at most 32 MiB and a PNG, copies it as above and removes it), and `note <picture> "Screen Narrator"` with the note on its standard input. Each call answers with one line of JSON. A new F12 waits until the note before it is written; switching F12 off stops new screenshots, not one already being saved.
- **Off:** switch **F12 saves a screenshot** off in the **Panel** group; F12 then does nothing in this popup.

Screenshots you took with F12 stay in `~/Pictures/Screen Narrator/` until you delete them, also after removing the plugin.

## Voice availability

Kokoro and Piper offer guided installation; Qwen offers a checklist for an existing
llama.cpp TTS runner, compatible backbone, audio projection and speaker recording.
Only available voices are selectable. Custom file paths remain under Advanced.
Installing a chat model does not install a speech voice; Whisper is speech-to-text.
See [MANUAL.md](MANUAL.md) for voice requirements and model update instructions.

## PDF reading

Open a PDF in **Evince** (GNOME Document Viewer) or **Papers** and press **▶ Start**.
Screen Narrator finds the page in the window and reads only its text: the toolbar, the
thumbnail sidebar and neighbouring pages are left out, and page numbers at the top or bottom
of a page are not read aloud. With **Turn Kindle and PDF pages after reading** on, it moves to
the next page when the page is finished (a page taller than the window is scrolled first) and
stops with **End of document** after the last page. **Read only the page in PDF viewers** turns
the page detection off, for example for slides without a visible page border. PDFs are read
from the screen with OCR like any other window, so scanned PDFs work too; the file itself is
never opened by the reader.

## Translation (optional)

Off by default. **Translation → Speak in** reads a page in one language and speaks it in
another, for example German text heard in Japanese. Translators: a local OpenAI-compatible
LLM server (llama.cpp `llama-server`, LM Studio or Ollama; remote HTTPS servers work too)
or the offline NLLB-200 1.3B model (about 1.4 GB, CC-BY-NC 4.0, non-commercial use only).
Neither is installed by default. [MANUAL.md](MANUAL.md#translation-optional) has the setup
steps for each server.

## Online speech providers

Under **Add / manage speech providers…**, choose **Speech server**, enter an HTTPS endpoint, choose or enter a speech model ID and voice ID, enter an API key/bearer token if required, then **Test provider voice → Use provider**. **Refresh models** is optional; enter the model manually when discovery is unavailable. The provider must support the [OpenAI-compatible speech request](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create) at `/v1/audio/speech` with WAV output. Model discovery can also list chat models, so select a speech-capable model. HTTP is allowed only on loopback for local compatible servers.

OCR stays local. Online speech sends the text being read to the selected provider and can incur provider charges. Requests occur after ▶ Start or Test voice. Tokens remain in reader memory unless **Remember token on this device** is selected. Saved tokens are owner-only plaintext at `~/.config/kindle-reader/speech-credentials.json`, bound to the configured endpoint; they are not included in status responses, shell.json or process arguments. Clear token removes the stored token. Closing the popup leaves narration running; Stop cancels speech requests and playback.

## Marketplace summary

**Screen Narrator — read any window aloud, in your language.** Local OCR and local voices (Kokoro, Piper) in 51 languages, with optional translation before reading: offline NLLB-200, or your own llama.cpp, LM Studio or Ollama server. One-click setup per language, collapsible Reading / Voice / Translation groups, passage highlighting, reading areas, PDF reading in Evince and Papers (page only, no page numbers) and automatic PDF and Kindle page turning. Optional OpenAI-compatible speech servers. No model or credential is bundled; nothing leaves your computer unless you choose a remote server.

## Development checks

```sh
omarchy plugin validate .
bash -n setup.sh
python3 -m unittest discover -s tests
QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME= QT_STYLE_OVERRIDE=Fusion ~/.local/share/kindle-reader/venv/bin/python -m unittest discover -s reader -p 'test_*.py'
```

`PanelShotNative.qml`, `shot_save.py` (with `tests/test_shot_save.py`) and `corners.js` come from the author's shared plugin kit and are the same in Video Trans.

MIT license. Vendored Omarchy controls retain their upstream MIT notice in `native/LICENSE`; see `THIRD_PARTY_NOTICES.md`.

Kokoro keeps its selected model in a reusable subprocess during reading, so
successive chunks and pages avoid reloading the voice model. Turning the reader
off releases it; changing a page during synthesis cancels the old request before
reusing audio files. Automatic Kindle and PDF page turns scan after 250 ms, confirm that
the page image is stable, and then run one OCR pass.

## Reading shortcuts

Setup adds the **Screen Narrator** application entry with **Start / stop reading**,
**Start reading**, and **Stop reading** desktop actions. In Launch & Bind,
open **Apps → Screen Narrator → Shortcuts**, choose the action and assign your key.
The default application action opens the reading controls. Setup keeps the
existing `simple-reader.desktop` ID and `simple-reader` command so previous
bindings continue to work. It does not assign a key automatically.

The same actions are available from a terminal as `simple-reader toggle`,
`simple-reader on`, and `simple-reader off`.

Launch & Bind's **Plugins** view also exposes these controls through Screen Narrator's
tray menu. Choose **Screen Narrator** under **Running in the bar**, open its action
menu, then **Shortcut…** and select **Start / stop reading**, **Start reading**,
**Stop reading** or **Pause / resume**. Their menu labels stay fixed so saved
shortcuts work in both reading states. The menu also offers **Read active window
again**, the reading area, and the submenus **Voice**, **Text language**, **Speak in (translation)**, **Audio
output** and **Reading speed**; each entry can be clicked or bound to a key. The
submenus follow the current settings (Voice lists the voices for the current
language). The separate shell-plugin entry continues to open the popup.

### Kokoro model updates

Open **Add / manage speech providers… → Kokoro → Advanced · files & maintenance**, select the voice language, and use
**Check for model updates**. The check compares your installed files with the
German model repository's SHA256 metadata or the standard Kokoro model releases.
If different verified files are available, **Update selected Kokoro model** appears.
Stop reading before checking or updating. Updates are never installed automatically.
Both downloaded files are checksum-verified and tested together before activation;
existing models stay available if downloading or validation fails. Updated models
are stored under `kokoro/versions/`, separately from the original default models.
Reader setup and repair retain the active updated model instead of reverting it.

Page changes now use two quick image captures to confirm a stable page, followed
by a single OCR pass. Unchanged pages skip OCR. The opening speech chunk is shorter
so narration can begin sooner while the remaining chunks are generated in advance.
