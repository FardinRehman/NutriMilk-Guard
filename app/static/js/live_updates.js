/**
 * Nutri Milk Guard - Real-Time Server-Sent Events (SSE) Manager.
 * Connects to /api/stream, handles automatic reconnection, stale-data warnings,
 * updates the header connection status, and broadcasts telemetry to listeners.
 */

class LiveUpdateManager {
  constructor() {
    this.eventSource = null;
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 10000;
    this.listeners = [];
    this.lastUpdateTime = null;
    this.staleCheckInterval = null;
    this.staleTimeoutSeconds = 45;

    this.statusPill = document.getElementById("connection-status-pill");
    this.statusText = document.getElementById("connection-status-text");
    this.lastUpdateEl = document.getElementById("last-update-time");
    this.reconnectBtn = document.getElementById("reconnect-btn");
    this.liveClockEl = document.getElementById("live-clock");

    this.initClock();
    this.initReconnectButton();
    this.connect();
    this.startStaleChecker();
  }

  initClock() {
    if (!this.liveClockEl) return;
    const updateTime = () => {
      const now = new Date();
      this.liveClockEl.textContent = now.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
    };
    updateTime();
    setInterval(updateTime, 1000);
  }

  initReconnectButton() {
    if (!this.reconnectBtn) return;
    this.reconnectBtn.addEventListener("click", () => {
      this.setStatus("reconnecting", "Reconnecting...");
      fetch("/api/reconnect", { method: "POST" })
        .then(res => res.json())
        .then(() => {
          this.disconnect();
          this.connect();
        })
        .catch(err => {
          console.error("Manual reconnect error:", err);
          this.disconnect();
          this.connect();
        });
    });
  }

  connect() {
    if (this.eventSource) {
      this.eventSource.close();
    }

    this.setStatus("connecting", "Connecting...");

    try {
      this.eventSource = new EventSource("/api/stream");

      this.eventSource.addEventListener("telemetry", (event) => {
        try {
          const data = JSON.parse(event.data);
          this.reconnectAttempts = 0;
          this.lastUpdateTime = Date.now();

          const conn = data.connection || {};
          if (conn.is_stale) {
            this.setStatus("stale", "Stale Data (Sensor Idle)");
          } else if (conn.is_connected) {
            this.setStatus("connected", "Live Firebase Connected");
          } else {
            this.setStatus("error", "Firebase Disconnected");
          }

          if (this.lastUpdateEl && data.telemetry) {
            this.lastUpdateEl.textContent = data.telemetry.timestamp || "Just now";
          }

          // Broadcast to registered dashboard/chart listeners
          this.notifyListeners(data);
        } catch (err) {
          console.error("Error processing telemetry payload:", err);
        }
      });

      this.eventSource.addEventListener("ping", (event) => {
        this.reconnectAttempts = 0;
      });

      this.eventSource.onerror = (err) => {
        console.warn("SSE connection interrupted. Reconnecting...", err);
        this.setStatus("reconnecting", "Reconnecting...");
        this.eventSource.close();
        this.scheduleReconnect();
      };

    } catch (e) {
      console.error("EventSource initialization failed:", e);
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), this.maxReconnectDelay);
    setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  setStatus(type, text) {
    if (!this.statusPill || !this.statusText) return;
    this.statusPill.className = `status-pill ${type}`;
    this.statusText.textContent = text;
  }

  onTelemetry(callback) {
    this.listeners.push(callback);
  }

  notifyListeners(data) {
    this.listeners.forEach(cb => {
      try {
        cb(data);
      } catch (err) {
        console.error("Listener error:", err);
      }
    });
  }

  startStaleChecker() {
    this.staleCheckInterval = setInterval(() => {
      if (this.lastUpdateTime) {
        const secondsElapsed = (Date.now() - this.lastUpdateTime) / 1000;
        if (secondsElapsed > this.staleTimeoutSeconds) {
          this.setStatus("stale", `Stale Data (${Math.round(secondsElapsed)}s ago)`);
        }
      }
    }, 5000);
  }
}

// Global instance attached to window
window.liveStream = new LiveUpdateManager();
