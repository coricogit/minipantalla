import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons
import qs.Commons as Commons

// Mini pantalla USB AX206 2.1" (2a55:9990). El panel solo lista la carpeta y
// lanza `minipantalla poner/rotar` (instantáneo: solo cambia el ajuste y el
// servicio minipantalla.service lo transmite en vivo); el estado lo lee
// lcdstate.py sin abrir el USB.
Panel {
  id: root
  moduleName: "corico.minipantalla"
  ipcTarget: "corico.minipantalla"

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  readonly property string backend: String(Qt.resolvedUrl("lcdstate.py")).replace(/^file:\/\//, "")
  readonly property string tool: Quickshell.env("HOME") + "/.local/bin/minipantalla"

  property bool connected: false
  property string folder: ""
  property var files: []
  property string current: ""
  property int rotation: 0
  property bool streaming: false

  // Una sola operación USB a la vez: guardar y rotar comparten `busy`.
  property bool busy: false
  property string busyKind: ""
  property string busyFile: ""
  property int progress: 0
  property string status: ""
  property bool statusError: false

  readonly property var rotations: [0, 1, 2, 3]

  function refresh() {
    if (!stateProc.running) stateProc.running = true
  }

  function readState(text) {
    try {
      var s = JSON.parse(text)
      root.connected = !!s.connected
      root.folder = s.folder || ""
      root.files = s.files || []
      root.current = s.current || ""
      root.rotation = s.rotation || 0
      root.streaming = !!s.streaming
    } catch (e) {
      root.connected = false
    }
  }

  function baseName(path) {
    return String(path || "").split("/").pop()
  }

  // La última línea útil de stderr: el CLI escribe "error: ...".
  function errorLine(text) {
    var lines = String(text || "").split("\n").filter(function(l) { return l.trim() !== "" })
    var last = lines.length ? lines[lines.length - 1].trim() : ""
    return last.replace(/^error:\s*/, "").slice(0, 180) || "?"
  }

  function put(path) {
    if (root.busy || !root.connected) return
    root.busy = true
    root.busyKind = "save"
    root.busyFile = path
    root.progress = 0
    root.status = ""
    usbProc.command = [root.tool, "poner", path]
    usbProc.running = true
  }

  function rotate(r) {
    if (root.busy || !root.connected || r === root.rotation) return
    root.busy = true
    root.busyKind = "rotate"
    root.progress = 0
    root.status = ""
    usbProc.command = [root.tool, "rotar", String(r * 90)]
    usbProc.running = true
  }

  function finish(code) {
    if (code === 0) {
      root.status = root.busyKind === "save"
        ? strings.t("saved").arg(root.baseName(root.busyFile))
        : strings.t("rotated")
      root.statusError = false
    } else {
      root.status = strings.t("failed").arg(root.errorLine(usbErr.text))
      root.statusError = true
    }
    root.busy = false
    root.busyKind = ""
    root.refresh()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Component.onCompleted: refresh()
  onOpenedChanged: if (opened) {
    if (!root.busy) root.status = ""
    refresh()
  }

  Timer {
    interval: 4000
    running: root.opened && !root.busy
    repeat: true
    onTriggered: root.refresh()
  }

  Process {
    id: stateProc
    command: ["/usr/bin/python3", root.backend, "state"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.readState(text)
    }
  }

  Process {
    id: usbProc
    // El CLI informa el progreso con "\r  saving...  42%".
    stdout: SplitParser {
      splitMarker: "\r"
      onRead: function(data) {
        var m = /(\d+)%/.exec(data)
        if (m) root.progress = Number(m[1])
      }
    }
    stderr: StdioCollector { id: usbErr; waitForEnd: true }
    onExited: function(exitCode, exitStatus) {
      // Deja que stderr termine de llegar antes de leerlo.
      var code = exitCode
      Qt.callLater(function() { root.finish(code) })
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰋩"
    opacity: root.connected ? 1 : 0.5
    onPressed: function(b) { root.toggle() }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: panel.loadedContent
    contentWidth: panel.fittedContentWidth(Style.space(420))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight, Style.space(760))

    content: PanelKeyCatcher {
      id: keyCatcher
      implicitHeight: panelColumn.implicitHeight
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      ScrollView {
        id: scrollArea
        anchors.fill: parent
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: panelColumn.implicitHeight > height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff

        Column {
          id: panelColumn
          width: scrollArea.availableWidth
          spacing: Style.space(14)

          // ---------- Cabecera ----------
          Item {
            width: parent.width
            implicitHeight: Math.max(heroIcon.implicitHeight, heroLabels.implicitHeight)

            Text {
              id: heroIcon
              textFormat: Text.PlainText
              text: "󰋩"
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.display
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
            }

            Column {
              id: heroLabels
              anchors.left: heroIcon.right
              anchors.leftMargin: Style.space(14)
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(2)

              Text {
                text: strings.t("title")
                textFormat: Text.PlainText
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.title
                font.bold: true
                elide: Text.ElideRight
                width: parent.width
              }

              Text {
                textFormat: Text.PlainText
                text: !root.connected ? strings.t("disconnected")
                  : root.streaming ? strings.t("streaming") : strings.t("stopped")
                color: root.connected && root.streaming ? Qt.darker(root.bar.foreground, 1.4) : Commons.Color.accent
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 1.2
                elide: Text.ElideRight
                width: parent.width
              }
            }
          }

          // ---------- Progreso / resultado ----------
          Rectangle {
            visible: root.busy || root.status !== ""
            width: parent.width
            height: statusCol.implicitHeight + Style.space(20)
            radius: Style.space(6)
            color: Style.hoverFillFor(root.bar.foreground, Commons.Color.accent)
            border.width: root.statusError ? 1 : 0
            border.color: Commons.Color.accent

            Column {
              id: statusCol
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              anchors.margins: Style.space(10)
              spacing: Style.space(8)

              Text {
                textFormat: Text.PlainText
                text: root.busy
                  ? (root.busyKind === "save"
                      ? strings.t("saving").arg(root.baseName(root.busyFile))
                      : strings.t("rotating"))
                  : root.status
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.body
                wrapMode: Text.Wrap
                width: parent.width
              }

              Rectangle {
                visible: root.busy
                width: parent.width
                height: Style.space(4)
                radius: height / 2
                color: Qt.darker(root.bar.foreground, 2.5)

                Rectangle {
                  width: parent.width * Math.max(0, Math.min(100, root.progress)) / 100
                  height: parent.height
                  radius: parent.radius
                  color: Commons.Color.accent
                }
              }
            }
          }

          // ---------- Archivos ----------
          Column {
            width: parent.width
            spacing: Style.space(10)

            PanelSectionHeader {
              text: strings.t("media")
              foreground: root.bar.foreground
              fontFamily: root.bar.fontFamily
            }

            Text {
              visible: root.files.length === 0
              textFormat: Text.PlainText
              text: strings.t("empty").arg(root.folder.replace(Quickshell.env("HOME"), "~"))
              color: Qt.darker(root.bar.foreground, 1.4)
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.Wrap
              width: parent.width
            }

            Grid {
              id: mediaGrid
              visible: root.files.length > 0
              width: parent.width
              columns: 3
              spacing: Style.spacing.xs
              readonly property real cellWidth: (width - spacing * (columns - 1)) / columns

              Repeater {
                model: root.files

                MediaTile {
                  required property var modelData
                  file: modelData
                  width: mediaGrid.cellWidth
                }
              }
            }

            Row {
              spacing: Style.spacing.xs

              Button {
                text: strings.t("openFolder")
                iconText: "󰉋"
                bordered: true
                foreground: root.bar.foreground
                fontFamily: root.bar.fontFamily
                fontSize: Style.font.caption
                onClicked: Quickshell.execDetached(["xdg-open", root.folder])
              }

              Button {
                text: strings.t("refresh")
                iconText: "󰑐"
                bordered: true
                foreground: root.bar.foreground
                fontFamily: root.bar.fontFamily
                fontSize: Style.font.caption
                onClicked: root.refresh()
              }
            }
          }

          PanelSeparator { foreground: root.bar.foreground }

          // ---------- Rotación ----------
          Column {
            width: parent.width
            spacing: Style.space(10)

            PanelSectionHeader {
              text: strings.t("rotation")
              foreground: root.bar.foreground
              fontFamily: root.bar.fontFamily
            }

            Grid {
              id: rotationRow
              width: parent.width
              columns: root.rotations.length
              spacing: Style.spacing.xs
              readonly property real cellWidth: (width - spacing * (columns - 1)) / columns

              Repeater {
                model: root.rotations

                Button {
                  required property int modelData
                  width: rotationRow.cellWidth
                  text: (modelData * 90) + "°"
                  active: root.rotation === modelData
                  enabled: root.connected && !root.busy
                  bordered: true
                  foreground: root.bar.foreground
                  fontFamily: root.bar.fontFamily
                  fontSize: Style.font.caption
                  horizontalPadding: Style.spacing.xs
                  onClicked: root.rotate(modelData)
                }
              }
            }
          }
        }
      }
    }
  }

  // Miniatura de un archivo: clic para ponerlo en la pantalla.
  component MediaTile: Rectangle {
    id: tile
    property var file: ({})
    readonly property bool isCurrent: file.path === root.current
    readonly property bool isBusy: root.busy && root.busyFile === file.path

    height: width + tileName.implicitHeight + Style.space(8)
    radius: Style.space(6)
    color: tileMouse.containsMouse
      ? Style.hoverFillFor(root.bar.foreground, Commons.Color.accent)
      : "transparent"
    border.width: isCurrent ? 2 : 1
    border.color: isCurrent ? Commons.Color.accent : Qt.darker(root.bar.foreground, 1.8)
    opacity: root.busy && !isBusy ? 0.5 : 1

    Item {
      id: thumbBox
      x: Style.space(4)
      y: Style.space(4)
      width: tile.width - Style.space(8)
      height: width
      clip: true

      Image {
        visible: !tile.file.video
        anchors.fill: parent
        source: tile.file.video ? "" : "file://" + tile.file.path
        sourceSize.width: 192
        sourceSize.height: 192
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
      }

      Text {
        visible: !!tile.file.video
        anchors.centerIn: parent
        textFormat: Text.PlainText
        text: "󰕧"
        color: root.bar.foreground
        font.family: root.bar.fontFamily
        font.pixelSize: Style.font.display
      }

      Text {
        visible: tile.isCurrent
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: Style.space(3)
        textFormat: Text.PlainText
        text: strings.t("current")
        color: Commons.Color.accent
        style: Text.Outline
        styleColor: "black"
        font.family: root.bar.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: true
      }
    }

    Text {
      id: tileName
      anchors.top: thumbBox.bottom
      anchors.topMargin: Style.space(2)
      anchors.horizontalCenter: parent.horizontalCenter
      width: parent.width - Style.space(8)
      textFormat: Text.PlainText
      text: tile.file.name || ""
      color: root.bar.foreground
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.caption
      elide: Text.ElideMiddle
      horizontalAlignment: Text.AlignHCenter
    }

    MouseArea {
      id: tileMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: root.busy || !root.connected ? Qt.ArrowCursor : Qt.PointingHandCursor
      onClicked: root.put(tile.file.path)
    }
  }
}
