import { Utils } from "./core.js";

class SequenceController {
  constructor() {
    this.currentPage = 1;
    this.currentSequenceId = null;
    this.elements = {
      list: document.getElementById("sequenceList"),
      modal: document.getElementById("sequenceModal"),
      detail: document.getElementById("sequenceDetail"),
      pagination: document.getElementById("pagination"),
      stats: {
        total: document.getElementById("totalSequences"),
        labeled: document.getElementById("labeledSequences"),
        unlabeled: document.getElementById("unlabeledSequences"),
      },
    };

    // Load initial data
    this.loadData();
  }

  async process(incremental) {
    const btn = incremental
      ? document.getElementById("incBtn")
      : document.getElementById("fullBtn");
    btn.disabled = true;
    btn.textContent = "Processing...";

    try {
      const res = await Utils.fetchJson("/api/sequences/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          window_size: parseInt(document.getElementById("windowSize").value),
          sequence_gap_threshold: parseInt(document.getElementById("gapThreshold").value),
          incremental,
        }),
      });
      if (res.success) {
        alert(res.message);
        this.loadData();
      }
    } catch (e) {
      alert(e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = incremental ? "Incremental Update" : "Rebuild All";
    }
  }

  async loadData() {
    // Load Stats
    try {
      const data = await Utils.fetchJson("/api/sequences/statistics");
      if (data.success) {
        this.elements.stats.total.textContent = data.statistics.total_sequences;
        this.elements.stats.labeled.textContent = data.statistics.labeled_sequences;
        this.elements.stats.unlabeled.textContent = data.statistics.unlabeled_sequences;
      }
    } catch (e) {}

    // Load List
    this.loadList(this.currentPage);
  }

  async loadList(page) {
    this.currentPage = page;
    this.elements.list.innerHTML =
      '<div class="loading-state"><div class="spinner"></div><p>Loading...</p></div>';

    try {
      const data = await Utils.fetchJson(`/api/sequences/list?page=${page}&per_page=15`);
      if (data.success) {
        this.renderList(data.sequences);
        this.updatePagination(data.pagination);
      }
    } catch (e) {
      this.elements.list.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
    }
  }

  renderList(sequences) {
    if (!sequences || sequences.length === 0) {
      this.elements.list.innerHTML = '<div class="empty-state"><p>No sequences found.</p></div>';
      return;
    }
    this.elements.list.innerHTML = sequences
      .map(
        (seq) => `
            <div class="sequence-item" onclick="window.ai.openModal(${seq.sequence_id})">
                <div class="sequence-header">
                    <span class="text-mono">ID: ${seq.sequence_id}</span>
                    <span class="sequence-label ${seq.label ? "labeled" : "unlabeled"}">${
          seq.label || "Unlabeled"
        }</span>
                </div>
                <div class="sequence-meta">
                    ${Utils.formatDate(seq.start_time)} • ${seq.duration_minutes.toFixed(1)} mins
                </div>
            </div>
        `
      )
      .join("");
  }

  updatePagination(pg) {
    const pag = this.elements.pagination;
    if (pg.total_pages <= 1) {
      pag.classList.add("is-hidden");
      pag.classList.remove("is-flex");
      return;
    }
    pag.classList.remove("is-hidden");
    pag.classList.add("is-flex");
    document.getElementById("pageInfo").textContent = `Page ${pg.page} of ${pg.total_pages}`;
    document.getElementById("prevBtn").disabled = !pg.has_prev;
    document.getElementById("nextBtn").disabled = !pg.has_next;
  }

  changePage(delta) {
    this.loadList(this.currentPage + delta);
  }

  async openModal(id) {
    this.currentSequenceId = id;
    this.elements.modal.classList.add("active");
    this.elements.detail.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
      const data = await Utils.fetchJson(`/api/sequences/${id}`);
      if (data.success) this.renderDetail(data.sequence);
    } catch (e) {
      this.elements.detail.innerHTML = "<p>Error loading detail</p>";
    }
  }

  renderDetail(seq) {
    const labels = [
      "Ignore",
      "Activity",
      "Bathroom",
      "Kitchen",
      "Sleeping",
      "Away",
      "Enter",
      "Exit",
    ];

    // Build detail HTML (simplified for brevity, keeps core functionality)
    this.elements.detail.innerHTML = `
            <h3>Sequence #${seq.sequence_id}</h3>
            <div class="sequence-stats-grid">
                <div><span>Duration</span><strong>${seq.duration_minutes.toFixed(1)}m</strong></div>
                <div><span>Events</span><strong>${seq.raw_events.length}</strong></div>
            </div>
            
            <div class="label-selector">
                ${labels
                  .map(
                    (lbl) => `
                    <button class="label-btn ${seq.label === lbl ? "selected" : ""}" 
                        onclick="window.ai.selectLabel(this, '${lbl}')">${lbl}</button>
                `
                  )
                  .join("")}
            </div>
            <button class="btn btn-primary full-width" onclick="window.ai.saveLabel()">Save Label</button>
            
            <div class="event-list-scroll" style="margin-top:15px;">
                ${seq.raw_events
                  .map(
                    (e) => `
                    <div class="event-item-small">
                        <span class="text-mono">${e.timestamp.split("T")[1].split(".")[0]}</span>
                        <strong>${e.hardware_name}</strong>: ${e.event}
                    </div>`
                  )
                  .join("")}
            </div>
        `;
  }

  selectLabel(btn, label) {
    document.querySelectorAll(".label-btn").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    btn.dataset.selectedLabel = label;
  }

  async saveLabel() {
    const btn = document.querySelector(".label-btn.selected");
    if (!btn) return;
    try {
      await Utils.fetchJson(`/api/sequences/${this.currentSequenceId}/label`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: btn.dataset.selectedLabel }),
      });
      this.elements.modal.classList.remove("active");
      this.loadList(this.currentPage);
      this.loadData(); // Refresh stats
    } catch (e) {
      alert("Failed to save");
    }
  }
}

window.ai = new SequenceController();
