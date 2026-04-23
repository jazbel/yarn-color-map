const API = "";  // same origin; change to "http://localhost:8000" if opening index.html directly

// ── State ────────────────────────────────────────────────────
const state = {
  yarns: [],
  filtered: [],
  displayed: [],
  pageSize: 60,
  offset: 0,
  activeStore: null,
  activeFamily: null,
  activeWeight: null,
  activeFiber: null,
  search: "",
  sort: "default",
  pickerActive: false,
  pickerHex: "#6495ED",
  loading: false,
};

// ── Color family swatch colors ────────────────────────────────
const FAMILY_COLORS = {
  red: "#CC0000", pink: "#FF69B4", orange: "#FF7F00", yellow: "#FFD700",
  green: "#228B22", teal: "#008080", blue: "#0047AB", purple: "#800080",
  gray: "#808080", white: "#F5F5F0", black: "#1A1A1A",
};

// ── DOM helpers ───────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const storeFiltersEl = $("store-filters");
const familyFiltersEl = $("family-filters");
const weightFiltersEl = $("weight-filters");
const fiberFiltersEl = $("fiber-filters");
const gridEl = $("yarn-grid");
const countEl = $("count-label");
const emptyEl = $("empty-state");
const errorEl = $("error-state");
const loadMoreWrap = $("load-more-wrap");
const searchEl = $("search");
const sortEl = $("sort-select");
const pickerEl = $("color-picker");
const pickerHexEl = $("picker-hex");
const refreshBtn = $("refresh-btn");
const toastEl = $("toast");
let toastTimer;

// ── Modal elements ────────────────────────────────────────────
const modalOverlay = $("modal-overlay");
const modalClose = $("modal-close");
const modalProduct = $("modal-product");
const modalColorName = $("modal-color-name");
const modalHex = $("modal-hex");
const modalCopy = $("modal-copy");
const modalStore = $("modal-store");
const modalWeight = $("modal-weight");
const modalPrice = $("modal-price");
const modalLink = $("modal-link");

// ── Utility ───────────────────────────────────────────────────
function hexToHsl(hex) {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  return [h * 360, s * 100, l * 100];
}

function colorDistance(hex1, hex2) {
  const r1 = parseInt(hex1.slice(1, 3), 16);
  const g1 = parseInt(hex1.slice(3, 5), 16);
  const b1 = parseInt(hex1.slice(5, 7), 16);
  const r2 = parseInt(hex2.slice(1, 3), 16);
  const g2 = parseInt(hex2.slice(3, 5), 16);
  const b2 = parseInt(hex2.slice(5, 7), 16);
  return Math.sqrt((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2);
}

function storeClass(storeId) {
  const map = { hobbii: "badge-hobbii", lovecrafts: "badge-lovecrafts", knitpicks: "badge-knitpicks" };
  return map[storeId] || "badge-unknown";
}

function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("show"), 1800);
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); showToast("Copied " + text); }
  catch { showToast("Copy failed"); }
}

// ── Fetch & init ──────────────────────────────────────────────
async function init() {
  showSkeletons(12);
  try {
    const [storesRes, familiesRes, weightsRes, fibersRes, yarnsRes] = await Promise.all([
      fetch(`${API}/api/stores`).then(r => r.json()),
      fetch(`${API}/api/color-families`).then(r => r.json()),
      fetch(`${API}/api/weights`).then(r => r.json()),
      fetch(`${API}/api/fibers`).then(r => r.json()),
      fetch(`${API}/api/yarns?limit=10000`).then(r => r.json()),
    ]);
    buildStoreChips(storesRes);
    buildFamilyChips(familiesRes);
    buildWeightChips(weightsRes);
    buildFiberChips(fibersRes, yarnsRes.items || []);
    state.yarns = yarnsRes.items || [];
    applyFiltersAndRender();
  } catch (e) {
    console.error(e);
    gridEl.innerHTML = "";
    errorEl.style.display = "";
    countEl.textContent = "";
  }
}

// ── Chip builders ─────────────────────────────────────────────
function buildStoreChips(stores) {
  storeFiltersEl.innerHTML = "";
  const all = makeChip("All Stores", null, "store", !state.activeStore);
  storeFiltersEl.appendChild(all);
  stores.forEach(s => {
    storeFiltersEl.appendChild(makeChip(s.name, s.id, "store", state.activeStore === s.id));
  });
}

function buildFamilyChips(families) {
  familyFiltersEl.innerHTML = "";
  const all = makeChip("All Colors", null, "family", !state.activeFamily);
  familyFiltersEl.appendChild(all);
  families.forEach(f => {
    familyFiltersEl.appendChild(
      makeChip(capitalize(f), f, "family", state.activeFamily === f, FAMILY_COLORS[f])
    );
  });
}

// Weight labels with abbreviated notation shown alongside
const WEIGHT_LABELS = {
  "Lace": "Lace (0)", "Fingering": "Fingering (1)", "Sport": "Sport (2)",
  "DK": "DK (3)", "Worsted": "Worsted (4)", "Aran": "Aran (5)",
  "Bulky": "Bulky (6)", "Super Bulky": "Super Bulky (7)", "Jumbo": "Jumbo (8)",
};

function buildWeightChips(weights) {
  weightFiltersEl.innerHTML = "";
  weightFiltersEl.appendChild(makeChip("All Weights", null, "weight", !state.activeWeight));
  weights.forEach(w => {
    weightFiltersEl.appendChild(
      makeChip(WEIGHT_LABELS[w] || w, w, "weight", state.activeWeight === w)
    );
  });
}

function buildFiberChips(fibers, yarns) {
  // Only show fibers that actually appear in the data
  const present = new Set(yarns.map(y => y.fiber).filter(Boolean));
  fiberFiltersEl.innerHTML = "";
  fiberFiltersEl.appendChild(makeChip("All Fibers", null, "fiber", !state.activeFiber));
  fibers.filter(f => present.has(f)).forEach(f => {
    fiberFiltersEl.appendChild(
      makeChip(f, f, "fiber", state.activeFiber === f)
    );
  });
}

function makeChip(label, value, kind, active, dotColor) {
  const btn = document.createElement("button");
  btn.className = "chip" + (active ? " active" : "");
  if (dotColor) {
    const dot = document.createElement("span");
    dot.className = "color-dot";
    dot.style.background = dotColor;
    btn.appendChild(dot);
  }
  btn.appendChild(document.createTextNode(label));
  btn.addEventListener("click", () => {
    const selectors = {
      store:  "#store-filters .chip",
      family: "#family-filters .chip",
      weight: "#weight-filters .chip",
      fiber:  "#fiber-filters .chip",
    };
    document.querySelectorAll(selectors[kind]).forEach(c => c.classList.remove("active"));
    btn.classList.add("active");

    if (kind === "store") {
      state.activeStore = value;
      state.pickerActive = false;
      $("clear-picker").style.display = "none";
    } else if (kind === "family") {
      state.activeFamily = value;
    } else if (kind === "weight") {
      state.activeWeight = value;
    } else if (kind === "fiber") {
      state.activeFiber = value;
    }
    state.offset = 0;
    applyFiltersAndRender();
  });
  return btn;
}

function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

// ── Skeletons ─────────────────────────────────────────────────
function showSkeletons(n) {
  gridEl.innerHTML = Array(n).fill('<div class="skeleton"></div>').join("");
  countEl.textContent = "Loading…";
  emptyEl.style.display = "none";
  errorEl.style.display = "none";
  loadMoreWrap.style.display = "none";
}

// ── Filter & Sort ─────────────────────────────────────────────
function applyFiltersAndRender() {
  let pool = [...state.yarns];

  if (state.activeStore)  pool = pool.filter(y => y.store_id === state.activeStore);
  if (state.activeFamily) pool = pool.filter(y => y.color_family === state.activeFamily);
  if (state.activeWeight) pool = pool.filter(y => y.weight === state.activeWeight);
  if (state.activeFiber)  pool = pool.filter(y => y.fiber  === state.activeFiber);

  if (state.search) {
    const q = state.search.toLowerCase();
    pool = pool.filter(y =>
      (y.product_name || "").toLowerCase().includes(q) ||
      (y.color_name  || "").toLowerCase().includes(q)
    );
  }

  if (state.pickerActive) {
    pool = pool
      .map(y => ({ ...y, _dist: colorDistance(y.hex_color, state.pickerHex) }))
      .filter(y => y._dist < 80)
      .sort((a, b) => a._dist - b._dist);
  }

  // Sort
  if (state.sort === "hue") {
    pool.sort((a, b) => hexToHsl(a.hex_color)[0] - hexToHsl(b.hex_color)[0]);
  } else if (state.sort === "lightness") {
    pool.sort((a, b) => hexToHsl(b.hex_color)[2] - hexToHsl(a.hex_color)[2]);
  } else if (state.sort === "name") {
    pool.sort((a, b) => (a.color_name || "").localeCompare(b.color_name || ""));
  }

  state.filtered = pool;
  state.offset = 0;
  renderGrid(true);
}

// ── Render ────────────────────────────────────────────────────
function renderGrid(reset) {
  if (reset) gridEl.innerHTML = "";

  const slice = state.filtered.slice(state.offset, state.offset + state.pageSize);
  state.offset += slice.length;

  if (reset && slice.length === 0) {
    emptyEl.style.display = "";
    loadMoreWrap.style.display = "none";
    countEl.textContent = "0 yarns";
    return;
  }
  emptyEl.style.display = "none";
  errorEl.style.display = "none";

  const frag = document.createDocumentFragment();
  slice.forEach((yarn, i) => {
    const card = document.createElement("div");
    card.className = "yarn-card";
    card.style.animationDelay = `${Math.min(i, 20) * 20}ms`;
    const hex = yarn.hex_color.toUpperCase();
    const hasImg = !!yarn.image_url;

    // Media area: real photo OR solid-colour fallback
    const mediaHtml = hasImg
      ? `<div class="card-media">
           <img class="card-yarn-img" src="${esc(yarn.image_url)}"
                alt="${esc(yarn.color_name || yarn.product_name)}"
                loading="lazy"
                onerror="this.parentElement.innerHTML='<div class=card-swatch-fallback style=background:${hex}></div>'">
           <div class="card-hex-pip">
             <span class="card-hex-pip-dot" style="background:${hex}"></span>
             <span class="card-hex-pip-code">${hex}</span>
           </div>
         </div>`
      : `<div class="card-media">
           <div class="card-swatch-fallback" style="background:${hex}"></div>
           <div class="card-hex-pip">
             <span class="card-hex-pip-dot" style="background:${hex}"></span>
             <span class="card-hex-pip-code">${hex}</span>
           </div>
         </div>`;

    card.innerHTML = `
      ${mediaHtml}
      <div class="card-body">
        <div class="card-product">${esc(yarn.product_name)}</div>
        <div class="card-color">${esc(yarn.color_name || "—")}</div>
        <div class="card-footer">
          <span class="card-hex" title="Click to copy">${hex}</span>
          <span class="card-store-badge ${storeClass(yarn.store_id)}">${esc(yarn.store)}</span>
        </div>
      </div>
    `;
    card.querySelector(".card-hex").addEventListener("click", (e) => {
      e.stopPropagation();
      copyText(yarn.hex_color.toUpperCase());
    });
    card.addEventListener("click", () => openModal(yarn));
    frag.appendChild(card);
  });
  gridEl.appendChild(frag);

  const shown = reset ? slice.length : state.offset;
  countEl.textContent = `${state.filtered.length} yarn${state.filtered.length !== 1 ? "s" : ""}`;
  loadMoreWrap.style.display = state.offset < state.filtered.length ? "" : "none";
}

function esc(str) {
  return String(str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Modal ─────────────────────────────────────────────────────
function openModal(yarn) {
  const hex = yarn.hex_color.toUpperCase();

  // Rebuild media area: yarn image + colour strip, or solid swatch fallback
  const mediaEl = document.querySelector(".modal-media");
  if (mediaEl) {
    if (yarn.image_url) {
      mediaEl.innerHTML = `
        <img class="modal-yarn-img" src="${esc(yarn.image_url)}"
             alt="${esc(yarn.color_name || yarn.product_name)}"
             onerror="this.parentElement.innerHTML='<div class=modal-swatch-fallback style=background:${hex}></div>'">
        <div class="modal-color-strip">
          <span class="modal-strip-dot" style="background:${hex}"></span>
          <span class="modal-strip-hex">${hex}</span>
        </div>`;
    } else {
      mediaEl.innerHTML = `
        <div class="modal-swatch-fallback" style="background:${hex}"></div>
        <div class="modal-color-strip">
          <span class="modal-strip-dot" style="background:${hex}"></span>
          <span class="modal-strip-hex">${hex}</span>
        </div>`;
    }
  }

  modalProduct.textContent = yarn.product_name || "Yarn";
  modalColorName.textContent = yarn.color_name || "—";
  modalHex.textContent = hex;
  modalHex.style.color = yarn.hex_color;

  modalStore.textContent = yarn.store;
  modalStore.className = "badge " + storeClass(yarn.store_id);
  const srcBadge = document.getElementById("modal-src");
  if (srcBadge) {
    srcBadge.textContent = yarn.color_source === "image" ? "📷 from image" : "🏷 from name";
    srcBadge.title = yarn.color_source === "image"
      ? "Hex extracted from product image"
      : "Hex mapped from color name";
  }

  const modalFiber = $("modal-fiber");
  if (modalFiber) {
    modalFiber.textContent = yarn.fiber || "";
    modalFiber.style.display = yarn.fiber ? "" : "none";
  }
  modalWeight.textContent = yarn.weight || "";
  modalWeight.style.display = yarn.weight ? "" : "none";

  modalPrice.textContent = yarn.price || "";
  modalPrice.style.display = yarn.price ? "" : "none";

  modalLink.href = yarn.url || "#";
  modalLink.style.display = yarn.url ? "" : "none";

  modalOverlay.style.display = "flex";
  modalClose.focus();
}

function closeModal() { modalOverlay.style.display = "none"; }

modalClose.addEventListener("click", closeModal);
modalOverlay.addEventListener("click", (e) => { if (e.target === modalOverlay) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

modalCopy.addEventListener("click", () => copyText(modalHex.textContent));

// ── Refresh ───────────────────────────────────────────────────
refreshBtn.addEventListener("click", async () => {
  refreshBtn.classList.add("loading");
  refreshBtn.textContent = "↻ Refreshing…";
  showSkeletons(12);
  try {
    await fetch(`${API}/api/refresh`, { method: "POST" });
    const res = await fetch(`${API}/api/yarns?limit=10000`).then(r => r.json());
    state.yarns = res.items || [];
    applyFiltersAndRender();
    showToast("Yarns refreshed!");
  } catch {
    showToast("Refresh failed");
  } finally {
    refreshBtn.classList.remove("loading");
    refreshBtn.textContent = "↻ Refresh";
  }
});

// ── Search ────────────────────────────────────────────────────
let searchTimer;
searchEl.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.search = searchEl.value.trim();
    state.offset = 0;
    applyFiltersAndRender();
  }, 250);
});

// ── Sort ──────────────────────────────────────────────────────
sortEl.addEventListener("change", () => {
  state.sort = sortEl.value;
  applyFiltersAndRender();
});

// ── Load more ─────────────────────────────────────────────────
$("load-more").addEventListener("click", () => renderGrid(false));

// ── Color picker ──────────────────────────────────────────────
pickerEl.addEventListener("input", () => {
  state.pickerHex = pickerEl.value;
  pickerHexEl.textContent = pickerEl.value.toUpperCase();
});

$("find-similar").addEventListener("click", () => {
  state.pickerActive = true;
  state.pickerHex = pickerEl.value;
  $("clear-picker").style.display = "";
  state.activeFamily = null;
  document.querySelectorAll("#family-filters .chip").forEach(c => c.classList.remove("active"));
  document.querySelector("#family-filters .chip").classList.add("active");
  applyFiltersAndRender();
});

$("clear-picker").addEventListener("click", () => {
  state.pickerActive = false;
  $("clear-picker").style.display = "none";
  applyFiltersAndRender();
});

// ── Start ─────────────────────────────────────────────────────
init();
