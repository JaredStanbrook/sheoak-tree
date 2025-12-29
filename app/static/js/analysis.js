/**
 * static/js/analysis.js
 */
import { socket, Utils } from "./core.js";

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

    if (this.elements.timeRange)
      this.elements.timeRange.addEventListener("change", () => this.requestData());
    if (this.elements.intervalRange)
      this.elements.intervalRange.addEventListener("change", () => this.requestData());

    socket.on("frequency_data", (data) => {
      if (data.frequency) this.updateChart(data.frequency);
    });
    socket.on("activity_data", (data) => {
      this.setHistoricalLog(data.activity || data);
    });
    socket.on("sensor_event", (data) => {
      this.addLogEntry(data);
    });

    this.initChart();
    this.requestData();
    socket.emit("request_activity_data", { hours: 24 });
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

  requestData() {
    const hours = parseInt(this.elements.timeRange.value);
    const interval = parseInt(this.elements.intervalRange.value);
    socket.emit("request_frequency_data", { hours, interval });
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
        // Door logic remains same, just colors updated
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
    this.activityLog = [];
    if (this.elements.logList) this.elements.logList.innerHTML = "";
    [...data].reverse().forEach((item) => {
      if (item.value === 1 || item.state === 1 || item.type === "relay") this.addLogEntry(item);
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
