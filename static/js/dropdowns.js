// static/js/dropdowns.js
(function () {
  const DATA = window.DROPDOWN_DATA || { categories: {}, tables: {} };

  // Category UI
  const categorySearchEl = document.getElementById("category-search");
  const categoryListEl = document.getElementById("category-list");
  const categoryChipsEl = document.getElementById("category-chips");

  // Main selector
  const tableEl = document.getElementById("table");
  const variableEl = document.getElementById("variable");
  const demographicEl = document.getElementById("demographic");
  const classificationEl = document.getElementById("classification");

  // Buttons / summaries / result
  const setPrimaryBtn = document.getElementById("set-primary-btn");
  const setCompareBtn = document.getElementById("set-compare-btn");
  const correlationBtn = document.getElementById("view-correlation-btn");
  const resetBtn = document.getElementById("reset-btn");

  const primarySummaryEl = document.getElementById("primary-summary");
  const compareSummaryEl = document.getElementById("compare-summary");

  const correlationResultEl = document.getElementById("correlation-result");
  const correlationTextEl = document.getElementById("correlation-text");

  const ALL_CATEGORIES = Object.keys(DATA.categories || {}).sort();
  const selected = new Set();

  let primarySelection = null;
  let compareSelection = null;

  function setOptions(selectEl, items, placeholder, { includePlaceholder = true } = {}) {
    if (!selectEl) return;

    selectEl.innerHTML = "";

    if (includePlaceholder) {
      const ph = document.createElement("option");
      ph.value = "";
      ph.textContent = placeholder;
      ph.disabled = true;
      ph.selected = true;
      selectEl.appendChild(ph);
    }

    (items || []).forEach(item => {
      const opt = document.createElement("option");

      if (typeof item === "string") {
        opt.value = item;
        opt.textContent = item;
      } else {
        opt.value = item.value;
        opt.textContent = item.label;
      }

      selectEl.appendChild(opt);
    });
  }

  function intersectArrays(arrays) {
    if (!arrays.length) return [];

    let set = new Set(arrays[0]);

    for (let i = 1; i < arrays.length; i++) {
      const next = new Set(arrays[i]);
      set = new Set([...set].filter(x => next.has(x)));
      if (set.size === 0) break;
    }

    return [...set];
  }

  function rankTablesForSelection(tableIds, selectedCats) {
    return tableIds
      .map(tid => {
        const t = DATA.tables[tid];
        const cats = t?.categories || [];
        const extra = Math.max(0, cats.length - selectedCats.length);

        return {
          tid,
          label: `${tid} — ${t?.table_name || "Unknown table"}`,
          extra,
          catsLen: cats.length
        };
      })
      .sort((a, b) => {
        if (a.extra !== b.extra) return a.extra - b.extra;
        if (a.catsLen !== b.catsLen) return a.catsLen - b.catsLen;
        return Number(a.tid) - Number(b.tid);
      });
  }

  function clearPrimarySelectors() {
    setOptions(tableEl, [], "Select table");
    setOptions(variableEl, [], "Select variable");
    setOptions(demographicEl, [], "Select demographic");
    setOptions(classificationEl, [], "Select option");
  }

  function showCorrelationMessage(text) {
    if (!correlationResultEl || !correlationTextEl) return;
    correlationResultEl.style.display = "block";
    correlationTextEl.textContent = text;
  }

  function resetCorrelationMessage() {
    if (!correlationResultEl || !correlationTextEl) return;
    correlationResultEl.style.display = "none";
    correlationTextEl.textContent = "No result yet";
  }

  function refreshTables() {
    const selectedCats = [...selected];

    clearPrimarySelectors();
    resetCorrelationMessage();

    if (!selectedCats.length) return;

    const lists = selectedCats.map(c => DATA.categories[c] || []);
    const intersection = intersectArrays(lists);

    const ranked = rankTablesForSelection(intersection, selectedCats);
    const top = ranked.slice(0, 3).map(x => ({
      value: x.tid,
      label: x.label
    }));

    setOptions(tableEl, top, top.length ? "Select table" : "No tables found");
  }

  function renderChips() {
    if (!categoryChipsEl) return;

    categoryChipsEl.innerHTML = "";

    [...selected].forEach(cat => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = cat;

      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "×";

      btn.addEventListener("click", () => {
        selected.delete(cat);

        const cb = categoryListEl?.querySelector(
          `input[data-cat="${CSS.escape(cat)}"]`
        );
        if (cb) cb.checked = false;

        renderChips();
        refreshTables();
      });

      chip.appendChild(btn);
      categoryChipsEl.appendChild(chip);
    });
  }

  function renderCategoryList(filter = "") {
    if (!categoryListEl) return;

    const q = (filter || "").toLowerCase();
    categoryListEl.innerHTML = "";

    ALL_CATEGORIES
      .filter(c => c.toLowerCase().includes(q))
      .forEach(cat => {
        const label = document.createElement("label");
        label.className = "checkbox-item";

        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.dataset.cat = cat;
        cb.checked = selected.has(cat);

        cb.addEventListener("change", () => {
          if (cb.checked) {
            selected.add(cat);
          } else {
            selected.delete(cat);
          }

          renderChips();
          refreshTables();
        });

        label.appendChild(cb);
        label.appendChild(document.createTextNode(cat));
        categoryListEl.appendChild(label);
      });
  }

  // ---------------------------
  // Map helpers
  // ---------------------------
  function getMapIframeWindow() {
    const iframe = document.querySelector("#map-container iframe");
    if (!iframe) return null;

    return iframe.contentWindow || null;
  }

  function getMapObjects() {
    const mapWin = getMapIframeWindow();
    if (!mapWin) return {};

    const regioesLayer = window.REGIOES_LAYER_NAME
      ? mapWin[window.REGIOES_LAYER_NAME]
      : null;

    const ufLayer = window.UF_LAYER_NAME
      ? mapWin[window.UF_LAYER_NAME]
      : null;

    const mapObj = Object.values(mapWin).find(
      v => v && typeof v.getZoom === "function" && typeof v.addLayer === "function"
    );

    return { mapWin, mapObj, regioesLayer, ufLayer };
  }

  function getRange(dataObj) {
    const values = Object.values(dataObj || {})
      .map(v => Number(v))
      .filter(v => !isNaN(v));

    if (!values.length) {
      return { min: 0, max: 0 };
    }

    return {
      min: Math.min(...values),
      max: Math.max(...values)
    };
  }

  function getColor(value, min, max) {
    if (value === undefined || value === null || isNaN(value)) return "#cccccc";
    if (max <= min) return "#3388ff";

    const ratio = (value - min) / (max - min);

    if (ratio > 0.8) return "#08306b";
    if (ratio > 0.6) return "#2171b5";
    if (ratio > 0.4) return "#4292c6";
    if (ratio > 0.2) return "#6baed6";
    return "#9ecae1";
  }

  function updateRegions(n2Data) {
    const { regioesLayer } = getMapObjects();

    if (!regioesLayer || typeof regioesLayer.eachLayer !== "function") {
      console.warn("Regions layer not found.");
      return;
    }

    const { min, max } = getRange(n2Data);

    const SIGLA_TO_N2 = {
      N: "1",
      NE: "2",
      SE: "3",
      S: "4",
      CO: "5"
    };

    regioesLayer.eachLayer(layer => {
      const props = layer.feature?.properties || {};
      const sigla = props.SIGLA_RG;
      const n2Key = SIGLA_TO_N2[sigla];
      const val = n2Key && n2Data ? Number(n2Data[n2Key]) : undefined;

      const regionName =
        props.NM_REGIAO ||
        props.NM_RG ||
        "Região";

      const valueText =
        val === undefined || val === null || isNaN(val)
          ? "Sem dado"
          : val.toLocaleString("pt-BR");

      if (typeof layer.setStyle === "function") {
        layer.setStyle({
          fillColor: getColor(val, min, max),
          color: "#222222",
          weight: 1,
          fillOpacity: 0.6
        });
      }

      if (typeof layer.unbindTooltip === "function") {
        layer.unbindTooltip();
      }

      layer.bindTooltip(
        `<div><b>${regionName}</b></div><div>Value: ${valueText}</div>`,
        { sticky: true }
      );
    });
  }

  function updateUFs(n3Data) {
    const { ufLayer } = getMapObjects();

    if (!ufLayer || typeof ufLayer.eachLayer !== "function") {
      console.warn("UF layer not found.");
      return;
    }

    const { min, max } = getRange(n3Data);

    ufLayer.eachLayer(layer => {
      const props = layer.feature?.properties || {};

      const ufCode = String(
        props.CD_UF ??
        props.cd_uf ??
        props.CODUF ??
        props.coduf ??
        props.CD_GEOCUF ??
        props.cd_geocuf ??
        ""
      );

      const ufName =
        props.NM_UF ||
        props.nome ||
        props.NAME ||
        props.SIGLA_UF ||
        "UF";

      const val = ufCode && n3Data ? Number(n3Data[ufCode]) : undefined;

      const valueText =
        val === undefined || val === null || isNaN(val)
          ? "Sem dado"
          : val.toLocaleString("pt-BR");

      if (typeof layer.setStyle === "function") {
        layer.setStyle({
          fillColor: getColor(val, min, max),
          color: "#222222",
          weight: 1,
          fillOpacity: 0.6
        });
      }

      if (typeof layer.unbindTooltip === "function") {
        layer.unbindTooltip();
      }

      layer.bindTooltip(
        `<div><b>${ufName}</b></div><div>Value: ${valueText}</div>`,
        { sticky: true }
      );
    });
  }

  function attachMapHandler() {
    const { mapObj } = getMapObjects();

    if (!mapObj) {
      console.warn("Map object not found yet.");
      return false;
    }

    return true;
  }

  // ---------------------------
  // Selection storage helpers
  // ---------------------------
  function getSelectionPayload() {
    const table = tableEl?.value || "";
    const variable = variableEl?.value || "";
    const demographic = demographicEl?.value || "";
    const category = classificationEl?.value || "";

    const classificationCode =
      DATA.tables[table]?.classification_ids?.[demographic] || "";

    return {
      table,
      variable,
      demographic,
      classification_code: classificationCode,
      category
    };
  }

  function formatSelectionLabel(sel) {
    if (!sel || !sel.table || !sel.variable) return "none selected";

    const tableName = DATA.tables[sel.table]?.table_name || sel.table;

    const variableName =
      DATA.tables[sel.table]?.variables?.find(
        v => String(v.value) === String(sel.variable)
      )?.label || sel.variable;

    const demographicName = sel.demographic || "No demographic";

    const optionName =
      DATA.tables[sel.table]?.classification_members?.[sel.demographic]?.find(
        x => String(x.value) === String(sel.category)
      )?.label || sel.category || "No option";

    return `${sel.table} — ${tableName} | ${variableName} | ${demographicName} | ${optionName}`;
  }

  function renderSelectionSummaries() {
    if (primarySummaryEl) {
      primarySummaryEl.textContent = `Map variable: ${formatSelectionLabel(primarySelection)}`;
    }

    if (compareSummaryEl) {
      compareSummaryEl.textContent = `Comparison variable: ${formatSelectionLabel(compareSelection)}`;
    }
  }

  async function fetchAndRenderPrimaryMapFromSelection(payload) {
    if (!payload.table || !payload.variable) return;

    try {
      const res = await fetch("/api/sidra-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const result = await res.json();

      if (result?.error) {
        console.error("SIDRA error:", result.error);
        showCorrelationMessage(result.error);
        return;
      }

      if (result?.n2) updateRegions(result.n2);
      if (result?.n3) updateUFs(result.n3);
    } catch (err) {
      console.error("Failed to fetch SIDRA data:", err);
      showCorrelationMessage("Failed to fetch map data.");
    }
  }

  async function setPrimarySelection() {
    const payload = getSelectionPayload();

    if (!payload.table || !payload.variable) {
      showCorrelationMessage("Choose a table and variable first.");
      return;
    }

    primarySelection = payload;
    renderSelectionSummaries();
    resetCorrelationMessage();

    await fetchAndRenderPrimaryMapFromSelection(primarySelection);
  }

  function setCompareSelection() {
    const payload = getSelectionPayload();

    if (!payload.table || !payload.variable) {
      showCorrelationMessage("Choose a table and variable first.");
      return;
    }

    compareSelection = payload;
    renderSelectionSummaries();
    resetCorrelationMessage();
  }

  function interpretCorrelation(r) {
    const abs = Math.abs(r);

    if (abs >= 0.8) return "very strong";
    if (abs >= 0.6) return "strong";
    if (abs >= 0.4) return "moderate";
    if (abs >= 0.2) return "weak";
    return "very weak";
  }

  async function calculateCorrelation() {
    if (!primarySelection) {
      showCorrelationMessage("Set a map variable first.");
      return;
    }

    if (!compareSelection) {
      showCorrelationMessage("Set a comparison variable first.");
      return;
    }

    showCorrelationMessage("Calculating correlation...");

    try {
      const res = await fetch("/api/correlate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          left: primarySelection,
          right: compareSelection
        })
      });

      const result = await res.json();

      if (result?.error) {
        showCorrelationMessage(result.error);
        return;
      }

      const r = Number(result.correlation);
      const strength = interpretCorrelation(r);

      showCorrelationMessage(
        `Pearson correlation: ${r.toFixed(3)} (${strength}) across ${result.count} states`
      );
    } catch (err) {
      console.error("Failed to calculate correlation:", err);
      showCorrelationMessage("Failed to calculate correlation.");
    }
  }

  function resetAll() {
    selected.clear();
    primarySelection = null;
    compareSelection = null;

    if (categorySearchEl) categorySearchEl.value = "";

    renderCategoryList();
    renderChips();
    clearPrimarySelectors();
    resetCorrelationMessage();
    renderSelectionSummaries();
  }

  // ---------------------------
  // Event wiring
  // ---------------------------
  if (categorySearchEl) {
    categorySearchEl.addEventListener("input", e => {
      renderCategoryList(e.target.value);
    });
  }

  if (tableEl) {
    tableEl.addEventListener("change", () => {
      const t = DATA.tables[tableEl.value];

      setOptions(variableEl, t?.variables || [], "Select variable");
      setOptions(demographicEl, [], "Select demographic");
      setOptions(classificationEl, [], "Select option");
      resetCorrelationMessage();
    });
  }

  if (variableEl) {
    variableEl.addEventListener("change", () => {
      const t = DATA.tables[tableEl.value];

      setOptions(demographicEl, t?.demographics || [], "Select demographic");
      setOptions(classificationEl, [], "Select option");
      resetCorrelationMessage();
    });
  }

  if (demographicEl) {
    demographicEl.addEventListener("change", () => {
      const t = DATA.tables[tableEl.value];

      setOptions(
        classificationEl,
        t?.classification_members?.[demographicEl.value] || [],
        "Select option"
      );
      resetCorrelationMessage();
    });
  }

  if (classificationEl) {
    classificationEl.addEventListener("change", () => {
      resetCorrelationMessage();
    });
  }

  if (setPrimaryBtn) {
    setPrimaryBtn.addEventListener("click", setPrimarySelection);
  }

  if (setCompareBtn) {
    setCompareBtn.addEventListener("click", setCompareSelection);
  }

  if (correlationBtn) {
    correlationBtn.addEventListener("click", calculateCorrelation);
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", resetAll);
  }

  // ---------------------------
  // Init
  // ---------------------------
  renderCategoryList();
  renderSelectionSummaries();

  window.addEventListener("load", () => {
    let tries = 0;
    const maxTries = 20;

    const timer = setInterval(() => {
      tries += 1;
      const ok = attachMapHandler();

      if (ok || tries >= maxTries) {
        clearInterval(timer);
      }
    }, 300);
  });
})();