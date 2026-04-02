// static/js/dropdowns.js
(function () {
  // Read dropdown metadata injected by the backend.
  // Falls back to an empty structure so the page does not crash if data is missing.
  const dropdownData = window.DROPDOWN_DATA || { categories: {}, tables: {} };

  // Category UI
  const categorySearchInput = document.getElementById("category-search");
  const categoryListContainer = document.getElementById("category-list");
  const categoryChipsContainer = document.getElementById("category-chips");

  // Main selector
  const tableSelect = document.getElementById("table");
  const variableSelect = document.getElementById("variable");
  const demographicSelect = document.getElementById("demographic");
  const classificationSelect = document.getElementById("classification");

  // Buttons / summaries / result
  const setPrimaryButton = document.getElementById("set-primary-btn");
  const setCompareButton = document.getElementById("set-compare-btn");
  const viewCorrelationButton = document.getElementById("view-correlation-btn");
  const resetButton = document.getElementById("reset-btn");

  const primarySummaryText = document.getElementById("primary-summary");
  const compareSummaryText = document.getElementById("compare-summary");

  const correlationResultContainer = document.getElementById("correlation-result");
  const correlationResultText = document.getElementById("correlation-text");

  // Sorted list of all category names from the catalog.
  const allCategories = Object.keys(dropdownData.categories || {}).sort();

  // Tracks the categories currently checked by the user.
  const selectedCategories = new Set();

  // Stores the current primary map selection and comparison selection.
  let primarySelection = null;
  let compareSelection = null;

  // Stores the saved database id for the exported primary selection, if available.
  let currentMapVariableId = null;

  // Stores the last numeric ranges used to color the region/state layers.
  // These are reused when the active base layer changes so the legend can be rebuilt.
  let lastRegionRange = null;
  let lastStateRange = null;

  function setOptions(selectElement, items, placeholder) {
    // Safely replace all options in a <select>.
    if (!selectElement) return;

    selectElement.innerHTML = "";

    // Add a disabled placeholder option at the top.
    const placeholderOption = document.createElement("option");
    placeholderOption.value = "";
    placeholderOption.textContent = placeholder;
    placeholderOption.disabled = true;
    placeholderOption.selected = true;
    selectElement.appendChild(placeholderOption);

    // Add the real options.
    // Supports both string arrays and { value, label } objects.
    (items || []).forEach(item => {
      const optionElement = document.createElement("option");

      if (typeof item === "string") {
        optionElement.value = item;
        optionElement.textContent = item;
      } else {
        optionElement.value = item.value;
        optionElement.textContent = item.label;
      }

      selectElement.appendChild(optionElement);
    });
  }

  function intersectArrays(arrays) {
    // Return the intersection of multiple arrays.
    // Used to find which tables belong to every selected category.
    if (!arrays.length) return [];

    let intersectionSet = new Set(arrays[0]);

    for (let index = 1; index < arrays.length; index++) {
      const nextSet = new Set(arrays[index]);
      intersectionSet = new Set(
        [...intersectionSet].filter(value => nextSet.has(value))
      );

      if (intersectionSet.size === 0) break;
    }

    return [...intersectionSet];
  }

  function rankTablesForSelection(tableIds, selectedCategoryNames) {
    // Rank matching tables so the most relevant ones appear first.
    // Preference order:
    // 1. Fewer extra categories beyond the user's selected categories
    // 2. Fewer total categories
    // 3. Lower numeric table id
    return tableIds
      .map(tableId => {
        const tableMetadata = dropdownData.tables[tableId];
        const categories = tableMetadata?.categories || [];
        const extraCategoryCount = Math.max(
          0,
          categories.length - selectedCategoryNames.length
        );

        return {
          tableId,
          label: tableMetadata?.table_name || "Unknown table",
          extraCategoryCount,
          categoryCount: categories.length
        };
      })
      .sort((leftItem, rightItem) => {
        if (leftItem.extraCategoryCount !== rightItem.extraCategoryCount) {
          return leftItem.extraCategoryCount - rightItem.extraCategoryCount;
        }

        if (leftItem.categoryCount !== rightItem.categoryCount) {
          return leftItem.categoryCount - rightItem.categoryCount;
        }

        return Number(leftItem.tableId) - Number(rightItem.tableId);
      });
  }

  function clearPrimarySelectors() {
    // Reset all dropdowns to empty placeholder state.
    setOptions(tableSelect, [], "Select table");
    setOptions(variableSelect, [], "Select variable");
    setOptions(demographicSelect, [], "Select demographic");
    setOptions(classificationSelect, [], "Select option");
  }

  function showCorrelationMessage(text) {
    // Show the correlation result box with a message.
    if (!correlationResultContainer || !correlationResultText) return;

    correlationResultContainer.style.display = "block";
    correlationResultText.textContent = text;
  }

  function resetCorrelationMessage() {
    // Hide the correlation result box and restore its default text.
    if (!correlationResultContainer || !correlationResultText) return;

    correlationResultContainer.style.display = "none";
    correlationResultText.textContent = "No result yet";
  }

  function refreshTables() {
    // Rebuild the table dropdown based on the selected categories.
    const selectedCategoryNames = [...selectedCategories];

    clearPrimarySelectors();
    resetCorrelationMessage();

    if (!selectedCategoryNames.length) return;

    const matchingTableLists = selectedCategoryNames.map(
      categoryName => dropdownData.categories[categoryName] || []
    );
    const matchingTableIds = intersectArrays(matchingTableLists);

    const rankedTables = rankTablesForSelection(
      matchingTableIds,
      selectedCategoryNames
    );

    const topTables = rankedTables.slice(0, 3).map(tableItem => ({
      value: tableItem.tableId,
      label: tableItem.label
    }));

    setOptions(
      tableSelect,
      topTables,
      topTables.length ? "Select table" : "No tables found"
    );
  }

  async function loadMapVariables() {
    // Load the user's saved map variables and render them into the saved variables table.
    const response = await fetch("/api/map-variables");
    const savedVariables = await response.json();

    const tableBody = document.querySelector("#map-vars-table tbody");
    if (!tableBody) return;

    tableBody.innerHTML = "";

    savedVariables.forEach(savedVariable => {
      const summaryRow = document.createElement("tr");

      const nameCell = document.createElement("td");
      const toggleButton = document.createElement("button");

      // Style the clickable summary as a simple text-like button.
      toggleButton.type = "button";
      toggleButton.style.cursor = "pointer";
      toggleButton.style.background = "none";
      toggleButton.style.border = "none";
      toggleButton.style.padding = "0";
      toggleButton.style.margin = "0";
      toggleButton.style.color = "#007bff";
      toggleButton.style.textAlign = "left";
      toggleButton.style.font = "inherit";
      toggleButton.style.textDecoration = "underline";

      // Build the one-line summary shown in the main row.
      const summaryParts = [
        `Table: ${savedVariable.table_name}`,
        `Variable: ${savedVariable.variable_name}`,
        `Classification: ${savedVariable.demographic_name || "—"}`,
        `Option: ${savedVariable.category_name || "—"}`
      ];

      toggleButton.textContent = summaryParts.join(" | ");
      nameCell.appendChild(toggleButton);

      const topCorrelationCell = document.createElement("td");

      // Show only the strongest saved correlation in the collapsed row.
      if (savedVariable.correlations.length) {
        const strongestCorrelation = [...savedVariable.correlations].sort(
          (leftItem, rightItem) =>
            Math.abs(rightItem.score) - Math.abs(leftItem.score)
        )[0];

        const correlationDisplay = correlationStyle(strongestCorrelation.score);
        let summaryText =
          `${strongestCorrelation.score.toFixed(3)} ` +
          `(${correlationDisplay.label})`;

        if (strongestCorrelation.compared_variable_name) {
          const comparedParts = [strongestCorrelation.compared_variable_name];

          if (strongestCorrelation.compared_demographic_name) {
            comparedParts.push(strongestCorrelation.compared_demographic_name);
          }

          if (strongestCorrelation.compared_category_name) {
            comparedParts.push(strongestCorrelation.compared_category_name);
          }

          summaryText += ` vs ${comparedParts.join(" | ")}`;
        }

        topCorrelationCell.innerHTML = `
          <div style="color:${correlationDisplay.color}; font-weight:600;">
            ${summaryText}
          </div>
        `;
      } else {
        topCorrelationCell.textContent = "—";
      }

      summaryRow.appendChild(nameCell);
      summaryRow.appendChild(topCorrelationCell);

      // Create a hidden detail row that expands on click.
      const detailRow = document.createElement("tr");
      detailRow.style.display = "none";

      const detailCell = document.createElement("td");
      detailCell.colSpan = 2;
      detailCell.style.padding = "10px 0 16px 0";

      if (savedVariable.correlations.length) {
        const sortedCorrelations = [...savedVariable.correlations].sort(
          (leftItem, rightItem) =>
            Math.abs(rightItem.score) - Math.abs(leftItem.score)
        );

        detailCell.innerHTML = `
          <div style="display:flex; flex-direction:column; gap:8px; margin-top:6px;">
            ${sortedCorrelations.map(correlationItem => {
              const correlationDisplay = correlationStyle(correlationItem.score);

              return `
                <div style="
                  padding:8px 10px;
                  border:1px solid #ddd;
                  border-radius:6px;
                  background: rgba(255,255,255,0.6);
                ">
                  <div><strong>Table:</strong> ${correlationItem.compared_table_name || "—"}</div>
                  <div><strong>Variable:</strong> ${correlationItem.compared_variable_name || "—"}</div>
                  <div><strong>Classification:</strong> ${correlationItem.compared_demographic_name || "—"}</div>
                  <div><strong>Option:</strong> ${correlationItem.compared_category_name || "—"}</div>
                  <div style="color:${correlationDisplay.color}; font-weight:600;">
                    ${correlationItem.score.toFixed(3)} (${correlationDisplay.label})
                  </div>
                </div>
              `;
            }).join("")}
          </div>
        `;
      } else {
        detailCell.textContent = "No correlations yet.";
      }

      detailRow.appendChild(detailCell);

      // Toggle the expanded detail row when the main button is clicked.
      toggleButton.addEventListener("click", () => {
        detailRow.style.display =
          detailRow.style.display === "none" ? "table-row" : "none";
      });

      tableBody.appendChild(summaryRow);
      tableBody.appendChild(detailRow);
    });
  }

  function renderChips() {
    // Render selected categories as removable chips above the selectors.
    if (!categoryChipsContainer) return;

    categoryChipsContainer.innerHTML = "";

    [...selectedCategories].forEach(categoryName => {
      const chipElement = document.createElement("span");
      chipElement.className = "chip";
      chipElement.textContent = categoryName;

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.textContent = "×";

      // Remove the category from the selected set and uncheck its checkbox.
      removeButton.addEventListener("click", () => {
        selectedCategories.delete(categoryName);

        const checkbox = categoryListContainer?.querySelector(
          `input[data-cat="${CSS.escape(categoryName)}"]`
        );
        if (checkbox) checkbox.checked = false;

        renderChips();
        refreshTables();
      });

      chipElement.appendChild(removeButton);
      categoryChipsContainer.appendChild(chipElement);
    });
  }

  function renderCategoryList() {
    // Render the category checkbox list.
    if (!categoryListContainer) return;

    categoryListContainer.innerHTML = "";

    allCategories.forEach(categoryName => {
      const labelElement = document.createElement("label");
      labelElement.className = "checkbox-item";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.dataset.cat = categoryName;
      checkbox.checked = selectedCategories.has(categoryName);

      // Keep the selected category set in sync with the checkbox state.
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          selectedCategories.add(categoryName);
        } else {
          selectedCategories.delete(categoryName);
        }

        renderChips();
        refreshTables();
      });

      labelElement.appendChild(checkbox);
      labelElement.appendChild(document.createTextNode(categoryName));
      categoryListContainer.appendChild(labelElement);
    });
  }

  // ---------------------------
  // Map helpers
  // ---------------------------
  function getMapIframeWindow() {
    // Folium renders the map inside an iframe.
    // This returns the iframe window so the map and layers can be accessed.
    const mapIframe = document.querySelector("#map-container iframe");
    if (!mapIframe) return null;

    return mapIframe.contentWindow || null;
  }

  function getMapObjects() {
    // Resolve the Folium map object and the named region/state layers from the iframe window.
    const mapWindow = getMapIframeWindow();
    if (!mapWindow) return {};

    const regionsLayer = window.REGIOES_LAYER_NAME
      ? mapWindow[window.REGIOES_LAYER_NAME]
      : null;

    const statesLayer = window.UF_LAYER_NAME
      ? mapWindow[window.UF_LAYER_NAME]
      : null;

    // Folium's generated map variable name is dynamic,
    // so detect it by looking for a Leaflet-like object.
    const mapObject = Object.values(mapWindow).find(
      value =>
        value &&
        typeof value.getZoom === "function" &&
        typeof value.addLayer === "function"
    );

    return { mapWindow, mapObject, regionsLayer, statesLayer };
  }

  function getActiveLayerType() {
    // Detect whether the currently visible base layer is regions or states.
    const { mapObject, regionsLayer, statesLayer } = getMapObjects();
    if (!mapObject) return null;

    if (regionsLayer && mapObject.hasLayer(regionsLayer)) return "regions";
    if (statesLayer && mapObject.hasLayer(statesLayer)) return "states";

    return null;
  }

  function getRange(dataByGeoCode) {
    // Return the min/max numeric range for a SIDRA response object.
    const numericValues = Object.values(dataByGeoCode || {})
      .map(value => Number(value))
      .filter(value => !isNaN(value));

    if (!numericValues.length) {
      return { min: 0, max: 0 };
    }

    return {
      min: Math.min(...numericValues),
      max: Math.max(...numericValues)
    };
  }

  function getColor(value, min, max) {
    // Convert a numeric value into a choropleth color bucket.
    if (value === undefined || value === null || isNaN(value)) return "#cccccc";
    if (max <= min) return "#3388ff";

    const ratio = (value - min) / (max - min);

    if (ratio > 0.8) return "#08306b";
    if (ratio > 0.6) return "#2171b5";
    if (ratio > 0.4) return "#4292c6";
    if (ratio > 0.2) return "#6baed6";
    return "#9ecae1";
  }

  function updateRegions(regionData) {
    // Apply values and tooltips to the regions layer.
    const { regionsLayer } = getMapObjects();

    if (!regionsLayer || typeof regionsLayer.eachLayer !== "function") {
      console.warn("Regions layer not found.");
      return;
    }

    const { min, max } = getRange(regionData);
    lastRegionRange = { min, max };

    const activeLayerType = getActiveLayerType();
    if (activeLayerType === "regions") {
      addLegend(min, max, "Regions");
    }

    // Map region abbreviations in the shapefile to SIDRA n2 codes.
    const regionCodeByAbbreviation = {
      N: "1",
      NE: "2",
      SE: "3",
      S: "4",
      CO: "5"
    };

    regionsLayer.eachLayer(regionLayer => {
      const properties = regionLayer.feature?.properties || {};
      const regionAbbreviation = properties.SIGLA_RG;
      const regionCode = regionCodeByAbbreviation[regionAbbreviation];
      const value = regionCode && regionData
        ? Number(regionData[regionCode])
        : undefined;

      const regionName =
        properties.NM_REGIAO ||
        properties.NM_RG ||
        "Região";

      const valueText =
        value === undefined || value === null || isNaN(value)
          ? "Sem dado"
          : value.toLocaleString("pt-BR");

      if (typeof regionLayer.setStyle === "function") {
        regionLayer.setStyle({
          fillColor: getColor(value, min, max),
          color: "#222222",
          weight: 1,
          fillOpacity: 0.6
        });
      }

      if (typeof regionLayer.unbindTooltip === "function") {
        regionLayer.unbindTooltip();
      }

      regionLayer.bindTooltip(
        `<div><b>${regionName}</b></div><div>Value: ${valueText}</div>`,
        { sticky: true }
      );
    });
  }

  function refreshLegendForActiveLayer() {
    // Remove the current legend and rebuild it for whichever base layer is active.
    const activeLayerType = getActiveLayerType();
    const mapWindow = getMapIframeWindow();

    if (!mapWindow || !mapWindow.document) return;

    const existingLegend = mapWindow.document.getElementById("map-legend");
    if (existingLegend) existingLegend.remove();

    if (activeLayerType === "regions" && lastRegionRange) {
      addLegend(lastRegionRange.min, lastRegionRange.max, "Regions");
    } else if (activeLayerType === "states" && lastStateRange) {
      addLegend(lastStateRange.min, lastStateRange.max, "States");
    }
  }

  function addLegend(min, max, label) {
    // Draw a custom legend inside the map iframe.
    const mapWindow = getMapIframeWindow();
    if (!mapWindow || !mapWindow.document) return;

    const existingLegend = mapWindow.document.getElementById("map-legend");
    if (existingLegend) existingLegend.remove();

    const legendElement = mapWindow.document.createElement("div");
    legendElement.id = "map-legend";

    legendElement.style.position = "absolute";
    legendElement.style.bottom = "20px";
    legendElement.style.left = "20px";
    legendElement.style.background = "white";
    legendElement.style.padding = "10px 12px";
    legendElement.style.border = "1px solid #ccc";
    legendElement.style.borderRadius = "6px";
    legendElement.style.fontSize = "12px";
    legendElement.style.boxShadow = "0 2px 6px rgba(0,0,0,0.2)";
    legendElement.style.zIndex = "999";
    legendElement.style.minWidth = "220px";

    function formatNumber(value) {
      // Format numeric labels using Brazilian number formatting.
      return Number(value).toLocaleString("pt-BR", {
        maximumFractionDigits: 1
      });
    }

    legendElement.innerHTML = `
      <div style="font-weight:bold; margin-bottom:8px;">${label}</div>

      <div style="
        display:grid;
        grid-template-columns: repeat(5, 1fr);
        width:100%;
        height:16px;
        border:1px solid #999;
        border-radius:4px;
        overflow:hidden;
        margin-bottom:6px;
      ">
        <div style="background:#9ecae1;"></div>
        <div style="background:#6baed6;"></div>
        <div style="background:#4292c6;"></div>
        <div style="background:#2171b5;"></div>
        <div style="background:#08306b;"></div>
      </div>

      <div style="display:flex; justify-content:space-between; gap:12px;">
        <span>${formatNumber(min)}</span>
        <span>${formatNumber(max)}</span>
      </div>
    `;

    mapWindow.document.body.appendChild(legendElement);
  }

  function updateStates(stateData) {
    // Apply values and tooltips to the states layer.
    const { statesLayer } = getMapObjects();

    if (!statesLayer || typeof statesLayer.eachLayer !== "function") {
      console.warn("UF layer not found.");
      return;
    }

    const { min, max } = getRange(stateData);
    lastStateRange = { min, max };

    const activeLayerType = getActiveLayerType();
    if (activeLayerType === "states") {
      addLegend(min, max, "States");
    }

    statesLayer.eachLayer(stateLayer => {
      const properties = stateLayer.feature?.properties || {};

      // Support several possible shapefile field names for the state code.
      const stateCode = String(
        properties.CD_UF ??
        properties.cd_uf ??
        properties.CODUF ??
        properties.coduf ??
        properties.CD_GEOCUF ??
        properties.cd_geocuf ??
        ""
      );

      const stateName =
        properties.NM_UF ||
        properties.nome ||
        properties.NAME ||
        properties.SIGLA_UF ||
        "UF";

      const value = stateCode && stateData
        ? Number(stateData[stateCode])
        : undefined;

      const valueText =
        value === undefined || value === null || isNaN(value)
          ? "Sem dado"
          : value.toLocaleString("pt-BR");

      if (typeof stateLayer.setStyle === "function") {
        stateLayer.setStyle({
          fillColor: getColor(value, min, max),
          color: "#222222",
          weight: 1,
          fillOpacity: 0.6
        });
      }

      if (typeof stateLayer.unbindTooltip === "function") {
        stateLayer.unbindTooltip();
      }

      stateLayer.bindTooltip(
        `<div><b>${stateName}</b></div><div>Value: ${valueText}</div>`,
        { sticky: true }
      );
    });
  }

  function attachMapHandler() {
    // Attach a one-time listener so switching between Regions/States refreshes the legend.
    const { mapObject } = getMapObjects();

    if (!mapObject) {
      console.warn("Map object not found yet.");
      return false;
    }

    if (mapObject._legendHandlerAttached) {
      return true;
    }

    mapObject.on("baselayerchange", () => {
      refreshLegendForActiveLayer();
    });

    mapObject._legendHandlerAttached = true;
    return true;
  }

  // ---------------------------
  // Selection storage helpers
  // ---------------------------
  function getSelectionPayload() {
    // Build the current selection payload from the dropdown values.
    const tableId = tableSelect?.value || "";
    const variableId = variableSelect?.value || "";
    const demographic = demographicSelect?.value || "";
    const category = classificationSelect?.value || "";

    const classificationCode =
      dropdownData.tables[tableId]?.classification_ids?.[demographic] || "";

    return {
      table: tableId,
      variable: variableId,
      demographic,
      classification_code: classificationCode,
      category
    };
  }

  function formatSelectionLabel(selection) {
    // Convert a selection object into a readable one-line label.
    if (!selection || !selection.table || !selection.variable) {
      return "none selected";
    }

    const tableName =
      dropdownData.tables[selection.table]?.table_name || selection.table;

    const variableName =
      dropdownData.tables[selection.table]?.variables?.find(
        variableItem => String(variableItem.value) === String(selection.variable)
      )?.label || selection.variable;

    const demographicName = selection.demographic || "No demographic";

    const optionName =
      dropdownData.tables[selection.table]?.classification_members?.[
        selection.demographic
      ]?.find(
        optionItem => String(optionItem.value) === String(selection.category)
      )?.label || selection.category || "No option";

    return `${tableName} | ${variableName} | ${demographicName} | ${optionName}`;
  }

  function renderSelectionSummaries() {
    // Update the visible summary text for the primary and comparison selections.
    if (primarySummaryText) {
      primarySummaryText.textContent =
        `Map variable: ${formatSelectionLabel(primarySelection)}`;
    }

    if (compareSummaryText) {
      compareSummaryText.textContent =
        `Comparison variable: ${formatSelectionLabel(compareSelection)}`;
    }
  }

  async function fetchAndRenderPrimaryMapFromSelection(selectionPayload) {
    // Fetch map-ready SIDRA data and repaint both map layers.
    if (!selectionPayload.table || !selectionPayload.variable) return;

    try {
      const response = await fetch("/api/sidra-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(selectionPayload)
      });

      const result = await response.json();

      if (result?.error) {
        console.error("SIDRA error:", result.error);
        showCorrelationMessage(result.error);
        return;
      }

      if (result?.n2) updateRegions(result.n2);
      if (result?.n3) updateStates(result.n3);
    } catch (error) {
      console.error("Failed to fetch SIDRA data:", error);
      showCorrelationMessage("Failed to fetch map data.");
    }
  }

  async function setPrimarySelection() {
    // Save the current dropdown state as the primary map variable and repaint the map.
    const selectionPayload = getSelectionPayload();

    if (!selectionPayload.table || !selectionPayload.variable) {
      showCorrelationMessage("Choose a table and variable first.");
      return;
    }

    primarySelection = selectionPayload;
    currentMapVariableId = null;

    renderSelectionSummaries();
    resetCorrelationMessage();

    await fetchAndRenderPrimaryMapFromSelection(primarySelection);
  }

  function setCompareSelection() {
    // Save the current dropdown state as the comparison variable.
    const selectionPayload = getSelectionPayload();

    if (!selectionPayload.table || !selectionPayload.variable) {
      showCorrelationMessage("Choose a table and variable first.");
      return;
    }

    compareSelection = selectionPayload;
    renderSelectionSummaries();
    resetCorrelationMessage();
  }

  function interpretCorrelation(correlationValue) {
    // Convert a numeric Pearson score into a text strength label.
    const absoluteValue = Math.abs(correlationValue);

    if (absoluteValue >= 0.8) return "very strong";
    if (absoluteValue >= 0.6) return "strong";
    if (absoluteValue >= 0.4) return "moderate";
    if (absoluteValue >= 0.2) return "weak";
    return "very weak";
  }

  async function calculateCorrelation() {
    // Export the primary variable if needed, then calculate and display correlation.
    if (!primarySelection) {
      showCorrelationMessage("Set a map variable first.");
      return;
    }

    if (!compareSelection) {
      showCorrelationMessage("Set a comparison variable first.");
      return;
    }

    // Save the primary selection to the backend once so future correlations can link to it.
    if (!currentMapVariableId) {
      try {
        const exportResponse = await fetch("/api/export-variable", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            table: primarySelection.table,
            variable: primarySelection.variable,
            demographic: primarySelection.demographic,
            classification: primarySelection.category,
            label: formatSelectionLabel(primarySelection)
          })
        });

        // Only use the result if the export succeeded.
        if (exportResponse.ok) {
          const exportResult = await exportResponse.json();
          currentMapVariableId = exportResult.id;
        }
      } catch (error) {
        console.warn("Export failed (ignored):", error);
        // Continue anyway so correlation still works even if export fails.
      }
    }

    showCorrelationMessage("Calculating correlation...");

    try {
      const response = await fetch("/api/correlate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          left: primarySelection,
          right: compareSelection,
          map_variable_id: currentMapVariableId,
          compare_table: compareSelection.table,
          compare_variable: compareSelection.variable,
          compare_demographic: compareSelection.demographic,
          compare_category: compareSelection.category
        })
      });

      const result = await response.json();

      if (result?.error) {
        showCorrelationMessage(result.error);
        return;
      }

      const correlationValue = Number(result.correlation);
      const correlationStrength = interpretCorrelation(correlationValue);

      showCorrelationMessage(
        `Pearson correlation: ${correlationValue.toFixed(3)} ` +
        `(${correlationStrength}) across ${result.count} states`
      );

      loadMapVariables();
    } catch (error) {
      console.error("Failed:", error);
      showCorrelationMessage("Failed to calculate correlation.");
    }
  }

  function resetAll() {
    // Reset all current selections and UI state.
    selectedCategories.clear();

    primarySelection = null;
    compareSelection = null;
    currentMapVariableId = null;

    lastRegionRange = null;
    lastStateRange = null;

    if (categorySearchInput) categorySearchInput.value = "";

    renderCategoryList();
    renderChips();
    clearPrimarySelectors();
    resetCorrelationMessage();
    renderSelectionSummaries();
  }

  function correlationStyle(correlationValue) {
    // Return a color + label pair for displaying saved correlation results.
    if (correlationValue >= 0.6) {
      return { color: "green", label: "strong positive" };
    }
    if (correlationValue >= 0.3) {
      return { color: "#6baed6", label: "moderate positive" };
    }
    if (correlationValue > 0) {
      return { color: "#9ecae1", label: "weak positive" };
    }
    if (correlationValue > -0.3) {
      return { color: "#fcae91", label: "weak negative" };
    }
    if (correlationValue > -0.6) {
      return { color: "#fb6a4a", label: "moderate negative" };
    }
    return { color: "#cb181d", label: "strong negative" };
  }

  // ---------------------------
  // Event wiring
  // ---------------------------
  if (categorySearchInput) {
    categorySearchInput.addEventListener("input", event => {
      // Use the search box to filter available tables by name.
      const searchQuery = event.target.value.toLowerCase();
      const selectedCategoryNames = [...selectedCategories];

      let matchingTableIds = [];

      // Step 1: start from category filter (if any)
      if (selectedCategoryNames.length) {
        const matchingTableLists = selectedCategoryNames.map(
          categoryName => dropdownData.categories[categoryName] || []
        );
        matchingTableIds = intersectArrays(matchingTableLists);
      } else {
        // no categories selected → all tables
        matchingTableIds = Object.keys(dropdownData.tables);
      }

      // Step 2: apply search filter
      if (searchQuery) {
        matchingTableIds = matchingTableIds.filter(tableId =>
          (dropdownData.tables[tableId]?.table_name || "")
            .toLowerCase()
            .includes(searchQuery)
        );
      }

      // Step 3: rank like your existing logic
      const rankedTables = rankTablesForSelection(
        matchingTableIds,
        selectedCategoryNames
      );

      const topTables = rankedTables.slice(0, 10).map(tableItem => ({
        value: tableItem.tableId,
        label: tableItem.label
      }));

      setOptions(
        tableSelect,
        topTables,
        topTables.length ? "Select table" : "No tables found"
      );

      // Clear dependent dropdowns
      setOptions(variableSelect, [], "Select variable");
      setOptions(demographicSelect, [], "Select demographic");
      setOptions(classificationSelect, [], "Select option");
    });
  }

  if (tableSelect) {
    tableSelect.addEventListener("change", () => {
      // Populate variables for the selected table and clear lower-level selectors.
      const tableMetadata = dropdownData.tables[tableSelect.value];

      setOptions(variableSelect, tableMetadata?.variables || [], "Select variable");
      setOptions(demographicSelect, [], "Select demographic");
      setOptions(classificationSelect, [], "Select option");
      resetCorrelationMessage();
    });
  }

  if (variableSelect) {
    variableSelect.addEventListener("change", () => {
      // Populate demographics after a variable is selected.
      const tableMetadata = dropdownData.tables[tableSelect.value];

      setOptions(
        demographicSelect,
        tableMetadata?.demographics || [],
        "Select demographic"
      );
      setOptions(classificationSelect, [], "Select option");
      resetCorrelationMessage();
    });
  }

  if (demographicSelect) {
    demographicSelect.addEventListener("change", () => {
      // Populate the classification options for the selected demographic.
      const tableMetadata = dropdownData.tables[tableSelect.value];

      setOptions(
        classificationSelect,
        tableMetadata?.classification_members?.[demographicSelect.value] || [],
        "Select option"
      );
      resetCorrelationMessage();
    });
  }

  if (classificationSelect) {
    classificationSelect.addEventListener("change", () => {
      // Any change to the last selector invalidates the previous result display.
      resetCorrelationMessage();
    });
  }

  if (setPrimaryButton) {
    setPrimaryButton.addEventListener("click", setPrimarySelection);
  }

  if (setCompareButton) {
    setCompareButton.addEventListener("click", setCompareSelection);
  }

  if (viewCorrelationButton) {
    viewCorrelationButton.addEventListener("click", calculateCorrelation);
  }

  if (resetButton) {
    resetButton.addEventListener("click", resetAll);
  }

  // ---------------------------
  // Init
  // ---------------------------
  // Render initial UI state.
  renderCategoryList();
  renderSelectionSummaries();

  // Load saved map variables only on the page that contains the table.
  if (document.querySelector("#map-vars-table tbody")) {
    loadMapVariables();
  }

  // Wait for the Folium iframe to finish loading, then attach the legend refresh handler.
  window.addEventListener("load", () => {
    let attemptCount = 0;
    const maxAttempts = 20;

    const retryTimer = setInterval(() => {
      attemptCount += 1;
      const attached = attachMapHandler();

      if (attached || attemptCount >= maxAttempts) {
        clearInterval(retryTimer);
      }
    }, 300);
  });
})();