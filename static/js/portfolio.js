/*
 * Portfolio sync UI for the Storage Vault:
 *   🌐 Publish to Portfolio — settings, diff preview since the last publish, commit via GitHub API
 *   in Import LinkedIn      — upload LinkedIn's data export zip, review, accept items one by one
 * Self-contained: adds its own buttons and modals using the app's existing styles.
 */
(function () {
  "use strict";

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(url, options = {}) {
    const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
    return body;
  }

  function makeModal(id, title, maxWidth) {
    const el = document.createElement("div");
    el.id = id;
    el.className = "modal-backdrop";
    el.innerHTML = `
      <div class="modal-card" style="max-width:${maxWidth}px; width:100%;">
        <div class="modal-header">
          <h3 style="font-size:15px;">${title}</h3>
          <button class="pf-close btn btn-secondary btn-sm" aria-label="Close">&times;</button>
        </div>
        <div class="modal-body" style="display:flex; flex-direction:column; gap:14px; max-height:70vh; overflow:auto;"></div>
        <div class="modal-footer"></div>
      </div>`;
    document.body.appendChild(el);
    const close = () => el.classList.remove("active", "open");
    el.addEventListener("click", (e) => { if (e.target === el || e.target.closest(".pf-close")) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
    return {
      el,
      body: el.querySelector(".modal-body"),
      footer: el.querySelector(".modal-footer"),
      open: () => el.classList.add("active", "open"),
      close,
    };
  }

  const box = (color, inner) =>
    `<div style="background:rgba(${color},0.08); border:1px solid rgba(${color},0.3); border-radius:8px; padding:12px;">${inner}</div>`;
  const note = (text) => `<p style="font-size:11px; color:var(--text-muted); line-height:1.5; margin:0;">${text}</p>`;
  const SECTION_LABEL = {
    projects: "Projects", experiences: "Experience", education: "Education", skills: "Skills",
    patents_certifications: "Certifications", pors_achievements: "PORs", awards_medals: "Awards",
    testimonials: "Recommendations", coursework: "Coursework", personal_info: "Personal info",
  };

  // ------------------------------------------------------------------ Publish
  const publish = makeModal("modal-portfolio-publish", "🌐 Publish to Portfolio", 640);

  async function renderPublish() {
    publish.body.innerHTML = note("Loading…");
    publish.footer.innerHTML = "";
    let settings, preview;
    try {
      [settings, preview] = await Promise.all([api("/api/portfolio/settings"), api("/api/portfolio/preview")]);
    } catch (e) {
      publish.body.innerHTML = note(`⚠ ${esc(e.message)}`);
      return;
    }
    const d = preview.diff;
    const list = (items, color, sign) =>
      items.map((c) => `<li style="font-size:12px; color:${color};">${sign} ${esc(c.title)} <span style="color:var(--text-muted);">· ${esc(SECTION_LABEL[c.section] || c.section)}</span></li>`).join("");
    const changes = d.added.length + d.updated.length + d.removed.length;

    publish.body.innerHTML = `
      ${box("99,102,241", `
        <h4 style="font-size:13px; font-weight:700; color:#818cf8; margin:0 0 8px;">Portfolio repository</h4>
        <div style="display:grid; grid-template-columns: 1fr 120px; gap:8px;">
          <input id="pf-repo" class="input-box" placeholder="owner/portfolio" value="${esc(settings.repo)}">
          <input id="pf-branch" class="input-box" placeholder="main" value="${esc(settings.branch)}">
        </div>
        <input id="pf-token" type="password" class="input-box" style="margin-top:8px;" autocomplete="off"
          placeholder="${settings.token_set ? "•••••••• token saved (leave blank to keep)" : "Fine-grained GitHub token"}">
        ${note('Create a <b>fine-grained</b> token with access to the portfolio repo only and <b>Contents: Read and write</b>. It is stored in data/settings.json (git-ignored) and never shown again.')}
        <div style="display:flex; gap:16px; margin-top:8px; font-size:12px;">
          <label><input type="checkbox" id="pf-email" ${settings.show_email ? "checked" : ""}> Publish email</label>
          <label><input type="checkbox" id="pf-gpa" ${settings.show_gpa ? "checked" : ""}> Publish GPA</label>
        </div>
        <button id="pf-save" class="btn btn-secondary btn-sm" style="margin-top:8px;">Save settings</button>
      `)}
      ${box("16,185,129", `
        <h4 style="font-size:13px; font-weight:700; color:#34d399; margin:0 0 6px;">What will be published</h4>
        <p style="font-size:12px; margin:0 0 6px;">${Object.entries(preview.counts).map(([k, n]) => `${n} ${esc(SECTION_LABEL[k] || k)}`).join(" · ")}</p>
        ${note(`Phone, tracker, cover letters, settings and private items are never exported.
          ${preview.report.template_bullets_removed ? `<b>${preview.report.template_bullets_removed}</b> auto-generated bullets with invented metrics were left out.` : ""}
          ${preview.report.private_items_excluded ? `<b>${preview.report.private_items_excluded}</b> private items excluded.` : ""}`)}
      `)}
      ${box("245,158,11", `
        <h4 style="font-size:13px; font-weight:700; color:#fbbf24; margin:0 0 6px;">${preview.first_publish ? "First publish" : `Changes since last publish (${esc(new Date(settings.last_published_at).toLocaleString())})`}</h4>
        ${preview.first_publish ? note("Everything above will be sent.") : changes === 0 ? note("No changes since the last publish.") : `
          <ul style="margin:0; padding-left:4px; list-style:none; display:flex; flex-direction:column; gap:2px;">
            ${list(d.added, "#34d399", "+")}${list(d.updated, "#93c5fd", "~")}${list(d.removed, "#fb7185", "−")}
          </ul>`}
      `)}
      <div id="pf-result"></div>`;

    publish.footer.innerHTML = `
      <a href="/api/portfolio/export?download=1" download="vault.public.json" class="btn btn-secondary" style="text-decoration:none;">📥 Download export</a>
      <button class="pf-close btn btn-secondary">Close</button>
      <button id="pf-publish" class="btn btn-primary">🚀 Publish</button>`;

    const result = publish.body.querySelector("#pf-result");
    const show = (html) => (result.innerHTML = html);
    const saveSettings = () =>
      api("/api/portfolio/settings", {
        method: "POST",
        body: JSON.stringify({
          repo: publish.body.querySelector("#pf-repo").value,
          branch: publish.body.querySelector("#pf-branch").value,
          token: publish.body.querySelector("#pf-token").value || null,
          show_email: publish.body.querySelector("#pf-email").checked,
          show_gpa: publish.body.querySelector("#pf-gpa").checked,
        }),
      });

    publish.body.querySelector("#pf-save").addEventListener("click", async () => {
      try {
        await saveSettings();
        renderPublish();
      } catch (e) {
        show(note(`⚠ ${esc(e.message)}`));
      }
    });
    publish.footer.querySelector("#pf-publish").addEventListener("click", async (ev) => {
      const btn = ev.currentTarget;
      btn.disabled = true;
      btn.textContent = "Publishing…";
      try {
        await saveSettings();
        const r = await api("/api/portfolio/publish", { method: "POST" });
        show(box("16,185,129", `<p style="font-size:13px; margin:0;">✅ Published. The portfolio's sync will open a pull request shortly.${r.commit_url ? ` <a href="${esc(r.commit_url)}" target="_blank" rel="noreferrer" style="color:#34d399;">View commit</a>` : ""}</p>`));
      } catch (e) {
        show(box("244,63,94", `<p style="font-size:12px; margin:0;">⚠ ${esc(e.message)}</p>`));
      } finally {
        btn.disabled = false;
        btn.textContent = "🚀 Publish";
      }
    });
  }

  // ------------------------------------------------------------------ LinkedIn
  const linkedin = makeModal("modal-linkedin-import", "<span style='background:#0a66c2;color:#fff;border-radius:3px;padding:0 4px;font-weight:800;'>in</span> Import LinkedIn data export", 720);
  const STATUS_STYLE = { new: ["badge-green", "New"], changed: ["badge-gold", "Changed"], duplicate: ["badge-indigo", "Already in vault"] };

  function renderLinkedInStart(message) {
    linkedin.body.innerHTML = `
      ${box("10,102,194", `
        <h4 style="font-size:13px; font-weight:700; color:#60a5fa; margin:0 0 6px;">1. Get your data from LinkedIn</h4>
        ${note('LinkedIn → <b>Settings & Privacy</b> → <b>Data privacy</b> → <b>Get a copy of your data</b>. Pick Positions, Profile, Skills, Education, Certifications, Projects, Honors and Recommendations (or the full archive). LinkedIn emails a .zip, usually within minutes.')}
      `)}
      ${box("16,185,129", `
        <h4 style="font-size:13px; font-weight:700; color:#34d399; margin:0 0 6px;">2. Upload the zip</h4>
        <input type="file" id="li-file" accept=".zip,application/zip" style="font-size:12px;">
        ${note("Nothing is changed until you review and accept items.")}
      `)}
      ${message ? `<div>${message}</div>` : ""}`;
    linkedin.footer.innerHTML = `<button class="pf-close btn btn-secondary">Close</button>`;
    linkedin.body.querySelector("#li-file").addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async () => {
        linkedin.body.insertAdjacentHTML("beforeend", note("Reading export…"));
        try {
          const b64 = String(reader.result).split(",")[1];
          const preview = await api("/api/linkedin/import_export", { method: "POST", body: JSON.stringify({ filename: file.name, data_base64: b64 }) });
          renderLinkedInPreview(preview);
        } catch (err) {
          renderLinkedInStart(box("244,63,94", `<p style="font-size:12px; margin:0;">⚠ ${esc(err.message)}</p>`));
        }
      };
      reader.readAsDataURL(file);
    });
  }

  function renderLinkedInPreview(preview) {
    const groups = {};
    preview.items.forEach((it) => (groups[it.section] = groups[it.section] || []).push(it));
    const s = preview.summary;
    linkedin.body.innerHTML = `
      <p style="font-size:12px; margin:0;"><b>${s.new}</b> new · <b>${s.changed}</b> changed · <b>${s.duplicate}</b> already in your vault.
      New items are pre-selected; changed items only update dates/location/degree, never your bullets.</p>
      ${Object.entries(groups).map(([section, items]) => `
        <div>
          <h4 style="font-size:12px; font-weight:700; margin:6px 0; text-transform:uppercase; letter-spacing:.04em; color:var(--text-muted);">${esc(SECTION_LABEL[section] || section)}</h4>
          ${items.map((it) => {
            const [badge, label] = STATUS_STYLE[it.status];
            const changes = Object.entries(it.changes || {}).map(([f, [a, b]]) => `<div style="font-size:11px; color:var(--text-muted);">${esc(f)}: <s>${esc(a || "—")}</s> → ${esc(b)}</div>`).join("");
            return `
              <label style="display:flex; gap:10px; align-items:flex-start; padding:6px 8px; border-radius:6px; ${it.status === "duplicate" ? "opacity:.55;" : "cursor:pointer;"}">
                <input type="checkbox" class="li-item" value="${esc(it.key)}" ${it.status === "new" ? "checked" : ""} ${it.status === "duplicate" ? "disabled" : ""} style="margin-top:3px;">
                <span style="flex:1; min-width:0;">
                  <span style="font-size:13px;">${esc(it.label)}</span>
                  <span class="pill-badge ${badge}" style="margin-left:6px; font-size:10px;">${label}</span>
                  ${it.detail ? `<div style="font-size:11px; color:var(--text-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(it.detail)}</div>` : ""}
                  ${changes}
                </span>
              </label>`;
          }).join("")}
        </div>`).join("")}`;
    linkedin.footer.innerHTML = `
      <button id="li-back" class="btn btn-secondary">Upload another</button>
      <button id="li-apply" class="btn btn-primary">Import selected</button>`;
    linkedin.footer.querySelector("#li-back").addEventListener("click", () => renderLinkedInStart());
    linkedin.footer.querySelector("#li-apply").addEventListener("click", async (ev) => {
      const keys = [...linkedin.body.querySelectorAll(".li-item:checked")].map((c) => c.value);
      ev.currentTarget.disabled = true;
      try {
        const r = await api("/api/linkedin/apply", { method: "POST", body: JSON.stringify({ import_id: preview.import_id, keys }) });
        linkedin.body.innerHTML = box("16,185,129", `<p style="font-size:13px; margin:0;">✅ Imported: ${r.added} added, ${r.updated} updated. Accepted recommendations are approved for the portfolio's Testimonials.</p>`);
        linkedin.footer.innerHTML = `<button class="btn btn-primary" onclick="location.reload()">Reload vault</button>`;
      } catch (err) {
        linkedin.body.insertAdjacentHTML("afterbegin", box("244,63,94", `<p style="font-size:12px; margin:0;">⚠ ${esc(err.message)}</p>`));
        ev.currentTarget.disabled = false;
      }
    });
  }

  // ------------------------------------------------------------------ Buttons
  function addButtons() {
    const anchor = document.getElementById("btn-page-sync-vault");
    if (!anchor || document.getElementById("btn-portfolio-publish")) return;
    const pub = document.createElement("button");
    pub.id = "btn-portfolio-publish";
    pub.className = "btn btn-gold btn-sm";
    pub.textContent = "🌐 Publish to Portfolio";
    pub.addEventListener("click", () => { publish.open(); renderPublish(); });
    const li = document.createElement("button");
    li.id = "btn-linkedin-import";
    li.className = "btn btn-secondary btn-sm";
    li.innerHTML = "<span style='background:#0a66c2;color:#fff;border-radius:3px;padding:0 4px;font-weight:800;'>in</span> Import LinkedIn";
    li.addEventListener("click", () => { linkedin.open(); renderLinkedInStart(); });
    anchor.after(pub, li);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", addButtons);
  else addButtons();
})();
