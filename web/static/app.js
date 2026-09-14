const form = document.getElementById("scrape-form");
const statusEl = document.getElementById("status");
const runBtn = document.getElementById("run-btn");
const tbody = document.getElementById("results-body");
const meta = document.getElementById("result-meta");
const filter = document.getElementById("table-filter");
const drawer = document.getElementById("drawer");
const drawerTitle = document.getElementById("drawer-title");
const drawerFields = document.getElementById("drawer-fields");
const registryBody = document.getElementById("registry-body");
const dentalOnly = document.getElementById("dental-only");

let records = [];

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("is-active"));
    document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("is-active"));
    tab.classList.add("is-active");
    document.getElementById(`panel-${tab.dataset.tab}`).classList.add("is-active");
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  data.demo = Boolean(form.demo.checked);
  data.all_states = false;
  runBtn.disabled = true;
  statusEl.classList.remove("error");
  statusEl.textContent = data.demo
    ? "Parsing sample HTML…"
    : "Searching, downloading HTML, extracting fields…";
  try {
    const response = await fetch("/api/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Scrape failed");
    }
    records = payload.records || [];
    renderTable(records);
    const csv = payload.outputs && payload.outputs.csv ? ` CSV: ${payload.outputs.csv}` : "";
    const pages = payload.stats && payload.stats.pages_downloaded != null
      ? ` Downloaded ${payload.stats.pages_downloaded} HTML page(s).`
      : "";
    meta.textContent = `${payload.count} records from HTML.${pages}${csv}`;
    statusEl.textContent = "CSV written.";
    filter.disabled = records.length === 0;
  } catch (error) {
    statusEl.classList.add("error");
    statusEl.textContent = error.message;
  } finally {
    runBtn.disabled = false;
  }
});

filter.addEventListener("input", () => {
  const query = filter.value.trim().toLowerCase();
  const filtered = records.filter((row) => JSON.stringify(row).toLowerCase().includes(query));
  renderTable(filtered);
});

tbody.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-index]");
  if (!row) return;
  openDrawer(records[Number(row.dataset.index)]);
});

document.getElementById("drawer-close").addEventListener("click", () => {
  drawer.hidden = true;
});

dentalOnly.addEventListener("change", loadRegistries);
loadRegistries();

function renderTable(rows) {
  if (!rows.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No matching records.</td></tr>';
    return;
  }
  tbody.innerHTML = rows
    .map((row, index) => {
      const original = records.indexOf(row);
      return `<tr data-index="${original >= 0 ? original : index}">
        <td>${escapeHtml(row.name)}</td>
        <td>${escapeHtml(row.registration_number)}</td>
        <td>${escapeHtml(row.job_title)}</td>
        <td>${escapeHtml(row.city)}</td>
        <td>${escapeHtml(row.state)}</td>
        <td>${escapeHtml(row.phone)}</td>
        <td>${escapeHtml(row.source_registry)}</td>
      </tr>`;
    })
    .join("");
}

function openDrawer(row) {
  if (!row) return;
  drawer.hidden = false;
  drawerTitle.textContent = row.name || "Provider";
  drawerFields.innerHTML = Object.entries(row)
    .map(([key, value]) => {
      const display = value
        ? key.includes("url") || key === "website"
          ? `<a href="${escapeHtml(value)}" target="_blank" rel="noopener">${escapeHtml(value)}</a>`
          : escapeHtml(String(value))
        : "—";
      return `<div><dt>${escapeHtml(key)}</dt><dd>${display}</dd></div>`;
    })
    .join("");
}

async function loadRegistries() {
  const dental = dentalOnly.checked ? "1" : "0";
  const response = await fetch(`/api/registries?dental=${dental}`);
  const payload = await response.json();
  registryBody.innerHTML = (payload.registries || [])
    .map((item) => {
      const url = item.webpage || item.official_url
        ? `<a href="${escapeHtml(item.webpage || item.official_url)}" target="_blank" rel="noopener">Open</a>`
        : "—";
      return `<tr>
        <td>${escapeHtml(item.country)}</td>
        <td>${escapeHtml(item.registry)}</td>
        <td>${escapeHtml(item.profession || item.professions)}</td>
        <td>${escapeHtml(item.extraction_method || item.scrape_mode)}</td>
        <td>${url}</td>
      </tr>`;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
