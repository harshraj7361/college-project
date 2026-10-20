/**
 * app.js - Frontend Controller for PDF Notes Generator (v2 - Topic-wise)
 * -----------------------------------------------------------------------
 * Key changes from v1:
 * - Renders SEPARATE topic panels instead of one combined block.
 * - Topic navigation sidebar with active-link highlighting on scroll.
 * - Collapsible individual topic panels (click header to collapse/expand).
 * - Overall summary displayed at the bottom with a special section.
 * - Download and Copy still work on the full combined notes text.
 */

document.addEventListener("DOMContentLoaded", () => {

  // ── DOM References ─────────────────────────────────────────────────────────
  const dropZone          = document.getElementById("dropZone");
  const dropZoneContent   = document.getElementById("dropZoneContent");
  const pdfFileInput      = document.getElementById("pdfFileInput");
  const browseFileBtn     = document.getElementById("browseFileBtn");
  const selectedFileChip  = document.getElementById("selectedFileChip");
  const selectedFileName  = document.getElementById("selectedFileName");
  const selectedFileSize  = document.getElementById("selectedFileSize");
  const removeFileBtn     = document.getElementById("removeFileBtn");

  const noteStyleSelect   = document.getElementById("noteStyleSelect");
  const generateBtn       = document.getElementById("generateBtn");
  const loadSampleBtn     = document.getElementById("loadSampleBtn");

  const apiKeyToggleBtn   = document.getElementById("apiKeyToggleBtn");
  const apiKeyBar         = document.getElementById("apiKeyBar");
  const apiStatusLabel    = document.getElementById("apiStatusLabel");
  const customApiKeyInput = document.getElementById("customApiKeyInput");
  const saveApiKeyBtn     = document.getElementById("saveApiKeyBtn");

  const loadingCard       = document.getElementById("loadingCard");
  const loadingStep       = document.getElementById("loadingStep");

  const errorAlert        = document.getElementById("errorAlert");
  const errorMessage      = document.getElementById("errorMessage");
  const closeAlertBtn     = document.getElementById("closeAlertBtn");

  // New notes output section elements
  const notesOutput       = document.getElementById("notesOutput");
  const docNameDisplay    = document.getElementById("docNameDisplay");
  const pageCountPill     = document.getElementById("pageCountPill");
  const wordCountPill     = document.getElementById("wordCountPill");
  const topicCountPill    = document.getElementById("topicCountPill");
  const enginePill        = document.getElementById("enginePill");
  const topicNavList      = document.getElementById("topicNavList");
  const notesPanels       = document.getElementById("notesPanels");

  // View tabs & Chat DOM elements
  const tabTopicNotes         = document.getElementById("tabTopicNotes");
  const tabAskPdf             = document.getElementById("tabAskPdf");
  const openChatBtn           = document.getElementById("openChatBtn");
  const notesBodyLayout       = document.getElementById("notesBodyLayout");
  const chatSection           = document.getElementById("chatSection");
  const chatDocSubtitle       = document.getElementById("chatDocSubtitle");
  const clearChatBtn          = document.getElementById("clearChatBtn");
  const suggestionsChips      = document.getElementById("suggestionsChips");
  const chatMessagesContainer = document.getElementById("chatMessagesContainer");
  const chatForm              = document.getElementById("chatForm");
  const chatInput             = document.getElementById("chatInput");
  const chatSendBtn           = document.getElementById("chatSendBtn");

  const copyNotesBtn      = document.getElementById("copyNotesBtn");
  const copyBtnText       = document.getElementById("copyBtnText");
  const downloadTxtBtn    = document.getElementById("downloadTxtBtn");
  const resetBtn          = document.getElementById("resetBtn");
  const toastContainer    = document.getElementById("toastContainer");

  // ── State ──────────────────────────────────────────────────────────────────
  let selectedFile     = null;
  let rawNotesText     = "";  // Combined all-topic text for copy/download
  let extractedPdfText = "";  // Full plain text from PDF for answering questions
  let chatMessages     = [];  // [{role, text, time, engine, isNotFound}]
  let isChatGenerating = false;
  let activeTab        = "notes";
  let progressInterval = null;

  // ── Init ───────────────────────────────────────────────────────────────────
  checkBackendHealth();
  loadSavedApiKey();

  // ── File Selection & Drag-and-Drop ────────────────────────────────────────
  browseFileBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    pdfFileInput.click();
  });

  dropZone.addEventListener("click", () => {
    if (!selectedFile) pdfFileInput.click();
  });

  pdfFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleFileSelected(e.target.files[0]);
  });

  ["dragenter", "dragover"].forEach(ev =>
    dropZone.addEventListener(ev, (e) => { e.preventDefault(); dropZone.classList.add("drag-active"); })
  );

  ["dragleave", "drop"].forEach(ev =>
    dropZone.addEventListener(ev, (e) => { e.preventDefault(); dropZone.classList.remove("drag-active"); })
  );

  dropZone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) handleFileSelected(dt.files[0]);
  });

  removeFileBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    clearSelectedFile();
  });

  function handleFileSelected(file) {
    hideError();

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Invalid file type. Please upload a PDF (.pdf) file.");
      return;
    }
    const maxBytes = 15 * 1024 * 1024;
    if (file.size > maxBytes) {
      showError("File is too large. Maximum allowed size is 15 MB.");
      return;
    }
    if (file.size === 0) {
      showError("The selected file is empty (0 bytes). Please choose a valid PDF.");
      return;
    }

    selectedFile = file;
    selectedFileName.textContent = file.name;
    selectedFileSize.textContent = formatBytes(file.size);
    dropZoneContent.classList.add("hidden");
    selectedFileChip.classList.remove("hidden");
    generateBtn.disabled = false;
  }

  function clearSelectedFile() {
    selectedFile = null;
    pdfFileInput.value = "";
    selectedFileChip.classList.add("hidden");
    dropZoneContent.classList.remove("hidden");
    generateBtn.disabled = true;
  }

  // ── API Key Bar ────────────────────────────────────────────────────────────
  apiKeyToggleBtn.addEventListener("click", () => {
    apiKeyBar.classList.toggle("hidden");
    if (!apiKeyBar.classList.contains("hidden")) customApiKeyInput.focus();
  });

  saveApiKeyBtn.addEventListener("click", () => {
    const key = customApiKeyInput.value.trim();
    if (key) {
      localStorage.setItem("gemini_api_key", key);
      apiStatusLabel.textContent = "API Key Saved";
      showToast("Gemini API key saved in browser storage!", "success");
    } else {
      localStorage.removeItem("gemini_api_key");
      apiStatusLabel.textContent = "API Key (Default)";
      showToast("Cleared custom API key.", "info");
    }
    apiKeyBar.classList.add("hidden");
  });

  function loadSavedApiKey() {
    const saved = localStorage.getItem("gemini_api_key");
    if (saved) {
      customApiKeyInput.value = saved;
      apiStatusLabel.textContent = "API Key Active";
    }
  }

  async function checkBackendHealth() {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        if (data.has_gemini_api_key) apiStatusLabel.textContent = "Gemini Ready";
      }
    } catch (err) {
      console.warn("Backend health check failed:", err);
    }
  }

  // ── Sample PDF Loader ──────────────────────────────────────────────────────
  loadSampleBtn.addEventListener("click", async () => {
    try {
      showToast("Loading Operating Systems sample PDF...", "info");
      const res = await fetch("/sample_pdfs/operating_systems_notes.pdf");
      if (!res.ok) throw new Error("Sample PDF not found on server.");
      const blob = await res.blob();
      const file = new File([blob], "operating_systems_notes.pdf", { type: "application/pdf" });
      handleFileSelected(file);
      showToast("Sample PDF loaded! Click 'Generate Notes'.", "success");
    } catch (err) {
      showError("Could not load sample PDF: " + err.message);
    }
  });

  // ── Generate Notes ─────────────────────────────────────────────────────────
  generateBtn.addEventListener("click", async () => {
    if (!selectedFile) { showError("Please select a PDF file first."); return; }

    hideError();
    notesOutput.classList.add("hidden");
    loadingCard.classList.remove("hidden");
    generateBtn.disabled = true;
    startProgressAnimation();

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("note_style", noteStyleSelect.value);

    const storedKey = localStorage.getItem("gemini_api_key") || customApiKeyInput.value.trim();
    if (storedKey) formData.append("custom_api_key", storedKey);

    try {
      const response = await fetch("/api/generate-notes", { method: "POST", body: formData });

      stopProgressAnimation();
      loadingCard.classList.add("hidden");
      generateBtn.disabled = false;

      const data = await response.json();

      if (!response.ok) {
        const msg = data.detail || "Failed to generate notes.";
        showError(msg);
        showToast(msg, "error");
        return;
      }

      renderNotesOutput(data);
      showToast(`Notes generated for ${data.topic_count} topic(s)!`, "success");

    } catch (err) {
      stopProgressAnimation();
      loadingCard.classList.add("hidden");
      generateBtn.disabled = false;
      const msg = "Network error: Could not reach the backend. Make sure the server is running.";
      showError(msg);
      showToast(msg, "error");
      console.error(err);
    }
  });

  // Loading step animation
  function startProgressAnimation() {
    const steps = [
      "Reading PDF pages with PyMuPDF...",
      "Detecting chapters, headings, and topics...",
      "Segmenting document into topic chunks...",
      "Generating detailed notes per topic with AI...",
      "Formatting structured study notes...",
      "Building topic navigation index..."
    ];
    let i = 0;
    loadingStep.textContent = steps[0];
    progressInterval = setInterval(() => {
      i = (i + 1) % steps.length;
      loadingStep.textContent = steps[i];
    }, 1900);
  }

  function stopProgressAnimation() {
    if (progressInterval) { clearInterval(progressInterval); progressInterval = null; }
  }

  // ── Render Topic-wise Notes Output ────────────────────────────────────────
  function renderNotesOutput(data) {
    rawNotesText = data.notes || "";
    extractedPdfText = data.extracted_text || "";

    // Update doc header metadata
    const docTitle = data.filename || (selectedFile ? selectedFile.name : "document.pdf");
    docNameDisplay.textContent    = docTitle;
    pageCountPill.textContent     = `📄 ${data.pages} ${data.pages === 1 ? "Page" : "Pages"}`;
    wordCountPill.textContent     = `📝 ${(data.word_count || 0).toLocaleString()} Words`;
    topicCountPill.textContent    = `📚 ${data.topic_count || 0} Topics`;
    enginePill.textContent        = `⚡ ${data.engine || "AI Engine"}`;

    // Setup chat for this document
    chatDocSubtitle.textContent = `Answers are generated strictly from "${docTitle}" (${data.pages} pages)`;
    resetChatForNewDoc(docTitle, data.pages, data.topic_count);
    switchTab("notes");

    const topics = data.topics || [];

    // Clear previous content
    topicNavList.innerHTML = "";
    notesPanels.innerHTML  = "";

    // Build topic nav + panels
    topics.forEach((topic, index) => {
      const sectionId = `topic-section-${index}`;
      const navId     = `topic-nav-${index}`;

      // ── Nav item ────────────────────────────────────────────────────────────
      const navItem = document.createElement("a");
      navItem.className   = "topic-nav-item";
      navItem.id          = navId;
      navItem.href        = `#${sectionId}`;
      navItem.setAttribute("data-target", sectionId);
      navItem.innerHTML   = `
        <span class="topic-nav-icon">📄</span>
        <span>${escapeHtml(topic.title)}</span>
      `;
      navItem.addEventListener("click", (e) => {
        e.preventDefault();
        document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
        setActiveNav(navId);
      });
      topicNavList.appendChild(navItem);

      // ── Topic panel ─────────────────────────────────────────────────────────
      const panel = document.createElement("div");
      panel.className = "topic-panel";
      panel.id        = sectionId;
      panel.setAttribute("data-nav-id", navId);

      panel.innerHTML = `
        <div class="topic-panel-header" role="button" aria-expanded="true" title="Click to collapse/expand">
          <div class="topic-panel-title">
            <span class="topic-num-badge">${index + 1}</span>
            ${escapeHtml(topic.title)}
          </div>
          <svg class="topic-collapse-icon" width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        <div class="topic-panel-body">
          ${renderMarkdown(topic.notes || "")}
        </div>
      `;

      // Toggle collapse on header click
      const header = panel.querySelector(".topic-panel-header");
      header.addEventListener("click", () => {
        panel.classList.toggle("collapsed");
        header.setAttribute("aria-expanded", !panel.classList.contains("collapsed"));
      });

      notesPanels.appendChild(panel);
    });

    // ── Overall Summary at the bottom ──────────────────────────────────────
    if (data.overall_summary) {
      const summaryDiv = document.createElement("div");
      summaryDiv.className = "overall-summary-panel";
      summaryDiv.id        = "section-overall-summary";
      summaryDiv.innerHTML = `
        <div class="overall-summary-title">
          <span>📋</span> Overall Document Summary
        </div>
        ${renderMarkdown(data.overall_summary)}
      `;
      notesPanels.appendChild(summaryDiv);
    }

    // Show the whole section
    notesOutput.classList.remove("hidden");
    notesOutput.scrollIntoView({ behavior: "smooth", block: "start" });

    // Start scroll-spy for active nav item
    setupScrollSpy();
  }

  // ── Scroll Spy: highlight active nav item while scrolling ─────────────────
  function setupScrollSpy() {
    const panels = notesPanels.querySelectorAll(".topic-panel");

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const navId = entry.target.getAttribute("data-nav-id");
          if (navId) setActiveNav(navId);
        }
      });
    }, { root: null, rootMargin: "-20% 0px -70% 0px", threshold: 0 });

    panels.forEach(p => observer.observe(p));
  }

  function setActiveNav(activeId) {
    document.querySelectorAll(".topic-nav-item").forEach(item => {
      item.classList.toggle("active", item.id === activeId);
    });
  }

  // ── Copy & Download ────────────────────────────────────────────────────────
  copyNotesBtn.addEventListener("click", async () => {
    if (!rawNotesText) return;
    try {
      await navigator.clipboard.writeText(rawNotesText);
      const orig = copyBtnText.textContent;
      copyBtnText.textContent = "Copied!";
      showToast("All notes copied to clipboard!", "success");
      setTimeout(() => { copyBtnText.textContent = orig; }, 2000);
    } catch (err) {
      showToast("Failed to copy: " + err.message, "error");
    }
  });

  downloadTxtBtn.addEventListener("click", () => {
    if (!rawNotesText) return;
    const baseName = (selectedFile ? selectedFile.name : "document").replace(/\.[^/.]+$/, "");
    const filename = `Notes_${baseName}.txt`;
    const blob = new Blob([rawNotesText], { type: "text/plain;charset=utf-8" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
    showToast(`Downloaded as ${filename}`, "success");
  });

  // ── Reset ──────────────────────────────────────────────────────────────────
  resetBtn.addEventListener("click", () => {
    clearSelectedFile();
    rawNotesText = "";
    extractedPdfText = "";
    chatMessages = [];
    switchTab("notes");
    notesOutput.classList.add("hidden");
    hideError();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  // ── Error Helpers ──────────────────────────────────────────────────────────
  function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.classList.remove("hidden");
    errorAlert.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  function hideError() { errorAlert.classList.add("hidden"); }
  closeAlertBtn.addEventListener("click", hideError);

  // ── Toast ──────────────────────────────────────────────────────────────────
  function showToast(text, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${text}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity   = "0";
      toast.style.transform = "translateX(40px)";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // ── Utilities ──────────────────────────────────────────────────────────────
  function formatBytes(bytes) {
    if (!bytes) return "0 Bytes";
    const k = 1024, sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  function escapeHtml(str) {
    return (str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /**
   * renderMarkdown(md) - Lightweight Markdown-to-HTML renderer.
   * Supports: # headings, ## headings, ### headings, **bold**, *italic*,
   *           - bullet lists, --- horizontal rules, and plain paragraphs.
   */
  function renderMarkdown(md) {
    if (!md) return "";

    // Escape HTML first to prevent XSS
    let html = md
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Headings (### before ## before # to prevent false matches)
    html = html.replace(/^### (.+)$/gim, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gim,  "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gim,   "<h1>$1</h1>");

    // Bold and italic
    html = html.replace(/\*\*(.+?)\*\*/gim, "<strong>$1</strong>");
    html = html.replace(/\*(.+?)\*/gim,     "<em>$1</em>");

    // Horizontal rule
    html = html.replace(/^---$/gim, "<hr>");

    // Process line-by-line: wrap lists and paragraphs
    const lines = html.split("\n");
    let result = [];
    let inList  = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        if (!inList) { result.push("<ul>"); inList = true; }
        result.push(`<li>${trimmed.substring(2)}</li>`);
      } else {
        if (inList) { result.push("</ul>"); inList = false; }

        const isTag = trimmed.startsWith("<h")
          || trimmed.startsWith("<hr")
          || trimmed.startsWith("<ul")
          || trimmed.startsWith("</ul");

        if (trimmed && !isTag) {
          result.push(`<p>${trimmed}</p>`);
        } else {
          result.push(line);
        }
      }
    }

    if (inList) result.push("</ul>");

    return result.join("\n");
  }

  // ── Tab Switching ──────────────────────────────────────────────────────────
  function switchTab(tab) {
    activeTab = tab;
    if (tab === "chat") {
      tabAskPdf.classList.add("active");
      tabAskPdf.setAttribute("aria-selected", "true");
      tabTopicNotes.classList.remove("active");
      tabTopicNotes.setAttribute("aria-selected", "false");
      notesBodyLayout.classList.add("hidden");
      chatSection.classList.remove("hidden");
      setTimeout(() => {
        chatInput.focus();
        scrollChatToBottom();
      }, 50);
    } else {
      tabTopicNotes.classList.add("active");
      tabTopicNotes.setAttribute("aria-selected", "true");
      tabAskPdf.classList.remove("active");
      tabAskPdf.setAttribute("aria-selected", "false");
      chatSection.classList.add("hidden");
      notesBodyLayout.classList.remove("hidden");
    }
  }

  tabTopicNotes.addEventListener("click", () => switchTab("notes"));
  tabAskPdf.addEventListener("click", () => switchTab("chat"));
  openChatBtn.addEventListener("click", () => switchTab("chat"));

  // ── Chat Controller ────────────────────────────────────────────────────────
  function resetChatForNewDoc(docName, pages, topicCount) {
    chatMessages = [{
      role: "assistant",
      text: `👋 **Welcome!** I've analyzed **${escapeHtml(docName)}** (${pages || 1} pages, ${topicCount || 0} topics).\n\nAsk me any question about this document below and I'll give you clear, beginner-friendly answers based strictly on its content.`,
      time: formatTime(),
    }];
    renderChatMessages();
  }

  function formatTime() {
    const d = new Date();
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function renderChatMessages() {
    chatMessagesContainer.innerHTML = "";
    chatMessages.forEach(msg => {
      const row = document.createElement("div");
      row.className = `chat-msg ${msg.role}`;

      const avatar = document.createElement("div");
      avatar.className = `msg-avatar ${msg.role}`;
      avatar.textContent = msg.role === "user" ? "You" : "AI";

      const bubble = document.createElement("div");
      bubble.className = "msg-bubble";

      let html = renderMarkdown(msg.text);
      if (msg.isNotFound) {
        html += `\n<div class="not-found-pill">⚠️ Information not found in PDF</div>`;
      }
      bubble.innerHTML = html;

      row.appendChild(avatar);
      row.appendChild(bubble);
      chatMessagesContainer.appendChild(row);
    });

    if (isChatGenerating) {
      const loadingRow = document.createElement("div");
      loadingRow.className = "chat-loading-row";
      loadingRow.innerHTML = `
        <div class="msg-avatar assistant">AI</div>
        <div class="typing-bubble">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-label">Searching PDF &amp; generating answer...</span>
        </div>
      `;
      chatMessagesContainer.appendChild(loadingRow);
    }

    scrollChatToBottom();
  }

  function scrollChatToBottom() {
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
  }

  async function handleQuestionSubmit() {
    const q = chatInput.value.trim();
    if (!q) return;

    if (!extractedPdfText) {
      showError("Please upload a PDF and generate notes first before asking questions.");
      return;
    }

    if (isChatGenerating) return;

    // Add user message to UI
    chatMessages.push({
      role: "user",
      text: q,
      time: formatTime(),
    });

    chatInput.value = "";
    chatInput.style.height = "auto";
    isChatGenerating = true;
    chatSendBtn.disabled = true;
    renderChatMessages();

    const storedKey = localStorage.getItem("gemini_api_key") || customApiKeyInput.value.trim();

    try {
      const response = await fetch("/api/ask-question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          pdf_text: extractedPdfText,
          custom_api_key: storedKey || null,
        }),
      });

      const data = await response.json();
      isChatGenerating = false;
      chatSendBtn.disabled = false;

      if (!response.ok) {
        const msg = data.detail || "Failed to answer question.";
        chatMessages.push({
          role: "assistant",
          text: `⚠️ **Error:** ${escapeHtml(msg)}`,
          time: formatTime(),
        });
      } else {
        const notFound = (data.answer || "").includes("This information was not found in the uploaded PDF.");
        chatMessages.push({
          role: "assistant",
          text: data.answer || "This information was not found in the uploaded PDF.",
          time: formatTime(),
          engine: data.engine,
          isNotFound: notFound,
        });
      }

      renderChatMessages();
      chatInput.focus();

    } catch (err) {
      isChatGenerating = false;
      chatSendBtn.disabled = false;
      chatMessages.push({
        role: "assistant",
        text: `⚠️ **Network Error:** Could not reach the server. Make sure the backend is running.`,
        time: formatTime(),
      });
      renderChatMessages();
    }
  }

  // Chat input listeners
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleQuestionSubmit();
  });

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleQuestionSubmit();
    }
  });

  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
  });

  clearChatBtn.addEventListener("click", () => {
    const docName = selectedFile ? selectedFile.name : (docNameDisplay.textContent || "document.pdf");
    resetChatForNewDoc(docName, 1, 1);
    showToast("Chat history cleared.", "info");
  });

  if (suggestionsChips) {
    suggestionsChips.addEventListener("click", (e) => {
      const btn = e.target.closest(".suggestion-chip");
      if (btn && btn.dataset.question) {
        chatInput.value = btn.dataset.question;
        handleQuestionSubmit();
      }
    });
  }

});

