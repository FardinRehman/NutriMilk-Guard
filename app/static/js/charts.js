/**
 * Nutri Milk Guard - Chart.js Sensor Visualization Controller.
 * Manages Temperature and pH time-series graphs, range switching,
 * tooltips, and real-time streaming data ingestion.
 */

class SensorChartsController {
  constructor() {
    this.tempChart = null;
    this.phChart = null;
    this.currentRange = "1h";

    this.tempCanvas = document.getElementById("temp-chart-canvas");
    this.phCanvas = document.getElementById("ph-chart-canvas");

    if (this.tempCanvas && this.phCanvas) {
      this.initCharts();
      this.initRangeButtons();
      this.loadHistory(this.currentRange);
      this.subscribeLiveUpdates();
    }
  }

  initCharts() {
    const commonOptions = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: {
            boxWidth: 12,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 12 }
          }
        },
        tooltip: {
          backgroundColor: "#0F172A",
          titleFont: { family: "'Plus Jakarta Sans', sans-serif", size: 12 },
          bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
          padding: 10,
          cornerRadius: 8
        }
      },
      scales: {
        x: {
          grid: { color: "#F1F5F9" },
          ticks: {
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 6
          }
        },
        y: {
          grid: { color: "#F1F5F9" },
          ticks: {
            font: { family: "'JetBrains Mono', monospace", size: 10 }
          }
        }
      }
    };

    // Temperature Chart
    this.tempChart = new Chart(this.tempCanvas.getContext("2d"), {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: "Temperature (°C)",
          data: [],
          borderColor: "#0284C7",
          backgroundColor: "rgba(2, 132, 199, 0.08)",
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 6
        }]
      },
      options: {
        ...commonOptions,
        scales: {
          ...commonOptions.scales,
          y: {
            ...commonOptions.scales.y,
            title: { display: true, text: "Degrees Celsius (°C)" }
          }
        }
      }
    });

    // pH Chart
    this.phChart = new Chart(this.phCanvas.getContext("2d"), {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: "pH Level",
          data: [],
          borderColor: "#16A34A",
          backgroundColor: "rgba(22, 163, 74, 0.08)",
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 6
        }]
      },
      options: {
        ...commonOptions,
        scales: {
          ...commonOptions.scales,
          y: {
            ...commonOptions.scales.y,
            min: 3.5,
            max: 8.5,
            title: { display: true, text: "pH Scale (0 - 14)" }
          }
        }
      }
    });
  }

  loadHistory(range) {
    fetch(`/api/sensors/history?range=${range}`)
      .then(res => res.json())
      .then(data => {
        const records = data.records || [];
        this.renderHistoryData(records);
      })
      .catch(err => console.error("Error loading history for charts:", err));
  }

  renderHistoryData(records) {
    const labels = [];
    const tempData = [];
    const phData = [];

    records.forEach(r => {
      // Short label from timestamp (HH:MM:SS)
      const parts = (r.timestamp || "").split(" ");
      const timePart = parts.length > 1 ? parts[1] : r.timestamp;
      labels.push(timePart);

      const sensors = r.sensors || {};
      tempData.push(sensors.temperature_C ? sensors.temperature_C.value : null);
      phData.push(sensors.pH ? sensors.pH.value : null);
    });

    if (this.tempChart) {
      this.tempChart.data.labels = labels;
      this.tempChart.data.datasets[0].data = tempData;
      this.tempChart.update();
    }

    if (this.phChart) {
      this.phChart.data.labels = labels;
      this.phChart.data.datasets[0].data = phData;
      this.phChart.update();
    }
  }

  subscribeLiveUpdates() {
    if (!window.liveStream) return;

    window.liveStream.onTelemetry((eventData) => {
      const telemetry = eventData.telemetry;
      if (!telemetry || !telemetry.sensors) return;

      const parts = (telemetry.timestamp || "").split(" ");
      const timeLabel = parts.length > 1 ? parts[1] : "Now";

      const tempVal = telemetry.sensors.temperature_C ? telemetry.sensors.temperature_C.value : null;
      const phVal = telemetry.sensors.pH ? telemetry.sensors.pH.value : null;

      // Append to Temperature Chart
      if (this.tempChart && tempVal !== null) {
        this.tempChart.data.labels.push(timeLabel);
        this.tempChart.data.datasets[0].data.push(tempVal);
        if (this.tempChart.data.labels.length > 30) {
          this.tempChart.data.labels.shift();
          this.tempChart.data.datasets[0].data.shift();
        }
        this.tempChart.update("none");
      }

      // Append to pH Chart
      if (this.phChart && phVal !== null) {
        this.phChart.data.labels.push(timeLabel);
        this.phChart.data.datasets[0].data.push(phVal);
        if (this.phChart.data.labels.length > 30) {
          this.phChart.data.labels.shift();
          this.phChart.data.datasets[0].data.shift();
        }
        this.phChart.update("none");
      }
    });
  }

  initRangeButtons() {
    const buttons = document.querySelectorAll(".range-btn");
    buttons.forEach(btn => {
      btn.addEventListener("click", (e) => {
        buttons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.currentRange = btn.dataset.range;
        this.loadHistory(this.currentRange);
      });
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.sensorCharts = new SensorChartsController();
});
