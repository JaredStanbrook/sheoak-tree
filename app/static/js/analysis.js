/**
 * static/js/analysis.js
 */
import { Utils } from "./core.js";

class AnalysisController {
  constructor() {
    this.chart = null;
    this.detailChart = null;
    this.openChart = null;
    this.elements = {
      ctx: document.getElementById("frequencyChart"),
      info: document.getElementById("chartInfo"),
      logList: document.getElementById("activity-list"),
      detailTitle: document.getElementById("hardwareDetailTitle"),
      detailSubtitle: document.getElementById("hardwareDetailSubtitle"),
      detailSummary: document.getElementById("hardwareDetailSummary"),
      detailEvents: document.getElementById("hardwareDetailEvents"),
      detailChart: document.getElementById("hardwareDetailChart"),
      openChart: document.getElementById("hardwareDetailOpenChart"),
      summaryGrid: document.getElementById("summaryGrid"),
      topNRange: document.getElementById("topNRange"),
      threshold: document.getElementById("activityThreshold"),
      exportButton: document.getElementById("exportHardwareSummary"),
      banner: document.getElementById("analysisBanner"),
      presetButtons: document.querySelectorAll(".preset-btn"),
      rangeStart: document.getElementById("rangeStart"),
      rangeEnd: document.getElementById("rangeEnd"),
      bucketSize: document.getElementById("bucketSize"),
      overlayToggle: document.getElementById("overlayToggle"),
      applyButton: document.getElementById("applyRange"),
      contributorsChart: document.getElementById("contributorsChart"),
      hourlyChart: document.getElementById("hourlyChart"),
      distributionChart: document.getElementById("distributionChart"),
      summaryCurrent: document.getElementById("summaryCurrent"),
      summaryAverage: document.getElementById("summaryAverage"),
      summaryPeak: document.getElementById("summaryPeak"),
      summaryChange: document.getElementById("summaryChange"),
      summaryEvents: document.getElementById("summaryEvents"),
      summaryAnomalies: document.getElementById("summaryAnomalies"),
      primarySubtitle: document.getElementById("primarySubtitle"),
      bucketTableBody: document.getElementById("bucketTableBody"),
    };
    this.hardwareIndex = new Map();
    this.summaryByName = new Map();
    this.state = {
      preset: "24h",
      start: null,
      end: null,
      bucket: "auto",
      overlay: true,
    };

    if (this.elements.applyButton)
      this.elements.applyButton.addEventListener("click", () => this.applyFilters());
    if (this.elements.presetButtons) {
      this.elements.presetButtons.forEach((btn) =>
        btn.addEventListener("click", () => this.applyPreset(btn.dataset.range)),
      );
    }
    if (this.elements.topNRange)
      this.elements.topNRange.addEventListener("change", () => this.renderSummary());
    if (this.elements.threshold)
      this.elements.threshold.addEventListener("change", () => {
        this.renderSummary();
        this.applyThreshold();
      });
    if (this.elements.exportButton)
      this.elements.exportButton.addEventListener("click", () => this.exportSummaryCsv());

    // Listen for Real-time SSE Events (dispatched by core.js)
    window.addEventListener("hardware_update", (e) => {
      // e.detail contains the raw hardware event data
      this.addLogEntry(e.detail);
    });

    // Initialize
    this.initChart();
    this.initDetailChart();
    this.initOpenChart();
    this.initSecondaryCharts();
    const hasUrlFilters = this.loadFiltersFromUrl();
    if (!hasUrlFilters) {
      this.setDefaultRange();
      this.applyPreset(this.state.preset, true);
    }
    this.requestFrequencyData();
    this.loadActivityHistory();
  }

  initChart() {
    if (typeof Chart === "undefined") return;

    // Light Theme Chart Config
    Chart.defaults.color = "#64748b";
    Chart.defaults.borderColor = "rgba(0, 0, 0, 0.05)";

    this.chart = new Chart(this.elements.ctx.getContext("2d"), {
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: false, axis: "x" },
        hover: { mode: "nearest", intersect: false },
        elements: { point: { radius: 0, hitRadius: 10, hoverRadius: 4 } },
        scales: {
          x: {
            type: "time",
            time: { unit: "hour", displayFormats: { hour: "HH:mm" } },
            ticks: { maxTicksLimit: 8 },
            grid: { color: "rgba(0, 0, 0, 0.05)" },
          },
          y: {
            beginAtZero: true,
            ticks: { maxTicksLimit: 6 },
            grid: { color: "rgba(0, 0, 0, 0.05)" },
          },
          y1: { display: false, position: "right", min: 0, max: 1 },
        },
        plugins: {
          legend: { labels: { usePointStyle: true, boxWidth: 6 } },
          tooltip: {
            mode: "nearest",
            intersect: false,
            position: "nearest",
            backgroundColor: "rgba(255, 255, 255, 0.9)",
            titleColor: "#1e293b",
            bodyColor: "#64748b",
            borderColor: "rgba(0,0,0,0.1)",
            borderWidth: 1,
            callbacks: {
              title: (items) =>
                items.length ? Utils.formatDate(items[0].parsed.x) : "",
              label: (ctx) =>
                `${ctx.dataset.label}: ${ctx.parsed.y ?? 0}`,
            },
          },
        },
      },
    });
  }

  initDetailChart(type = "line") {
    if (typeof Chart === "undefined" || !this.elements.detailChart) return;

    this.detailChart = new Chart(this.elements.detailChart.getContext("2d"), {
      type,
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false, axis: "x" },
        hover: { mode: "index", intersect: false },
        elements: { point: { radius: 0, hitRadius: 10, hoverRadius: 4 } },
        scales: {
          x: { type: "time", time: { unit: "hour", displayFormats: { hour: "HH:mm" } } },
          y: { beginAtZero: true, title: { display: false } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: "index",
            intersect: false,
            position: "nearest",
            backgroundColor: "rgba(255, 255, 255, 0.9)",
            titleColor: "#1e293b",
            bodyColor: "#64748b",
            borderColor: "rgba(0,0,0,0.1)",
            borderWidth: 1,
          },
        },
      },
    });
  }

  initOpenChart() {
    if (typeof Chart === "undefined" || !this.elements.openChart) return;

    this.openChart = new Chart(this.elements.openChart.getContext("2d"), {
      type: "bar",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false, axis: "x" },
        hover: { mode: "index", intersect: false },
        scales: {
          x: { ticks: { autoSkip: true } },
          y: { beginAtZero: true, title: { display: false } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: "index",
            intersect: false,
            position: "nearest",
            backgroundColor: "rgba(255, 255, 255, 0.9)",
            titleColor: "#1e293b",
            bodyColor: "#64748b",
            borderColor: "rgba(0,0,0,0.1)",
            borderWidth: 1,
          },
        },
      },
    });
  }

  initSecondaryCharts() {
    if (typeof Chart === "undefined") return;

    if (this.elements.contributorsChart) {
      this.contributorsChart = new Chart(this.elements.contributorsChart.getContext("2d"), {
        type: "bar",
        data: { labels: [], datasets: [] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
      });
    }

    if (this.elements.hourlyChart) {
      this.hourlyChart = new Chart(this.elements.hourlyChart.getContext("2d"), {
        type: "bar",
        data: { labels: [], datasets: [] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
      });
    }

    if (this.elements.distributionChart) {
      this.distributionChart = new Chart(this.elements.distributionChart.getContext("2d"), {
        type: "bar",
        data: { labels: [], datasets: [] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
      });
    }
  }

  async requestFrequencyData() {
    const filters = this.getFilters();

    try {
      this.setBanner();
      const data = await this.fetchAnalysis(filters);
      if (!data || !data.success) return;
      this.renderAll(data, filters);
    } catch (e) {
      console.error("Failed to load frequency data:", e);
      this.setBanner("Failed to load analysis data.");
    }
  }

  async loadActivityHistory() {
    try {
      // Fetch historical log directly from API
      const data = await Utils.fetchJson("/api/activity/24");
      if (data.success && data.activity) {
        this.setHistoricalLog(data.activity);
      }
    } catch (e) {
      console.error("Failed to load activity history:", e);
      if (this.elements.logList) {
        this.elements.logList.innerHTML =
          '<div class="text-center text-danger list-empty">Failed to load history</div>';
      }
    }
  }

  updateChart(data, hardwareIndex, summary, totalCounts) {
    if (!this.chart) return;
    const { hardwares, timestamps, interval_minutes } = data;
    this.buildHardwareIndex(hardwareIndex);
    this.buildSummaryIndex(summary);
    this.configureTimeScale(timestamps);
    // Updated Light Palette: Emerald, Blue, Amber, Violet
    const palette = ["#059669", "#2563eb", "#d97706", "#7c3aed"];
    let colorIdx = 0;
    const datasets = [];

    const showOverlays = this.elements.overlayToggle?.value !== "off";
    if (!showOverlays) {
      this.chart.data.labels = timestamps;
      this.chart.data.datasets = datasets;
      this.chart.update();
      if (this.elements.info) {
        this.elements.info.innerHTML = `Bucket: <strong>${interval_minutes} min</strong>`;
      }
      return;
    }

    Object.keys(hardwares).forEach((label) => {
      const rawData = hardwares[label];
      const isDoor =
        Array.isArray(rawData) && rawData.length > 0 && rawData[0].hasOwnProperty("state");

      if (isDoor) {
        // Door logic remains same
        const blocks = [];
        let openTime = null;
        rawData.forEach((evt) => {
          if (evt.state === "open") openTime = evt.x;
          else if (evt.state === "closed" && openTime) {
            blocks.push({ x: [openTime, evt.x], y: 1 });
            openTime = null;
          }
        });
        if (openTime) blocks.push({ x: [openTime, new Date().toISOString()], y: 1 });

        if (blocks.length > 0) {
          datasets.push({
            label: label,
            type: "bar",
            yAxisID: "y1",
            data: blocks,
            backgroundColor: "rgba(245, 158, 11, 0.5)", // Amber transparent
            borderColor: "#d97706",
            borderWidth: 1,
            barThickness: 12,
            indexAxis: "y",
          });
        }
      } else {
        const color = palette[colorIdx++ % palette.length];
        datasets.push({
          label: label,
          type: "line",
          yAxisID: "y",
          data: rawData,
          borderColor: color,
          backgroundColor: color + "10", // Low opacity hex
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          pointRadius: 0,
          pointHitRadius: 10,
          pointHoverRadius: 4,
          _baseColor: color,
        });
      }
    });

    this.chart.data.labels = timestamps;
    this.chart.data.datasets = datasets;
    this.chart.options.onClick = (evt) => {
      if (!this.chart) return;
      const elements = this.chart.getElementsAtEventForMode(
        evt,
        "nearest",
        { intersect: false },
        true,
      );
      if (!elements.length) return;
      const dataset = this.chart.data.datasets[elements[0].datasetIndex];
      if (!dataset) return;
      const hardwareId = this.hardwareIndex.get(dataset.label);
      if (!hardwareId) return;
      this.loadHardwareDetail(hardwareId, dataset.label);
    };
    this.chart.update();
    if (this.elements.info) {
      this.elements.info.innerHTML = `Bucket: <strong>${interval_minutes} min</strong>`;
    }
  }

  configureTimeScale(timestamps) {
    if (!this.chart || !Array.isArray(timestamps) || timestamps.length < 2) return;
    const start = new Date(timestamps[0]).getTime();
    const end = new Date(timestamps[timestamps.length - 1]).getTime();
    if (Number.isNaN(start) || Number.isNaN(end)) return;

    const hours = Math.max(1, (end - start) / 36e5);
    let unit = "hour";
    let displayFormats = { hour: "HH:mm" };
    let maxTicks = 8;

    if (hours > 24 * 30) {
      unit = "week";
      displayFormats = { week: "MMM d" };
      maxTicks = 6;
    } else if (hours > 24 * 7) {
      unit = "day";
      displayFormats = { day: "MMM d" };
      maxTicks = 8;
    } else if (hours > 24) {
      unit = "day";
      displayFormats = { day: "EEE d" };
      maxTicks = 10;
    } else if (hours > 6) {
      unit = "hour";
      displayFormats = { hour: "HH:mm" };
      maxTicks = 8;
    } else {
      unit = "minute";
      displayFormats = { minute: "HH:mm" };
      maxTicks = 8;
    }

    this.chart.options.scales.x.time.unit = unit;
    this.chart.options.scales.x.time.displayFormats = displayFormats;
    this.chart.options.scales.x.ticks.maxTicksLimit = maxTicks;
  }

  setHistoricalLog(data) {
    if (this.elements.logList) this.elements.logList.innerHTML = "";
    // Process list in reverse to show newest first
    // Note: API returns newest first usually, but setHistoricalLog logic suggests we iterate and prepend?
    // Let's stick to your original logic: iterate and add.
    // If 'data' is newest-first, we should iterate normally if 'addLogEntry' uses 'afterbegin' (prepend).
    // Actually, looking at original code: [...data].reverse().forEach(...) -> addLogEntry.
    // addLogEntry uses insertAdjacentHTML('afterbegin').
    // So to keep newest at top, we want to add oldest FIRST, then newest LAST.
    // So [...data].reverse() is correct if data is Newest->Oldest.
    [...data].reverse().forEach((item) => {
      // Filter for significant events (active state or specific types)
      if (item.value === 1 || item.state === 1 || item.type === "relay") {
        this.addLogEntry(item);
      }
    });
  }

  addLogEntry(data) {
    if (!this.elements.logList) return;
    const type = (data.type || "motion").toLowerCase();
    const event = data.event || data.type;
    const hardware = data.hardware_name || data.name;

    const entryHtml = `
            <div class="log-item type-${type.includes("door") ? "door" : "motion"}">
                <div class="log-content">
                    <strong>${hardware}</strong>
                    <span>${event}</span>
                </div>
                <div class="log-time">
                    <div>${Utils.formatDate(data.timestamp).split(", ")[1]}</div> 
                    <div class="text-muted text-xs">${Utils.timeAgo(data.timestamp)}</div>
                </div>
            </div>`;

    this.elements.logList.insertAdjacentHTML("afterbegin", entryHtml);
    while (this.elements.logList.children.length > 50) {
      this.elements.logList.removeChild(this.elements.logList.lastChild);
    }
  }

  buildHardwareIndex(list) {
    this.hardwareIndex.clear();
    if (!Array.isArray(list)) return;
    list.forEach((hw) => {
      if (hw && hw.name && hw.id) {
        this.hardwareIndex.set(hw.name, hw.id);
      }
    });
  }

  buildSummaryIndex(list) {
    this.summaryByName.clear();
    if (!Array.isArray(list)) return;
    list.forEach((item) => {
      if (item && item.name) {
        this.summaryByName.set(item.name, item);
      }
    });
  }

  renderSummaryTotals(summary, interval) {
    if (!summary || !this.elements.info) return;
    const totals = [
      `Hardware: <strong>${summary.hardware_count}</strong>`,
      `Events: <strong>${summary.total_events}</strong>`,
      `Active: <strong>${summary.active_events}</strong>`,
      `Interval: <strong>${interval} min</strong>`,
    ];
    this.elements.info.innerHTML = totals.join(" • ");
  }

  renderSummary(summary) {
    if (!this.elements.summaryGrid) return;
    if (!summary || summary.length === 0) {
      this.elements.summaryGrid.innerHTML =
        '<div class="text-muted text-center list-empty">No hardware data</div>';
      return;
    }

    const topN = parseInt(this.elements.topNRange?.value || "0");
    const threshold = parseInt(this.elements.threshold?.value || "0");
    const sorted = [...summary].sort((a, b) => (b.active_events || 0) - (a.active_events || 0));
    const filtered =
      threshold > 0 ? sorted.filter((item) => (item.active_events || 0) >= threshold) : sorted;
    const list = topN > 0 ? filtered.slice(0, topN) : filtered;

    this.elements.summaryGrid.innerHTML = list
      .map((item) => {
        const lastSeen = item.last_seen ? Utils.timeAgo(item.last_seen) : "—";
        const extra =
          item.config_type === "door"
            ? `${item.total_open_minutes || 0} min open`
            : item.config_type === "motion"
              ? `${item.avg_events_per_hour || 0} / hr`
              : `${item.active_events || 0} active`;
        return `
        <div class="summary-card" data-hardware-id="${item.id}" data-label="${item.name}">
          <div class="summary-title">${item.name}</div>
          <div class="summary-meta">${item.config_type} • ${lastSeen}</div>
          <div class="summary-meta">${item.total_events || 0} events • ${extra}</div>
        </div>`;
      })
      .join("");

    this.elements.summaryGrid.querySelectorAll(".summary-card").forEach((card) => {
      card.addEventListener("click", () => {
        const hwId = card.dataset.hardwareId;
        const label = card.dataset.label;
        if (hwId) {
          this.loadHardwareDetail(hwId, label);
        }
      });
    });
  }

  applyThreshold() {
    if (!this.chart || !this.elements.threshold) return;
    const threshold = parseInt(this.elements.threshold.value || "0");
    this.chart.data.datasets.forEach((dataset) => {
      const summary = this.summaryByName.get(dataset.label);
      const active = summary?.active_events || 0;
      if (threshold > 0 && active < threshold) {
        dataset.borderColor = "#cbd5f5";
        dataset.backgroundColor = "transparent";
        dataset.borderWidth = 1;
      } else if (dataset._baseColor) {
        dataset.borderColor = dataset._baseColor;
        dataset.backgroundColor = dataset._baseColor + "10";
        dataset.borderWidth = 2;
      }
    });
    this.chart.update();
  }

  async loadHardwareDetail(hardwareId, label) {
    const hours = this.estimateHours(
      this.elements.rangeStart?.value,
      this.elements.rangeEnd?.value,
    );
    const interval = this.elements.bucketSize?.value || "auto";

    if (
      !this.elements.detailTitle ||
      !this.elements.detailSubtitle ||
      !this.elements.detailSummary ||
      !this.elements.detailEvents
    )
      return;

    this.elements.detailTitle.textContent = label;
    this.elements.detailSubtitle.textContent = `Last ${hours} hours`;

    this.elements.detailSummary.innerHTML = "";
    this.elements.detailEvents.innerHTML =
      '<div class="text-center text-muted list-empty">Loading details...</div>';

    try {
      const queryInterval = interval === "auto" ? 30 : parseInt(interval);
      const data = await Utils.fetchJson(
        `/api/hardwares/${hardwareId}/history?hours=${hours}&interval=${queryInterval}`,
      );
      if (!data.success) return;

      const configType = data.hardware?.config_type || "generic";
      this.elements.detailSubtitle.textContent = `${configType} • Last ${hours} hours`;

      this.renderDetailSummary(data.summary);
      this.renderDetailEvents(data.recent_events);
      this.renderDetailChart(data.series, label);
      this.renderOpenChart(data.summary);
    } catch (e) {
      if (this.elements.detailEvents) {
        this.elements.detailEvents.innerHTML =
          '<div class="text-center text-danger list-empty">Failed to load details</div>';
      }
    }
  }

  renderDetailSummary(summary) {
    if (!summary || !this.elements.detailSummary) return;

    const items = [
      { label: "Total Events", value: summary.total_events ?? 0 },
      { label: "Active Events", value: summary.active_events ?? 0 },
      { label: "Last Seen", value: summary.last_seen ? Utils.timeAgo(summary.last_seen) : "—" },
    ];

    if (summary.min_value !== undefined) {
      items.push({ label: "Min Value", value: summary.min_value });
    }
    if (summary.max_value !== undefined) {
      items.push({ label: "Max Value", value: summary.max_value });
    }
    if (summary.avg_value !== undefined) {
      items.push({ label: "Avg Value", value: summary.avg_value });
    }
    if (summary.open_count !== undefined) {
      items.push({ label: "Opens", value: summary.open_count });
      items.push({ label: "Closes", value: summary.close_count });
      items.push({ label: "Open Minutes", value: summary.total_open_minutes });
      if (summary.longest_open_seconds !== undefined) {
        items.push({ label: "Longest Open (s)", value: summary.longest_open_seconds });
      }
      if (summary.peak_open_hour) {
        items.push({ label: "Peak Open Hour", value: summary.peak_open_hour });
      }
    }
    if (summary.avg_events_per_hour !== undefined) {
      items.push({ label: "Avg Events / Hr", value: summary.avg_events_per_hour });
      items.push({ label: "P90 Interval", value: summary.p90_interval_events });
      items.push({ label: "P95 Interval", value: summary.p95_interval_events });
    }

    this.elements.detailSummary.innerHTML = items
      .map(
        (item) => `
        <div class="detail-card">
          <div class="detail-label">${item.label}</div>
          <div class="detail-value">${item.value}</div>
        </div>`,
      )
      .join("");
  }

  renderDetailEvents(events) {
    if (!this.elements.detailEvents) return;
    if (!events || events.length === 0) {
      this.elements.detailEvents.innerHTML =
        '<div class="text-center text-muted list-empty">No recent events</div>';
      return;
    }

    this.elements.detailEvents.innerHTML = events
      .map(
        (event) => `
      <div class="log-item type-${event.type && event.type.includes("door") ? "door" : "motion"}">
        <div class="log-content">
          <strong>${event.hardware_name || "Hardware"}</strong>
          <span>${event.event || event.type || "Event"}</span>
        </div>
        <div class="log-time">
          <div>${Utils.formatDate(event.timestamp).split(", ")[1]}</div>
          <div class="text-muted text-xs">${Utils.timeAgo(event.timestamp)}</div>
        </div>
      </div>`,
      )
      .join("");
  }

  renderDetailChart(series, label) {
    if (!this.detailChart || !series) return;
    const desiredType = series.mode === "state_blocks" ? "bar" : "line";
    if (this.detailChart.config.type !== desiredType) {
      this.detailChart.destroy();
      this.initDetailChart(desiredType);
    }

    if (series.mode === "state_blocks") {
      this.detailChart.data.labels = series.timestamps;
      this.detailChart.data.datasets = [
        {
          label,
          data: series.data,
          backgroundColor: "rgba(245, 158, 11, 0.5)",
          borderColor: "#d97706",
          borderWidth: 1,
          barThickness: 12,
          indexAxis: "y",
        },
      ];
    } else {
      this.detailChart.data.labels = series.timestamps;
      this.detailChart.data.datasets = [
        {
          label: `${label} (count)`,
          data: series.counts,
          borderColor: "#2563eb",
          backgroundColor: "#2563eb10",
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          pointRadius: 0,
          pointHitRadius: 10,
          pointHoverRadius: 4,
        },
      ];
    }
    this.detailChart.update();
  }

  renderOpenChart(summary) {
    if (!this.openChart) return;
    if (!summary || !summary.open_minutes_by_hour) {
      this.openChart.data.labels = [];
      this.openChart.data.datasets = [];
      this.openChart.update();
      return;
    }

    const labels = summary.open_minutes_by_hour.map((b) => b.bucket);
    const values = summary.open_minutes_by_hour.map((b) => b.minutes);
    this.openChart.data.labels = labels;
    this.openChart.data.datasets = [
      {
        label: "Open Minutes",
        data: values,
        backgroundColor: "rgba(245, 158, 11, 0.5)",
        borderColor: "#d97706",
        borderWidth: 1,
      },
    ];
    this.openChart.update();
  }

  exportSummaryCsv() {
    if (!this.summaryByName.size) return;
    const rows = [
      [
        "Name",
        "Type",
        "Total Events",
        "Active Events",
        "Last Seen",
        "Open Minutes",
        "Avg Events / Hr",
        "Peak Interval",
      ],
    ];

    this.summaryByName.forEach((item) => {
      rows.push([
        item.name,
        item.config_type,
        item.total_events ?? 0,
        item.active_events ?? 0,
        item.last_seen ?? "",
        item.total_open_minutes ?? "",
        item.avg_events_per_hour ?? "",
        item.peak_interval_events ?? "",
      ]);
    });

    const csv = rows.map((r) => r.map((v) => `"${v}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "hardware_summary.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  renderAll(data, filters) {
    this.updatePrimarySubtitle(filters);
    this.updateChart(data.frequency, data.hardware_index, data.summary, data.total_counts);
    this.renderSummaryTotals(data.summary_totals, data.interval_minutes);
    this.renderSummary(data.summary);
    this.applyThreshold();
    this.renderSummaryCards(data.stats);
    this.renderSecondaryCharts(data);
    this.renderBucketTable(data.bucket_table);
    this.setBanner();
  }

  renderSummaryCards(stats) {
    if (!stats) return;
    this.elements.summaryCurrent.textContent = stats.current ?? "—";
    this.elements.summaryAverage.textContent = stats.average ?? "—";
    this.elements.summaryPeak.textContent = stats.peak ?? "—";
    this.elements.summaryChange.textContent = stats.change ?? "—";
    this.elements.summaryEvents.textContent = stats.active_events ?? "—";
    this.elements.summaryAnomalies.textContent = stats.anomalies ?? "—";
  }

  renderSecondaryCharts(data) {
    if (this.contributorsChart && data.top_contributors) {
      const labels = data.top_contributors.map((c) => c.name);
      const values = data.top_contributors.map((c) => c.active_events);
      this.contributorsChart.data.labels = labels;
      this.contributorsChart.data.datasets = [
        { data: values, backgroundColor: "rgba(37, 99, 235, 0.5)", borderColor: "#2563eb" },
      ];
      this.contributorsChart.update();
    }

    if (this.hourlyChart && data.hourly_distribution) {
      const labels = data.hourly_distribution.map((d) => d.hour);
      const values = data.hourly_distribution.map((d) => d.count);
      this.hourlyChart.data.labels = labels;
      this.hourlyChart.data.datasets = [
        { data: values, backgroundColor: "rgba(5, 150, 105, 0.5)", borderColor: "#059669" },
      ];
      this.hourlyChart.update();
    }

    if (this.distributionChart && data.distribution) {
      const labels = data.distribution.map((d) => d.bucket);
      const values = data.distribution.map((d) => d.count);
      this.distributionChart.data.labels = labels;
      this.distributionChart.data.datasets = [
        { data: values, backgroundColor: "rgba(217, 119, 6, 0.5)", borderColor: "#d97706" },
      ];
      this.distributionChart.update();
    }
  }

  renderBucketTable(rows) {
    if (!this.elements.bucketTableBody) return;
    if (!rows || rows.length === 0) {
      this.elements.bucketTableBody.innerHTML =
        '<tr><td colspan="3" class="text-center text-muted table-empty">No buckets</td></tr>';
      return;
    }
    this.elements.bucketTableBody.innerHTML = rows
      .map(
        (row) => `
        <tr>
          <td>${Utils.formatDate(row.timestamp)}</td>
          <td>${row.count}</td>
          <td>${row.avg_value ?? "—"}</td>
        </tr>`,
      )
      .join("");
  }

  updatePrimarySubtitle(filters) {
    if (!this.elements.primarySubtitle) return;
    const rangeText = filters.start && filters.end ? `${filters.start} → ${filters.end}` : filters.presetLabel;
    this.elements.primarySubtitle.textContent = rangeText;
  }

  setBanner(message) {
    if (!this.elements.banner) return;
    if (!message) {
      this.elements.banner.classList.add("is-hidden");
      this.elements.banner.textContent = "";
      return;
    }
    this.elements.banner.classList.remove("is-hidden");
    this.elements.banner.textContent = message;
  }

  setDefaultRange() {
    const now = new Date();
    const endValue = now.toISOString().slice(0, 16);
    const start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const startValue = start.toISOString().slice(0, 16);
    if (this.elements.rangeStart) this.elements.rangeStart.value = startValue;
    if (this.elements.rangeEnd) this.elements.rangeEnd.value = endValue;
  }

  applyPreset(range, silent = false) {
    this.state.preset = range;
    if (this.elements.presetButtons) {
      this.elements.presetButtons.forEach((btn) =>
        btn.classList.toggle("is-active", btn.dataset.range === range),
      );
    }
    const now = new Date();
    let hours = 24;
    if (range === "1h") hours = 1;
    if (range === "7d") hours = 168;
    if (range === "30d") hours = 720;
    const start = new Date(now.getTime() - hours * 60 * 60 * 1000);
    if (this.elements.rangeStart) this.elements.rangeStart.value = start.toISOString().slice(0, 16);
    if (this.elements.rangeEnd) this.elements.rangeEnd.value = now.toISOString().slice(0, 16);
    if (!silent) {
      this.applyFilters();
    }
  }

  applyFilters() {
    this.updateUrl(this.getFilters());
    this.requestFrequencyData();
  }

  getFilters() {
    const startValue = this.elements.rangeStart?.value;
    const endValue = this.elements.rangeEnd?.value;
    const bucket = this.elements.bucketSize?.value || "auto";
    const overlay = this.elements.overlayToggle?.value !== "off";
    const topN = this.elements.topNRange?.value;
    const min = this.elements.threshold?.value;
    return {
      start: startValue,
      end: endValue,
      bucket,
      overlay,
      topN,
      min,
      presetLabel: this.state.preset,
    };
  }

  loadFiltersFromUrl() {
    if (typeof window === "undefined") return false;
    const params = new URLSearchParams(window.location.search);
    const start = params.get("from");
    const end = params.get("to");
    const preset = params.get("preset");
    const bucket = params.get("bucket") || "auto";
    const overlay = params.get("overlay");
    const topN = params.get("topN");
    const min = params.get("min");
    const hasParams =
      Boolean(start || end || preset || bucket !== "auto" || overlay || topN || min);
    if (!hasParams) return false;

    if (bucket && this.elements.bucketSize) this.elements.bucketSize.value = bucket;
    if (overlay && this.elements.overlayToggle) {
      this.elements.overlayToggle.value = overlay === "0" ? "off" : "on";
    }
    if (topN && this.elements.topNRange) this.elements.topNRange.value = topN;
    if (min && this.elements.threshold) this.elements.threshold.value = min;

    if (start && this.elements.rangeStart) this.elements.rangeStart.value = start;
    if (end && this.elements.rangeEnd) this.elements.rangeEnd.value = end;

    if (preset && !(start || end)) {
      this.state.preset = preset;
      this.applyPreset(preset, true);
    }
    if (!(start || end)) {
      this.setDefaultRange();
    }
    return true;
  }

  updateUrl(filters) {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams();
    if (filters.start) params.set("from", filters.start);
    if (filters.end) params.set("to", filters.end);
    if (filters.bucket && filters.bucket !== "auto") params.set("bucket", filters.bucket);
    if (filters.overlay === false) params.set("overlay", "0");
    if (filters.topN && filters.topN !== "10") params.set("topN", filters.topN);
    if (filters.min && filters.min !== "0") params.set("min", filters.min);
    if (filters.presetLabel) params.set("preset", filters.presetLabel);
    const query = params.toString();
    const url = query ? `${window.location.pathname}?${query}` : window.location.pathname;
    window.history.replaceState({}, "", url);
  }

  async fetchAnalysis(filters) {
    const params = new URLSearchParams();
    if (filters.start) params.append("from", filters.start);
    if (filters.end) params.append("to", filters.end);
    if (filters.bucket && filters.bucket !== "auto") params.append("bucket", filters.bucket);
    params.append("overlay", filters.overlay ? "1" : "0");

    const url = `/api/analysis?${params.toString()}`;
    const data = await Utils.fetchJson(url);
    if (data && data.success) return data;

    // Fallback to legacy endpoints
    const hours = this.estimateHours(filters.start, filters.end);
    const interval = filters.bucket && filters.bucket !== "auto" ? parseInt(filters.bucket) : 30;
    const legacy = await Utils.fetchJson(`/api/frequency/${hours}/${interval}`);
    if (!legacy.success) return legacy;
    return {
      success: true,
      frequency: legacy.frequency,
      summary: legacy.summary,
      summary_totals: legacy.summary_totals,
      hardware_index: legacy.hardware_index,
      stats: {},
      top_contributors: [],
      hourly_distribution: [],
      distribution: [],
      bucket_table: [],
      interval_minutes: legacy.interval_minutes,
    };
  }

  estimateHours(start, end) {
    if (!start || !end) return 24;
    const startDate = new Date(start);
    const endDate = new Date(end);
    const diff = Math.max(1, (endDate - startDate) / 36e5);
    return Math.ceil(diff);
  }
}
window.analysis = new AnalysisController();
