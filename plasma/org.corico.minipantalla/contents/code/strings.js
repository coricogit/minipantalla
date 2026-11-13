.pragma library

var STRINGS = {
  en: {
    title: "Mini Screen",
    disconnected: "Not connected",
    streaming: "Streaming",
    stopped: "Connected · service stopped",
    media: "GIFs and images",
    empty: "Copy GIFs, images or videos to %1",
    openFolder: "Open folder",
    refresh: "Refresh",
    rotation: "Rotation",
    saving: "Switching to %1…",
    rotating: "Applying rotation…",
    saved: "Streaming %1",
    rotated: "Rotation applied",
    failed: "Could not finish: %1",
    current: "CURRENT",
    startService: "Start service",
    missingCli: "The minipantalla CLI is missing. Run install.sh from the minipantalla repo.",
    ignored: "Skipped, no .gif/.png/.jpg/.mp4… extension: %1"
  },
  es: {
    title: "Mini pantalla",
    disconnected: "No conectada",
    streaming: "Transmitiendo",
    stopped: "Conectada · servicio parado",
    media: "GIFs e imágenes",
    empty: "Copia GIFs, imágenes o videos a %1",
    openFolder: "Abrir carpeta",
    refresh: "Actualizar",
    rotation: "Rotación",
    saving: "Cambiando a %1…",
    rotating: "Aplicando rotación…",
    saved: "Transmitiendo %1",
    rotated: "Rotación aplicada",
    failed: "No se pudo completar: %1",
    current: "ACTUAL",
    startService: "Iniciar servicio",
    missingCli: "Falta el CLI minipantalla. Ejecuta install.sh del repo minipantalla.",
    ignored: "Ignorados por no tener extensión .gif/.png/.jpg/.mp4…: %1"
  }
}

function t(key) {
  var lang = Qt.locale().name.indexOf("es") === 0 ? "es" : "en"
  return STRINGS[lang][key] || STRINGS.en[key] || key
}
