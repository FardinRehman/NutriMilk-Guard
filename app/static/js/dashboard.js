/**
 * Nutri Milk Guard - Live Dashboard Controller.
 * Subscribes to SSE telemetry updates, alters sensor cards, sparklines,
 * status pills, and system health counters dynamically without page reload.
 */

document.addEventListener("DOMContentLoaded", () => {
  if (!window.liveStream) return;

  const overallBanner = document.getElementById("overall-banner");
  const overallStatusTitle = document.getElementById("overall-status-title");
  const overallSummary = document.getElementById("overall-summary");
  const overallDisclaimer = document.getElementById("overall-disclaimer");
  const reportingCountEl = document.getElementById("stat-reporting-count");
  const alertCountNav = document.getElementById("nav-alert-count");

  // Mobile menu toggle
  const mobileToggle = document.getElementById("mobile-menu-toggle");
  const sidebar = document.querySelector(".sidebar");
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
  }

  // Subscribe to live telemetry stream
  window.liveStream.onTelemetry((eventData) => {
    const telemetry = eventData.telemetry;
    if (!telemetry) return;

    // 1. Update Overall Quality Banner
    if (overallBanner && overallStatusTitle && overallSummary) {
      overallStatusTitle.textContent = telemetry.overall_status;
      overallSummary.textContent = telemetry.overall_summary;
      if (overallDisclaimer && telemetry.overall_disclaimer) {
        overallDisclaimer.textContent = telemetry.overall_disclaimer;
      }

      // Update banner accent class
      overallBanner.className = `quality-banner ${getBannerClass(telemetry.overall_status)}`;
    }

    // 2. Update Reporting Counters
    if (reportingCountEl) {
      reportingCountEl.textContent = `${telemetry.sensors_reporting} / ${telemetry.sensors_configured}`;
    }

    // 3. Update Active Alerts Badge
    if (alertCountNav && eventData.active_alerts !== undefined) {
      if (eventData.active_alerts > 0) {
        alertCountNav.textContent = eventData.active_alerts;
        alertCountNav.style.display = "inline-block";
      } else {
        alertCountNav.style.display = "none";
      }
    }

    // 4. Update Individual Sensor Cards
    const sensors = telemetry.sensors || {};
    for (const [key, sensor] of Object.entries(sensors)) {
      updateSensorCard(key, sensor);
    }
  });

  function updateSensorCard(sensorKey, data) {
    const valEl = document.getElementById(`sensor-val-${sensorKey}`);
    const badgeEl = document.getElementById(`sensor-badge-${sensorKey}`);
    const deltaEl = document.getElementById(`sensor-delta-${sensorKey}`);
    const explEl = document.getElementById(`sensor-expl-${sensorKey}`);
    const threshEl = document.getElementById(`sensor-thresh-${sensorKey}`);

    if (valEl) {
      valEl.textContent = data.formatted_value;
    }

    if (badgeEl) {
      badgeEl.className = `badge ${data.badge_class || "badge-secondary"}`;
      badgeEl.textContent = data.status || "Unknown";
    }

    if (deltaEl && data.delta !== null && data.delta !== undefined) {
      const prefix = data.delta > 0 ? "+" : "";
      deltaEl.textContent = `${prefix}${data.delta} ${data.unit}`;
      deltaEl.className = `reading-delta ${data.delta_direction || "neutral"}`;
    }

    if (explEl && data.explanation) {
      explEl.textContent = data.explanation;
    }

    if (threshEl && data.threshold_applied) {
      threshEl.textContent = `Applied: ${data.threshold_applied}`;
    }
  }

  function getBannerClass(status) {
    if (!status) return "offline";
    const s = status.toLowerCase();
    if (s.includes("normal")) return "normal";
    if (s.includes("warning")) return "warning";
    if (s.includes("critical")) return "critical";
    return "offline";
  }
});
