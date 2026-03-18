// State
let currentSort = { by: "date_posted", order: "desc" };
let currentOffset = 0;
const PAGE_SIZE = 200;
let debounceTimer = null;

// Init
document.addEventListener("DOMContentLoaded", () => {
    loadJobs();
    loadStats();
    loadLastRefresh();
    // Auto-refresh stats every 60s
    setInterval(loadStats, 60000);
    setInterval(loadLastRefresh, 60000);
});

// Debounced search
function debouncedLoadJobs() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => loadJobs(), 300);
}

// Fetch and render jobs
async function loadJobs(append = false) {
    if (!append) currentOffset = 0;

    const params = new URLSearchParams({
        status: document.getElementById("filter-status").value,
        source: document.getElementById("filter-source").value,
        favorite: document.getElementById("filter-favorite").checked,
        search: document.getElementById("filter-search").value,
        sort_by: currentSort.by,
        sort_order: currentSort.order,
        limit: PAGE_SIZE,
        offset: currentOffset,
    });

    try {
        const res = await fetch(`/api/jobs?${params}`);
        const jobs = await res.json();
        renderJobs(jobs, append);
        document.getElementById("btn-load-more").style.display =
            jobs.length >= PAGE_SIZE ? "" : "none";
    } catch (err) {
        console.error("Failed to load jobs:", err);
        const tbody = document.getElementById("jobs-body");
        if (!append) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center py-5 text-danger">
                        <i class="bi bi-exclamation-triangle fs-1 d-block mb-2"></i>
                        Failed to load jobs. Please try refreshing the page.
                    </td>
                </tr>`;
        }
    }
}

function loadMore() {
    currentOffset += PAGE_SIZE;
    loadJobs(true);
}

function renderJobs(jobs, append) {
    const tbody = document.getElementById("jobs-body");
    if (!append) tbody.innerHTML = "";

    if (jobs.length === 0 && !append) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-5 text-muted">
                    <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                    No jobs found. Try adjusting your filters or click Refresh.
                </td>
            </tr>`;
        document.getElementById("results-count").textContent = "0 jobs";
        return;
    }

    for (const job of jobs) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>
                <button class="fav-btn" onclick="toggleFavorite(${job.id}, this)" title="Toggle favorite">
                    <i class="bi ${job.is_favorite ? 'bi-star-fill text-warning' : 'bi-star text-muted'}"></i>
                </button>
            </td>
            <td>
                <a class="job-title-link" onclick="showJobDetail(${job.id})" title="View details">
                    ${escapeHtml(job.title || "Untitled")}
                </a>
                ${job.location ? `<br><small class="text-muted">${escapeHtml(job.location)}</small>` : ""}
            </td>
            <td>${escapeHtml(job.company || "—")}</td>
            <td>${formatSalary(job)}</td>
            <td>${formatDate(job.date_posted)}</td>
            <td><span class="source-badge source-${job.source}">${escapeHtml(job.source || "—")}</span></td>
            <td>
                <select class="status-select status-${job.status}"
                        onchange="updateStatus(${job.id}, this.value, this)">
                    <option value="new" ${job.status === "new" ? "selected" : ""}>New</option>
                    <option value="seen" ${job.status === "seen" ? "selected" : ""}>Seen</option>
                    <option value="applied" ${job.status === "applied" ? "selected" : ""}>Applied</option>
                    <option value="hidden" ${job.status === "hidden" ? "selected" : ""}>Hidden</option>
                </select>
            </td>
            <td>
                <a href="${escapeHtml(job.job_url || "#")}" target="_blank"
                   class="btn btn-sm btn-outline-primary" title="Open application page">
                    <i class="bi bi-box-arrow-up-right"></i>
                </a>
            </td>
        `;
        tbody.appendChild(tr);
    }

    const total = append ? tbody.children.length : jobs.length;
    document.getElementById("results-count").textContent = `${total} job${total !== 1 ? "s" : ""} shown`;
}

// Job detail modal
let allJobs = [];
async function showJobDetail(jobId) {
    // Fetch the single job from the current table data
    try {
        const params = new URLSearchParams({
            status: document.getElementById("filter-status").value,
            source: document.getElementById("filter-source").value,
            favorite: document.getElementById("filter-favorite").checked,
            search: document.getElementById("filter-search").value,
            sort_by: currentSort.by,
            sort_order: currentSort.order,
            limit: 500,
            offset: 0,
        });
        const res = await fetch(`/api/jobs?${params}`);
        const jobs = await res.json();
        const job = jobs.find(j => j.id === jobId);
        if (!job) return;

        document.getElementById("modal-title").textContent = job.title || "Untitled";
        document.getElementById("modal-company").textContent = job.company || "Unknown";
        document.getElementById("modal-source").textContent = job.source || "";
        document.getElementById("modal-salary").textContent = formatSalary(job) || "No salary info";
        document.getElementById("modal-date").textContent = formatDate(job.date_posted);
        document.getElementById("modal-description").textContent = job.description || "No description available.";
        document.getElementById("modal-apply-link").href = job.job_url || "#";

        const modal = new bootstrap.Modal(document.getElementById("jobModal"));
        modal.show();

        // Mark as seen if currently new
        if (job.status === "new") {
            await fetch(`/api/jobs/${jobId}/status`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: "seen" }),
            });
        }
    } catch (err) {
        console.error("Failed to load job detail:", err);
    }
}

// Actions
async function updateStatus(jobId, status, selectEl) {
    try {
        await fetch(`/api/jobs/${jobId}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status }),
        });
        selectEl.className = `status-select status-${status}`;
        loadStats();
    } catch (err) {
        console.error("Failed to update status:", err);
    }
}

async function toggleFavorite(jobId, btn) {
    try {
        await fetch(`/api/jobs/${jobId}/favorite`, { method: "PATCH" });
        const icon = btn.querySelector("i");
        icon.classList.toggle("bi-star-fill");
        icon.classList.toggle("bi-star");
        icon.classList.toggle("text-warning");
        icon.classList.toggle("text-muted");
        loadStats();
    } catch (err) {
        console.error("Failed to toggle favorite:", err);
    }
}

async function manualRefresh() {
    const btn = document.getElementById("btn-refresh");
    btn.classList.add("btn-refresh-spinning");
    btn.disabled = true;

    try {
        await fetch("/api/refresh", { method: "POST" });
        // Wait a bit for scrape to start, then poll
        setTimeout(() => {
            loadJobs();
            loadStats();
            loadLastRefresh();
            btn.classList.remove("btn-refresh-spinning");
            btn.disabled = false;
        }, 5000);
    } catch (err) {
        console.error("Refresh failed:", err);
        btn.classList.remove("btn-refresh-spinning");
        btn.disabled = false;
    }
}

// Sorting
function toggleSort(field) {
    if (currentSort.by === field) {
        currentSort.order = currentSort.order === "desc" ? "asc" : "desc";
    } else {
        currentSort.by = field;
        currentSort.order = "desc";
    }

    // Update sort icons
    document.querySelectorAll(".sortable").forEach(th => {
        const icon = th.querySelector(".sort-icon");
        const sortField = th.dataset.sort;
        if (sortField === currentSort.by) {
            icon.className = `bi sort-icon ${currentSort.order === "desc" ? "bi-chevron-down" : "bi-chevron-up"}`;
            icon.style.opacity = "1";
        } else {
            icon.className = "bi bi-chevron-expand sort-icon";
            icon.style.opacity = "0.5";
        }
    });

    loadJobs();
}

// Stats
async function loadStats() {
    try {
        const res = await fetch("/api/stats");
        const stats = await res.json();
        document.getElementById("stat-total").textContent = stats.total;
        document.getElementById("stat-new").textContent = stats.new;
        document.getElementById("stat-today").textContent = stats.new_today;
        document.getElementById("stat-applied").textContent = stats.applied;
        document.getElementById("stat-favorites").textContent = stats.favorites;
    } catch (err) {
        console.error("Failed to load stats:", err);
    }
}

async function loadLastRefresh() {
    try {
        const res = await fetch("/api/last-refresh");
        const data = await res.json();
        const el = document.getElementById("last-refresh");
        if (data.last_refresh) {
            const d = new Date(data.last_refresh);
            el.textContent = `Last refresh: ${d.toLocaleTimeString()}`;
        } else {
            el.textContent = "Last refresh: running...";
        }
    } catch (err) {
        console.error("Failed to load last refresh:", err);
    }
}

// Helpers
function formatSalary(job) {
    if (!job.salary_min && !job.salary_max) return "—";
    let s = "";
    if (job.salary_min) s += `$${Number(job.salary_min).toLocaleString()}`;
    if (job.salary_max) s += ` - $${Number(job.salary_max).toLocaleString()}`;
    if (job.salary_interval) s += ` / ${job.salary_interval}`;
    return s;
}

function formatDate(dateStr) {
    if (!dateStr || dateStr === "None" || dateStr === "NaT") return "—";
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const diffMs = now - d;
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 14) return `${diffDays}d ago`;
    return d.toLocaleDateString();
}

function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}
