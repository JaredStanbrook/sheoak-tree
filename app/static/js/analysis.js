/**
 * static/js/analysis.js
 */
import { Utils } from "./core.js";

class AnalysisController {
  constructor() {
    this.chart = null;
    this.elements = {
      ctx: document.getElementById("frequencyChart"),
      info: document.getElementById("chartInfo"),
      timeRange: document.getElementById("timeRange"),
      intervalRange: document.getElementById("intervalRange"),
      logList: document.getElementById("activity-list"),
    };

    // Bind UI controls to refresh data
    if (this.elements.timeRange)
      this.elements.timeRange.addEventListener("change", () => this.requestFrequencyData());
    if (this.elements.intervalRange)
      this.elements.intervalRange.addEventListener("change", () => this.requestFrequencyData());

    // Listen for Real-time SSE Events (dispatched by core.js)
    window.addEventListener("sensor_update", (e) => {
      // e.detail contains the raw sensor event data
      this.addLogEntry(e.detail);
    });

    // Initialize
    this.initChart();
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
        scales: {
          x: { type: "time", time: { unit: "hour", displayFormats: { hour: "HH:mm" } } },
          y: { beginAtZero: true, title: { display: false } },
          y1: { display: false, position: "right", min: 0, max: 1, offset: true },
        },
        plugins: {
          legend: { labels: { usePointStyle: true, boxWidth: 6 } },
          tooltip: {
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

  async requestFrequencyData() {
    const hours = parseInt(this.elements.timeRange.value);
    const interval = parseInt(this.elements.intervalRange.value);

    try {
      // Fetch directly from API instead of socket.emit
      const data = await Utils.fetchJson(`/api/frequency/${hours}/${interval}`);
      if (data.success && data.frequency) {
        this.updateChart(data.frequency);
      }
    } catch (e) {
      console.error("Failed to load frequency data:", e);
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
        this.elements.logList.innerHTML = `<div class="text-center text-danger" style="padding:20px">Failed to load history</div>`;
      }
    }
  }

  updateChart(data) {
    if (!this.chart) return;
    const { sensors, timestamps, interval_minutes } = data;
    // Updated Light Palette: Emerald, Blue, Amber, Violet
    const palette = ["#059669", "#2563eb", "#d97706", "#7c3aed"];
    let colorIdx = 0;
    const datasets = [];

    Object.keys(sensors).forEach((label) => {
      const rawData = sensors[label];
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
        });
      }
    });

    this.chart.data.labels = timestamps;
    this.chart.data.datasets = datasets;
    this.chart.update();
    if (this.elements.info)
      this.elements.info.innerHTML = `Grouping: <strong>${interval_minutes} min</strong> intervals`;
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
    const sensor = data.sensor_name || data.name;

    const entryHtml = `
            <div class="log-item type-${type.includes("door") ? "door" : "motion"}">
                <div class="log-content">
                    <strong>${sensor}</strong>
                    <span>${event}</span>
                </div>
                <div class="log-time">
                    <div>${Utils.formatDate(data.timestamp).split(", ")[1]}</div> 
                    <div style="opacity:0.6">${Utils.timeAgo(data.timestamp)}</div>
                </div>
            </div>`;

    this.elements.logList.insertAdjacentHTML("afterbegin", entryHtml);
    while (this.elements.logList.children.length > 50) {
      this.elements.logList.removeChild(this.elements.logList.lastChild);
    }
  }
}
window.analysis = new AnalysisController();
