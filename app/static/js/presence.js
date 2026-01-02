import { Utils, socket } from "./core.js";

class PresenceController {
  constructor() {
    this.elements = {
      tableBody: document.getElementById("device-list-body"),
      modal: document.getElementById("editDeviceModal"),
      inputs: {
        id: document.getElementById("edit-device-id"),
        name: document.getElementById("edit-device-name"),
        owner: document.getElementById("edit-device-owner"),
      },
    };

    // Listen for updates
    socket.on("presence_update", () => this.loadDevices());

    // Initial Load
    this.loadDevices();
  }

  async loadDevices() {
    if (!this.elements.tableBody) return;
    this.elements.tableBody.innerHTML =
      '<tr><td colspan="6" class="text-center">Loading...</td></tr>';

    try {
      const data = await Utils.fetchJson("/api/presence/devices");
      this.elements.tableBody.innerHTML = "";

      if (data.success) {
        data.devices.forEach((device) => {
          const tr = document.createElement("tr");
          const lastSeen = new Date(device.last_seen).toLocaleString("en-AU");
          const isRecentlyHome = Date.now() - new Date(device.last_seen).getTime() < 60000;
          const statusClass = isRecentlyHome ? "connected" : "offline";

          const privacyIcon = device.is_randomized_mac
            ? '<span title="Private Wi-Fi Address" style="cursor:help">🛡️</span>'
            : "";

          const safeName = Utils.escape(device.name);
          const safeOwner = Utils.escape(device.owner || "");

          tr.innerHTML = `
                        <td><div class="status-dot ${statusClass}"></div></td>
                        <td>
                            <div style="font-weight: 600; color: var(--color-text);">${
                              device.name
                            }</div>
                            <div style="font-size: 0.8rem; color: var(--color-text-muted);">${
                              safeOwner || "Unassigned"
                            }</div>
                        </td>
                        <td>
                            ${
                              device.vendor
                                ? `<span class="badge-gray">${device.vendor}</span>`
                                : ""
                            }
                            <div class="mono" style="font-size: 0.75rem; margin-top:4px; opacity:0.7;">${
                              device.last_ip || "No IP"
                            }</div>
                        </td>
                        <td>
                            ${
                              device.hostname
                                ? `<div style="color:var(--color-primary); font-size:0.85rem;">${Utils.escape(
                                    device.hostname
                                  )}</div>`
                                : '<span style="opacity:0.3">-</span>'
                            }
                            <div class="mono" style="font-size: 0.75rem; opacity: 0.6;">${
                              device.mac_address
                            } ${privacyIcon}</div>
                        </td>
                        <td style="font-size: 0.85rem; color: var(--color-text-muted);">${lastSeen}</td>
                        <td>
                            <button class="btn btn-small" 
                                onclick="window.presence.openEditModal(${
                                  device.id
                                }, '${safeName}', '${safeOwner}', ${device.track_presence})">
                                Edit
                            </button>
                        </td>
                    `;
          this.elements.tableBody.appendChild(tr);
        });
      }
    } catch (e) {
      this.elements.tableBody.innerHTML = `<tr><td colspan="6" class="text-warning">Error: ${e.message}</td></tr>`;
    }
  }

  openEditModal(id, name, owner, track_presence) {
    this.elements.inputs.id.value = id;
    this.elements.inputs.name.value = name;
    this.elements.inputs.owner.value = owner;
    document.getElementById("edit-device-track").checked = track_presence === true;
    this.elements.modal.classList.add("active");
  }

  async submitUpdate() {
    const id = this.elements.inputs.id.value;
    const name = this.elements.inputs.name.value;
    const owner = this.elements.inputs.owner.value;
    const track_presence = document.getElementById("edit-device-track").checked;
    const btn = document.querySelector("#editDeviceModal .btn-primary");

    btn.textContent = "Saving...";
    try {
      const res = await Utils.fetchJson(`/api/presence/devices/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, owner, track_presence }),
      });
      if (res.success) {
        this.elements.modal.classList.remove("active");
        this.loadDevices();
      } else {
        alert("Error: " + res.error);
      }
    } catch (e) {
      alert("Failed: " + e);
    } finally {
      btn.textContent = "Save";
    }
  }

  async deleteDevice() {
    if (!confirm("Stop monitoring this device?")) return;
    const id = this.elements.inputs.id.value;
    try {
      const res = await Utils.fetchJson(`/api/presence/devices/${id}`, { method: "DELETE" });
      if (res.success) {
        this.elements.modal.classList.remove("active");
        this.loadDevices();
      }
    } catch (e) {
      alert("Delete failed");
    }
  }
}

// Initialize
window.presence = new PresenceController();
