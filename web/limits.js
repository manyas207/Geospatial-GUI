/**
 * Shared server limits for uploads and chat (fetched from GET /api/config).
 */
(function () {
  const DEFAULTS = {
    upload_max_file_bytes: 500 * 1024 * 1024,
    upload_max_total_bytes: 2 * 1024 * 1024 * 1024,
    chat_max_question_length: 2000,
    chat_rate_limit_max: 15,
    chat_rate_limit_window: 60,
  };

  let limits = { ...DEFAULTS };
  let loadPromise = null;

  function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes < 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }

  function get() {
    return { ...limits };
  }

  async function load() {
    if (!loadPromise) {
      loadPromise = fetch("/api/config")
        .then((response) => (response.ok ? response.json() : null))
        .then((payload) => {
          if (payload && typeof payload === "object") {
            limits = { ...DEFAULTS, ...payload };
          }
          return limits;
        })
        .catch(() => limits);
    }
    return loadPromise;
  }

  function validateUploadFiles(files, existingFiles) {
    const current = Array.isArray(existingFiles) ? existingFiles : [];
    const incoming = Array.isArray(files) ? files : [];
    const perFileMax = limits.upload_max_file_bytes;
    const totalMax = limits.upload_max_total_bytes;
    let totalBytes = current.reduce((sum, file) => sum + (file.size || 0), 0);

    for (const file of incoming) {
      if ((file.size || 0) > perFileMax) {
        return {
          ok: false,
          message: `${file.name} is too large (max ${formatBytes(perFileMax)} per file).`,
        };
      }
      totalBytes += file.size || 0;
      if (totalBytes > totalMax) {
        return {
          ok: false,
          message: `Selected files exceed the ${formatBytes(totalMax)} upload limit.`,
        };
      }
    }

    return { ok: true };
  }

  function validateChatQuestion(question) {
    const q = (question || "").trim();
    if (!q) {
      return { ok: false, message: "Enter a question first." };
    }
    const maxLen = limits.chat_max_question_length;
    if (q.length > maxLen) {
      return {
        ok: false,
        message: `Question is too long (max ${maxLen} characters).`,
      };
    }
    return { ok: true, question: q };
  }

  function applyChatInputLimits(inputEl) {
    if (!inputEl) return;
    inputEl.maxLength = limits.chat_max_question_length;
  }

  window.AppLimits = {
    load,
    get,
    formatBytes,
    validateUploadFiles,
    validateChatQuestion,
    applyChatInputLimits,
  };
})();
