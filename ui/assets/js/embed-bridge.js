/**
 * Parent site ↔ embed communication via postMessage.
 * Parent example:
 *   iframe.contentWindow.postMessage({ type: 'geospatial-gui', action: 'setData', payload: {...} }, '*');
 */
(function () {
  const PROTOCOL = "geospatial-gui";

  function isEmbedded() {
    try {
      return window.self !== window.top;
    } catch {
      return true;
    }
  }

  function notifyParent(action, payload) {
    if (!isEmbedded()) return;
    window.parent.postMessage(
      { type: PROTOCOL, action, payload },
      "*"
    );
  }

  function onMessage(event) {
    const data = event.data;
    if (!data || data.type !== PROTOCOL) return;
    window.dispatchEvent(
      new CustomEvent("geospatial-gui", { detail: data })
    );
  }

  window.GeospatialEmbed = {
    protocol: PROTOCOL,
    isEmbedded,
    notifyParent,
    ready() {
      notifyParent("ready", { embed: document.body.dataset.embed || "unknown" });
    },
  };

  window.addEventListener("message", onMessage);
  document.addEventListener("DOMContentLoaded", () => GeospatialEmbed.ready());
})();
