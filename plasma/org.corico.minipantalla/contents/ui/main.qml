import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

import "../code/strings.js" as S

// Mini pantalla USB AX206 2.1" (2a55:9990) para Plasma 6. Igual que el panel de
// Omarchy: solo lista la carpeta y lanza `minipantalla poner/rotar`; el estado lo
// lee lcdstate.py sin abrir el USB.
PlasmoidItem {
  id: root

  readonly property string backend: String(Qt.resolvedUrl("../code/lcdstate.py")).replace(/^file:\/\//, "")
  readonly property string home: backend.replace(/\/\.local\/share\/.*$/, "")

  property bool connected: false
  property string folder: ""
  property var files: []
  property var ignored: []
  property string current: ""
  property int lcdRotation: 0
  property bool streaming: false
  property bool installed: true
  property string tool: ""

  property bool busy: false
  property string busyKind: ""
  property string busyFile: ""
  property string status: ""
  property bool statusError: false

  Plasmoid.icon: "video-display"
  Plasmoid.status: connected ? PlasmaCore.Types.ActiveStatus : PlasmaCore.Types.PassiveStatus
  toolTipMainText: S.t("title")
  toolTipSubText: !connected ? S.t("disconnected")
    : streaming ? (current ? S.t("saved").arg(baseName(current)) : S.t("streaming"))
    : S.t("stopped")

  // ---------- Ejecutar comandos ----------
  property var pending: ({})

  function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

  function exec(cmd, callback) {
    pending[cmd] = callback
    runner.connectSource(cmd)
  }

  P5Support.DataSource {
    id: runner
    engine: "executable"
    connectedSources: []
    onNewData: function(source, data) {
      var cb = root.pending[source]
      delete root.pending[source]
      disconnectSource(source)
      if (cb) cb(data["exit code"], data.stdout || "", data.stderr || "")
    }
  }

  readonly property string stateCmd: "/usr/bin/python3 " + shq(backend) + " state"

  function refresh() {
    if (pending[stateCmd]) return
    exec(stateCmd, function(code, out) { readState(out) })
  }

  function readState(text) {
    try {
      var s = JSON.parse(text)
      connected = !!s.connected
      folder = s.folder || ""
      files = s.files || []
      ignored = s.ignored || []
      current = s.current || ""
      lcdRotation = s.rotation || 0
      streaming = !!s.streaming
      installed = s.installed !== false
      tool = s.tool || ""
    } catch (e) {
      connected = false
    }
  }

  function baseName(path) { return String(path || "").split("/").pop() }

  function errorLine(text) {
    var lines = String(text || "").split(/[\r\n]/).filter(function(l) { return l.trim() !== "" })
    var last = lines.length ? lines[lines.length - 1].trim() : ""
    return last.replace(/^error:\s*/, "").slice(0, 180) || "?"
  }

  function runTool(kind, file, args) {
    if (busy || !installed) return
    busy = true
    busyKind = kind
    busyFile = file
    status = ""
    exec(shq(tool) + " " + args.map(shq).join(" "), function(code, out, err) {
      if (code === 0) {
        status = kind === "save" ? S.t("saved").arg(baseName(file))
          : kind === "rotate" ? S.t("rotated") : ""
        statusError = false
      } else {
        status = S.t("failed").arg(errorLine(err || out))
        statusError = true
      }
      busy = false
      busyKind = ""
      refresh()
    })
  }

  function put(path) { if (connected) runTool("save", path, ["poner", path]) }
  function rotate(r) { if (connected && r !== lcdRotation) runTool("rotate", "", ["rotar", String(r * 90)]) }
  function startService() { runTool("start", "", ["iniciar"]) }

  Component.onCompleted: refresh()
  onExpandedChanged: if (root.expanded) {
    if (!busy) status = ""
    refresh()
  }

  // Cerrado: cada 15 s para el icono y el tooltip. Abierto: cada 4 s.
  Timer {
    interval: root.expanded ? 4000 : 15000
    running: !root.busy
    repeat: true
    onTriggered: root.refresh()
  }

  // ---------- Panel ----------
  fullRepresentation: PlasmaExtras.Representation {
    Layout.minimumWidth: Kirigami.Units.gridUnit * 20
    Layout.preferredWidth: Kirigami.Units.gridUnit * 24
    Layout.preferredHeight: Kirigami.Units.gridUnit * 30
    collapseMarginsHint: true

    header: PlasmaExtras.PlasmoidHeading {
      RowLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Icon {
          source: "video-display"
          Layout.preferredWidth: Kirigami.Units.iconSizes.medium
          Layout.preferredHeight: Kirigami.Units.iconSizes.medium
          opacity: root.connected ? 1 : 0.5
        }

        ColumnLayout {
          Layout.fillWidth: true
          spacing: 0
          Kirigami.Heading {
            level: 3
            text: S.t("title")
            Layout.fillWidth: true
            elide: Text.ElideRight
          }
          PlasmaComponents.Label {
            text: !root.connected ? S.t("disconnected")
              : root.streaming ? S.t("streaming") : S.t("stopped")
            color: root.connected && root.streaming ? Kirigami.Theme.positiveTextColor
              : root.connected ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.disabledTextColor
            font: Kirigami.Theme.smallFont
            Layout.fillWidth: true
            elide: Text.ElideRight
          }
        }

        PlasmaComponents.Button {
          visible: root.connected && root.installed && !root.streaming
          text: S.t("startService")
          icon.name: "media-playback-start"
          enabled: !root.busy
          onClicked: root.startService()
        }
      }
    }

    contentItem: ColumnLayout {
      spacing: Kirigami.Units.largeSpacing

      PlasmaComponents.Label {
        visible: !root.installed
        text: S.t("missingCli")
        color: Kirigami.Theme.negativeTextColor
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
      }

      // Progreso / resultado
      Kirigami.InlineMessage {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        Layout.topMargin: Kirigami.Units.smallSpacing
        visible: root.busy || root.status !== ""
        type: root.statusError ? Kirigami.MessageType.Error
          : root.busy ? Kirigami.MessageType.Information : Kirigami.MessageType.Positive
        text: root.busy
          ? (root.busyKind === "save" ? S.t("saving").arg(root.baseName(root.busyFile))
             : root.busyKind === "rotate" ? S.t("rotating") : "…")
          : root.status
      }

      Kirigami.Heading {
        level: 5
        text: S.t("media")
        Layout.leftMargin: Kirigami.Units.largeSpacing
        opacity: 0.8
      }

      PlasmaComponents.Label {
        visible: root.files.length === 0
        text: S.t("empty").arg(root.folder.replace(root.home, "~"))
        wrapMode: Text.Wrap
        opacity: 0.7
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
      }

      PlasmaComponents.Label {
        visible: root.ignored.length > 0
        text: S.t("ignored").arg(root.ignored.join(", "))
        color: Kirigami.Theme.neutralTextColor
        font: Kirigami.Theme.smallFont
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
      }

      PlasmaComponents.ScrollView {
        id: scroll
        visible: root.files.length > 0
        Layout.fillWidth: true
        Layout.fillHeight: true
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

        GridView {
          id: grid
          model: root.files
          clip: true
          readonly property int columns: 3
          cellWidth: Math.floor(width / columns)
          cellHeight: cellWidth + Kirigami.Units.gridUnit * 1.5
          leftMargin: Kirigami.Units.smallSpacing
          rightMargin: Kirigami.Units.smallSpacing

          delegate: Item {
            id: tile
            required property var modelData
            readonly property bool isCurrent: modelData.path === root.current
            readonly property bool isBusy: root.busy && root.busyFile === modelData.path
            width: grid.cellWidth
            height: grid.cellHeight
            opacity: root.busy && !isBusy ? 0.5 : 1

            Rectangle {
              anchors.fill: parent
              anchors.margins: Kirigami.Units.smallSpacing / 2
              radius: Kirigami.Units.cornerRadius
              color: mouse.containsMouse ? Qt.alpha(Kirigami.Theme.highlightColor, 0.2) : "transparent"
              border.width: tile.isCurrent ? 2 : 1
              border.color: tile.isCurrent ? Kirigami.Theme.highlightColor
                : Qt.alpha(Kirigami.Theme.textColor, 0.15)

              Item {
                id: thumb
                x: Kirigami.Units.smallSpacing
                y: Kirigami.Units.smallSpacing
                width: parent.width - 2 * Kirigami.Units.smallSpacing
                height: width
                clip: true

                Image {
                  visible: !tile.modelData.video
                  anchors.fill: parent
                  source: tile.modelData.video ? "" : "file://" + tile.modelData.path
                  sourceSize.width: 192
                  sourceSize.height: 192
                  fillMode: Image.PreserveAspectCrop
                  asynchronous: true
                }

                Kirigami.Icon {
                  visible: !!tile.modelData.video
                  anchors.centerIn: parent
                  width: Kirigami.Units.iconSizes.large
                  height: width
                  source: "video-x-generic"
                }

                PlasmaComponents.BusyIndicator {
                  visible: tile.isBusy
                  anchors.centerIn: parent
                }

                Rectangle {
                  visible: tile.isCurrent
                  anchors.left: parent.left
                  anchors.bottom: parent.bottom
                  anchors.margins: 3
                  width: currentLabel.implicitWidth + 6
                  height: currentLabel.implicitHeight + 2
                  radius: 3
                  color: Kirigami.Theme.highlightColor
                  PlasmaComponents.Label {
                    id: currentLabel
                    anchors.centerIn: parent
                    text: S.t("current")
                    color: Kirigami.Theme.highlightedTextColor
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                    font.bold: true
                  }
                }
              }

              PlasmaComponents.Label {
                anchors.top: thumb.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: Kirigami.Units.smallSpacing
                anchors.topMargin: 2
                text: tile.modelData.name || ""
                font: Kirigami.Theme.smallFont
                elide: Text.ElideMiddle
                horizontalAlignment: Text.AlignHCenter
              }

              MouseArea {
                id: mouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: root.busy || !root.connected ? Qt.ArrowCursor : Qt.PointingHandCursor
                onClicked: root.put(tile.modelData.path)
              }

              PlasmaComponents.ToolTip { text: tile.modelData.name || ""; visible: mouse.containsMouse }
            }
          }
        }
      }

      Item { visible: root.files.length === 0; Layout.fillHeight: true }

      RowLayout {
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing

        PlasmaComponents.Button {
          text: S.t("openFolder")
          icon.name: "folder-open"
          onClicked: Qt.openUrlExternally("file://" + root.folder)
        }
        PlasmaComponents.Button {
          text: S.t("refresh")
          icon.name: "view-refresh"
          onClicked: root.refresh()
        }
      }

      Kirigami.Separator { Layout.fillWidth: true }

      Kirigami.Heading {
        level: 5
        text: S.t("rotation")
        Layout.leftMargin: Kirigami.Units.largeSpacing
        opacity: 0.8
      }

      RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        Layout.bottomMargin: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing

        Repeater {
          model: [0, 1, 2, 3]
          PlasmaComponents.Button {
            required property int modelData
            Layout.fillWidth: true
            text: (modelData * 90) + "°"
            checkable: true
            checked: root.lcdRotation === modelData
            enabled: root.connected && root.installed && !root.busy
            onClicked: { checked = Qt.binding(function() { return root.lcdRotation === modelData }); root.rotate(modelData) }
          }
        }
      }
    }
  }
}
