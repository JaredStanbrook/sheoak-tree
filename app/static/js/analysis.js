import { socket, Utils, CONFIG } from "./core.js";

class AnalysisController {
  constructor() {
    this.chart = null;
    this.activityLog = [];
    this.elements = {
      ctx: document.getElementById("frequencyChart"),
      info: document.getElementById("chartInfo"),
      timeRange: document.getElementById("timeRange"),
      intervalRange: document.getElementById("intervalRange"),
      logList: document.getElementById("activity-list"),
    };

    // Event Listeners
    if (this.elements.timeRange)
      this.elements.timeRange.addEventListener("change", () => this.requestData());
    if (this.elements.intervalRange)
      this.elements.intervalRange.addEventListener("change", () => this.requestData());

    // Socket Events
    socket.on("frequency_data", (data) => {
      if (data.frequency) this.updateChart(data.frequency);
    });

    socket.on("activity_data", (data) => {
      const list = data.activity || data;
      this.setHistoricalLog(list);
    });

    socket.on("sensor_event", (data) => {
      // Live update the log if new event comes in while viewing
      this.addLogEntry(data);
    });

    // Initialize
    this.initChart();
    this.requestData();
    socket.emit("request_activity_data", { hours: 24 });
  }

  // --- CHART LOGIC ---
  initChart() {
    if (typeof Chart === "undefined") return;

    Chart.defaults.color = "#94a3b8";
    Chart.defaults.borderColor = "rgba(255, 255, 255, 0.08)";

    this.chart = new Chart(this.elements.ctx.getContext("2d"), {
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", axis: "x", intersect: false },
        scales: {
          x: { type: "time", time: { unit: "hour", displayFormats: { hour: "HH:mm" } } },
          y: {
            beginAtZero: true,
            title: { display: true, text: "Motion Intensity" },
            stack: "motionStack",
            weight: 2,
          },
          y1: { display: false, position: "right", min: 0, max: 1, weight: 0, offset: true }, // Door lane
        },
        plugins: {
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (ctx.raw.x && Array.isArray(ctx.raw.x)) return "Door Open";
                return `Events: ${ctx.raw}`;
              },
            },
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
    const palette = ["#10b981", "#3b82f6", "#ec4899", "#8b5cf6"];
    let colorIdx = 0;
    const datasets = [];

    Object.keys(sensors).forEach((label) => {
      const rawData = sensors[label];
      const isDoor =
        Array.isArray(rawData) && rawData.length > 0 && rawData[0].hasOwnProperty("state");

      if (isDoor) {
        // Process Door Blocks (Same logic as original app.js)
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
            backgroundColor: "rgba(245, 158, 11, 0.5)",
            borderColor: "#f59e0b",
            borderWidth: 2,
            barThickness: 15,
            indexAxis: "y", // Horizontal bars on time axis
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
          backgroundColor: color + "15",
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
      this.elements.info.innerHTML = `Grouping: <strong>${interval_minutes}m</strong>`;
  }

  // --- LOG LOGIC ---
  setHistoricalLog(data) {
    this.activityLog = [];
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
            <div class="log-entry ${type.includes("door") ? "door" : "motion"}">
                <div class="log-info">
                    <strong>${sensor}</strong>
                    <span>${event}</span>
                </div>
                <div style="text-align:right">
                    <div class="timestamp">${Utils.formatDate(data.timestamp).split(", ")[1]}</div> 
                    <div style="font-size:0.7rem; opacity:0.5">${Utils.timeAgo(
                      data.timestamp
                    )}</div>
                </div>
            </div>`;

    this.elements.logList.insertAdjacentHTML("afterbegin", entryHtml);

    // Trim log
    while (this.elements.logList.children.length > 50) {
      this.elements.logList.removeChild(this.elements.logList.lastChild);
    }
  }
}

window.analysis = new AnalysisController();
