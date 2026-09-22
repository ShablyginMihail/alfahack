const elements = {
  source: document.getElementById("source"),
  maskButton: document.getElementById("mask-btn"),
  unmaskButton: document.getElementById("unmask-btn"),
  status: document.getElementById("status"),
  masked: document.getElementById("masked"),
  maskedMeta: document.getElementById("masked-meta"),
  restored: document.getElementById("restored"),
  restoredMeta: document.getElementById("restored-meta"),
};

const state = { payloadId: null, original: "", masked: "", busy: false };

// crypto.randomUUID есть только в защищённом контексте, а демо может открываться по http
function newPayloadId() {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function formatMs(value) {
  return `${value.toFixed(value < 10 ? 1 : 0)} мс`;
}

function setStatus(message, kind) {
  elements.status.textContent = message;
  elements.status.dataset.kind = kind;
}

function setMeta(element, message, kind) {
  element.textContent = message;
  element.dataset.kind = kind;
}

function updateButtons() {
  elements.maskButton.disabled = state.busy;
  elements.unmaskButton.disabled = state.busy || state.payloadId === null;
}

function resetResults() {
  state.payloadId = null;
  state.masked = "";
  elements.masked.replaceChildren();
  elements.restored.replaceChildren();
  setMeta(elements.maskedMeta, "", "");
  setMeta(elements.restoredMeta, "", "");
  setStatus("", "");
  updateButtons();
}

async function callProcess(payload, payloadId) {
  const started = performance.now();
  let response;
  try {
    response = await fetch("/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload, payload_id: payloadId }),
    });
  } catch {
    throw new Error("Сервис недоступен. Проверьте соединение и попробуйте ещё раз.");
  }
  const elapsed = performance.now() - started;
  if (response.status === 429) {
    throw new Error("Сервис перегружен. Повторите запрос через несколько секунд.");
  }
  if (!response.ok) {
    throw new Error(`Сервис ответил ошибкой ${response.status}.`);
  }
  const data = await response.json();
  return { result: data.result, elapsed };
}

function renderMasked(container, text) {
  container.replaceChildren();
  let cursor = 0;
  let fragments = 0;
  for (const match of text.matchAll(/\*+/g)) {
    if (match.index > cursor) {
      container.append(text.slice(cursor, match.index));
    }
    const mark = document.createElement("mark");
    mark.className = "pii";
    mark.textContent = match[0];
    container.append(mark);
    cursor = match.index + match[0].length;
    fragments += 1;
  }
  if (cursor < text.length) {
    container.append(text.slice(cursor));
  }
  return fragments;
}

async function runStep(step) {
  state.busy = true;
  updateButtons();
  try {
    await step();
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    state.busy = false;
    updateButtons();
  }
}

async function maskText() {
  const text = elements.source.value;
  if (text.trim() === "") {
    setStatus("Введите текст или выберите пример.", "error");
    return;
  }
  resetResults();
  const payloadId = newPayloadId();
  const { result, elapsed } = await callProcess(text, payloadId);
  state.payloadId = payloadId;
  state.original = text;
  state.masked = result;
  const fragments = renderMasked(elements.masked, result);
  if (fragments === 0) {
    setMeta(elements.maskedMeta, `персональные данные не найдены · ${formatMs(elapsed)}`, "neutral");
  } else {
    setMeta(elements.maskedMeta, `скрыто фрагментов: ${fragments} · ${formatMs(elapsed)}`, "ok");
  }
}

async function unmaskText() {
  const { result, elapsed } = await callProcess(state.masked, state.payloadId);
  elements.restored.textContent = result;
  if (result === state.original) {
    setMeta(elements.restoredMeta, `совпадает с исходным · ${formatMs(elapsed)}`, "ok");
  } else {
    setMeta(elements.restoredMeta, `отличается от исходного · ${formatMs(elapsed)}`, "error");
  }
}

for (const chip of document.querySelectorAll("[data-example]")) {
  chip.addEventListener("click", () => {
    elements.source.value = chip.dataset.example;
    resetResults();
    elements.source.focus();
  });
}

elements.maskButton.addEventListener("click", () => runStep(maskText));
elements.unmaskButton.addEventListener("click", () => runStep(unmaskText));
elements.source.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !state.busy) {
    event.preventDefault();
    runStep(maskText);
  }
});

updateButtons();
