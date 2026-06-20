/* Phase J7 — voice input + screenshot/paste image context */
(function () {
  const vscode = window.__merisVscode || { postMessage: () => {} };

  const micBtn = document.getElementById("mic-btn");
  const imageBtn = document.getElementById("image-btn");
  const imageInput = document.getElementById("image-input");
  const taskInput = document.getElementById("task-input");
  const composer = document.getElementById("composer");
  const composerCard = document.querySelector(".composer-card");
  const dragTarget = composerCard || composer;
  const composerHint = document.getElementById("composer-hint");

  if (!micBtn && !imageBtn && !taskInput) return;

  let hintTimer = 0;

  function showHint(msg, kind) {
    if (!composerHint) return;
    composerHint.textContent = msg;
    composerHint.className = "composer-hint" + (kind ? " " + kind : "");
    composerHint.classList.remove("hidden");
    clearTimeout(hintTimer);
    hintTimer = setTimeout(() => composerHint.classList.add("hidden"), 2800);
  }

  window.__merisComposerHint = showHint;

  function saveImageDataUrl(dataUrl, name) {
    if (!dataUrl || !String(dataUrl).startsWith("data:image/")) return;
    showHint("保存图片…", "pending");
    vscode.postMessage({
      type: "saveContextImage",
      dataUrl: dataUrl,
      filename: name || "paste.png",
    });
  }

  function readFileAsDataUrl(file) {
    if (!file || !file.type || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => saveImageDataUrl(reader.result, file.name);
    reader.readAsDataURL(file);
  }

  function handleImageFiles(files) {
    if (!files || !files.length) return;
    for (let i = 0; i < files.length; i++) {
      if (files[i].type && files[i].type.startsWith("image/")) {
        readFileAsDataUrl(files[i]);
        return;
      }
    }
  }

  if (imageBtn && imageInput) {
    imageBtn.addEventListener("click", () => imageInput.click());
    imageInput.addEventListener("change", () => {
      if (imageInput.files) handleImageFiles(imageInput.files);
      imageInput.value = "";
    });
  }

  if (taskInput) {
    taskInput.addEventListener("paste", (e) => {
      const items = e.clipboardData && e.clipboardData.items;
      if (!items) return;
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type && item.type.startsWith("image/")) {
          e.preventDefault();
          const blob = item.getAsFile();
          if (blob) readFileAsDataUrl(blob);
          return;
        }
      }
    });
  }

  if (dragTarget) {
    dragTarget.addEventListener("dragover", (e) => {
      if (!e.dataTransfer || !e.dataTransfer.types.includes("Files")) return;
      e.preventDefault();
      dragTarget.classList.add("drag-over");
    });
    dragTarget.addEventListener("dragleave", () => dragTarget.classList.remove("drag-over"));
    dragTarget.addEventListener("drop", (e) => {
      dragTarget.classList.remove("drag-over");
      if (!e.dataTransfer || !e.dataTransfer.files.length) return;
      e.preventDefault();
      handleImageFiles(e.dataTransfer.files);
    });
  }

  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (micBtn && SpeechRec) {
    const recognition = new SpeechRec();
    recognition.lang = document.documentElement.lang || "zh-CN";
    recognition.interimResults = true;
    recognition.continuous = false;
    let listening = false;

    recognition.onresult = (ev) => {
      let text = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        text += ev.results[i][0].transcript;
      }
      if (taskInput && text.trim()) {
        const cur = taskInput.value.trim();
        taskInput.value = cur ? cur + " " + text.trim() : text.trim();
        showHint("语音识别已写入", "ok");
      }
    };
    recognition.onend = () => {
      listening = false;
      micBtn.classList.remove("listening");
    };
    recognition.onerror = () => {
      listening = false;
      micBtn.classList.remove("listening");
      showHint("语音识别失败", "error");
    };
    micBtn.addEventListener("click", () => {
      if (listening) {
        recognition.stop();
        return;
      }
      try {
        recognition.start();
        listening = true;
        micBtn.classList.add("listening");
        showHint("正在聆听…", "pending");
      } catch (_) {
        listening = false;
        micBtn.classList.remove("listening");
      }
    });
  } else if (micBtn) {
    micBtn.disabled = true;
    micBtn.title = "语音输入（当前环境不支持 Web Speech API）";
  }
})();
