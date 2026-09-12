let currentCategory = "quant";
let currentResumeData = null;
let currentHtml = "";
let currentTex = "";
let currentFontSize = "9.5pt";
let currentLineHeight = "1.15";
let zoomLevel = 1.0;

// Explicit lists of IDs / items currently active in the resume
let activeProjectIds = null;
let activeExperienceIds = null;
let activeSkills = null;
let projectTiers = {};
let experienceTiers = {};

// Drawer state: "projects" | "experiences" | "skills"
let activeDrawerType = "projects";

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  setupEventListeners();
  setupV2EventListeners();
  checkStatus();
  loadLLMSettingsStatus();
  switchAppView("hub");
  await loadResume(currentCategory);
}

async function checkStatus() {
  try {
    const res = await fetch("/api/settings/status");
    const data = await res.json();
    const dot = document.getElementById("gemini-status-dot");
    const text = document.getElementById("gemini-status-text");
    if (data.has_gemini_key) {
      dot.textContent = "🟢";
      text.textContent = "Gemini AI Active";
    } else {
      dot.textContent = "⚪";
      text.textContent = "API Key (Offline Mode)";
    }
  } catch (e) {
    console.error(e);
  }
}

async function loadResume(category, options = {}) {
  const company = options.company || document.getElementById("target-company")?.value || "";
  const role = options.role || document.getElementById("target-role")?.value || "";
  const jd = options.jd || document.getElementById("target-jd")?.value || "";
  const useGemini = options.useGemini || false;

  setGaugeStatus("loading");

  try {
    const payload = {
      category: category,
      company: company,
      role: role,
      custom_jd: jd,
      use_gemini: useGemini,
      project_tiers: projectTiers,
      experience_tiers: experienceTiers,
      active_project_ids: activeProjectIds,
      active_experience_ids: activeExperienceIds,
      active_skills: activeSkills,
      font_size: currentFontSize,
      line_height: currentLineHeight
    };

    const res = await fetch("/api/resume/tailor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.status === "success") {
      currentResumeData = data.data;
      currentHtml = data.html;
      currentTex = data.tex;

      if (data.category) {
        currentCategory = data.category;
      }

      // If Gemini think was run, sync all active items to Gemini's optimal selection
      if (useGemini) {
        if (data.data.projects) activeProjectIds = data.data.projects.map(p => p.id);
        if (data.data.experiences) activeExperienceIds = data.data.experiences.map(e => e.id);
        if (data.data.skills) activeSkills = data.data.skills.map(s => ({ category: s.category, entries: s.entries }));
      } else {
        // Sync active IDs with what was returned if first load or category switch
        if (activeProjectIds === null && data.data.projects) {
          activeProjectIds = data.data.projects.map(p => p.id);
        }
        if (activeExperienceIds === null && data.data.experiences) {
          activeExperienceIds = data.data.experiences.map(e => e.id);
        }
        if (activeSkills === null && data.data.skills) {
          activeSkills = data.data.skills.map(s => ({ category: s.category, entries: s.entries }));
        }
      }

      // Update AI reasoning box
      const reasonBox = document.getElementById("ai-reasoning-container");
      if (data.reasoning && reasonBox) {
        reasonBox.style.display = "block";
        reasonBox.innerHTML = `<b>🧠 Strategic AI Rationale:</b><br>${data.reasoning}`;
      } else if (reasonBox && useGemini) {
        reasonBox.style.display = "block";
        const roleLabel = role || company || currentCategory.toUpperCase();
        reasonBox.innerHTML = `<b>⚡ Role-Tailored:</b> Selected top high-impact projects, skills, and coursework aligned with <b>${roleLabel}</b>.`;
      } else if (reasonBox && !useGemini) {
        reasonBox.style.display = "none";
      }

      updatePreview(data.html);
      renderActiveItemsControls(data.data);
      updateATSScore();
    }
  } catch (err) {
    console.error("Failed to load resume:", err);
  }
}

function updatePreview(html) {
  const iframe = document.getElementById("resume-frame");
  const blob = new Blob([html], { type: "text/html" });
  iframe.src = URL.createObjectURL(blob);

  iframe.onload = () => {
    checkCreaseLineOverflow(iframe);
  };
}

function checkCreaseLineOverflow(iframe) {
  try {
    const doc = iframe.contentWindow.document;
    const body = doc.body;
    const html = doc.documentElement;
    const contentHeight = Math.max(body.scrollHeight, body.offsetHeight, html.clientHeight, html.scrollHeight);

    const a4PixelLimit = 1122; // 11.69 inches at 96 DPI
    const fillPercent = Math.round((contentHeight / a4PixelLimit) * 100);

    const gauge = document.getElementById("page-fit-gauge");
    if (!gauge) return;

    if (contentHeight <= a4PixelLimit + 15) {
      gauge.className = "pill-badge badge-green";
      gauge.innerHTML = `✓ 100% 1-Page Guaranteed (${fillPercent}% filled • Zero Spill)`;
    } else {
      gauge.className = "pill-badge badge-red";
      gauge.innerHTML = `⚠️ Overflows 1-Page Crease Line (${fillPercent}%) — Reduce Points or Font Size`;
    }
  } catch (e) {}
}

function setGaugeStatus(status) {
  const gauge = document.getElementById("page-fit-gauge");
  if (!gauge) return;
  if (status === "loading") {
    gauge.className = "pill-badge badge-gold";
    gauge.textContent = "⚙️ Tailoring 1-Page Resume...";
  }
}

function renderActiveItemsControls(data) {
  // 1. Render Skills List with Edit & Remove (✕)
  const skillContainer = document.getElementById("active-skills-list");
  if (skillContainer && data.skills) {
    skillContainer.innerHTML = "";
    data.skills.forEach((sk, idx) => {
      const card = document.createElement("div");
      card.className = "tune-card";

      card.innerHTML = `
        <div class="tune-header">
          <span class="tune-title" style="color:var(--accent-cyan);">🏷️ ${sk.category}</span>
          <div style="display:flex; align-items:center; gap:6px;">
            <button class="btn btn-secondary btn-sm edit-skill-row-btn" data-idx="${idx}" title="Edit Skills List">✏️ Edit</button>
            <button class="btn btn-secondary btn-sm remove-skill-row-btn" data-idx="${idx}" title="Remove from Resume" style="padding:2px 6px; color:#f43f5e;">✕</button>
          </div>
        </div>
        <div style="font-size: 11px; color: #cbd5e1; line-height: 1.35;">
          ${sk.entries}
        </div>
      `;
      skillContainer.appendChild(card);
    });

    // Wire up edit skill row
    skillContainer.querySelectorAll(".edit-skill-row-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.idx);
        const currentSk = activeSkills[idx];
        const newEntries = prompt(`Edit skills for ${currentSk.category}:`, currentSk.entries);
        if (newEntries !== null && newEntries.trim()) {
          activeSkills[idx].entries = newEntries.trim();
          loadResume(currentCategory);
        }
      });
    });

    // Wire up remove skill row
    skillContainer.querySelectorAll(".remove-skill-row-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.idx);
        activeSkills.splice(idx, 1);
        loadResume(currentCategory);
      });
    });
  }

  // 2. Render Projects List with 1/2/3 Pt buttons and Remove (✕)
  const projContainer = document.getElementById("active-projects-list");
  if (projContainer && data.projects) {
    projContainer.innerHTML = "";
    data.projects.forEach((proj) => {
      const card = document.createElement("div");
      card.className = "tune-card";
      
      const currentTier = projectTiers[proj.id] || proj.selected_tier || "2";

      card.innerHTML = `
        <div class="tune-header">
          <span class="tune-title" style="flex:1;">📁 ${proj.title}</span>
          <div style="display:flex; align-items:center; gap:6px;">
            <div class="tier-btn-group">
              <button class="tier-btn ${currentTier === '1' ? 'active' : ''}" data-type="proj" data-id="${proj.id}" data-tier="1">1 Pt</button>
              <button class="tier-btn ${currentTier === '2' ? 'active' : ''}" data-type="proj" data-id="${proj.id}" data-tier="2">2 Pts</button>
              <button class="tier-btn ${currentTier === '3' ? 'active' : ''}" data-type="proj" data-id="${proj.id}" data-tier="3">3 Pts</button>
            </div>
            <button class="btn btn-secondary btn-sm remove-proj-btn" data-id="${proj.id}" title="Remove from Resume" style="padding:2px 6px; color:#f43f5e;">✕</button>
          </div>
        </div>
        <div style="font-size: 11px; color: var(--text-muted); display:flex; justify-content:space-between; align-items:center; margin-top:2px;">
          <span>${proj.bullets.length} bullet(s) showing • <span style="color:#6366f1;">${proj.context || ''}</span></span>
          <button class="btn btn-secondary btn-sm inspect-bullets-critic-btn" data-type="proj" data-id="${proj.id}" style="padding:1px 6px; font-size:10px;">✨ XYZ Critic</button>
        </div>
      `;
      projContainer.appendChild(card);
    });
  }

  // 3. Render Experiences List with 1/2/3 Pt buttons and Remove (✕)
  const expContainer = document.getElementById("active-experiences-list");
  if (expContainer && data.experiences) {
    expContainer.innerHTML = "";
    data.experiences.forEach((exp) => {
      const card = document.createElement("div");
      card.className = "tune-card";
      const currentTier = experienceTiers[exp.id] || exp.selected_tier || "2";

      card.innerHTML = `
        <div class="tune-header">
          <span class="tune-title" style="flex:1;">🏢 ${exp.role}</span>
          <div style="display:flex; align-items:center; gap:6px;">
            <div class="tier-btn-group">
              <button class="tier-btn ${currentTier === '1' ? 'active' : ''}" data-type="exp" data-id="${exp.id}" data-tier="1">1 Pt</button>
              <button class="tier-btn ${currentTier === '2' ? 'active' : ''}" data-type="exp" data-id="${exp.id}" data-tier="2">2 Pts</button>
              <button class="tier-btn ${currentTier === '3' ? 'active' : ''}" data-type="exp" data-id="${exp.id}" data-tier="3">3 Pts</button>
            </div>
            <button class="btn btn-secondary btn-sm remove-exp-btn" data-id="${exp.id}" title="Remove from Resume" style="padding:2px 6px; color:#f43f5e;">✕</button>
          </div>
        </div>
        <div style="font-size: 11px; color: var(--text-muted); display:flex; justify-content:space-between; align-items:center; margin-top:2px;">
          <span>${exp.company} (${exp.duration})</span>
          <button class="btn btn-secondary btn-sm inspect-bullets-critic-btn" data-type="exp" data-id="${exp.id}" style="padding:1px 6px; font-size:10px;">✨ XYZ Critic</button>
        </div>
      `;
      expContainer.appendChild(card);
    });
  }

  // Wire up tier selector buttons
  document.querySelectorAll(".tier-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const type = btn.dataset.type;
      const id = btn.dataset.id;
      const tier = btn.dataset.tier;

      if (type === "proj") {
        projectTiers[id] = tier;
      } else if (type === "exp") {
        experienceTiers[id] = tier;
      }
      loadResume(currentCategory);
    });
  });

  // Wire up remove project
  document.querySelectorAll(".remove-proj-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      activeProjectIds = (activeProjectIds || []).filter(pid => pid !== id);
      loadResume(currentCategory);
    });
  });

  // Wire up remove experience
  document.querySelectorAll(".remove-exp-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      activeExperienceIds = (activeExperienceIds || []).filter(eid => eid !== id);
      loadResume(currentCategory);
    });
  });
}

function setupEventListeners() {
  // Mode Tabs
  const aiTab = document.getElementById("tab-ai-mode");
  const offlineTab = document.getElementById("tab-offline-mode");
  const aiSec = document.getElementById("sec-ai-inputs");
  const offlineSec = document.getElementById("sec-offline-inputs");

  aiTab?.addEventListener("click", () => {
    aiTab.classList.add("active");
    offlineTab.classList.remove("active");
    aiSec.style.display = "flex";
    offlineSec.style.display = "none";
  });

  offlineTab?.addEventListener("click", () => {
    offlineTab.classList.add("active");
    aiTab.classList.remove("active");
    aiSec.style.display = "none";
    offlineSec.style.display = "flex";
  });

  // AI Think Button
  document.getElementById("btn-ai-think")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-ai-think");
    const company = document.getElementById("target-company")?.value.trim() || "";
    const role = document.getElementById("target-role")?.value.trim() || "";
    const jd = document.getElementById("target-jd")?.value.trim() || "";

    if (!role && !company && !jd) {
      alert("Please enter a Target Role or Company before clicking AI Think!");
      return;
    }

    const origHtml = btn.innerHTML;
    btn.innerHTML = "🧠 Gemini AI is Thinking & Tailoring...";
    btn.disabled = true;

    // Reset active overrides so AI picks the optimal set
    activeProjectIds = null;
    activeExperienceIds = null;
    activeSkills = null;
    projectTiers = {};
    experienceTiers = {};

    try {
      await loadResume(currentCategory, { company, role, jd, useGemini: true });
    } finally {
      btn.innerHTML = origHtml;
      btn.disabled = false;
    }
  });

  // Enter key shortcuts for role & company
  document.getElementById("target-role")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      document.getElementById("btn-ai-think")?.click();
    }
  });
  document.getElementById("target-company")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      document.getElementById("btn-ai-think")?.click();
    }
  });

  // Quick Role buttons (Offline Mode)
  document.querySelectorAll(".quick-role-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const role = btn.dataset.role;
      const offInput = document.getElementById("offline-role-input");
      if (offInput) offInput.value = role;
      currentCategory = role;
      activeProjectIds = null;
      activeExperienceIds = null;
      activeSkills = null;
      projectTiers = {};
      experienceTiers = {};
      loadResume(role);
    });
  });

  // Offline custom role input
  document.getElementById("offline-role-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const role = e.target.value.trim();
      if (role) {
        currentCategory = role;
        activeProjectIds = null;
        activeExperienceIds = null;
        activeSkills = null;
        projectTiers = {};
        experienceTiers = {};
        loadResume(role);
      }
    }
  });

  // Typography Sliders
  const fontSlider = document.getElementById("slider-font-size");
  const fontLbl = document.getElementById("lbl-font-size");
  fontSlider?.addEventListener("input", (e) => {
    currentFontSize = `${e.target.value}pt`;
    fontLbl.textContent = currentFontSize;
    loadResume(currentCategory);
  });

  const lineSlider = document.getElementById("slider-line-height");
  const lineLbl = document.getElementById("lbl-line-height");
  lineSlider?.addEventListener("input", (e) => {
    currentLineHeight = e.target.value;
    lineLbl.textContent = currentLineHeight;
    loadResume(currentCategory);
  });

  // Print PDF with Mobile Fallback
  document.getElementById("btn-print-pdf")?.addEventListener("click", () => {
    const iframe = document.getElementById("resume-frame");
    if (!iframe) return;
    try {
      iframe.contentWindow.focus();
      iframe.contentWindow.print();
    } catch (e) {
      const win = window.open("", "_blank");
      if (win && currentHtml) {
        win.document.write(currentHtml);
        win.document.close();
        win.focus();
        setTimeout(() => win.print(), 300);
      } else {
        window.print();
      }
    }
  });

  // Download HTML
  document.getElementById("btn-download-html")?.addEventListener("click", () => {
    downloadFile(`Resume_${currentCategory.toUpperCase()}.html`, currentHtml, "text/html");
  });

  // Download LaTeX
  document.getElementById("btn-download-tex")?.addEventListener("click", () => {
    downloadFile(`Resume_${currentCategory.toUpperCase()}.tex`, currentTex, "text/plain");
  });

  // Zoom Controls
  document.getElementById("btn-zoom-in")?.addEventListener("click", () => {
    zoomLevel = Math.min(zoomLevel + 0.1, 1.4);
    applyZoom();
  });
  document.getElementById("btn-zoom-out")?.addEventListener("click", () => {
    zoomLevel = Math.max(zoomLevel - 0.1, 0.35);
    applyZoom();
  });
  document.getElementById("btn-zoom-fit")?.addEventListener("click", () => {
    autoFitMobileZoom();
  });

  // Modals
  setupModal("btn-api-key", "modal-api-key");
  setupModal("btn-open-github", "modal-github", loadGitHubRepos);
  setupModal("btn-open-linkedin", "modal-linkedin");
  // Top '+ Add Record' button opens right-side drawer
  document.getElementById("btn-open-vault")?.addEventListener("click", () => {
    openDrawer("create_new");
  });
  setupModal("btn-open-vault-explorer", "modal-vault-explorer", loadStorageVaultExplorer);
  setupModal(null, "modal-item-editor");
  setupModal(null, "modal-skill-editor");

  // Section "+" Buttons -> Open Right-Side Drawer
  document.getElementById("btn-add-skill-from-vault")?.addEventListener("click", () => {
    openDrawer("skills");
  });

  document.getElementById("btn-add-proj-from-vault")?.addEventListener("click", () => {
    openDrawer("projects");
  });

  document.getElementById("btn-add-exp-from-vault")?.addEventListener("click", () => {
    openDrawer("experiences");
  });

  // Generic Modal Close Triggers (Works for all current and future modals)
  document.querySelectorAll(".modal-backdrop").forEach(modal => {
    modal.querySelectorAll(".modal-close-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        modal.classList.remove("active");
        modal.classList.remove("open");
      });
    });
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.classList.remove("active");
        modal.classList.remove("open");
      }
    });
  });

  // Drawer Close triggers & Global Escape key
  document.getElementById("btn-close-drawer")?.addEventListener("click", closeDrawer);
  document.getElementById("btn-drawer-cancel")?.addEventListener("click", closeDrawer);
  document.getElementById("drawer-backdrop")?.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDrawer();
      document.querySelectorAll(".modal-backdrop").forEach(m => {
        m.classList.remove("active");
        m.classList.remove("open");
      });
    }
  });

  // Drawer Sub-tab switching
  document.querySelectorAll(".drawer-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      openDrawer(btn.dataset.type);
    });
  });

  // Drawer Search
  document.getElementById("drawer-search")?.addEventListener("input", (e) => {
    renderDrawerItems(e.target.value);
  });

  // Vault Explorer Filter & Search
  document.getElementById("vault-section-filter")?.addEventListener("change", () => {
    loadStorageVaultExplorer();
  });
  document.getElementById("vault-explorer-search")?.addEventListener("input", (e) => {
    filterVaultExplorer(e.target.value);
  });

  // Save Gemini Key
  document.getElementById("btn-save-api-key")?.addEventListener("click", async () => {
    const key = document.getElementById("input-gemini-key").value;
    if (!key.trim()) return;
    const res = await fetch("/api/settings/api_key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key })
    });
    const d = await res.json();
    if (d.status === "success") {
      alert("Gemini API Key configured! AI Thinking enabled.");
      closeModal("modal-api-key");
      checkStatus();
    }
  });

  // Quick Add Forms
  document.getElementById("btn-v-add-skill")?.addEventListener("click", async () => {
    const cat = document.getElementById("v-skill-cat").value;
    const skill = document.getElementById("v-skill-val").value;
    if (!skill.trim()) return;
    await fetch("/api/profile/add_skill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: cat, skill_text: skill })
    });
    alert("Skill saved to storage!");
    document.getElementById("v-skill-val").value = "";
    loadResume(currentCategory);
  });

  document.getElementById("btn-v-add-proj")?.addEventListener("click", async () => {
    const title = document.getElementById("v-proj-title").value;
    const context = document.getElementById("v-proj-context").value;
    const pt1 = document.getElementById("v-proj-pt1").value;
    const pt2 = document.getElementById("v-proj-pt2").value;
    const pt3 = document.getElementById("v-proj-pt3").value;
    const tags = document.getElementById("v-proj-tags").value.split(",").map(t => t.trim()).filter(Boolean);

    if (!title.trim() || !pt1.trim()) {
      alert("Please provide project title and at least Point 1.");
      return;
    }

    const bullets = [pt1];
    if (pt2.trim()) bullets.push(pt2);
    if (pt3.trim()) bullets.push(pt3);

    const points_tier = {
      "1": [pt1],
      "2": bullets.slice(0, 2),
      "3": bullets
    };

    await fetch("/api/profile/add_project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, context, bullets, points_tier, tags })
    });

    alert("Project saved to storage with 1/2/3 point tiers!");
    closeModal("modal-vault");
    loadResume(currentCategory);
  });

  document.getElementById("btn-v-add-award")?.addEventListener("click", async () => {
    const title = document.getElementById("v-award-title").value;
    const desc = document.getElementById("v-award-desc").value;
    if (!title.trim()) return;
    await fetch("/api/profile/add_award", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, details: desc, tags: [] })
    });
    alert("Award saved to storage!");
    closeModal("modal-vault");
    loadResume(currentCategory);
  });

  // Item Editor Save
  document.getElementById("btn-save-edited-item")?.addEventListener("click", saveEditedItem);
  document.getElementById("btn-save-edited-skill")?.addEventListener("click", saveEditedSkillCategory);

  // Top Nav View Switcher (Resume Builder vs Dedicated Storage Vault)
  document.getElementById("nav-btn-builder")?.addEventListener("click", () => switchAppView("builder"));
  document.getElementById("nav-btn-vault")?.addEventListener("click", () => switchAppView("vault"));
  document.getElementById("btn-switch-to-builder")?.addEventListener("click", () => switchAppView("builder"));

  // Dedicated Vault Workspace Action Buttons
  document.getElementById("btn-page-add-proj")?.addEventListener("click", () => {
    document.getElementById("modal-vault")?.classList.add("active");
    document.getElementById("v-proj-title")?.focus();
  });
  document.getElementById("btn-page-add-exp")?.addEventListener("click", () => {
    document.getElementById("modal-vault")?.classList.add("active");
  });
  document.getElementById("btn-page-add-skill-cat")?.addEventListener("click", () => {
    openSkillCategoryEditor("", "");
  });
  document.getElementById("btn-page-add-award")?.addEventListener("click", () => {
    document.getElementById("modal-vault")?.classList.add("active");
    document.getElementById("v-award-title")?.focus();
  });

  // Dedicated Vault Search & Category Filters
  document.getElementById("dedicated-vault-search")?.addEventListener("input", (e) => {
    dedicatedVaultSearchQuery = e.target.value.trim();
    renderDedicatedVaultGrid();
  });

  document.querySelectorAll("#dedicated-vault-chips .vault-chip-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#dedicated-vault-chips .vault-chip-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      dedicatedVaultSec = btn.dataset.sec || "all";
      renderDedicatedVaultGrid();
    });
  });
}

// ---------------- DRAWER: Add from Storage Vault ----------------

// Helper to format skill category names nicely
function formatSkillCatName(cat) {
  const map = {
    "programming": "Programming",
    "frameworks_web": "Frameworks & Web",
    "quant_methods": "Quantitative Methods",
    "ai_ml": "AI & Machine Learning",
    "data_systems": "Data Systems & Cloud",
    "chemical_engineering": "Chemical Engineering"
  };
  if (map[cat]) return map[cat];
  return cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

let drawerStorageItems = [];

async function openDrawer(type) {
  activeDrawerType = type || "skills";
  const drawer = document.getElementById("side-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  const title = document.getElementById("drawer-title");
  const subtitle = document.getElementById("drawer-subtitle");
  const searchWrap = document.getElementById("drawer-search")?.parentElement;
  if (document.getElementById("drawer-search")) document.getElementById("drawer-search").value = "";

  // Update tabs UI in drawer
  document.querySelectorAll(".drawer-tab-btn").forEach(btn => {
    if (btn.dataset.type === activeDrawerType) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  if (activeDrawerType === "skills") {
    title.textContent = "🏷️ Add Skills from Storage Vault";
    subtitle.textContent = "Select any skill category in your vault to insert into the resume";
    if (searchWrap) searchWrap.style.display = "block";
  } else if (activeDrawerType === "projects") {
    title.textContent = "📁 Add Project from Storage Vault";
    subtitle.textContent = "Select any project in your vault to insert into the 1-page resume";
    if (searchWrap) searchWrap.style.display = "block";
  } else if (activeDrawerType === "experiences") {
    title.textContent = "🏢 Add Experience from Storage Vault";
    subtitle.textContent = "Select any internship or role to insert into the resume";
    if (searchWrap) searchWrap.style.display = "block";
  } else if (activeDrawerType === "create_new") {
    title.textContent = "➕ Create New Career Record";
    subtitle.textContent = "Quickly add a project, experience, or skill to your vault & resume";
    if (searchWrap) searchWrap.style.display = "none";
  }

  drawer?.classList.add("active");
  backdrop?.classList.add("active");

  if (activeDrawerType === "create_new") {
    renderDrawerCreateNew();
    return;
  }

  try {
    const res = await fetch("/api/profile");
    const profile = await res.json();
    if (activeDrawerType === "skills") {
      drawerStorageItems = Object.entries(profile.skills || {}).map(([key, list]) => ({
        id: key,
        rawCategory: key,
        category: formatSkillCatName(key),
        entries: Array.isArray(list) ? list.join(", ") : String(list)
      }));
    } else {
      drawerStorageItems = profile[activeDrawerType] || [];
    }
    renderDrawerItems();
  } catch (e) {
    console.error(e);
  }
}

function closeDrawer() {
  document.getElementById("side-drawer")?.classList.remove("active");
  document.getElementById("drawer-backdrop")?.classList.remove("active");
}

function renderDrawerCreateNew() {
  const container = document.getElementById("drawer-items-list");
  if (!container) return;
  container.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:14px;">
      <div style="background:rgba(255,255,255,0.04); border:1px solid var(--border-color); border-radius:8px; padding:12px;">
        <label style="font-size:11px; font-weight:700; color:var(--accent-gold); display:block; margin-bottom:8px;">Record Type to Add</label>
        <div style="display:flex; gap:8px;">
          <button type="button" class="btn btn-sm btn-primary drawer-new-type-btn" data-form="project">📁 New Project</button>
          <button type="button" class="btn btn-sm btn-secondary drawer-new-type-btn" data-form="experience">🏢 New Experience</button>
          <button type="button" class="btn btn-sm btn-secondary drawer-new-type-btn" data-form="skill">🏷️ New Skill</button>
        </div>
      </div>

      <!-- Project Form -->
      <div id="drawer-form-project" style="display:flex; flex-direction:column; gap:10px;">
        <input type="text" id="drw-proj-title" class="input-box" placeholder="Project Title (e.g. High-Frequency Limit Order Engine)">
        <input type="text" id="drw-proj-context" class="input-box" placeholder="Context / Tech Stack (e.g. C++20, DPDK, Lock-Free Queues)">
        <div>
          <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Point 1 (Core Architecture & High Impact):</label>
          <textarea id="drw-proj-pt1" class="input-box" rows="2" placeholder="Engineered ultra-low-latency order router achieving sub-1.2us tick-to-trade..."></textarea>
        </div>
        <div>
          <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Point 2 (Algorithms & Scale):</label>
          <textarea id="drw-proj-pt2" class="input-box" rows="2" placeholder="Implemented lock-free ring buffer handling 2.5M msgs/sec..."></textarea>
        </div>
        <div>
          <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Point 3 (Production Benchmark):</label>
          <textarea id="drw-proj-pt3" class="input-box" rows="2" placeholder="Benchmarked across 10GbE Solarflare NICs with zero packet drop..."></textarea>
        </div>
        <input type="text" id="drw-proj-tags" class="input-box" placeholder="Category Tags (comma-separated: quant, ai_ml, sde, finance, chemical)">
        <button id="btn-drw-save-proj" class="btn btn-primary" style="justify-content:center; padding:9px;">Save Project & Add to Resume</button>
      </div>

      <!-- Experience Form -->
      <div id="drawer-form-experience" style="display:none; flex-direction:column; gap:10px;">
        <input type="text" id="drw-exp-role" class="input-box" placeholder="Role Title (e.g. Quantitative Research Intern)">
        <input type="text" id="drw-exp-company" class="input-box" placeholder="Company / Organization (e.g. Shell / PIEDS)">
        <div style="display:flex; gap:8px;">
          <input type="text" id="drw-exp-duration" class="input-box" placeholder="Duration (e.g. May 2025 – Jul 2025)">
          <input type="text" id="drw-exp-location" class="input-box" placeholder="Location (e.g. Bengaluru, India)">
        </div>
        <div>
          <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Bullet 1 (Primary Achievement):</label>
          <textarea id="drw-exp-b1" class="input-box" rows="2" placeholder="Key Achievement / Responsibility bullet 1..."></textarea>
        </div>
        <div>
          <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Bullet 2 (Secondary Achievement):</label>
          <textarea id="drw-exp-b2" class="input-box" rows="2" placeholder="Bullet 2..."></textarea>
        </div>
        <input type="text" id="drw-exp-tags" class="input-box" placeholder="Category Tags (quant, finance, sde, chemical)">
        <button id="btn-drw-save-exp" class="btn btn-primary" style="justify-content:center; padding:9px;">Save Experience & Add to Resume</button>
      </div>

      <!-- Skill Form -->
      <div id="drawer-form-skill" style="display:none; flex-direction:column; gap:10px;">
        <label style="font-size:11px; color:var(--text-muted);">Skill Domain Category:</label>
        <select id="drw-skill-cat" class="input-box">
          <option value="programming">Programming</option>
          <option value="ai_ml">AI & ML</option>
          <option value="frameworks_web">Frameworks & Web</option>
          <option value="quant_methods">Quant Methods</option>
          <option value="data_systems">Data & Systems</option>
          <option value="chemical_engineering">Chemical Engineering</option>
        </select>
        <input type="text" id="drw-skill-val" class="input-box" placeholder="Skills (e.g. PyTorch, CUDA, Polars, Docker...)">
        <button id="btn-drw-save-skill" class="btn btn-primary" style="justify-content:center; padding:9px;">Save Skill & Add to Resume</button>
      </div>
    </div>
  `;

  // Wire up form type switcher inside drawer
  container.querySelectorAll(".drawer-new-type-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".drawer-new-type-btn").forEach(b => {
        b.classList.remove("btn-primary");
        b.classList.add("btn-secondary");
      });
      btn.classList.remove("btn-secondary");
      btn.classList.add("btn-primary");

      const f = btn.dataset.form;
      document.getElementById("drawer-form-project").style.display = f === "project" ? "flex" : "none";
      document.getElementById("drawer-form-experience").style.display = f === "experience" ? "flex" : "none";
      document.getElementById("drawer-form-skill").style.display = f === "skill" ? "flex" : "none";
    });
  });

  // Wire up Project save
  document.getElementById("btn-drw-save-proj")?.addEventListener("click", async () => {
    const title = document.getElementById("drw-proj-title")?.value.trim();
    if (!title) { alert("Please enter a project title"); return; }
    const context = document.getElementById("drw-proj-context")?.value.trim() || "";
    const pt1 = document.getElementById("drw-proj-pt1")?.value.trim();
    const pt2 = document.getElementById("drw-proj-pt2")?.value.trim();
    const pt3 = document.getElementById("drw-proj-pt3")?.value.trim();
    const tags = (document.getElementById("drw-proj-tags")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
    const bullets = [pt1, pt2, pt3].filter(Boolean);

    try {
      const res = await fetch("/api/project/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title, context, bullets,
          points_tier: { "1": [pt1 || ""], "2": [pt1 || "", pt2 || ""].filter(Boolean), "3": bullets },
          tags
        })
      });
      const data = await res.json();
      if (data.status === "success" && data.project) {
        if (!activeProjectIds) activeProjectIds = [];
        activeProjectIds.push(data.project.id);
        projectTiers[data.project.id] = "2";
      }
      closeDrawer();
      await loadResume(currentCategory);
    } catch (e) {
      console.error(e);
    }
  });

  // Wire up Experience save
  document.getElementById("btn-drw-save-exp")?.addEventListener("click", async () => {
    const role = document.getElementById("drw-exp-role")?.value.trim();
    const company = document.getElementById("drw-exp-company")?.value.trim();
    if (!role || !company) { alert("Please enter role and company"); return; }
    const duration = document.getElementById("drw-exp-duration")?.value.trim() || "";
    const location = document.getElementById("drw-exp-location")?.value.trim() || "";
    const b1 = document.getElementById("drw-exp-b1")?.value.trim();
    const b2 = document.getElementById("drw-exp-b2")?.value.trim();
    const tags = (document.getElementById("drw-exp-tags")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
    const bullets = [b1, b2].filter(Boolean);

    try {
      const res = await fetch("/api/experience/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role, company, duration, location, bullets,
          points_tier: { "1": [b1 || ""], "2": bullets, "3": bullets },
          tags
        })
      });
      const data = await res.json();
      if (data.status === "success" && data.experience) {
        if (!activeExperienceIds) activeExperienceIds = [];
        activeExperienceIds.push(data.experience.id);
        experienceTiers[data.experience.id] = "2";
      }
      closeDrawer();
      await loadResume(currentCategory);
    } catch (e) {
      console.error(e);
    }
  });

  // Wire up Skill save
  document.getElementById("btn-drw-save-skill")?.addEventListener("click", async () => {
    const cat = document.getElementById("drw-skill-cat")?.value;
    const skillText = document.getElementById("drw-skill-val")?.value.trim();
    if (!skillText) { alert("Please enter skill text"); return; }
    try {
      await fetch("/api/skill/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat, skill_text: skillText })
      });
      const dispName = formatSkillCatName(cat);
      if (!activeSkills) activeSkills = [];
      const existing = activeSkills.find(s => s.category.toLowerCase() === dispName.toLowerCase());
      if (existing) {
        existing.entries += ", " + skillText;
      } else {
        activeSkills.push({ category: dispName, entries: skillText });
      }
      closeDrawer();
      await loadResume(currentCategory);
    } catch (e) {
      console.error(e);
    }
  });
}

function renderDrawerItems(query = "") {
  const container = document.getElementById("drawer-items-list");
  if (!container) return;
  container.innerHTML = "";

  const queryLower = query.toLowerCase();

  // 1. Drawer for Skills
  if (activeDrawerType === "skills") {
    const filtered = drawerStorageItems.filter(item => {
      if (!queryLower) return true;
      return (item.category || "").toLowerCase().includes(queryLower) ||
             (item.entries || "").toLowerCase().includes(queryLower) ||
             (item.rawCategory || "").toLowerCase().includes(queryLower);
    });

    if (filtered.length === 0) {
      container.innerHTML = "<div style='color:var(--text-muted); font-size:12px;'>No matching skill categories found in Storage Vault.</div>";
      return;
    }

    filtered.forEach(item => {
      const isAlreadyIn = (activeSkills || []).some(
        s => s.category.toLowerCase() === item.category.toLowerCase() ||
             s.category.toLowerCase() === item.id.toLowerCase() ||
             s.category.toLowerCase() === item.rawCategory.toLowerCase()
      );

      const card = document.createElement("div");
      card.className = "vault-item-card";

      card.innerHTML = `
        <div class="vault-item-header">
          <div>
            <div style="font-weight:700; font-size:13px; color:var(--accent-cyan);">🏷️ ${item.category}</div>
            <div style="font-size:10px; color:var(--text-muted); margin-top:2px;">Storage Key: ${item.rawCategory}</div>
          </div>
          ${isAlreadyIn 
            ? `<span class="pill-badge badge-green" style="font-size:10px;">✓ In Resume</span>` 
            : `<span class="pill-badge badge-gold" style="font-size:10px;">Available</span>`}
        </div>

        <div class="vault-tier-preview" style="margin-top:6px; line-height:1.4; color:#cbd5e1;">
          ${item.entries}
        </div>

        ${!isAlreadyIn ? `
          <div style="display:flex; justify-content:flex-end; align-items:center; margin-top:8px; border-top:1px solid rgba(255,255,255,0.06); padding-top:6px;">
            <button class="btn btn-primary btn-sm add-drawer-skill-btn" data-category="${item.category}" data-entries="${encodeURIComponent(item.entries)}">
              + Add to Resume
            </button>
          </div>
        ` : ''}
      `;

      container.appendChild(card);
    });

    // Wire up "+ Add to Resume" for skills
    container.querySelectorAll(".add-drawer-skill-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const category = btn.dataset.category;
        const entries = decodeURIComponent(btn.dataset.entries);
        if (!activeSkills) activeSkills = [];
        activeSkills.push({ category, entries });
        closeDrawer();
        loadResume(currentCategory);
      });
    });

    return;
  }

  // 2. Drawer for Projects & Experiences
  const currentActiveIds = activeDrawerType === "projects" ? (activeProjectIds || []) : (activeExperienceIds || []);

  const filtered = drawerStorageItems.filter(item => {
    const matchQ = !queryLower || (item.title || item.role || "").toLowerCase().includes(queryLower) ||
      (item.context || item.company || "").toLowerCase().includes(queryLower) ||
      (item.tags || []).some(t => t.toLowerCase().includes(queryLower));
    return matchQ;
  });

  if (filtered.length === 0) {
    container.innerHTML = "<div style='color:var(--text-muted); font-size:12px;'>No matching items found in Storage Vault.</div>";
    return;
  }

  filtered.forEach(item => {
    const isAlreadyIn = currentActiveIds.includes(item.id);
    const card = document.createElement("div");
    card.className = "vault-item-card";

    const titleStr = item.title || item.role;
    const subStr = item.context || `${item.company} (${item.duration})`;
    const pt1 = (item.points_tier && item.points_tier["1"]) ? item.points_tier["1"][0] : (item.bullets ? item.bullets[0] : "");

    card.innerHTML = `
      <div class="vault-item-header">
        <div>
          <div style="font-weight:700; font-size:13px; color:#fff;">${titleStr}</div>
          <div style="font-size:11px; color:#a5b4fc; margin-top:2px;">${subStr}</div>
          <div style="font-size:10px; color:#6366f1; margin-top:3px;">
            ${(item.tags || []).map(t => '#' + t).join(' ')}
          </div>
        </div>
        ${isAlreadyIn 
          ? `<span class="pill-badge badge-green" style="font-size:10px;">✓ In Resume</span>` 
          : `<span class="pill-badge badge-gold" style="font-size:10px;">Available</span>`}
      </div>

      <div class="vault-tier-preview">
        <b>1-Pt Preview:</b> ${pt1 ? pt1.replace(/<[^>]*>?/gm, '').slice(0, 140) + '...' : 'No preview'}
      </div>

      ${!isAlreadyIn ? `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px; border-top:1px solid rgba(255,255,255,0.06); padding-top:6px;">
          <div style="display:flex; align-items:center; gap:4px;">
            <span style="font-size:11px; color:var(--text-muted);">Points:</span>
            <div class="tier-btn-group" id="drawer-tier-${item.id}">
              <button class="tier-btn" data-val="1">1 Pt</button>
              <button class="tier-btn active" data-val="2">2 Pts</button>
              <button class="tier-btn" data-val="3">3 Pts</button>
            </div>
          </div>
          <button class="btn btn-primary btn-sm add-drawer-item-btn" data-id="${item.id}">
            + Add to Resume
          </button>
        </div>
      ` : ''}
    `;

    container.appendChild(card);
  });

  // Handle tier selection inside drawer
  container.querySelectorAll(".tier-btn-group").forEach(group => {
    const btns = group.querySelectorAll(".tier-btn");
    btns.forEach(btn => {
      btn.addEventListener("click", () => {
        btns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
      });
    });
  });

  // Handle "+ Add to Resume"
  container.querySelectorAll(".add-drawer-item-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const tierGroup = document.getElementById(`drawer-tier-${id}`);
      const activeBtn = tierGroup?.querySelector(".tier-btn.active");
      const chosenTier = activeBtn?.dataset.val || "2";

      if (activeDrawerType === "projects") {
        if (!activeProjectIds) activeProjectIds = [];
        if (!activeProjectIds.includes(id)) activeProjectIds.push(id);
        projectTiers[id] = chosenTier;
      } else if (activeDrawerType === "experiences") {
        if (!activeExperienceIds) activeExperienceIds = [];
        if (!activeExperienceIds.includes(id)) activeExperienceIds.push(id);
        experienceTiers[id] = chosenTier;
      }

      closeDrawer();
      loadResume(currentCategory);
    });
  });
}

// ---------------- STORAGE VAULT EXPLORER (Look into Vault & Edit) ----------------

let rawVaultProfile = null;

async function loadStorageVaultExplorer() {
  const container = document.getElementById("vault-explorer-list");
  if (!container) return;
  container.innerHTML = "<div style='color:var(--text-muted);'>Loading Storage Vault records...</div>";

  try {
    const res = await fetch("/api/profile");
    rawVaultProfile = await res.json();
    renderVaultExplorerList();
  } catch (e) {
    container.innerHTML = `<div style='color:#f43f5e;'>Error loading vault: ${e.message}</div>`;
  }
}

function renderVaultExplorerList(query = "") {
  const container = document.getElementById("vault-explorer-list");
  const secFilter = document.getElementById("vault-section-filter")?.value || "all";
  if (!container || !rawVaultProfile) return;

  container.innerHTML = "";
  const queryLower = query.toLowerCase();

  // 1. Render Projects
  if (secFilter === "all" || secFilter === "projects") {
    const projects = rawVaultProfile.projects || [];
    renderSectionItems(container, "Projects (📁)", projects, "proj", queryLower);
  }

  // 2. Render Experiences
  if (secFilter === "all" || secFilter === "experiences") {
    const experiences = rawVaultProfile.experiences || [];
    renderSectionItems(container, "Experiences (🏢)", experiences, "exp", queryLower);
  }

  // 3. Render Patents & Certifications
  if (secFilter === "all" || secFilter === "patents_certifications") {
    const pcs = rawVaultProfile.patents_certifications || [];
    renderSectionItems(container, "Patents & Certifications (📜)", pcs, "pc", queryLower);
  }

  // 4. Render POR & Achievements
  if (secFilter === "all" || secFilter === "pors_achievements") {
    const pors = rawVaultProfile.pors_achievements || [];
    renderSectionItems(container, "Position of Responsibility (🏆)", pors, "por", queryLower);
  }

  // 5. Render Awards & Medals
  if (secFilter === "all" || secFilter === "awards_medals") {
    const awards = rawVaultProfile.awards_medals || [];
    renderSectionItems(container, "Awards & Medals (🎖️)", awards, "award", queryLower);
  }

  // 6. Render Skills
  if (secFilter === "all" || secFilter === "skills") {
    renderSkillsVault(container, rawVaultProfile.skills || {}, queryLower);
  }
}

function renderSectionItems(container, sectionTitle, items, type, queryLower) {
  const filtered = items.filter(item => {
    if (!queryLower) return true;
    const str = `${item.title || ''} ${item.role || ''} ${item.context || ''} ${item.company || ''} ${item.details || ''} ${(item.tags || []).join(' ')}`.toLowerCase();
    return str.includes(queryLower);
  });

  if (filtered.length === 0) return;

  const header = document.createElement("div");
  header.style.fontSize = "13px";
  header.style.fontWeight = "800";
  header.style.color = "var(--accent-primary)";
  header.style.marginTop = "10px";
  header.style.marginBottom = "4px";
  header.textContent = `${sectionTitle} — ${filtered.length} Items`;
  container.appendChild(header);

  filtered.forEach(item => {
    const card = document.createElement("div");
    card.className = "vault-item-card";

    const titleStr = item.title || item.role;
    const subStr = item.context || (item.company ? `${item.company} | ${item.duration}` : item.details || "");
    const pt1 = (item.points_tier && item.points_tier["1"]) ? item.points_tier["1"][0] : (item.bullets ? item.bullets[0] : (item.details || ""));
    const pt2 = (item.points_tier && item.points_tier["2"] && item.points_tier["2"][1]) ? item.points_tier["2"][1] : (item.bullets && item.bullets[1] ? item.bullets[1] : "");

    card.innerHTML = `
      <div class="vault-item-header">
        <div>
          <div style="font-weight:700; font-size:13px; color:#fff;">${titleStr}</div>
          <div style="font-size:11px; color:#93c5fd; margin-top:2px;">${subStr}</div>
          <div style="font-size:10px; color:#a855f7; margin-top:3px;">
            ${(item.tags || []).map(t => '#' + t).join(' ')}
          </div>
        </div>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-secondary btn-sm edit-vault-btn" data-type="${type}" data-id="${item.id || item.title}">
            ✏️ Edit
          </button>
          <button class="btn btn-secondary btn-sm delete-vault-btn" data-type="${type}" data-id="${item.id || item.title}" style="color:#f43f5e;">
            🗑️
          </button>
        </div>
      </div>

      <div class="vault-tier-preview">
        <div><b>Point 1:</b> ${pt1 ? pt1.replace(/<[^>]*>?/gm, '') : 'None'}</div>
        ${pt2 ? `<div style="margin-top:4px;"><b>Point 2:</b> ${pt2.replace(/<[^>]*>?/gm, '')}</div>` : ''}
      </div>
    `;

    container.appendChild(card);
  });

  // Wire up Edit & Delete buttons
  container.querySelectorAll(".edit-vault-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      openItemEditor(btn.dataset.type, btn.dataset.id);
    });
  });

  container.querySelectorAll(".delete-vault-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (!confirm(`Delete this item from the Storage Vault?`)) return;
      const t = btn.dataset.type;
      const id = btn.dataset.id;
      const secMap = {
        "proj": "projects",
        "exp": "experiences",
        "pc": "patents_certifications",
        "por": "pors_achievements",
        "award": "awards_medals"
      };
      const section = secMap[t] || "projects";

      await fetch("/api/profile/delete_item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ section, id })
      });

      // Remove from active resume if present
      if (activeProjectIds) activeProjectIds = activeProjectIds.filter(pid => pid !== id);
      if (activeExperienceIds) activeExperienceIds = activeExperienceIds.filter(eid => eid !== id);

      loadStorageVaultExplorer();
      loadResume(currentCategory);
    });
  });
}

function renderSkillsVault(container, skillsDict, queryLower) {
  const header = document.createElement("div");
  header.style.display = "flex";
  header.style.justifyContent = "space-between";
  header.style.alignItems = "center";
  header.style.marginTop = "14px";
  header.style.marginBottom = "8px";

  header.innerHTML = `
    <span style="font-size:13px; font-weight:800; color:var(--accent-primary);">Skills Catalog (${Object.keys(skillsDict).length} Categories)</span>
    <button class="btn btn-primary btn-sm" id="btn-vault-new-skill-cat">+ Add Skill Category</button>
  `;
  container.appendChild(header);

  // Wire up Add Skill Category button
  header.querySelector("#btn-vault-new-skill-cat")?.addEventListener("click", () => {
    openSkillCategoryEditor("", "");
  });

  const entries = Object.entries(skillsDict);
  const filtered = entries.filter(([cat, list]) => {
    if (!queryLower) return true;
    const listStr = Array.isArray(list) ? list.join(", ") : String(list);
    return cat.toLowerCase().includes(queryLower) ||
           formatSkillCatName(cat).toLowerCase().includes(queryLower) ||
           listStr.toLowerCase().includes(queryLower);
  });

  if (filtered.length === 0) {
    const emptyMsg = document.createElement("div");
    emptyMsg.style.color = "var(--text-muted)";
    emptyMsg.style.fontSize = "12px";
    emptyMsg.textContent = "No matching skill categories found.";
    container.appendChild(emptyMsg);
    return;
  }

  filtered.forEach(([cat, list]) => {
    const card = document.createElement("div");
    card.className = "vault-item-card";
    const displayName = formatSkillCatName(cat);
    const listStr = Array.isArray(list) ? list.join(', ') : String(list);

    card.innerHTML = `
      <div class="vault-item-header">
        <div>
          <div style="font-weight:700; font-size:13px; color:var(--accent-cyan);">${displayName}</div>
          <div style="font-size:10px; color:var(--text-muted); margin-top:1px;">Key: ${cat}</div>
        </div>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-secondary btn-sm edit-skill-vault-btn" data-cat="${cat}" data-entries="${encodeURIComponent(listStr)}">
            ✏️ Edit
          </button>
          <button class="btn btn-secondary btn-sm delete-skill-vault-btn" data-cat="${cat}" style="color:#f43f5e;">
            🗑️
          </button>
        </div>
      </div>
      <div style="font-size:12px; color:#e2e8f0; line-height:1.45; margin-top:6px;">
        ${listStr}
      </div>
    `;
    container.appendChild(card);
  });

  // Wire up Edit Skill Category
  container.querySelectorAll(".edit-skill-vault-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const cat = btn.dataset.cat;
      const entries = decodeURIComponent(btn.dataset.entries);
      openSkillCategoryEditor(cat, entries);
    });
  });

  // Wire up Delete Skill Category
  container.querySelectorAll(".delete-skill-vault-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const cat = btn.dataset.cat;
      if (!confirm(`Delete skill category "${cat}" from Storage Vault?`)) return;

      await fetch("/api/profile/delete_skill_category", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat })
      });

      // Also remove from activeSkills if present
      if (activeSkills) {
        const formatted = formatSkillCatName(cat).toLowerCase();
        activeSkills = activeSkills.filter(s => s.category.toLowerCase() !== formatted && s.category.toLowerCase() !== cat.toLowerCase());
      }

      await loadStorageVaultExplorer();
      await loadResume(currentCategory);
    });
  });
}

function filterVaultExplorer(val) {
  renderVaultExplorerList(val);
}

// ---------------- SKILL CATEGORY EDITOR ----------------

function openSkillCategoryEditor(categoryKey, entriesStr) {
  const modal = document.getElementById("modal-skill-editor");
  const title = document.getElementById("skill-editor-title");
  document.getElementById("edit-skill-orig-cat").value = categoryKey;
  document.getElementById("edit-skill-cat-name").value = categoryKey ? formatSkillCatName(categoryKey) : "";
  document.getElementById("edit-skill-entries").value = entriesStr || "";

  if (categoryKey) {
    title.textContent = `✏️ Edit Skill Category: ${formatSkillCatName(categoryKey)}`;
  } else {
    title.textContent = "➕ Add New Skill Category to Vault";
  }

  modal.classList.add("active");
}

async function saveEditedSkillCategory() {
  const origCat = document.getElementById("edit-skill-orig-cat").value.trim();
  let catName = document.getElementById("edit-skill-cat-name").value.trim();
  const entriesRaw = document.getElementById("edit-skill-entries").value.trim();

  if (!catName) {
    alert("Category name cannot be empty!");
    return;
  }
  if (!entriesRaw) {
    alert("Please enter at least one skill!");
    return;
  }

  const skillsList = entriesRaw.split(",").map(s => s.trim()).filter(Boolean);
  const targetCategory = origCat || catName.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");

  // If user changed category name from an existing one, delete old if different
  if (origCat && targetCategory !== origCat) {
    await fetch("/api/profile/delete_skill_category", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: origCat })
    });
  }

  await fetch("/api/profile/update_skill_category", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      category: targetCategory,
      skills: skillsList
    })
  });

  // Sync to activeSkills in resume if this category is currently shown
  if (activeSkills) {
    const formatted = formatSkillCatName(targetCategory);
    const existingIdx = activeSkills.findIndex(s => 
      s.category.toLowerCase() === formatted.toLowerCase() || 
      s.category.toLowerCase() === targetCategory.toLowerCase() ||
      (origCat && s.category.toLowerCase() === origCat.toLowerCase())
    );
    if (existingIdx !== -1) {
      activeSkills[existingIdx].category = formatted;
      activeSkills[existingIdx].entries = skillsList.join(", ");
    }
  }

  closeModal("modal-skill-editor");
  alert("Skill category saved to Storage Vault and synced to live resume!");
  await loadStorageVaultExplorer();
  await loadResume(currentCategory);
}

// ---------------- ITEM INLINE EDITOR ----------------

function openItemEditor(type, id) {
  if (!rawVaultProfile) return;

  const modal = document.getElementById("modal-item-editor");
  const modalTitle = document.getElementById("editor-modal-title");
  document.getElementById("edit-item-type").value = type;
  document.getElementById("edit-item-id").value = id;

  const datesWrapper = document.getElementById("edit-dates-wrapper");
  const tiersWrapper = document.getElementById("edit-tiers-wrapper");
  const contextLbl = document.getElementById("edit-lbl-context");

  let item = null;
  if (type === "proj") {
    item = (rawVaultProfile.projects || []).find(p => p.id === id || p.title === id);
    modalTitle.textContent = "✏️ Edit Project in Vault";
    datesWrapper.style.display = "none";
    tiersWrapper.style.display = "block";
    contextLbl.textContent = "Context / Affiliation / Mentor";
  } else if (type === "exp") {
    item = (rawVaultProfile.experiences || []).find(e => e.id === id);
    modalTitle.textContent = "✏️ Edit Experience in Vault";
    datesWrapper.style.display = "flex";
    tiersWrapper.style.display = "block";
    contextLbl.textContent = "Company Name";
  } else if (type === "pc" || type === "por" || type === "award") {
    const sec = type === "pc" ? rawVaultProfile.patents_certifications : (type === "por" ? rawVaultProfile.pors_achievements : rawVaultProfile.awards_medals);
    item = (sec || []).find(x => x.title === id || x.id === id);
    modalTitle.textContent = "✏️ Edit Record in Vault";
    datesWrapper.style.display = "none";
    tiersWrapper.style.display = "none";
    contextLbl.textContent = "Details / Description";
  }

  if (!item) {
    alert("Record not found!");
    return;
  }

  // Pre-fill fields
  document.getElementById("edit-field-title").value = item.title || item.role || "";
  document.getElementById("edit-field-context").value = item.context || item.company || item.details || "";
  document.getElementById("edit-field-duration").value = item.duration || "";
  document.getElementById("edit-field-location").value = item.location || "";
  document.getElementById("edit-field-tags").value = (item.tags || []).join(", ");

  const pt1 = (item.points_tier && item.points_tier["1"]) ? item.points_tier["1"][0] : (item.bullets ? item.bullets[0] : "");
  const pt2 = (item.points_tier && item.points_tier["2"]) ? (item.points_tier["2"][1] || "") : (item.bullets ? (item.bullets[1] || "") : "");
  const pt3 = (item.points_tier && item.points_tier["3"]) ? (item.points_tier["3"][2] || "") : (item.bullets ? (item.bullets[2] || "") : "");

  document.getElementById("edit-field-pt1").value = pt1 || "";
  document.getElementById("edit-field-pt2").value = pt2 || "";
  document.getElementById("edit-field-pt3").value = pt3 || "";

  modal.classList.add("active");
}

async function saveEditedItem() {
  const type = document.getElementById("edit-item-type").value;
  const id = document.getElementById("edit-item-id").value;

  const title = document.getElementById("edit-field-title").value.trim();
  const context = document.getElementById("edit-field-context").value.trim();
  const duration = document.getElementById("edit-field-duration").value.trim();
  const location = document.getElementById("edit-field-location").value.trim();
  const tags = document.getElementById("edit-field-tags").value.split(",").map(t => t.trim()).filter(Boolean);

  const pt1 = document.getElementById("edit-field-pt1").value.trim();
  const pt2 = document.getElementById("edit-field-pt2").value.trim();
  const pt3 = document.getElementById("edit-field-pt3").value.trim();

  if (!title) {
    alert("Title/Role cannot be empty!");
    return;
  }

  const bullets = [pt1];
  if (pt2) bullets.push(pt2);
  if (pt3) bullets.push(pt3);

  const points_tier = {
    "1": [pt1],
    "2": bullets.slice(0, 2),
    "3": bullets
  };

  if (type === "proj") {
    await fetch("/api/profile/update_project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id,
        title,
        context,
        bullets,
        points_tier,
        tags
      })
    });
  } else if (type === "exp") {
    await fetch("/api/profile/update_experience", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id,
        role: title,
        company: context,
        duration,
        location,
        bullets,
        points_tier,
        tags
      })
    });
  }

  closeModal("modal-item-editor");
  alert("Item updated in Storage Vault and synced to live resume!");
  await loadStorageVaultExplorer();
  await loadResume(currentCategory);
}

// ---------------- GITHUB MODAL ----------------

async function loadGitHubRepos() {
  const container = document.getElementById("github-repos-container");
  if (!container) return;
  container.innerHTML = "<div style='color:#9ca3af;'>Fetching public GitHub repos for DEBANJAN-KAKATI...</div>";

  try {
    const res = await fetch("/api/github/repos");
    const data = await res.json();
    container.innerHTML = "";

    data.repos.forEach(repo => {
      const el = document.createElement("div");
      el.className = "tune-card";
      el.innerHTML = `
        <div class="tune-header">
          <div>
            <a href="${repo.url}" target="_blank" style="color:var(--accent-cyan); font-weight:700; text-decoration:none;">${repo.name}</a>
            <span style="font-size:11px; color:#f59e0b; margin-left:6px;">★ ${repo.stars}</span>
            <span style="font-size:11px; color:#9ca3af; margin-left:6px;">(${repo.language})</span>
          </div>
          <div>
            ${repo.already_imported
              ? `<span class="pill-badge badge-green">✓ In Storage</span>`
              : `<button class="btn btn-primary btn-sm import-repo-btn" data-name="${repo.name}">+ Import (1/2/3 Pts)</button>`}
          </div>
        </div>
        <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">${repo.description}</div>
        <div style="font-size:10px; color:#6366f1; margin-top:4px;">${(repo.topics || []).map(t => '#' + t).join(' ')}</div>
      `;
      container.appendChild(el);
    });

    container.querySelectorAll(".import-repo-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const repoName = btn.dataset.name;
        btn.textContent = "Synthesizing 1/2/3 Pts...";
        await fetch("/api/github/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_name: repoName })
        });
        btn.parentElement.innerHTML = `<span class="pill-badge badge-green">✓ In Storage</span>`;
        loadResume(currentCategory);
      });
    });

  } catch (err) {
    container.innerHTML = `<div style="color:#ef4444;">Failed to fetch repos: ${err.message}</div>`;
  }
}

function autoFitMobileZoom() {
  const container = document.querySelector("#view-resume-builder .paper-wrapper") || document.querySelector(".paper-wrapper");
  if (!container) return;
  const containerWidth = container.clientWidth;
  if (containerWidth > 0 && containerWidth < 800) {
    const scale = Math.max(0.35, Math.min(1.0, (containerWidth - 24) / 794));
    zoomLevel = parseFloat(scale.toFixed(2));
  } else {
    zoomLevel = 1.0;
  }
  applyZoom();
}

function applyZoom() {
  const sheet = document.getElementById("paper-sheet");
  const clSheet = document.getElementById("cl-paper-sheet");
  const lbl = document.getElementById("zoom-value");
  
  [sheet, clSheet].forEach(s => {
    if (s) {
      s.style.transform = `scale(${zoomLevel})`;
      s.style.transformOrigin = "top center";
      const baseHeight = 11.69 * 96;
      if (zoomLevel < 1.0) {
        s.style.marginBottom = `-${Math.round((1.0 - zoomLevel) * baseHeight)}px`;
      } else {
        s.style.marginBottom = "24px";
      }
    }
  });

  if (lbl) {
    lbl.textContent = `${Math.round(zoomLevel * 100)}%`;
  }
}

function setupModal(triggerId, modalId, onOpen = null) {
  const trigger = triggerId ? document.getElementById(triggerId) : null;
  const modal = document.getElementById(modalId);
  if (!modal) return;

  trigger?.addEventListener("click", () => {
    modal.classList.add("active");
    modal.classList.add("open");
    if (onOpen) onOpen();
  });

  modal.querySelectorAll(".modal-close-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      modal.classList.remove("active");
      modal.classList.remove("open");
    });
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.remove("active");
      modal.classList.remove("open");
    }
  });
}

function openModal(modalId, onOpen = null) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.classList.add("active");
  modal.classList.add("open");
  if (onOpen) onOpen();
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.classList.remove("active");
  modal.classList.remove("open");
}

function downloadFile(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ================= DEDICATED STORAGE VAULT VIEW =================

let dedicatedVaultSec = "all";
let dedicatedVaultSearchQuery = "";



async function loadDedicatedVaultWorkspace() {
  const grid = document.getElementById("dedicated-vault-grid");
  const badge = document.getElementById("vault-total-count-badge");
  if (grid) grid.innerHTML = "<div style='color:var(--text-muted); font-size:13px;'>Loading Storage Vault repository...</div>";

  try {
    const res = await fetch("/api/profile");
    rawVaultProfile = await res.json();

    const projs = rawVaultProfile.projects || [];
    const exps = rawVaultProfile.experiences || [];
    const skills = rawVaultProfile.skills || {};
    const pcs = rawVaultProfile.patents_certifications || [];
    const pors = rawVaultProfile.pors_achievements || [];
    const awards = rawVaultProfile.awards_medals || [];
    const cw = rawVaultProfile.coursework || {};

    const totalCount = projs.length + exps.length + Object.keys(skills).length + pcs.length + pors.length + awards.length + Object.keys(cw).length;
    if (badge) badge.textContent = `✓ ${totalCount} Career Records Archived`;

    renderDedicatedVaultGrid();
  } catch (err) {
    if (grid) grid.innerHTML = `<div style='color:#f43f5e;'>Error loading vault: ${err.message}</div>`;
  }
}

function renderDedicatedVaultGrid() {
  const grid = document.getElementById("dedicated-vault-grid");
  if (!grid || !rawVaultProfile) return;
  grid.innerHTML = "";

  const q = (dedicatedVaultSearchQuery || "").toLowerCase();
  const sec = dedicatedVaultSec || "all";
  let renderedCount = 0;

  // Active items for badges
  const activePids = activeProjectIds || (currentResumeData?.projects || []).map(p => p.id);
  const activeEids = activeExperienceIds || (currentResumeData?.experiences || []).map(e => e.id);
  const activeSkNames = (activeSkills || (currentResumeData?.skills || [])).map(s => s.category.toLowerCase());

  // 1. Projects
  if (sec === "all" || sec === "projects") {
    (rawVaultProfile.projects || []).forEach(proj => {
      const matchQ = !q || (proj.title || "").toLowerCase().includes(q) ||
        (proj.context || "").toLowerCase().includes(q) ||
        (proj.bullets || []).some(b => b.toLowerCase().includes(q)) ||
        (proj.tags || []).some(t => t.toLowerCase().includes(q));

      if (!matchQ) return;
      renderedCount++;

      const isAct = activePids.includes(proj.id);
      const pt1 = (proj.points_tier && proj.points_tier["1"]) ? proj.points_tier["1"][0] : (proj.bullets ? proj.bullets[0] : "");
      const pt2 = (proj.points_tier && proj.points_tier["2"] && proj.points_tier["2"][1]) ? proj.points_tier["2"][1] : (proj.bullets && proj.bullets[1] ? proj.bullets[1] : "");
      const pt3 = (proj.points_tier && proj.points_tier["3"] && proj.points_tier["3"][2]) ? proj.points_tier["3"][2] : (proj.bullets && proj.bullets[2] ? proj.bullets[2] : "");

      const card = document.createElement("div");
      card.className = "vault-item-card";
      card.innerHTML = `
        <div class="vault-item-header">
          <div>
            <span class="pill-badge" style="background:rgba(99,102,241,0.15); color:#818cf8; font-size:10px; margin-bottom:4px; display:inline-block;">📁 Project (1/2/3 Pts)</span>
            <div style="font-weight:700; font-size:14px; color:#fff;">${proj.title}</div>
            <div style="font-size:11px; color:#a5b4fc; margin-top:2px;">${proj.context || ''}</div>
            <div style="font-size:10px; color:#6366f1; margin-top:4px;">
              ${(proj.tags || []).map(t => '#' + t).join(' ')}
            </div>
          </div>
          ${isAct
            ? `<span class="pill-badge badge-green" style="font-size:10px; align-self:flex-start;">✓ In Resume</span>`
            : `<span class="pill-badge badge-gold" style="font-size:10px; align-self:flex-start;">In Vault</span>`}
        </div>

        <div class="vault-tier-preview" style="margin-top:8px;">
          <div><b style="color:#818cf8;">Pt 1:</b> ${pt1 ? pt1.replace(/<[^>]*>?/gm, '').slice(0, 120) + '...' : 'None'}</div>
          ${pt2 ? `<div style="margin-top:4px;"><b style="color:#818cf8;">Pt 2:</b> ${pt2.replace(/<[^>]*>?/gm, '').slice(0, 120) + '...'}</div>` : ''}
          ${pt3 ? `<div style="margin-top:4px;"><b style="color:#818cf8;">Pt 3:</b> ${pt3.replace(/<[^>]*>?/gm, '').slice(0, 120) + '...'}</div>` : ''}
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; border-top:1px solid rgba(255,255,255,0.06); padding-top:8px;">
          <div style="display:flex; gap:6px;">
            <button class="btn btn-secondary btn-sm edit-proj-grid-btn" data-id="${proj.id}">✏️ Edit</button>
            <button class="btn btn-secondary btn-sm delete-proj-grid-btn" data-id="${proj.id}" style="color:#f43f5e;">🗑️</button>
          </div>
          ${!isAct ? `
            <button class="btn btn-primary btn-sm add-proj-to-canvas-btn" data-id="${proj.id}">+ Add to Resume</button>
          ` : `
            <button class="btn btn-secondary btn-sm remove-proj-from-canvas-btn" data-id="${proj.id}" style="color:#f43f5e;">✕ Remove</button>
          `}
        </div>
      `;
      grid.appendChild(card);
    });
  }

  // 2. Experiences
  if (sec === "all" || sec === "experiences") {
    (rawVaultProfile.experiences || []).forEach(exp => {
      const matchQ = !q || (exp.role || "").toLowerCase().includes(q) ||
        (exp.company || "").toLowerCase().includes(q) ||
        (exp.duration || "").toLowerCase().includes(q) ||
        (exp.bullets || []).some(b => b.toLowerCase().includes(q)) ||
        (exp.tags || []).some(t => t.toLowerCase().includes(q));

      if (!matchQ) return;
      renderedCount++;

      const isAct = activeEids.includes(exp.id);
      const b1 = (exp.bullets && exp.bullets[0]) ? exp.bullets[0] : "";
      const b2 = (exp.bullets && exp.bullets[1]) ? exp.bullets[1] : "";

      const card = document.createElement("div");
      card.className = "vault-item-card";
      card.innerHTML = `
        <div class="vault-item-header">
          <div>
            <span class="pill-badge" style="background:rgba(52,211,153,0.15); color:#34d399; font-size:10px; margin-bottom:4px; display:inline-block;">🏢 Work Experience</span>
            <div style="font-weight:700; font-size:14px; color:#fff;">${exp.role}</div>
            <div style="font-size:11px; color:#a7f3d0; margin-top:2px;">${exp.company} (${exp.duration}) • ${exp.location}</div>
            <div style="font-size:10px; color:#059669; margin-top:4px;">
              ${(exp.tags || []).map(t => '#' + t).join(' ')}
            </div>
          </div>
          ${isAct
            ? `<span class="pill-badge badge-green" style="font-size:10px; align-self:flex-start;">✓ In Resume</span>`
            : `<span class="pill-badge badge-gold" style="font-size:10px; align-self:flex-start;">In Vault</span>`}
        </div>

        <div class="vault-tier-preview" style="margin-top:8px;">
          <div><b>Bullet 1:</b> ${b1 ? b1.replace(/<[^>]*>?/gm, '').slice(0, 130) + '...' : 'None'}</div>
          ${b2 ? `<div style="margin-top:4px;"><b>Bullet 2:</b> ${b2.replace(/<[^>]*>?/gm, '').slice(0, 130) + '...'}</div>` : ''}
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; border-top:1px solid rgba(255,255,255,0.06); padding-top:8px;">
          <div style="display:flex; gap:6px;">
            <button class="btn btn-secondary btn-sm edit-exp-grid-btn" data-id="${exp.id}">✏️ Edit</button>
            <button class="btn btn-secondary btn-sm delete-exp-grid-btn" data-id="${exp.id}" style="color:#f43f5e;">🗑️</button>
          </div>
          ${!isAct ? `
            <button class="btn btn-primary btn-sm add-exp-to-canvas-btn" data-id="${exp.id}">+ Add to Resume</button>
          ` : `
            <button class="btn btn-secondary btn-sm remove-exp-from-canvas-btn" data-id="${exp.id}" style="color:#f43f5e;">✕ Remove</button>
          `}
        </div>
      `;
      grid.appendChild(card);
    });
  }

  // 3. Skills Catalog
  if (sec === "all" || sec === "skills") {
    Object.entries(rawVaultProfile.skills || {}).forEach(([cat, list]) => {
      const listStr = Array.isArray(list) ? list.join(", ") : String(list);
      const dispName = formatSkillCatName(cat);
      const matchQ = !q || cat.toLowerCase().includes(q) ||
        dispName.toLowerCase().includes(q) ||
        listStr.toLowerCase().includes(q);

      if (!matchQ) return;
      renderedCount++;

      const isAct = activeSkNames.includes(dispName.toLowerCase()) || activeSkNames.includes(cat.toLowerCase());

      const card = document.createElement("div");
      card.className = "vault-item-card";
      card.innerHTML = `
        <div class="vault-item-header">
          <div>
            <span class="pill-badge" style="background:rgba(6,182,212,0.15); color:#22d3ee; font-size:10px; margin-bottom:4px; display:inline-block;">🏷️ Skill Domain</span>
            <div style="font-weight:700; font-size:14px; color:var(--accent-cyan);">${dispName}</div>
            <div style="font-size:10px; color:var(--text-muted); margin-top:2px;">Storage ID: ${cat}</div>
          </div>
          ${isAct
            ? `<span class="pill-badge badge-green" style="font-size:10px; align-self:flex-start;">✓ In Resume</span>`
            : `<span class="pill-badge badge-gold" style="font-size:10px; align-self:flex-start;">In Vault</span>`}
        </div>

        <div style="font-size:11.5px; color:#e2e8f0; line-height:1.45; margin-top:8px;">
          ${listStr}
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; border-top:1px solid rgba(255,255,255,0.06); padding-top:8px;">
          <div style="display:flex; gap:6px;">
            <button class="btn btn-secondary btn-sm edit-skill-grid-btn" data-cat="${cat}" data-entries="${encodeURIComponent(listStr)}">✏️ Edit</button>
            <button class="btn btn-secondary btn-sm delete-skill-grid-btn" data-cat="${cat}" style="color:#f43f5e;">🗑️</button>
          </div>
          ${!isAct ? `
            <button class="btn btn-primary btn-sm add-skill-to-canvas-btn" data-cat="${dispName}" data-entries="${encodeURIComponent(listStr)}">+ Add to Resume</button>
          ` : `
            <button class="btn btn-secondary btn-sm remove-skill-from-canvas-btn" data-cat="${dispName}" style="color:#f43f5e;">✕ Remove</button>
          `}
        </div>
      `;
      grid.appendChild(card);
    });
  }

  // 4. Patents & Certifications
  if (sec === "all" || sec === "patents_certifications") {
    (rawVaultProfile.patents_certifications || []).forEach(pc => {
      const matchQ = !q || (pc.title || "").toLowerCase().includes(q) || (pc.details || "").toLowerCase().includes(q) || (pc.tags || []).some(t => t.toLowerCase().includes(q));
      if (!matchQ) return;
      renderedCount++;

      const card = document.createElement("div");
      card.className = "vault-item-card";
      card.innerHTML = `
        <div class="vault-item-header">
          <div>
            <span class="pill-badge" style="background:rgba(234,179,8,0.15); color:#facc15; font-size:10px; margin-bottom:4px; display:inline-block;">📜 Patent / Cert</span>
            <div style="font-weight:700; font-size:13.5px; color:#fff;">${pc.title}</div>
            <div style="font-size:10px; color:#a855f7; margin-top:3px;">${(pc.tags || []).map(t => '#' + t).join(' ')}</div>
          </div>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-secondary btn-sm edit-pc-grid-btn" data-id="${pc.title}">✏️</button>
            <button class="btn btn-secondary btn-sm delete-pc-grid-btn" data-id="${pc.title}" style="color:#f43f5e;">🗑️</button>
          </div>
        </div>
        <div style="font-size:11.5px; color:#cbd5e1; line-height:1.4; margin-top:6px;">
          ${pc.details || ''}
        </div>
      `;
      grid.appendChild(card);
    });
  }

  // 5. POR & Achievements
  if (sec === "all" || sec === "pors_achievements") {
    (rawVaultProfile.pors_achievements || []).forEach(por => {
      const matchQ = !q || (por.title || "").toLowerCase().includes(q) || (por.details || "").toLowerCase().includes(q) || (por.tags || []).some(t => t.toLowerCase().includes(q));
      if (!matchQ) return;
      renderedCount++;

      const card = document.createElement("div");
      card.className = "vault-item-card";
      card.innerHTML = `
        <div class="vault-item-header">
          <div>
            <span class="pill-badge" style="background:rgba(244,63,94,0.15); color:#fb7185; font-size:10px; margin-bottom:4px; display:inline-block;">🏆 POR & Responsibility</span>
            <div style="font-weight:700; font-size:13.5px; color:#fff;">${por.title}</div>
            <div style="font-size:10px; color:#a855f7; margin-top:3px;">${(por.tags || []).map(t => '#' + t).join(' ')}</div>
          </div>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-secondary btn-sm edit-por-grid-btn" data-id="${por.title}">✏️</button>
            <button class="btn btn-secondary btn-sm delete-por-grid-btn" data-id="${por.title}" style="color:#f43f5e;">🗑️</button>
          </div>
        </div>
        <div style="font-size:11.5px; color:#cbd5e1; line-height:1.4; margin-top:6px;">
          ${por.details || ''}
        </div>
      `;
      grid.appendChild(card);
    });
  }

  // 6. Awards & Medals
  if (sec === "all" || sec === "awards_medals") {
    (rawVaultProfile.awards_medals || []).forEach(aw => {
      const matchQ = !q || (aw.title || "").toLowerCase().includes(q) || (aw.details || "").toLowerCase().includes(q) || (aw.tags || []).some(t => t.toLowerCase().includes(q));
      if (!matchQ) return;
      renderedCount++;

      const card = document.createElement("div");
      card.className = "vault-item-card";
      card.innerHTML = `
        <div class="vault-item-header">
          <div>
            <span class="pill-badge" style="background:rgba(16,185,129,0.15); color:#34d399; font-size:10px; margin-bottom:4px; display:inline-block;">🎖️ Award / Medal</span>
            <div style="font-weight:700; font-size:13.5px; color:#fff;">${aw.title}</div>
            <div style="font-size:10px; color:#a855f7; margin-top:3px;">${(aw.tags || []).map(t => '#' + t).join(' ')}</div>
          </div>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-secondary btn-sm edit-award-grid-btn" data-id="${aw.title}">✏️</button>
            <button class="btn btn-secondary btn-sm delete-award-grid-btn" data-id="${aw.title}" style="color:#f43f5e;">🗑️</button>
          </div>
        </div>
        <div style="font-size:11.5px; color:#cbd5e1; line-height:1.4; margin-top:6px;">
          ${aw.details || ''}
        </div>
      `;
      grid.appendChild(card);
    });
  }

  // 7. Coursework
  if (sec === "all" || sec === "coursework") {
    Object.entries(rawVaultProfile.coursework || {}).forEach(([cat, list]) => {
      const listStr = Array.isArray(list) ? list.join(", ") : String(list);
      const matchQ = !q || cat.toLowerCase().includes(q) || listStr.toLowerCase().includes(q);
      if (!matchQ) return;
      renderedCount++;

      const card = document.createElement("div");
      card.className = "vault-item-card";
      card.innerHTML = `
        <div class="vault-item-header">
          <div>
            <span class="pill-badge" style="background:rgba(147,51,234,0.15); color:#c084fc; font-size:10px; margin-bottom:4px; display:inline-block;">📚 Academic Coursework</span>
            <div style="font-weight:700; font-size:13.5px; color:#c084fc; text-transform:uppercase;">${cat.replace('_', ' ')}</div>
          </div>
        </div>
        <div style="font-size:11.5px; color:#e2e8f0; line-height:1.4; margin-top:6px;">
          ${listStr}
        </div>
      `;
      grid.appendChild(card);
    });
  }

  if (renderedCount === 0) {
    grid.innerHTML = "<div style='color:var(--text-muted); font-size:13px;'>No matching items found in Storage Vault.</div>";
    return;
  }

  // Wire up Project actions
  grid.querySelectorAll(".edit-proj-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => openItemEditor("proj", btn.dataset.id));
  });
  grid.querySelectorAll(".delete-proj-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => deleteVaultRecordItem("projects", btn.dataset.id));
  });
  grid.querySelectorAll(".add-proj-to-canvas-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      if (!activeProjectIds) activeProjectIds = (currentResumeData?.projects || []).map(p => p.id);
      if (!activeProjectIds.includes(id)) activeProjectIds.push(id);
      switchAppView("builder");
      loadResume(currentCategory);
    });
  });
  grid.querySelectorAll(".remove-proj-from-canvas-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      activeProjectIds = (activeProjectIds || []).filter(pid => pid !== id);
      renderDedicatedVaultGrid();
      loadResume(currentCategory);
    });
  });

  // Wire up Experience actions
  grid.querySelectorAll(".edit-exp-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => openItemEditor("exp", btn.dataset.id));
  });
  grid.querySelectorAll(".delete-exp-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => deleteVaultRecordItem("experiences", btn.dataset.id));
  });
  grid.querySelectorAll(".add-exp-to-canvas-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      if (!activeExperienceIds) activeExperienceIds = (currentResumeData?.experiences || []).map(e => e.id);
      if (!activeExperienceIds.includes(id)) activeExperienceIds.push(id);
      switchAppView("builder");
      loadResume(currentCategory);
    });
  });
  grid.querySelectorAll(".remove-exp-from-canvas-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      activeExperienceIds = (activeExperienceIds || []).filter(eid => eid !== id);
      renderDedicatedVaultGrid();
      loadResume(currentCategory);
    });
  });

  // Wire up Skill actions
  grid.querySelectorAll(".edit-skill-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const cat = btn.dataset.cat;
      const entries = decodeURIComponent(btn.dataset.entries);
      openSkillCategoryEditor(cat, entries);
    });
  });
  grid.querySelectorAll(".delete-skill-grid-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const cat = btn.dataset.cat;
      if (!confirm(`Delete skill category "${cat}" from Storage Vault?`)) return;
      await fetch("/api/profile/delete_skill_category", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat })
      });
      if (activeSkills) {
        const fmt = formatSkillCatName(cat).toLowerCase();
        activeSkills = activeSkills.filter(s => s.category.toLowerCase() !== fmt && s.category.toLowerCase() !== cat.toLowerCase());
      }
      await loadDedicatedVaultWorkspace();
      loadResume(currentCategory);
    });
  });
  grid.querySelectorAll(".add-skill-to-canvas-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const cat = btn.dataset.cat;
      const entries = decodeURIComponent(btn.dataset.entries);
      if (!activeSkills) activeSkills = (currentResumeData?.skills || []).map(s => ({ category: s.category, entries: s.entries }));
      activeSkills.push({ category: cat, entries });
      switchAppView("builder");
      loadResume(currentCategory);
    });
  });
  grid.querySelectorAll(".remove-skill-from-canvas-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const cat = btn.dataset.cat.toLowerCase();
      activeSkills = (activeSkills || []).filter(s => s.category.toLowerCase() !== cat);
      renderDedicatedVaultGrid();
      loadResume(currentCategory);
    });
  });

  // Wire up Patents, POR, Awards
  grid.querySelectorAll(".edit-pc-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => openItemEditor("pc", btn.dataset.id));
  });
  grid.querySelectorAll(".delete-pc-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => deleteVaultRecordItem("patents_certifications", btn.dataset.id));
  });

  grid.querySelectorAll(".edit-por-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => openItemEditor("por", btn.dataset.id));
  });
  grid.querySelectorAll(".delete-por-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => deleteVaultRecordItem("pors_achievements", btn.dataset.id));
  });

  grid.querySelectorAll(".edit-award-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => openItemEditor("award", btn.dataset.id));
  });
  grid.querySelectorAll(".delete-award-grid-btn").forEach(btn => {
    btn.addEventListener("click", () => deleteVaultRecordItem("awards_medals", btn.dataset.id));
  });
}

async function deleteVaultRecordItem(section, id) {
  if (!confirm(`Delete record from Storage Vault?`)) return;
  await fetch("/api/profile/delete_item", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section, id })
  });

  if (section === "projects" && activeProjectIds) {
    activeProjectIds = activeProjectIds.filter(pid => pid !== id);
  } else if (section === "experiences" && activeExperienceIds) {
    activeExperienceIds = activeExperienceIds.filter(eid => eid !== id);
  }

  await loadDedicatedVaultWorkspace();
  loadResume(currentCategory);
}

// ==================== V2 CAREER OS EXTENSIONS ====================

let lastATSResult = null;
let lastParsedJD = null;
let activeCriticTarget = null; // { type, id, bulletIdx, bulletText }

function setupV2EventListeners() {
  // 1. Top Navigation & Home Hub Switchers
  document.getElementById("nav-btn-hub")?.addEventListener("click", () => switchAppView("hub"));
  document.getElementById("logo-home-btn")?.addEventListener("click", () => switchAppView("hub"));
  document.getElementById("nav-btn-builder")?.addEventListener("click", () => switchAppView("builder"));
  document.getElementById("nav-btn-vault")?.addEventListener("click", () => switchAppView("vault"));
  document.getElementById("nav-btn-tracker")?.addEventListener("click", () => switchAppView("tracker"));
  document.getElementById("nav-btn-cover")?.addEventListener("click", () => switchAppView("cover"));
  document.getElementById("btn-switch-to-builder")?.addEventListener("click", () => switchAppView("builder"));

  // Universal Back to Hub buttons across all views
  document.querySelectorAll(".btn-back-hub").forEach(btn => {
    btn.addEventListener("click", () => switchAppView("hub"));
  });

  // Home Hub Platform Cards (Click to launch workspace)
  document.querySelectorAll(".hub-card").forEach(card => {
    card.addEventListener("click", () => {
      const view = card.dataset.view;
      if (view) switchAppView(view);
    });
  });

  // Hub Footer Quick Integrations
  document.getElementById("btn-hub-github")?.addEventListener("click", () => {
    openModal("modal-github", loadGitHubRepos);
  });
  document.getElementById("btn-hub-linkedin")?.addEventListener("click", () => {
    openModal("modal-linkedin");
  });
  document.getElementById("btn-hub-ats")?.addEventListener("click", () => {
    openATSBreakdownModal();
  });

  // 2. ATS Score Badge & Modal
  document.getElementById("btn-open-ats")?.addEventListener("click", () => openATSBreakdownModal());

  // 3. Multi-LLM Provider Settings
  document.getElementById("btn-open-llm-settings")?.addEventListener("click", () => openLLMSettingsModal());
  document.getElementById("btn-save-llm-settings")?.addEventListener("click", () => saveLLMSettings());

  // 4. JD Parser & Gap Analysis
  document.getElementById("btn-parse-jd")?.addEventListener("click", () => handleParseJD());

  // 5. CRM Logging
  document.getElementById("btn-save-to-crm")?.addEventListener("click", () => saveCurrentToCRM());
  document.getElementById("btn-add-tracker-app")?.addEventListener("click", () => openTrackerAddModal());
  document.getElementById("btn-tracker-submit-add")?.addEventListener("click", () => submitTrackerAdd());

  // 6. Cover Letter Studio
  document.getElementById("btn-gen-cover-letter")?.addEventListener("click", () => generateCoverLetter());
  document.getElementById("btn-cl-copy-text")?.addEventListener("click", () => copyCoverLetterText());
  document.getElementById("btn-cl-download-html")?.addEventListener("click", () => downloadCoverLetterHTML());
  document.getElementById("btn-cl-print-pdf")?.addEventListener("click", () => printCoverLetterPDF());
  document.getElementById("btn-cl-link-tracker")?.addEventListener("click", () => linkCoverLetterToCRM());

  // 7. Bullet Critic
  document.getElementById("btn-critic-rewrite-ai")?.addEventListener("click", () => generateCriticAIRewrite());
  document.getElementById("btn-critic-apply")?.addEventListener("click", () => applyCriticRewrite());

  // Wire inspect critic button delegations on active cards
  document.addEventListener("click", (e) => {
    const criticBtn = e.target.closest(".inspect-bullets-critic-btn");
    if (criticBtn) {
      const type = criticBtn.dataset.type;
      const id = criticBtn.dataset.id;
      openBulletCritic(type, id);
    }
  });

  // 8. Mobile Subview Switchers (Phone UI)
  const builderEl = document.getElementById("view-resume-builder");
  const btnMBuilderEdit = document.getElementById("btn-m-builder-edit");
  const btnMBuilderPreview = document.getElementById("btn-m-builder-preview");
  const btnMJumpPreview = document.getElementById("btn-m-jump-preview");
  const btnMBackEditor = document.getElementById("btn-m-back-editor");

  function setMobileBuilderMode(mode) {
    if (mode === "preview") {
      builderEl?.classList.add("mobile-show-preview");
      btnMBuilderPreview?.classList.add("active");
      btnMBuilderEdit?.classList.remove("active");
      setTimeout(autoFitMobileZoom, 50);
    } else {
      builderEl?.classList.remove("mobile-show-preview");
      btnMBuilderEdit?.classList.add("active");
      btnMBuilderPreview?.classList.remove("active");
    }
  }

  btnMBuilderEdit?.addEventListener("click", () => setMobileBuilderMode("edit"));
  btnMBuilderPreview?.addEventListener("click", () => setMobileBuilderMode("preview"));
  btnMJumpPreview?.addEventListener("click", () => setMobileBuilderMode("preview"));
  btnMBackEditor?.addEventListener("click", () => setMobileBuilderMode("edit"));

  const coverEl = document.getElementById("view-cover-letter");
  const btnMCoverEdit = document.getElementById("btn-m-cover-edit");
  const btnMCoverPreview = document.getElementById("btn-m-cover-preview");
  const btnMJumpClPreview = document.getElementById("btn-m-jump-cl-preview");
  const btnMBackClEditor = document.getElementById("btn-m-back-cl-editor");

  function setMobileCoverMode(mode) {
    if (mode === "preview") {
      coverEl?.classList.add("mobile-show-preview");
      btnMCoverPreview?.classList.add("active");
      btnMCoverEdit?.classList.remove("active");
      setTimeout(autoFitMobileZoom, 50);
    } else {
      coverEl?.classList.remove("mobile-show-preview");
      btnMCoverEdit?.classList.add("active");
      btnMCoverPreview?.classList.remove("active");
    }
  }

  btnMCoverEdit?.addEventListener("click", () => setMobileCoverMode("edit"));
  btnMCoverPreview?.addEventListener("click", () => setMobileCoverMode("preview"));
  btnMJumpClPreview?.addEventListener("click", () => setMobileCoverMode("preview"));
  btnMBackClEditor?.addEventListener("click", () => setMobileCoverMode("edit"));

  // Handle window resize for mobile auto-fit zoom
  window.addEventListener("resize", () => {
    if (window.innerWidth < 860) {
      autoFitMobileZoom();
    }
  });
}

function switchAppView(viewName) {
  const views = {
    hub: document.getElementById("view-home-hub"),
    builder: document.getElementById("view-resume-builder"),
    vault: document.getElementById("view-storage-vault"),
    tracker: document.getElementById("view-application-tracker"),
    cover: document.getElementById("view-cover-letter")
  };

  const navBtns = {
    hub: document.getElementById("nav-btn-hub"),
    builder: document.getElementById("nav-btn-builder"),
    vault: document.getElementById("nav-btn-vault"),
    tracker: document.getElementById("nav-btn-tracker"),
    cover: document.getElementById("nav-btn-cover")
  };

  // Toggle views without overriding CSS media query rules
  Object.keys(views).forEach(key => {
    if (views[key]) {
      if (key === viewName) {
        views[key].style.display = "";
      } else {
        views[key].style.display = "none";
      }
    }
    if (navBtns[key]) {
      if (key === viewName) {
        navBtns[key].classList.add("active");
      } else {
        navBtns[key].classList.remove("active");
      }
    }
  });

  // Action on switch
  if (viewName === "vault") {
    loadDedicatedVaultWorkspace();
  } else if (viewName === "tracker") {
    loadTrackerBoard();
  } else if (viewName === "cover") {
    initCoverLetterStudio();
    if (window.innerWidth < 860) setTimeout(autoFitMobileZoom, 60);
  } else if (viewName === "builder") {
    if (currentHtml) updatePreview(currentHtml);
    if (window.innerWidth < 860) setTimeout(autoFitMobileZoom, 60);
  }
}

// ==================== ATS SCORER & GAP ANALYSIS ====================

async function updateATSScore() {
  if (!currentResumeData) return;
  try {
    const kws = lastParsedJD?.target_keywords || null;
    const res = await fetch("/api/ats/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_data: currentResumeData,
        jd_keywords: kws
      })
    });
    const data = await res.json();
    if (data.status === "success") {
      lastATSResult = data.score;
      const scoreEl = document.getElementById("hdr-ats-score");
      const hubScoreEl = document.getElementById("hub-ats-val");
      const badgeBtn = document.getElementById("btn-open-ats");
      const hubBadgeBtn = document.getElementById("btn-hub-ats");
      if (scoreEl) scoreEl.textContent = data.score.total_score;
      if (hubScoreEl) hubScoreEl.textContent = data.score.total_score;
      const cls = `ats-score-badge ${data.score.total_score >= 85 ? 'elite' : data.score.total_score >= 75 ? 'good' : 'warn'}`;
      if (badgeBtn) {
        badgeBtn.className = cls;
        badgeBtn.title = `ATS Grade: ${data.score.grade} (${data.score.status}) — Click for breakdown`;
      }
      if (hubBadgeBtn) {
        hubBadgeBtn.className = cls;
      }
    }
  } catch (e) {
    console.error("ATS score error:", e);
  }
}

function openATSBreakdownModal() {
  const modal = document.getElementById("modal-ats-breakdown");
  if (!modal || !lastATSResult) return;

  document.getElementById("ats-big-score").textContent = lastATSResult.total_score;
  document.getElementById("ats-modal-grade").textContent = `Grade ${lastATSResult.grade} (${lastATSResult.status})`;
  document.getElementById("ats-status-title").textContent = `${lastATSResult.status} (1-Page Compliant)`;

  // Breakdown numbers & progress bars
  const bd = lastATSResult.breakdown;
  document.getElementById("ats-val-kws").textContent = `${bd.keywords} / 35`;
  document.getElementById("ats-fill-kws").style.width = `${(bd.keywords / 35) * 100}%`;

  document.getElementById("ats-val-metrics").textContent = `${bd.metrics} / 25`;
  document.getElementById("ats-fill-metrics").style.width = `${(bd.metrics / 25) * 100}%`;

  document.getElementById("ats-val-verbs").textContent = `${bd.action_verbs} / 20`;
  document.getElementById("ats-fill-verbs").style.width = `${(bd.action_verbs / 20) * 100}%`;

  document.getElementById("ats-val-format").textContent = `${bd.formatting} / 20`;
  document.getElementById("ats-fill-format").style.width = `${(bd.formatting / 20) * 100}%`;

  // Suggestions checklist
  const sugList = document.getElementById("ats-suggestions-list");
  sugList.innerHTML = "";
  if (lastATSResult.suggestions && lastATSResult.suggestions.length > 0) {
    lastATSResult.suggestions.forEach(sug => {
      const item = document.createElement("div");
      item.style.padding = "6px 8px";
      item.style.background = "rgba(255,255,255,0.03)";
      item.style.border = "1px solid rgba(255,255,255,0.08)";
      item.style.borderRadius = "5px";
      item.innerHTML = `<span style="color:var(--accent-gold);">⚡</span> ${sug}`;
      sugList.appendChild(item);
    });
  } else {
    sugList.innerHTML = "<div style='color:var(--accent-emerald); font-weight:600;'>✓ All Wall Street & Silicon Valley ATS checks fully satisfied!</div>";
  }

  modal.classList.add("active");
  modal.classList.add("open");
}

async function handleParseJD() {
  const btn = document.getElementById("btn-parse-jd");
  const jd = document.getElementById("target-jd")?.value.trim() || "";
  const company = document.getElementById("target-company")?.value.trim() || "";
  const role = document.getElementById("target-role")?.value.trim() || "";

  if (!jd) {
    alert("Please paste a Job Description (JD) to parse requirements and perform gap analysis.");
    return;
  }

  const origHtml = btn.innerHTML;
  btn.innerHTML = "⏳ Parsing...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/jd/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jd_text: jd, company, role })
    });
    const data = await res.json();
    if (data.status === "success") {
      lastParsedJD = data.parsed;
      const gap = data.gap_analysis;

      const container = document.getElementById("jd-gap-analysis-container");
      container.style.display = "block";

      const matchedChips = gap.matched_skills.map(s => `<span class="gap-skill-chip matched">✓ ${s}</span>`).join(" ");
      const missingChips = gap.missing_skills.map(s => `<span class="gap-skill-chip missing">+ ${s}</span>`).join(" ");

      container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <b style="color:var(--accent-cyan);">🔍 JD Gap Analysis</b>
          <span class="pill-badge ${gap.match_rate >= 80 ? 'badge-green' : 'badge-gold'}">${gap.match_rate}% Vault Match</span>
        </div>
        <div style="font-size:11px; color:var(--text-muted); margin-bottom:6px;">
          Detected Domain: <b>${gap.jd_domain.toUpperCase()}</b> • Target: <b>${data.parsed.summary}</b>
        </div>
        <div style="margin-bottom:6px;">
          <div style="font-size:10px; color:var(--text-muted); font-weight:700; margin-bottom:2px;">MATCHED SKILLS IN VAULT (${gap.matched_skills.length}):</div>
          ${matchedChips || '<span style="font-size:11px; color:var(--text-muted);">None detected</span>'}
        </div>
        ${gap.missing_skills.length > 0 ? `
        <div>
          <div style="font-size:10px; color:var(--accent-rose); font-weight:700; margin-bottom:2px;">MISSING FROM RESUME (${gap.missing_skills.length}):</div>
          ${missingChips}
        </div>` : ''}
      `;

      updateATSScore();
    }
  } catch (err) {
    console.error("JD parse error:", err);
  } finally {
    btn.innerHTML = origHtml;
    btn.disabled = false;
  }
}

// ==================== MULTI-LLM SETTINGS ====================

async function loadLLMSettingsStatus() {
  try {
    const res = await fetch("/api/settings/llm");
    const data = await res.json();
    const dot = document.getElementById("hdr-llm-dot");
    const lbl = document.getElementById("hdr-llm-text");
    
    let active = data.llm_provider || "auto";
    if (data.has_gemini || data.has_openai || data.has_anthropic) {
      if (dot) dot.textContent = "🟢";
      if (lbl) lbl.textContent = `${active.toUpperCase()} AI Active`;
    } else {
      if (dot) dot.textContent = "⚪";
      if (lbl) lbl.textContent = "Configure AI";
    }
  } catch (e) {
    console.error("LLM settings status error:", e);
  }
}

async function openLLMSettingsModal() {
  const modal = document.getElementById("modal-llm-settings");
  if (!modal) return;
  modal.classList.add("active");
  modal.classList.add("open");

  try {
    const res = await fetch("/api/settings/llm");
    const data = await res.json();
    
    const prefSelect = document.getElementById("llm-pref-provider");
    if (prefSelect) prefSelect.value = data.llm_provider || "auto";

    const costBadge = document.getElementById("llm-total-cost-badge");
    const usageText = document.getElementById("llm-usage-summary-text");
    
    const totalCost = data.usage_summary?.total?.total_cost || 0.0;
    const totalCalls = data.usage_summary?.total?.total_calls || 0;
    
    if (costBadge) costBadge.textContent = `$${totalCost.toFixed(4)} USD`;
    if (usageText) usageText.textContent = `${totalCalls} cached call(s) executed. Fast local retrieval with SQLite AI cache.`;
  } catch (e) {
    console.error(e);
  }
}

async function saveLLMSettings() {
  const provider = document.getElementById("llm-pref-provider")?.value || "auto";
  const geminiKey = document.getElementById("input-llm-gemini-key")?.value;
  const openaiKey = document.getElementById("input-llm-openai-key")?.value;
  const anthropicKey = document.getElementById("input-llm-anthropic-key")?.value;
  const ollamaUrl = document.getElementById("input-llm-ollama-url")?.value;

  const payload = {
    llm_provider: provider
  };
  if (geminiKey) payload.gemini_api_key = geminiKey;
  if (openaiKey) payload.openai_api_key = openaiKey;
  if (anthropicKey) payload.anthropic_api_key = anthropicKey;
  if (ollamaUrl) payload.ollama_endpoint = ollamaUrl;

  try {
    const res = await fetch("/api/settings/llm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === "success") {
      const modal = document.getElementById("modal-llm-settings");
      modal?.classList.remove("active");
      modal?.classList.remove("open");
      loadLLMSettingsStatus();
      checkStatus();
      alert("✓ Multi-LLM provider & credentials saved successfully!");
    }
  } catch (e) {
    console.error("Save LLM settings error:", e);
  }
}

// ==================== APPLICATION LIFECYCLE CRM ====================

async function saveCurrentToCRM() {
  const company = document.getElementById("target-company")?.value.trim() || "Target Firm";
  const role = document.getElementById("target-role")?.value.trim() || "Candidate";
  const jd = document.getElementById("target-jd")?.value.trim() || "";

  try {
    const res = await fetch("/api/tracker/application", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company: company,
        role: role,
        stage: "Applied",
        jd_snapshot: jd,
        resume_data: currentResumeData,
        notes: `Tailored resume version created on ${new Date().toLocaleDateString()}`
      })
    });
    const data = await res.json();
    if (data.status === "success") {
      alert(`✓ Application for ${role} at ${company} logged to CRM Kanban!`);
    }
  } catch (e) {
    console.error("Save to CRM error:", e);
  }
}

async function loadTrackerBoard() {
  const boardEl = document.getElementById("kanban-board-container");
  if (!boardEl) return;
  boardEl.innerHTML = "<div style='color:var(--text-muted); padding:20px;'>Loading Kanban board...</div>";

  try {
    const res = await fetch("/api/tracker/board");
    const data = await res.json();
    if (data.status === "success") {
      renderTrackerBoard(data.board, data.metrics);
    }
  } catch (e) {
    console.error("Load tracker error:", e);
  }
}

function renderTrackerBoard(board, metrics) {
  const boardEl = document.getElementById("kanban-board-container");
  if (!boardEl) return;

  // Update metrics
  document.getElementById("metric-total-apps").textContent = metrics.total_applications || 0;
  document.getElementById("metric-interview-rate").textContent = `${metrics.interview_rate || 0}%`;
  document.getElementById("metric-offer-rate").textContent = `${metrics.offer_rate || 0}%`;
  document.getElementById("tracker-total-badge").textContent = `${metrics.total_applications || 0} Total Applications`;

  boardEl.innerHTML = "";
  const stages = ["Wishlist", "Applied", "Online Assessment", "Interview", "Offer", "Rejected"];

  stages.forEach(stage => {
    const col = document.createElement("div");
    col.className = "kanban-col";
    const apps = board[stage] || [];

    col.innerHTML = `
      <div class="kanban-col-header">
        <span>${stage}</span>
        <span class="pill-badge badge-cyan">${apps.length}</span>
      </div>
      <div class="kanban-col-body" id="col-body-${stage.replace(/\s+/g, '')}">
        ${apps.length === 0 ? `<div style="font-size:11px; color:rgba(255,255,255,0.25); text-align:center; padding:20px 0;">No applications in this stage</div>` : ''}
      </div>
    `;

    const colBody = col.querySelector(".kanban-col-body");

    apps.forEach(app => {
      const card = document.createElement("div");
      card.className = "kanban-card";

      const atsPill = app.ats_score > 0 ? `
        <span class="pill-badge ${app.ats_score >= 85 ? 'badge-green' : 'badge-gold'}" style="font-size:10px;">
          ${app.ats_score} ATS
        </span>` : '';

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <div class="kanban-card-title">${app.company}</div>
            <div class="kanban-card-role">${app.role}</div>
          </div>
          ${atsPill}
        </div>
        ${app.notes ? `<div style="font-size:11px; color:var(--text-muted);">${app.notes}</div>` : ''}
        <div class="kanban-card-footer">
          <select class="input-box stage-move-select" data-id="${app.id}" style="font-size:10px; padding:2px 4px; max-width:140px;">
            ${stages.map(s => `<option value="${s}" ${s === stage ? 'selected' : ''}>→ ${s}</option>`).join('')}
          </select>
          <button class="btn btn-secondary btn-sm delete-app-btn" data-id="${app.id}" style="padding:2px 6px; color:var(--accent-rose);">✕</button>
        </div>
      `;
      colBody.appendChild(card);
    });

    boardEl.appendChild(col);
  });

  // Wire stage move dropdowns
  boardEl.querySelectorAll(".stage-move-select").forEach(sel => {
    sel.addEventListener("change", async (e) => {
      const id = e.target.dataset.id;
      const newStage = e.target.value;
      await fetch("/api/tracker/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, stage: newStage })
      });
      loadTrackerBoard();
    });
  });

  // Wire delete buttons
  boardEl.querySelectorAll(".delete-app-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      if (!confirm("Delete this job application from CRM?")) return;
      await fetch(`/api/tracker/application/${id}`, { method: "DELETE" });
      loadTrackerBoard();
    });
  });
}

function openTrackerAddModal() {
  const modal = document.getElementById("modal-tracker-add");
  if (!modal) return;
  document.getElementById("tracker-add-company").value = document.getElementById("target-company")?.value || "";
  document.getElementById("tracker-add-role").value = document.getElementById("target-role")?.value || "";
  modal.classList.add("active");
  modal.classList.add("open");
}

async function submitTrackerAdd() {
  const company = document.getElementById("tracker-add-company")?.value.trim();
  const role = document.getElementById("tracker-add-role")?.value.trim();
  const stage = document.getElementById("tracker-add-stage")?.value || "Applied";
  const notes = document.getElementById("tracker-add-notes")?.value.trim() || "";

  if (!company || !role) {
    alert("Please enter Company and Role.");
    return;
  }

  try {
    const res = await fetch("/api/tracker/application", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company, role, stage, notes, resume_data: currentResumeData })
    });
    const data = await res.json();
    if (data.status === "success") {
      document.getElementById("modal-tracker-add")?.classList.remove("open");
      loadTrackerBoard();
    }
  } catch (e) {
    console.error("Add application error:", e);
  }
}

// ==================== COVER LETTER STUDIO ====================

let currentCoverLetterHTML = "";
let currentCoverLetterResult = null;

function initCoverLetterStudio() {
  const bCompany = document.getElementById("target-company")?.value || "";
  const bRole = document.getElementById("target-role")?.value || "";
  const bJd = document.getElementById("target-jd")?.value || "";

  const clCompany = document.getElementById("cl-target-company");
  const clRole = document.getElementById("cl-target-role");
  const clJd = document.getElementById("cl-target-jd");

  if (clCompany && !clCompany.value) clCompany.value = bCompany;
  if (clRole && !clRole.value) clRole.value = bRole;
  if (clJd && !clJd.value) clJd.value = bJd;

  if (!currentCoverLetterHTML) {
    generateCoverLetter();
  }
}

async function generateCoverLetter() {
  const company = document.getElementById("cl-target-company")?.value.trim() || "Target Organization";
  const role = document.getElementById("cl-target-role")?.value.trim() || "Engineering / Quantitative Associate";
  const jd = document.getElementById("cl-target-jd")?.value.trim() || "";
  const useLLM = document.getElementById("cl-use-llm")?.checked ?? true;
  const btn = document.getElementById("btn-gen-cover-letter");

  const origText = btn.innerHTML;
  btn.innerHTML = "⚡ Formulating Executive Letter...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/cover_letter/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company, role, jd_text: jd, use_llm: useLLM })
    });
    const data = await res.json();
    if (data.status === "success") {
      currentCoverLetterResult = data.result;
      currentCoverLetterHTML = data.result.html;
      const iframe = document.getElementById("cover-letter-frame");
      if (iframe) {
        const blob = new Blob([data.result.html], { type: "text/html" });
        iframe.src = URL.createObjectURL(blob);
      }
    }
  } catch (e) {
    console.error("Cover letter generation error:", e);
  } finally {
    btn.innerHTML = origText;
    btn.disabled = false;
  }
}

function copyCoverLetterText() {
  if (!currentCoverLetterResult) return;
  const paras = currentCoverLetterResult.paragraphs || [];
  const highlights = (currentCoverLetterResult.key_highlights || []).map(h => `- ${h.replace(/<[^>]+>/g, '')}`).join("\n");
  const text = `${paras.join("\n\n")}\n\n${highlights}\n\n${currentCoverLetterResult.closing || ''}`;
  navigator.clipboard.writeText(text);
  alert("✓ Cover letter text copied to clipboard!");
}

function downloadCoverLetterHTML() {
  if (!currentCoverLetterHTML) return;
  const company = document.getElementById("cl-target-company")?.value.trim() || "Application";
  downloadFile(`Cover_Letter_${company}.html`, currentCoverLetterHTML, "text/html");
}

function printCoverLetterPDF() {
  const iframe = document.getElementById("cover-letter-frame");
  if (iframe) iframe.contentWindow.print();
}

async function linkCoverLetterToCRM() {
  const company = document.getElementById("cl-target-company")?.value.trim() || "Target Firm";
  const role = document.getElementById("cl-target-role")?.value.trim() || "Candidate";
  try {
    await fetch("/api/tracker/application", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company: company,
        role: role,
        stage: "Applied",
        cover_letter: currentCoverLetterHTML
      })
    });
    alert(`✓ Cover letter linked to ${company} application in CRM!`);
  } catch (e) {
    console.error(e);
  }
}

// ==================== BULLET CRITIC (GOOGLE XYZ) ====================

async function openBulletCritic(type, id) {
  let targetItem = null;
  if (type === "proj" && currentResumeData?.projects) {
    targetItem = currentResumeData.projects.find(p => p.id === id);
  } else if (type === "exp" && currentResumeData?.experiences) {
    targetItem = currentResumeData.experiences.find(e => e.id === id);
  }

  if (!targetItem || !targetItem.bullets || targetItem.bullets.length === 0) return;

  // Inspect the first bullet by default (or user selected)
  const bulletText = targetItem.bullets[0];
  activeCriticTarget = { type, id, bulletIdx: 0, bulletText };

  const modal = document.getElementById("modal-bullet-critic");
  if (!modal) return;

  document.getElementById("critic-item-id").value = id;
  document.getElementById("critic-bullet-idx").value = "0";
  document.getElementById("critic-original-bullet").innerHTML = bulletText;
  document.getElementById("critic-rewritten-box").value = "";

  // Call critique API
  try {
    const res = await fetch("/api/bullet/critique", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bullet_text: bulletText })
    });
    const data = await res.json();
    if (data.status === "success") {
      const cr = data.result;
      document.getElementById("critic-score-pill").textContent = `${cr.score} / 100`;
      document.getElementById("critic-score-pill").className = `pill-badge ${cr.score >= 80 ? 'badge-green' : 'badge-gold'}`;
      
      const xyzBadge = document.getElementById("critic-xyz-badge");
      if (cr.xyz_compliant) {
        xyzBadge.textContent = "✓ Google XYZ Compliant";
        xyzBadge.className = "pill-badge badge-green";
      } else {
        xyzBadge.textContent = "⚠ Missing XYZ Metric or Verb";
        xyzBadge.className = "pill-badge badge-rose";
      }

      const fbList = document.getElementById("critic-feedback-list");
      fbList.innerHTML = "";
      cr.strengths.forEach(s => {
        fbList.innerHTML += `<div style="color:var(--accent-emerald);">✓ ${s}</div>`;
      });
      cr.issues.forEach(iss => {
        fbList.innerHTML += `<div style="color:var(--accent-rose);">• ${iss}</div>`;
      });
    }
  } catch (e) {
    console.error("Critique error:", e);
  }

  modal.classList.add("active");
  modal.classList.add("open");
}

async function generateCriticAIRewrite() {
  if (!activeCriticTarget) return;
  const btn = document.getElementById("btn-critic-rewrite-ai");
  const role = document.getElementById("target-role")?.value || currentCategory;

  const orig = btn.innerHTML;
  btn.innerHTML = "⚡ Rewriting...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/bullet/improve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bullet_text: activeCriticTarget.bulletText,
        role_context: role
      })
    });
    const data = await res.json();
    if (data.status === "success" && data.improved_bullet) {
      document.getElementById("critic-rewritten-box").value = data.improved_bullet;
    }
  } catch (e) {
    console.error("Improve bullet error:", e);
  } finally {
    btn.innerHTML = orig;
    btn.disabled = false;
  }
}

async function applyCriticRewrite() {
  const rewritten = document.getElementById("critic-rewritten-box")?.value.trim();
  if (!rewritten || !activeCriticTarget) {
    document.getElementById("modal-bullet-critic")?.classList.remove("open");
    return;
  }

  const { type, id, bulletIdx } = activeCriticTarget;
  if (type === "proj" && currentResumeData?.projects) {
    const p = currentResumeData.projects.find(proj => proj.id === id);
    if (p && p.bullets) {
      p.bullets[bulletIdx] = rewritten;
    }
  } else if (type === "exp" && currentResumeData?.experiences) {
    const exp = currentResumeData.experiences.find(e => e.id === id);
    if (exp && exp.bullets) {
      exp.bullets[bulletIdx] = rewritten;
    }
  }

  document.getElementById("modal-bullet-critic")?.classList.remove("open");

  // Re-render canvas with custom updated bullet
  try {
    const res = await fetch("/api/resume/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_data: currentResumeData,
        font_size: currentFontSize,
        line_height: currentLineHeight
      })
    });
    const data = await res.json();
    currentHtml = data.html;
    currentTex = data.tex;
    updatePreview(data.html);
    updateATSScore();
  } catch (e) {
    console.error("Render after critic error:", e);
  }
}

