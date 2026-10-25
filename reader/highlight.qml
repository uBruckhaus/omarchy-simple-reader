import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland

ShellRoot {
    id: root
    property var rectangles: []
    property string target: ""
    property string activeAddress: ""
    property int focusRevision: 0
    Component.onCompleted: focusQuery.running = true
    Process {
        id: focusQuery
        property int revision: 0
        command: ["hyprctl", "activewindow", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                if (focusQuery.revision !== root.focusRevision) return;
                try { root.activeAddress = String(JSON.parse(text).address || "").replace(/^0x/, ""); }
                catch (error) { root.activeAddress = ""; }
            }
        }
    }
    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (event.name === "activewindowv2") {
                root.focusRevision++;
                root.activeAddress = event.data.replace(/^0x/, "");
            }
        }
    }
    FileView {
        path: Quickshell.env("XDG_RUNTIME_DIR") + "/kindle-reader/highlight.json"
        preload: true
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const state = JSON.parse(text());
                root.target = state.target;
                root.rectangles = state.rectangles;
            }
            // A bad read keeps the last good state instead of blinking it off.
            catch (error) { console.warn("Highlight state error", error); }
        }
        onLoadFailed: root.rectangles = []
    }
    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            // Stays mapped: unmapping per update runs the compositor's layer
            // fade (Omarchy animates layers), so only the content is hidden.
            visible: true
            anchors { top: true; bottom: true; left: true; right: true }
            color: "transparent"
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.namespace: "ocrvox-highlight"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            mask: Region {}
            Repeater {
                model: root.target === root.activeAddress ? root.rectangles : []
                Rectangle {
                    required property var modelData
                    x: modelData.x - panel.screen.x - 2
                    y: modelData.y - panel.screen.y - 2
                    width: modelData.width + 4
                    height: modelData.height + 4
                    radius: 3
                    color: "#38ffd54f"
                    border.color: "#99ffc107"
                    border.width: 1
                }
            }
        }
    }
}
