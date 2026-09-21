const API_BASE = "";

// STATIC_MODE is true when this page is served from a static host (e.g.
// GitHub Pages) with no FastAPI backend behind it -- detected once at
// startup by probing /api/days. In that mode, reads come from pre-published
// JSON/media files instead (see scripts/build_static_site.py), and every
// write action (publish toggle, metadata edit, regenerate) is a no-op with
// an explanatory toast, since there's nothing to write to.
let STATIC_MODE = false;

function authHeaders() {
  const token = localStorage.getItem("dashboardToken");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiGet(path) {
  const resp = await fetch(API_BASE + path, { headers: authHeaders() });
  if (!resp.ok) throw new Error(`GET ${path} failed: ${resp.status}`);
  return resp.json();
}

async function apiPost(path, body) {
  if (STATIC_MODE) {
    showToast("Static site -- эдгээр үйлдэл зөвхөн local dashboard дээр ажиллана");
    throw new Error("static mode: writes disabled");
  }
  const resp = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body || {}),
  });
  if (!resp.ok) throw new Error(`POST ${path} failed: ${resp.status}`);
  return resp.json();
}

async function listDays() {
  if (STATIC_MODE) return fetch("data/days.json").then((r) => r.json());
  return apiGet("/api/days");
}

async function listArtDays() {
  if (STATIC_MODE) return fetch("data/art_days.json").then((r) => (r.ok ? r.json() : []));
  return apiGet("/api/art/days");
}

async function getArtDay(dateStr) {
  if (STATIC_MODE) return fetch(`data/${dateStr}/art/items.json`).then((r) => {
    if (!r.ok) throw new Error("not found");
    return r.json();
  });
  return apiGet(`/api/art/days/${dateStr}`);
}

async function getPackage(dateStr) {
  if (STATIC_MODE) return fetch(`data/${dateStr}/package.json`).then((r) => {
    if (!r.ok) throw new Error("not found");
    return r.json();
  });
  return apiGet(`/api/days/${dateStr}/package`);
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 1800);
}

function copyText(text, btnEl) {
  navigator.clipboard
    .writeText(text)
    .then(() => showToast("Copied"))
    .catch(() => showToast("Copy failed"));
}

function fileUrl(dateStr, relPath) {
  const clean = relPath.replace(/\\/g, "/");
  return STATIC_MODE ? `data/${dateStr}/${clean}` : `${API_BASE}/files/${dateStr}/${clean}`;
}

const REGEN_STAGES = [
  { id: "object", label: "Pick new object" },
  { id: "script", label: "Rewrite script" },
  { id: "assets", label: "New images" },
  { id: "render", label: "Re-render video" },
  { id: "thumbnails", label: "Re-render thumbnail" },
];

let currentDate = null;
let currentPackage = null;

async function loadDay(dateStr) {
  currentDate = dateStr;
  document.getElementById("dateBadge").textContent = dateStr;
  const app = document.getElementById("app");
  app.innerHTML = `<div class="empty-state">Loading ${dateStr}...</div>`;
  try {
    currentPackage = await getPackage(dateStr);
    renderToday();
  } catch (e) {
    app.innerHTML = `<div class="empty-state">No package for ${dateStr} yet.<br>Run the pipeline for this date first.</div>`;
  }
}

function renderToday() {
  const pkg = currentPackage;
  const d = currentDate;
  const app = document.getElementById("app");

  const thumbHtml = pkg.thumbnails
    .map(
      (t) => `
    <div class="thumb-item">
      <a href="${fileUrl(d, t.path)}" download><img src="${fileUrl(d, t.path)}" alt="${t.text}"></a>
      <div class="thumb-caption">${t.text}</div>
    </div>`
    )
    .join("");

  app.innerHTML = `
    <div class="eyebrow" style="padding:0 16px">Today's Object</div>
    <div class="object-title" style="padding:0 16px">${pkg.object.title || "Untitled"}</div>
    <div class="object-meta" style="padding:0 16px">${pkg.object.museum} &middot; object #${pkg.object.object_id ?? "?"}</div>
    ${pkg.object.pick_reason ? `<div class="reason-box">${pkg.object.pick_reason}</div>` : ""}

    <div class="card">
      <div class="card-row">
        <div class="card-label">Publish status</div>
      </div>
      <div class="publish-toggle">
        <button id="pubNotPosted" class="${pkg.publish_status === "not_posted" ? "active" : ""}">Not posted</button>
        <button id="pubPosted" class="${pkg.publish_status === "posted" ? "active" : ""}">Posted</button>
      </div>
    </div>

    <div class="section-label">Video Package</div>
    <div class="card">
      <video controls src="${fileUrl(d, pkg.video.long)}"></video>
      <div class="card-row" style="margin-top:10px">
        <div class="card-label">Long video</div>
        <a class="btn btn-primary" href="${fileUrl(d, pkg.video.long)}" download>Download</a>
      </div>
    </div>
    <div class="card">
      <video controls class="shorts-video" src="${fileUrl(d, pkg.video.shorts)}"></video>
      <div class="card-row" style="margin-top:10px">
        <div class="card-label">Shorts</div>
        <a class="btn btn-outline" href="${fileUrl(d, pkg.video.shorts)}" download>Download</a>
      </div>
    </div>

    <div class="section-label">Thumbnails</div>
    <div class="thumb-strip">
      ${thumbHtml}
      <div class="thumb-item">
        <a href="${fileUrl(d, pkg.shorts_cover)}" download><img src="${fileUrl(d, pkg.shorts_cover)}" alt="Shorts cover" style="height:142px;width:80px"></a>
        <div class="thumb-caption">Shorts cover</div>
      </div>
    </div>

    <div class="section-label">Metadata</div>
    <div class="card">
      <div class="card-label" style="margin-bottom:8px">Title options</div>
      ${pkg.metadata.title_options
        .map(
          (t, i) => `
        <div class="title-option">
          <div class="title-badge">${i + 1}</div>
          <div class="title-text">${t}</div>
          <button class="btn btn-ghost btn-small" data-copy="${encodeURIComponent(t)}">Copy</button>
        </div>`
        )
        .join("")}
    </div>

    <div class="card">
      <div class="card-row">
        <div class="card-label">Description</div>
        <button class="btn btn-ghost btn-small" id="copyDesc">Copy</button>
      </div>
      <textarea id="descriptionBox" rows="6">${pkg.metadata.description}</textarea>
    </div>

    <div class="card">
      <div class="card-row">
        <div class="card-label">Tags</div>
        <button class="btn btn-ghost btn-small" data-copy="${encodeURIComponent(pkg.metadata.tags)}">Copy</button>
      </div>
      <div class="field-box">${pkg.metadata.tags}</div>
    </div>

    <div class="card">
      <div class="card-row">
        <div class="card-label">Pinned comment</div>
        <button class="btn btn-ghost btn-small" id="copyPinned">Copy</button>
      </div>
      <textarea id="pinnedBox" rows="2">${pkg.metadata.pinned_comment}</textarea>
    </div>

    <div class="section-label">Script</div>
    <div class="card">
      <details open>
        <summary>Long script</summary>
        <div class="script-body">${pkg.scripts.long}</div>
      </details>
      <details>
        <summary>Shorts script</summary>
        <div class="script-body">${pkg.scripts.shorts}</div>
      </details>
    </div>

    <div class="section-label">Regenerate a stage</div>
    <div class="regen-grid">
      ${REGEN_STAGES.map((s) => `<button class="regen-btn" data-stage="${s.id}">${s.label}</button>`).join("")}
    </div>
    <div style="height:12px"></div>
  `;

  app.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", () => copyText(decodeURIComponent(btn.dataset.copy), btn));
  });
  document.getElementById("copyDesc").addEventListener("click", () => {
    copyText(document.getElementById("descriptionBox").value);
  });
  document.getElementById("copyPinned").addEventListener("click", () => {
    copyText(document.getElementById("pinnedBox").value);
  });

  document.getElementById("pubNotPosted").addEventListener("click", () => setPublishStatus("not_posted"));
  document.getElementById("pubPosted").addEventListener("click", () => setPublishStatus("posted"));

  ["descriptionBox", "pinnedBox"].forEach((id) => {
    const el = document.getElementById(id);
    if (STATIC_MODE) {
      el.readOnly = true;
    } else {
      el.addEventListener("blur", saveMetadata);
    }
  });

  app.querySelectorAll(".regen-btn").forEach((btn) => {
    btn.addEventListener("click", () => regenerateStage(btn.dataset.stage, btn));
  });

  if (STATIC_MODE) {
    app.querySelectorAll(".regen-btn, #pubNotPosted, #pubPosted").forEach((btn) => {
      btn.disabled = true;
    });
  }
}

async function setPublishStatus(status) {
  try {
    currentPackage = await apiPost(`/api/days/${currentDate}/publish-status`, { status });
    renderToday();
    showToast(status === "posted" ? "Marked as posted" : "Marked as not posted");
  } catch (e) {
    showToast("Failed to update status");
  }
}

async function saveMetadata() {
  try {
    const body = {
      description: document.getElementById("descriptionBox").value,
      pinned_comment: document.getElementById("pinnedBox").value,
    };
    currentPackage = await apiPost(`/api/days/${currentDate}/metadata`, body);
    showToast("Saved");
  } catch (e) {
    showToast("Save failed");
  }
}

async function regenerateStage(stage, btnEl) {
  const original = btnEl.textContent;
  btnEl.disabled = true;
  btnEl.textContent = "Working...";
  try {
    currentPackage = await apiPost(`/api/days/${currentDate}/regenerate`, { stage });
    renderToday();
    showToast("Regenerated");
  } catch (e) {
    showToast("Regenerate failed");
    btnEl.disabled = false;
    btnEl.textContent = original;
  }
}

async function loadHistory() {
  const app = document.getElementById("app");
  app.innerHTML = `<div class="empty-state">Loading history...</div>`;
  try {
    const days = await listDays();
    if (!days.length) {
      app.innerHTML = `<div class="empty-state">No packages yet.</div>`;
      return;
    }
    app.innerHTML =
      `<div class="section-label">History</div>` +
      days.map((d) => `<div class="history-item" data-date="${d}">${d}</div>`).join("");
    app.querySelectorAll(".history-item").forEach((el) => {
      el.addEventListener("click", () => {
        setActiveNav("today");
        loadDay(el.dataset.date);
      });
    });
  } catch (e) {
    app.innerHTML = `<div class="empty-state">Could not load history.</div>`;
  }
}

let currentArtDate = null;
let currentArtItems = null;

async function loadArt(dateStr) {
  currentArtDate = dateStr;
  document.getElementById("dateBadge").textContent = dateStr;
  const app = document.getElementById("app");
  app.innerHTML = `<div class="empty-state">Loading ${dateStr}...</div>`;
  try {
    currentArtItems = await getArtDay(dateStr);
    renderArt();
  } catch (e) {
    app.innerHTML = `<div class="empty-state">No art pieces for ${dateStr} yet.</div>`;
  }
}

async function loadArtDefault() {
  const app = document.getElementById("app");
  app.innerHTML = `<div class="empty-state">Loading...</div>`;
  try {
    const days = await listArtDays();
    if (!days.length) {
      app.innerHTML = `<div class="empty-state">No art pieces yet.</div>`;
      return;
    }
    loadArt(days[0]);
  } catch (e) {
    app.innerHTML = `<div class="empty-state">Could not load art pieces.</div>`;
  }
}

function renderArt() {
  const d = currentArtDate;
  const app = document.getElementById("app");

  app.innerHTML =
    `<div class="eyebrow" style="padding:0 16px">Art Explainer -- ${d}</div>` +
    currentArtItems
      .map(
        (pkg) => `
    <div class="section-label">${pkg.object.title || "Untitled"}${pkg.object.artist ? " &mdash; " + pkg.object.artist : ""}</div>
    <div class="card">
      <video controls class="shorts-video" src="${fileUrl(d, pkg.video)}"></video>
      <div class="card-row" style="margin-top:10px">
        <div class="card-label">Video</div>
        <a class="btn btn-primary" href="${fileUrl(d, pkg.video)}" download>Download</a>
      </div>
    </div>
    <div class="card">
      <div class="card-row"><div class="card-label">Publish status</div></div>
      <div class="publish-toggle">
        <button class="art-pub ${pkg.publish_status === "not_posted" ? "active" : ""}" data-idx="${pkg.index}" data-status="not_posted">Not posted</button>
        <button class="art-pub ${pkg.publish_status === "posted" ? "active" : ""}" data-idx="${pkg.index}" data-status="posted">Posted</button>
      </div>
    </div>
    <div class="card">
      <div class="card-label" style="margin-bottom:8px">Title options</div>
      ${pkg.metadata.title_options
        .map(
          (t, i) => `
        <div class="title-option">
          <div class="title-badge">${i + 1}</div>
          <div class="title-text">${t}</div>
          <button class="btn btn-ghost btn-small" data-copy="${encodeURIComponent(t)}">Copy</button>
        </div>`
        )
        .join("")}
    </div>
    <div class="card">
      <div class="card-row">
        <div class="card-label">Description</div>
        <button class="btn btn-ghost btn-small" data-copy="${encodeURIComponent(pkg.metadata.description)}">Copy</button>
      </div>
      <div class="field-box">${pkg.metadata.description}</div>
    </div>
    <div class="card">
      <div class="card-row">
        <div class="card-label">Tags</div>
        <button class="btn btn-ghost btn-small" data-copy="${encodeURIComponent(pkg.metadata.tags)}">Copy</button>
      </div>
      <div class="field-box">${pkg.metadata.tags}</div>
    </div>
    <div class="card">
      <div class="card-row">
        <div class="card-label">Pinned comment</div>
        <button class="btn btn-ghost btn-small" data-copy="${encodeURIComponent(pkg.metadata.pinned_comment)}">Copy</button>
      </div>
      <div class="field-box">${pkg.metadata.pinned_comment}</div>
    </div>
    <div class="card">
      <details>
        <summary>Script</summary>
        <div class="script-body">${pkg.script}</div>
      </details>
    </div>
    <div style="height:12px"></div>
  `
      )
      .join("");

  app.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", () => copyText(decodeURIComponent(btn.dataset.copy), btn));
  });
  app.querySelectorAll(".art-pub").forEach((btn) => {
    btn.addEventListener("click", () => setArtPublishStatus(parseInt(btn.dataset.idx, 10), btn.dataset.status));
  });
  if (STATIC_MODE) {
    app.querySelectorAll(".art-pub").forEach((btn) => {
      btn.disabled = true;
    });
  }
}

async function setArtPublishStatus(index, status) {
  try {
    await apiPost(`/api/art/days/${currentArtDate}/${index}/publish-status`, { status });
    currentArtItems = await getArtDay(currentArtDate);
    renderArt();
    showToast(status === "posted" ? "Marked as posted" : "Marked as not posted");
  } catch (e) {
    showToast("Failed to update status");
  }
}

function setActiveNav(which) {
  document.getElementById("navToday").classList.toggle("active", which === "today");
  document.getElementById("navArt").classList.toggle("active", which === "art");
  document.getElementById("navHistory").classList.toggle("active", which === "history");
}

document.getElementById("navToday").addEventListener("click", () => {
  setActiveNav("today");
  loadDay(currentDate || todayStr());
});
document.getElementById("navArt").addEventListener("click", () => {
  setActiveNav("art");
  loadArtDefault();
});
document.getElementById("navHistory").addEventListener("click", () => {
  setActiveNav("history");
  loadHistory();
});
document.getElementById("dateBadge").addEventListener("click", () => {
  setActiveNav("history");
  loadHistory();
});

function todayStr() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

(async function init() {
  try {
    const days = await apiGet("/api/days");
    STATIC_MODE = false;
    loadDay(days[0] || todayStr());
  } catch (e) {
    STATIC_MODE = true;
    try {
      const days = await listDays();
      loadDay(days[0] || todayStr());
    } catch (e2) {
      loadDay(todayStr());
    }
  }
})();
