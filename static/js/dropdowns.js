(function () {
  const DATA = window.DROPDOWN_DATA;

  // Category UI
  const categorySearchEl = document.getElementById("category-search");
  const categoryListEl = document.getElementById("category-list");
  const categoryChipsEl = document.getElementById("category-chips");

  // Other dropdowns
  const tableEl = document.getElementById("table");
  const variableEl = document.getElementById("variable");
  const demographicEl = document.getElementById("demographic");
  const classificationEl = document.getElementById("classification");

  const ALL_CATEGORIES = Object.keys(DATA.categories || {}).sort();
  const selected = new Set();

  function setOptions(selectEl, items, placeholder, { includePlaceholder = true } = {}) {
    selectEl.innerHTML = "";
    if (includePlaceholder) {
      const ph = document.createElement("option");
      ph.value = "";
      ph.textContent = placeholder;
      ph.disabled = true;
      ph.selected = true;
      selectEl.appendChild(ph);
    }
    items.forEach(item => {
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

  function refreshTables() {
    const selectedCats = [...selected];

    setOptions(tableEl, [], "Select table");
    setOptions(variableEl, [], "Select variable");
    setOptions(demographicEl, [], "Select demographic");
    setOptions(classificationEl, [], "Select option");

    if (!selectedCats.length) return;

    const lists = selectedCats.map(c => DATA.categories[c] || []);
    const intersection = intersectArrays(lists);

    const ranked = rankTablesForSelection(intersection, selectedCats);
    const top = ranked.slice(0, 3).map(x => ({ value: x.tid, label: x.label }));

    setOptions(tableEl, top, top.length ? "Select table" : "No tables found");
  }

  function renderChips() {
    categoryChipsEl.innerHTML = "";
    [...selected].forEach(cat => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = cat;

      const btn = document.createElement("button");
      btn.textContent = "×";
      btn.addEventListener("click", () => {
        selected.delete(cat);
        const cb = categoryListEl.querySelector(`input[data-cat="${CSS.escape(cat)}"]`);
        if (cb) cb.checked = false;
        renderChips();
        refreshTables();
      });

      chip.appendChild(btn);
      categoryChipsEl.appendChild(chip);
    });
  }

  function renderCategoryList(filter = "") {
    const q = filter.toLowerCase();
    categoryListEl.innerHTML = "";

    ALL_CATEGORIES.filter(c => c.toLowerCase().includes(q)).forEach(cat => {
      const label = document.createElement("label");
      label.className = "checkbox-item";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.dataset.cat = cat;
      cb.checked = selected.has(cat);

      cb.addEventListener("change", () => {
        cb.checked ? selected.add(cat) : selected.delete(cat);
        renderChips();
        refreshTables();
      });

      label.appendChild(cb);
      label.appendChild(document.createTextNode(cat));
      categoryListEl.appendChild(label);
    });
  }

  categorySearchEl.addEventListener("input", e => {
    renderCategoryList(e.target.value);
  });

  tableEl.addEventListener("change", () => {
    const t = DATA.tables[tableEl.value];
    setOptions(variableEl, t?.variables || [], "Select variable");

    // reset downstream
    setOptions(demographicEl, [], "Select demographic");
    setOptions(classificationEl, [], "Select option");
  });

  variableEl.addEventListener("change", () => {
    const t = DATA.tables[tableEl.value];
    setOptions(demographicEl, t?.demographics || [], "Select demographic");

    // reset downstream
    setOptions(classificationEl, [], "Select option");
  });

  demographicEl.addEventListener("change", () => {
    const t = DATA.tables[tableEl.value];
    setOptions(
      classificationEl,
      t?.classification_members?.[demographicEl.value] || [],
      "Select option"
    );
  });

  // ✅ UPDATED: uses classification_ids (dimension id) + selected member id
  classificationEl.addEventListener("change", async () => {
    const table = tableEl.value;
    const variable = variableEl.value;
    const demographic = demographicEl.value;

    // classification (dimension) id: used as /c{ID}/...
    const classificationCode = DATA.tables[table]?.classification_ids?.[demographic];

    // selected member/category id: used as /c{ID}/{member}
    const category = classificationEl.value;

    if (!table || !variable) return;

    console.log("Sending:", { table, variable, demographic, classificationCode, category });

    const res = await fetch("/api/sidra-data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table,
        variable,
        classification_code: classificationCode,
        category
      })
    });

    const result = await res.json();
    console.log("SIDRA result:", result);
  });

  // init
  renderCategoryList();
})();