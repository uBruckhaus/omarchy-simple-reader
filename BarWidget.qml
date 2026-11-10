import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Theme
import qs.Ui as Ui
import "corners.js" as Corners

Ui.BarWidget {
  id: root
  moduleName: "ubruckhaus.simple-reader"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  readonly property bool opened: panel.opened
  readonly property bool popoutSwitchClosing: panel.popoutSwitchClosing
  function open() { panel.open() }
  function close() { panel.close() }
  function closeForPopoutSwitch() { panel.closeForPopoutSwitch() }

  // Corners of the popup's cards and controls, and the F12 screenshot key (the popup's Panel
  // group). Both live in this widget's shell.json entry, the defaults as no key; the reading
  // settings stay with the reader service.
  readonly property string cornersSetting: Corners.choice(String(root.setting("corners", "windows")))
  readonly property var corners: Corners.sizes(cornersSetting, Theme.Style.cornerRadius)
  readonly property bool screenshotKey: root.setting("screenshotKey", true) !== false
  function saveSetting(key, value, fallback) {
    if (!root.bar || !root.bar.shell || typeof root.bar.shell.updateEntryInline !== "function") return
    var next = Object.assign({}, root.settings || {})
    if (value === fallback) delete next[key]
    else next[key] = value
    root.bar.shell.updateEntryInline(root.moduleName, next)
  }
  function setCorners(code) { saveSetting("corners", Corners.choice(code), "windows") }
  function setScreenshotKey(on) { saveSetting("screenshotKey", on === true, true) }

  // Reading (or paused): the icon turns the theme's green.
  property bool reading: false
  property string status: "Off"
  property color green: "#66c98b"
  // A reader from before the watch command answers one request per connection;
  // ask it with "status" every 10 s, and retry "watch" about once a minute in
  // case setup has updated the reader since.
  property bool legacy: false
  property int legacyPolls: 0
  property int ticks: 0
  function accept(state) {
    if (state.error) { legacy = true; return }
    if (state.enabled !== undefined) reading = state.enabled === true
    if (state.status) status = state.status
  }
  Connections { target: panel; function onStateChanged() { root.accept(panel.state) } }

  // Ask the reader service over its private socket. Connect only when the socket exists:
  // no socket means the service is not running, and failed connects would fill the shell log.
  Socket {
    id: service
    path: (Quickshell.env("XDG_RUNTIME_DIR") || "/run/user/" + Quickshell.env("UID")) + "/kindle-reader/control.sock"
    function ask() { write(root.legacy ? '{"command":"status"}\n' : '{"command":"watch","keep":true}\n'); flush() }
    onConnectionStateChanged: if (connected) ask()
    // The connection stays open while the service runs; it only ends when the service stops.
    // Quickshell sets connected back to false by itself; setting it here, inside the error
    // signal of a closed connection, makes quickshell 0.3.2 free the socket twice and crash.
    onError: {
      if (!root.legacy) root.reading = false
      else if (++root.legacyPolls % 6 === 0) root.legacy = false
    }
    parser: SplitParser {
      onRead: function(line) {
        try { root.accept(JSON.parse(line)) } catch (e) {}
      }
    }
  }
  Process {
    id: probe
    command: ["test", "-S", service.path]
    onExited: function(code) {
      if (code !== 0) root.reading = false
      else if (!service.connected) service.connected = true
    }
  }
  Timer {
    interval: 2000; repeat: true; running: true; triggeredOnStart: true
    onTriggered: {
      root.ticks++
      if (service.connected) service.ask()
      else if (!probe.running && (!root.legacy || root.ticks % 5 === 0)) probe.running = true
    }
  }
  FileView {
    path: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/omarchy/current/theme/colors.toml"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: {
      var match = text().match(/^\s*green\s*=\s*"(#[0-9a-fA-F]{6})"/m)
      if (match) root.green = match[1]
    }
  }

  SimpleReaderPanel { id: panel; bar: root.bar; anchorItem: button; hostWidget: root }
  Ui.BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    active: root.reading
    activeColor: root.green
    tooltipText: "Screen Narrator · " + (panel.state.status || root.status) + "\n" + panel.providerSummary + "\nClick: reading controls · Right-click: " + (root.reading ? "stop" : "start") + " reading"
    onPressed: function(button) {
      if (button === Qt.RightButton) panel.request({command: "toggle"})
      else panel.toggle()
    }
  }
}
