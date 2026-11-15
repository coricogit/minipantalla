import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls

// Panel de la bandeja: el mismo contenido que el widget de KDE Plasma
// (plasma/org.corico.minipantalla) y el plugin de Omarchy: archivos de la
// carpeta, rotación y encaje. Todo lo hace minipantalla.pyw (backend).
Window {
  id: root

  width: 400
  height: 560
  visible: false
  title: t("title")
  color: "transparent"
  flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

  onActiveChanged: if (!active && visible) hide()

  SystemPalette { id: pal; colorGroup: SystemPalette.Active }
  readonly property color fg: pal.windowText
  readonly property color bg: pal.window
  readonly property color accent: "#38BDF8"
  readonly property int pad: 14
  readonly property real small: 11

  property var st: ({})
  Connections {
    target: backend
    function onStateChanged() { root.parse() }
  }
  Component.onCompleted: parse()
  function parse() { try { st = JSON.parse(backend.stateText) } catch (e) {} }

  readonly property var files: st.files || []
  readonly property bool connected: !!st.connected
  readonly property bool paused: !!st.paused

  // ---------- Textos ----------
  readonly property var strings: ({
    en: {
      title: "Mini Screen", disconnected: "Not connected", streaming: "Streaming %1", paused: "Screen off",
      nofile: "Connected · choose a file", connecting: "Connecting…", sleeping: "Suspended",
      badfile: "Can't play %1", empty: "Copy GIFs, images or videos to %1",
      openFolder: "Open folder", rotation: "Rotation", fit: "Fit", cover: "Fill", contain: "Fit", stretch: "Stretch",
      current: "CURRENT", turnOff: "Turn off", turnOn: "Turn on",
      ignored: "Skipped, no .gif/.png/.jpg/.mp4… extension: %1",
      driver: "Plug the screen in. If it's plugged in, it needs the WinUSB driver (see the README)."
    },
    es: {
      title: "Mini pantalla", disconnected: "No conectada", streaming: "Transmitiendo %1", paused: "Pantalla apagada",
      nofile: "Conectada · elige un archivo", connecting: "Conectando…", sleeping: "Suspendido",
      badfile: "No se puede reproducir %1", empty: "Copia GIFs, imágenes o videos a %1",
      openFolder: "Abrir carpeta", rotation: "Rotación", fit: "Encaje", cover: "Llenar", contain: "Encajar", stretch: "Estirar",
      current: "ACTUAL", turnOff: "Apagar", turnOn: "Encender",
      ignored: "Ignorados por no tener extensión .gif/.png/.jpg/.mp4…: %1",
      driver: "Conecta la pantalla. Si ya está conectada, necesita el driver WinUSB (mira el README)."
    }
  })
  function t(key) {
    var lang = st.lang === "es" ? "es" : "en"
    return strings[lang][key] || strings.en[key] || key
  }

  readonly property string statusText: {
    var s = st.state || "connecting"
    if (s === "streaming") return t("streaming").arg(st.currentName || "")
    if (s === "badfile") return t("badfile").arg(st.currentName || "")
    if (s === "sleeping") return t("sleeping")
    if (!connected) return t("disconnected")
    return t(s)
  }
  readonly property color statusColor: {
    var s = st.state
    if (s === "streaming") return "#22C55E"
    if (!connected) return "#EF4444"
    if (s === "paused" || s === "sleeping") return Qt.rgba(fg.r, fg.g, fg.b, 0.4)
    return "#F59E0B"
  }

  // ---------- Marco ----------
  Rectangle {
    anchors.fill: parent
    radius: 10
    color: root.bg
    border.color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.18)
    clip: true

    ColumnLayout {
      anchors.fill: parent
      anchors.margins: 1
      spacing: 0

      // Cabecera
      RowLayout {
        Layout.fillWidth: true
        Layout.margins: root.pad
        spacing: 12

        Rectangle {
          Layout.preferredWidth: 40
          Layout.preferredHeight: 40
          radius: 20
          color: "#111111"
          border.width: 3
          border.color: root.statusColor
          Rectangle {
            visible: root.st.state === "streaming"
            anchors.centerIn: parent
            width: 20; height: 20; radius: 10
            color: root.accent
          }
        }
        ColumnLayout {
          Layout.fillWidth: true
          spacing: 1
          Txt { text: root.t("title"); font.pixelSize: 16; font.bold: true }
          Txt {
            text: root.statusText
            font.pixelSize: root.small
            opacity: 0.75
            elide: Text.ElideMiddle
            Layout.fillWidth: true
          }
        }
        Button {
          text: root.paused ? root.t("turnOn") : root.t("turnOff")
          enabled: root.connected || root.paused
          onClicked: backend.togglePause()
        }
        ToolButton { text: "✕"; onClicked: root.hide() }
      }

      Sep {}

      // Avisos
      Txt {
        visible: !root.connected && root.st.state !== "sleeping"
        text: root.t("driver")
        wrapMode: Text.Wrap
        font.pixelSize: root.small
        opacity: 0.75
        Layout.fillWidth: true
        Layout.margins: root.pad
        Layout.bottomMargin: 0
      }
      Txt {
        visible: !!root.st.msg && root.connected
        text: root.st.msg || ""
        color: "#F59E0B"
        wrapMode: Text.Wrap
        font.pixelSize: root.small
        Layout.fillWidth: true
        Layout.margins: root.pad
        Layout.bottomMargin: 0
      }

      // Archivos
      GridView {
        id: grid
        visible: root.files.length > 0
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.margins: root.pad - 4
        clip: true
        cellWidth: Math.floor(width / 3)
        cellHeight: cellWidth + 20
        model: root.files
        ScrollBar.vertical: ScrollBar {}

        delegate: Item {
          id: tile
          required property var modelData
          readonly property bool isCurrent: modelData.path === root.st.current
          width: grid.cellWidth
          height: grid.cellHeight

          Rectangle {
            id: frame
            anchors.horizontalCenter: parent.horizontalCenter
            y: 4
            width: parent.width - 10
            height: width
            radius: width / 2
            color: "#111111"
            border.width: tile.isCurrent ? 3 : (mouse.containsMouse ? 2 : 0)
            border.color: tile.isCurrent ? root.accent : Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.4)

            // Solo para conocer la proporción de la imagen (no se dibuja)
            Image {
              id: thumb
              visible: false
              source: tile.modelData.thumb || ""
              sourceSize.width: 192
              asynchronous: true
            }
            // Miniatura recortada en círculo, como la pantalla (Canvas: vale con el renderizado por software)
            Canvas {
              id: circle
              anchors.fill: parent
              anchors.margins: 3
              property string src: tile.modelData.thumb || ""
              onSrcChanged: { if (src) loadImage(src); requestPaint() }
              onImageLoaded: requestPaint()
              Connections { target: thumb; function onStatusChanged() { circle.requestPaint() } }
              onPaint: {
                var c = getContext("2d")
                c.reset()
                c.beginPath()
                c.arc(width / 2, height / 2, width / 2, 0, 2 * Math.PI)
                c.closePath()
                c.clip()
                c.fillStyle = "#222222"
                c.fill()
                if (src && isImageLoaded(src) && thumb.implicitWidth > 0) {
                  var s = Math.max(width / thumb.implicitWidth, height / thumb.implicitHeight)
                  var dw = thumb.implicitWidth * s, dh = thumb.implicitHeight * s
                  c.drawImage(src, (width - dw) / 2, (height - dh) / 2, dw, dh)
                }
              }
            }

            Txt {
              visible: !!tile.modelData.video
              anchors.centerIn: parent
              text: "▶"
              color: "white"
              font.pixelSize: 22
              style: Text.Outline
              styleColor: "#000000"
            }

            Rectangle {
              visible: tile.isCurrent
              anchors.horizontalCenter: parent.horizontalCenter
              anchors.bottom: parent.bottom
              anchors.bottomMargin: 4
              width: curLabel.implicitWidth + 8
              height: curLabel.implicitHeight + 2
              radius: 3
              color: root.accent
              Txt {
                id: curLabel
                anchors.centerIn: parent
                text: root.t("current")
                color: "#0B1220"
                font.pixelSize: 9
                font.bold: true
              }
            }
          }

          Txt {
            anchors.top: frame.bottom
            anchors.topMargin: 2
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 4
            anchors.rightMargin: 4
            text: tile.modelData.name || ""
            font.pixelSize: root.small
            elide: Text.ElideMiddle
            horizontalAlignment: Text.AlignHCenter
          }

          MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: backend.choose(tile.modelData.path)
          }
          ToolTip.visible: mouse.containsMouse
          ToolTip.delay: 500
          ToolTip.text: tile.modelData.name || ""
        }
      }

      // Carpeta vacía
      Item {
        visible: root.files.length === 0
        Layout.fillWidth: true
        Layout.fillHeight: true
        Txt {
          anchors.centerIn: parent
          width: parent.width - 2 * root.pad
          text: root.t("empty").arg(root.st.folder || "")
          wrapMode: Text.WrapAnywhere
          horizontalAlignment: Text.AlignHCenter
          opacity: 0.7
        }
      }

      Txt {
        visible: (root.st.ignored || []).length > 0
        text: root.t("ignored").arg((root.st.ignored || []).join(", "))
        wrapMode: Text.Wrap
        font.pixelSize: root.small
        opacity: 0.6
        Layout.fillWidth: true
        Layout.leftMargin: root.pad
        Layout.rightMargin: root.pad
      }

      Sep {}

      // Rotación y encaje
      GridLayout {
        Layout.fillWidth: true
        Layout.margins: root.pad
        columns: 2
        columnSpacing: 10
        rowSpacing: 8

        Txt { text: root.t("rotation"); opacity: 0.75 }
        RowLayout {
          spacing: 4
          Repeater {
            model: [0, 1, 2, 3]
            Button {
              required property int modelData
              text: (modelData * 90) + "°"
              checkable: true
              checked: root.st.rotation === modelData
              onClicked: backend.rotate(modelData)
              Layout.preferredWidth: 56
            }
          }
        }

        Txt { text: root.t("fit"); opacity: 0.75 }
        RowLayout {
          spacing: 4
          Repeater {
            model: ["cover", "contain", "stretch"]
            Button {
              required property string modelData
              text: root.t(modelData)
              checkable: true
              checked: root.st.fit === modelData
              onClicked: backend.setFit(modelData)
              Layout.preferredWidth: 76
            }
          }
        }
      }

      Button {
        Layout.alignment: Qt.AlignHCenter
        Layout.bottomMargin: root.pad
        text: root.t("openFolder")
        onClicked: backend.openFolder()
      }
    }
  }

  component Txt: Text {
    color: root.fg
    font.pixelSize: 13
  }

  component Sep: Rectangle {
    Layout.fillWidth: true
    Layout.preferredHeight: 1
    color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.12)
  }
}
