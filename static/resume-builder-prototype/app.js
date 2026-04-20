(function () {
  "use strict";

  const STORAGE_KEY =
    typeof window.__TT_STORAGE_KEY === "string" && window.__TT_STORAGE_KEY.trim()
      ? window.__TT_STORAGE_KEY.trim()
      : "resume-builder-data-v2";

  function deepMergeResume(def, srv) {
    if (!srv || typeof srv !== "object") return { ...def };
    const o = { ...def, ...srv };
    const arrKeys = ["skills", "experience", "education", "certifications", "languages"];
    for (const k of arrKeys) {
      if (Array.isArray(srv[k])) o[k] = srv[k].map((x) => (x && typeof x === "object" ? { ...x } : x));
    }
    return o;
  }

  const resumeEl = document.getElementById("resume");
  const resumeMount = document.getElementById("resumeMount");
  const editorMount = document.getElementById("editorMount");
  const colorSchemesEl = document.getElementById("colorSchemes");
  const templateGrid = document.getElementById("templateGrid");
  const fontFamily = document.getElementById("fontFamily");
  const textAlignEl = document.getElementById("textAlignOptions");
  const filterNav = document.getElementById("filterNav");
  const btnPdf = document.getElementById("btnPdf");
  const btnPrint = document.getElementById("btnPrint");
  const btnFinish = document.getElementById("btnFinish");
  const scoreArc = document.getElementById("scoreArc");
  const scoreNum = document.getElementById("scoreNum");

  const COLOR_SCHEMES = [
    { id: "teal", label: "Teal", accent: "#1b9e7a", contrast: "#ffffff" },
    { id: "blue", label: "Blue", accent: "#2563eb", contrast: "#ffffff" },
    { id: "sky", label: "Sky", accent: "#0ea5e9", contrast: "#ffffff" },
    { id: "indigo", label: "Indigo", accent: "#4f46e5", contrast: "#ffffff" },
    { id: "green", label: "Green", accent: "#16a34a", contrast: "#ffffff" },
    { id: "purple", label: "Purple", accent: "#7c3aed", contrast: "#ffffff" },
    { id: "orange", label: "Orange", accent: "#ea580c", contrast: "#ffffff" },
    { id: "rose", label: "Rose", accent: "#e11d48", contrast: "#ffffff" },
    { id: "slate", label: "Slate", accent: "#334155", contrast: "#ffffff" },
    { id: "black", label: "Black", accent: "#171717", contrast: "#ffffff" },
  ];

  const FONTS = [
    { value: '"Source Sans 3", system-ui, sans-serif', label: "Source Sans 3" },
    { value: '"Inter", system-ui, sans-serif', label: "Inter" },
    { value: '"DM Sans", system-ui, sans-serif', label: "DM Sans" },
    { value: '"Open Sans", system-ui, sans-serif', label: "Open Sans" },
    { value: '"IBM Plex Sans", system-ui, sans-serif', label: "IBM Plex Sans" },
    { value: '"Lora", Georgia, serif', label: "Lora" },
    { value: '"Merriweather", Georgia, serif', label: "Merriweather" },
    { value: '"Crimson Pro", Georgia, serif', label: "Crimson Pro" },
    { value: '"Playfair Display", Georgia, serif', label: "Playfair Display" },
    { value: '"Outfit", system-ui, sans-serif', label: "Outfit" },
  ];

  const TEXT_ALIGN_OPTIONS = [
    { id: "start", label: "Left", css: "start" },
    { id: "center", label: "Center", css: "center" },
    { id: "end", label: "Right", css: "end" },
    { id: "justify", label: "Justify", css: "justify" },
  ];

  const CATEGORIES = [
    { id: "all", label: "All templates" },
    { id: "modern", label: "Modern" },
    { id: "professional", label: "Professional" },
    { id: "creative", label: "Creative" },
    { id: "simple", label: "Simple" },
  ];

  const DEFAULT_TEMPLATES = [
    { id: "minimalist", name: "Minimalist", category: "simple", mock: "mock-minimalist" },
    { id: "classic-sidebar", name: "Classic Sidebar", category: "professional", mock: "mock-classic-sidebar" },
    { id: "colored-header", name: "Colored Header", category: "modern", mock: "mock-colored-header" },
    { id: "modern-split", name: "Modern Split", category: "modern", mock: "mock-modern-split" },
    { id: "professional-border", name: "Pro Border", category: "professional", mock: "mock-professional-border" },
    { id: "bold-header", name: "Bold Header", category: "creative", mock: "mock-bold-header" },
    { id: "tech-focus", name: "Tech Focus", category: "professional", mock: "mock-tech-focus" },
    { id: "elegant-serif", name: "Elegant Serif", category: "simple", mock: "mock-elegant-serif" },
    { id: "geometric", name: "Geometric", category: "creative", mock: "mock-geometric" },
    { id: "high-contrast", name: "High Contrast", category: "modern", mock: "mock-high-contrast" },
    { id: "aurora", name: "Aurora", category: "creative", mock: "mock-aurora" },
    { id: "magazine", name: "Magazine", category: "creative", mock: "mock-magazine" },
    { id: "timeline", name: "Timeline", category: "modern", mock: "mock-timeline" },
    { id: "executive", name: "Executive", category: "professional", mock: "mock-executive" },
    { id: "studio", name: "Studio", category: "modern", mock: "mock-studio" },
    { id: "nova", name: "Nova", category: "creative", mock: "mock-nova" },
    { id: "ledger", name: "Ledger", category: "professional", mock: "mock-ledger" },
    { id: "horizon", name: "Horizon", category: "modern", mock: "mock-horizon" },
    { id: "folio", name: "Folio", category: "simple", mock: "mock-folio" },
    { id: "vertex", name: "Vertex", category: "creative", mock: "mock-vertex" },
  ];

  function readStudioTemplatesCatalog() {
    var el = document.getElementById("tt-studio-template-catalog");
    if (!el || !String(el.textContent || "").trim()) return DEFAULT_TEMPLATES.slice();
    try {
      var arr = JSON.parse(el.textContent);
      if (!Array.isArray(arr) || !arr.length) return DEFAULT_TEMPLATES.slice();
      var fromServer = arr
        .map(function (row) {
          var id = String((row && (row.id || row.template_key)) || "").trim();
          if (!id) return null;
          var cat = String((row && row.category) || "professional")
            .trim()
            .toLowerCase();
          var mock = String((row && row.mock) || "mock-" + id).trim();
          return {
            id: id,
            name: String((row && row.name) || id).trim(),
            category: cat,
            mock: mock,
          };
        })
        .filter(Boolean);
      // Admin catalog may list only a subset; saved resumes can still reference any
      // RENDERERS id. Merge defaults so prefs + grid resolve (e.g. duplicated copy).
      var seen = new Set();
      var merged = [];
      fromServer.forEach(function (t) {
        if (!seen.has(t.id)) {
          seen.add(t.id);
          merged.push(t);
        }
      });
      DEFAULT_TEMPLATES.forEach(function (t) {
        if (!seen.has(t.id)) {
          seen.add(t.id);
          merged.push(t);
        }
      });
      return merged.length ? merged : DEFAULT_TEMPLATES.slice();
    } catch (e) {
      return DEFAULT_TEMPLATES.slice();
    }
  }

  const TEMPLATES = readStudioTemplatesCatalog();

  let resumeData =
    window.__TT_RESUME_INITIAL && typeof window.__TT_RESUME_INITIAL === "object"
      ? deepMergeResume(defaultResume(), window.__TT_RESUME_INITIAL)
      : defaultResume();
  let activeColorId = "teal";
  let activeTemplateId = "classic-sidebar";
  let activeFilterId = "all";
  let activeTextAlignId = "start";
  let saveTimer = null;

  function defaultResume() {
    return {
      fullName: "Alex Morgan",
      headline: "Senior Product Manager",
      email: "alex@email.com",
      phone: "+1 (555) 123-4567",
      address: "San Francisco, CA",
      linkedin: "linkedin.com/in/alexmorgan",
      website: "alexmorgan.dev",
      summary:
        "Results-driven professional with 6+ years of experience leading cross-functional teams, owning roadmaps, and delivering measurable business outcomes.",
      photo: "",
      skills: [
        { name: "Product strategy & roadmaps", level: 4 },
        { name: "SQL, Excel & analytics", level: 5 },
        { name: "Agile / Scrum delivery", level: 4 },
        { name: "Stakeholder communication", level: 5 },
      ],
      experience: [
        {
          title: "Senior Product Manager",
          company: "Northwind Labs",
          location: "Remote",
          dates: "2021 — Present",
          bullets: [
            "Owned core platform roadmap; improved retention by 18% YoY.",
            "Partnered with engineering and design in agile two-week cycles.",
          ],
        },
        {
          title: "Product Analyst",
          company: "Contoso Inc.",
          location: "New York, NY",
          dates: "2018 — 2021",
          bullets: ["Built dashboards and weekly metrics reviews for leadership."],
        },
      ],
      education: [
        {
          degree: "B.S. Business Administration",
          school: "State University",
          dates: "2014 — 2018",
          detail: "Dean's List",
        },
      ],
      certifications: [
        { name: "Certified Scrum Product Owner (CSPO)", issuer: "Scrum Alliance", date: "2020" },
      ],
      languages: [
        { name: "English", level: "Native" },
        { name: "Spanish", level: "Professional working proficiency" },
      ],
      interests: "Cycling, reading, open-source contributions",
    };
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function photoHtml(d, className) {
    if (d.photo && String(d.photo).trim()) {
      return `<img class="${className}" src="${esc(d.photo)}" alt="" />`;
    }
    return `<div class="${className} tpl-photo tpl-photo--placeholder" aria-hidden="true"></div>`;
  }

  function contactParts(d) {
    const out = [];
    if (d.phone) out.push(esc(d.phone));
    if (d.email) out.push(esc(d.email));
    if (d.address) out.push(esc(d.address));
    if (d.linkedin) out.push(esc(d.linkedin));
    if (d.website) out.push(esc(d.website));
    return out;
  }

  function skillsListHtml(d, numbered) {
    return (d.skills || [])
      .map((s, i) => {
        const nm = esc(s.name || "");
        if (!numbered) return `<li>${nm}</li>`;
        return `<li><span class="tpl-skill-num">${i + 1}.</span> ${nm}</li>`;
      })
      .join("");
  }

  function skillBarsHtml(d) {
    return (d.skills || [])
      .map((s) => {
        const lv = Math.min(5, Math.max(1, Number(s.level) || 3));
        const pct = (lv / 5) * 100;
        return `<div class="tpl-skill-row">
          <span class="tpl-skill-name">${esc(s.name)}</span>
          <div class="tpl-skill-bar" role="presentation"><span style="width:${pct}%"></span></div>
        </div>`;
      })
      .join("");
  }

  function experienceHtml(d, classJob) {
    const cj = classJob || "tpl-job";
    return (d.experience || [])
      .map((exp) => {
        const bullets = (exp.bullets || []).map((b) => `<li>${esc(b)}</li>`).join("");
        return `<div class="${cj}">
          <div class="tpl-job-head">
            <strong>${esc(exp.title)}</strong>
            <span class="tpl-job-dates">${esc(exp.dates)}</span>
          </div>
          <div class="tpl-job-sub">${esc(exp.company)}${exp.location ? " · " + esc(exp.location) : ""}</div>
          ${bullets ? `<ul class="tpl-bullets">${bullets}</ul>` : ""}
        </div>`;
      })
      .join("");
  }

  function educationHtml(d) {
    return (d.education || [])
      .map(
        (ed) => `<div class="tpl-edu-block">
        <div class="tpl-job-head">
          <strong>${esc(ed.degree)}</strong>
          <span class="tpl-job-dates">${esc(ed.dates)}</span>
        </div>
        <div class="tpl-job-sub">${esc(ed.school)}${ed.detail ? " — " + esc(ed.detail) : ""}</div>
      </div>`
      )
      .join("");
  }

  function certificationsHtml(d) {
    return (d.certifications || [])
      .map(
        (c) => `<div class="tpl-cert">
        <strong>${esc(c.name)}</strong>
        <span class="tpl-cert-meta">${esc(c.issuer)}${c.date ? " · " + esc(c.date) : ""}</span>
      </div>`
      )
      .join("");
  }

  function languagesHtml(d) {
    return (d.languages || [])
      .map((l) => `<li><span class="tpl-lang-name">${esc(l.name)}</span> — ${esc(l.level)}</li>`)
      .join("");
  }

  function skillsPillsHtml(d) {
    return (d.skills || [])
      .map((s) => `<span class="tpl-pill">${esc(s.name)}</span>`)
      .join("");
  }

  function experienceTimelineHtml(d) {
    return (d.experience || [])
      .map((exp) => {
        const bullets = (exp.bullets || []).map((b) => `<li>${esc(b)}</li>`).join("");
        return `<div class="tpl-tl-item">
          <span class="tpl-tl-dot"></span>
          <div class="tpl-tl-inner">
            <div class="tpl-job-head">
              <strong>${esc(exp.title)}</strong>
              <span class="tpl-job-dates">${esc(exp.dates)}</span>
            </div>
            <div class="tpl-job-sub">${esc(exp.company)}${exp.location ? " · " + esc(exp.location) : ""}</div>
            ${bullets ? `<ul class="tpl-bullets">${bullets}</ul>` : ""}
          </div>
        </div>`;
      })
      .join("");
  }

  const RENDERERS = {
    minimalist(d) {
      const contact = contactParts(d).join(" · ");
      return `<div class="tpl tpl-minimalist">
        <header class="tpl-min-head">
          <h1 class="tpl-min-name">${esc(d.fullName)}</h1>
          <p class="tpl-min-title">${esc(d.headline)}</p>
          <p class="tpl-min-contact">${contact}</p>
        </header>
        <hr class="tpl-min-rule" />
        <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
        <hr class="tpl-min-rule" />
        <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Experience</h2>${experienceHtml(d, "tpl-job tpl-job--min")}</section>
        <hr class="tpl-min-rule" />
        <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Education</h2>${educationHtml(d)}</section>
        <hr class="tpl-min-rule" />
        <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Skills</h2><ul class="tpl-bullets tpl-bullets--center">${skillsListHtml(d)}</ul></section>
        <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Certifications</h2>${certificationsHtml(d)}</section>
        <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Languages</h2><ul class="tpl-bullets tpl-bullets--center">${languagesHtml(d)}</ul></section>
        <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--center">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
      </div>`;
    },

    "classic-sidebar"(d) {
      return `<div class="tpl tpl-classic-sidebar">
        <aside class="tpl-cs-side">
          ${photoHtml(d, "tpl-avatar")}
          <h1 class="tpl-cs-name">${esc(d.fullName)}</h1>
          <p class="tpl-cs-title">${esc(d.headline)}</p>
          <ul class="tpl-cs-contact">${contactParts(d).map((x) => `<li>${x}</li>`).join("")}</ul>
          <h3 class="tpl-cs-h3">Skills</h3>
          <ul class="tpl-bullets tpl-bullets--tight">${skillsListHtml(d)}</ul>
          <h3 class="tpl-cs-h3">Languages</h3>
          <ul class="tpl-bullets tpl-bullets--tight">${languagesHtml(d)}</ul>
        </aside>
        <div class="tpl-cs-main">
          <section class="tpl-sec"><h2 class="tpl-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-sec"><h2 class="tpl-h2">Experience</h2>${experienceHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Certifications</h2>${certificationsHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    "colored-header"(d) {
      const contact = contactParts(d).join(" · ");
      return `<div class="tpl tpl-colored-header">
        <header class="tpl-ch-bar">
          <h1 class="tpl-ch-name">${esc(d.fullName)}</h1>
          <p class="tpl-ch-title">${esc(d.headline)}</p>
          <p class="tpl-ch-contact">${contact}</p>
        </header>
        <div class="tpl-ch-body">
          <section class="tpl-sec"><h2 class="tpl-h2">Profile</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <div class="tpl-ch-row">
            <section class="tpl-sec tpl-sec--half"><h2 class="tpl-h2">Experience</h2>${experienceHtml(d)}</section>
            <section class="tpl-sec tpl-sec--half">
              <h2 class="tpl-h2">Education</h2>${educationHtml(d)}
              <h2 class="tpl-h2 tpl-h2--spaced">Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul>
            </section>
          </div>
          <section class="tpl-sec"><h2 class="tpl-h2">Certifications &amp; languages</h2>
            <div class="tpl-two-col">${certificationsHtml(d)}</div>
            <ul class="tpl-bullets">${languagesHtml(d)}</ul>
          </section>
          <section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    "modern-split"(d) {
      const contact = contactParts(d).join(" · ");
      return `<div class="tpl tpl-modern-split">
        <header class="tpl-ms-top">
          <div class="tpl-ms-brand">
            ${photoHtml(d, "tpl-ms-photo")}
            <div>
              <h1 class="tpl-ms-name">${esc(d.fullName)}</h1>
              <p class="tpl-ms-title">${esc(d.headline)}</p>
            </div>
          </div>
          <p class="tpl-ms-contact">${contact}</p>
        </header>
        <div class="tpl-ms-grid">
          <section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">📋</span> Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">🎓</span> Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec tpl-ms-span2"><h2 class="tpl-h2"><span class="tpl-ico">💼</span> Experience</h2>${experienceHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">⚡</span> Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul></section>
          <section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">🌐</span> Languages</h2><ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
          <section class="tpl-sec tpl-ms-span2"><h2 class="tpl-h2"><span class="tpl-ico">🏅</span> Certifications</h2>${certificationsHtml(d)}</section>
          <section class="tpl-sec tpl-ms-span2"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    "professional-border"(d) {
      return `<div class="tpl tpl-professional-border">
        <div class="tpl-pb-main">
          <header class="tpl-pb-header">
            <h1 class="tpl-pb-name">${esc(d.fullName)}</h1>
            <p class="tpl-pb-title">${esc(d.headline)}</p>
            <p class="tpl-pb-contact">${contactParts(d).join(" · ")}</p>
          </header>
          <section class="tpl-sec"><h2 class="tpl-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-sec"><h2 class="tpl-h2">Experience</h2>${experienceHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Certifications</h2>${certificationsHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
        <aside class="tpl-pb-side">
          ${photoHtml(d, "tpl-pb-avatar")}
          <h3 class="tpl-pb-h3">Skills</h3>
          <ul class="tpl-bullets tpl-bullets--tight">${skillsListHtml(d)}</ul>
          <h3 class="tpl-pb-h3">Languages</h3>
          <ul class="tpl-bullets tpl-bullets--tight">${languagesHtml(d)}</ul>
        </aside>
      </div>`;
    },

    "bold-header"(d) {
      return `<div class="tpl tpl-bold-header">
        <header class="tpl-bh-bar">
          <h1 class="tpl-bh-name">${esc(d.fullName)}</h1>
          <p class="tpl-bh-title">${esc(d.headline)}</p>
          <p class="tpl-bh-contact">${contactParts(d).join(" · ")}</p>
        </header>
        <div class="tpl-bh-body">
          <section class="tpl-sec"><h2 class="tpl-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-sec"><h2 class="tpl-h2">Experience</h2>${experienceHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul></section>
          <section class="tpl-sec"><h2 class="tpl-h2">Certifications &amp; languages</h2>${certificationsHtml(d)}<ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
          <section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    "tech-focus"(d) {
      return `<div class="tpl tpl-tech-focus">
        <aside class="tpl-tf-side">
          <h2 class="tpl-tf-h2">Skills</h2>
          ${skillBarsHtml(d)}
          <h2 class="tpl-tf-h2">Languages</h2>
          <ul class="tpl-bullets tpl-bullets--tight">${languagesHtml(d)}</ul>
          <h2 class="tpl-tf-h2">Contact</h2>
          <ul class="tpl-bullets tpl-bullets--tight">${contactParts(d).map((x) => `<li>${x}</li>`).join("")}</ul>
        </aside>
        <div class="tpl-tf-main">
          <header class="tpl-tf-head">
            <h1 class="tpl-tf-name">${esc(d.fullName)}</h1>
            <p class="tpl-tf-title">${esc(d.headline)}</p>
          </header>
          <section class="tpl-sec"><h2 class="tpl-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-sec"><h2 class="tpl-h2">Experience</h2>${experienceHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Certifications</h2>${certificationsHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    "elegant-serif"(d) {
      const contact = contactParts(d).join(" · ");
      return `<div class="tpl tpl-elegant-serif">
        <header class="tpl-el-head">
          <h1 class="tpl-el-name">${esc(d.fullName)}</h1>
          <p class="tpl-el-title">${esc(d.headline)}</p>
          <p class="tpl-el-contact">${contact}</p>
        </header>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Summary</h2><p class="tpl-el-p">${esc(d.summary)}</p></section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Experience</h2>${experienceHtml(d, "tpl-job tpl-job--elegant")}</section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Education</h2>${educationHtml(d)}</section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Skills</h2><p class="tpl-el-p">${(d.skills || []).map((s) => esc(s.name)).join(" · ")}</p></section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Certifications</h2>${certificationsHtml(d)}</section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Languages</h2><ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Interests</h2><p class="tpl-el-p">${esc(d.interests)}</p></section>
      </div>`;
    },

    geometric(d) {
      return `<div class="tpl tpl-geometric">
        <header class="tpl-geo-head">
          ${photoHtml(d, "tpl-geo-photo")}
          <div class="tpl-geo-text">
            <h1 class="tpl-geo-name">${esc(d.fullName)}</h1>
            <p class="tpl-geo-title">${esc(d.headline)}</p>
            <p class="tpl-geo-contact">${contactParts(d).join(" · ")}</p>
          </div>
        </header>
        <section class="tpl-sec"><h2 class="tpl-geo-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
        <section class="tpl-sec"><h2 class="tpl-geo-h2">Experience</h2>${experienceHtml(d)}</section>
        <div class="tpl-geo-split">
          <section class="tpl-sec"><h2 class="tpl-geo-h2">Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-geo-h2">Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul></section>
        </div>
        <section class="tpl-sec"><h2 class="tpl-geo-h2">Certifications &amp; languages</h2>${certificationsHtml(d)}<ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
        <section class="tpl-sec"><h2 class="tpl-geo-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
      </div>`;
    },

    "high-contrast"(d) {
      return `<div class="tpl tpl-high-contrast">
        <header class="tpl-hc-top">
          <h1 class="tpl-hc-name">${esc(d.fullName)}</h1>
          <p class="tpl-hc-title">${esc(d.headline)}</p>
          <p class="tpl-hc-contact">${contactParts(d).join(" · ")}</p>
        </header>
        <div class="tpl-hc-body">
          <aside class="tpl-hc-side">
            <h3 class="tpl-hc-h3">Skills</h3>
            <ul class="tpl-bullets">${skillsListHtml(d)}</ul>
            <h3 class="tpl-hc-h3">Languages</h3>
            <ul class="tpl-bullets">${languagesHtml(d)}</ul>
            <h3 class="tpl-hc-h3">Interests</h3>
            <p class="tpl-hc-small">${esc(d.interests)}</p>
          </aside>
          <div class="tpl-hc-main">
            <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--hc">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
            <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--hc">Experience</h2>${experienceHtml(d)}</section>
            <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--hc">Education</h2>${educationHtml(d)}</section>
            <section class="tpl-sec"><h2 class="tpl-h2 tpl-h2--hc">Certifications</h2>${certificationsHtml(d)}</section>
          </div>
        </div>
      </div>`;
    },

    aurora(d) {
      return `<div class="tpl tpl-aurora">
        <div class="tpl-au-hero">
          ${photoHtml(d, "tpl-au-photo")}
          <div class="tpl-au-hero-text">
            <h1 class="tpl-au-name">${esc(d.fullName)}</h1>
            <p class="tpl-au-tagline">${esc(d.headline)}</p>
            <p class="tpl-au-contact">${contactParts(d).join(" · ")}</p>
          </div>
        </div>
        <div class="tpl-au-body">
          <section class="tpl-au-card"><h2 class="tpl-au-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-au-card"><h2 class="tpl-au-h2">Experience</h2>${experienceHtml(d)}</section>
          <div class="tpl-au-row">
            <section class="tpl-au-card tpl-au-card--half"><h2 class="tpl-au-h2">Education</h2>${educationHtml(d)}</section>
            <section class="tpl-au-card tpl-au-card--half"><h2 class="tpl-au-h2">Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul></section>
          </div>
          <section class="tpl-au-card"><h2 class="tpl-au-h2">Certifications &amp; languages</h2>${certificationsHtml(d)}<ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
          <section class="tpl-au-card"><h2 class="tpl-au-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    magazine(d) {
      return `<div class="tpl tpl-magazine">
        <header class="tpl-mz-header">
          <div class="tpl-mz-accent"></div>
          <div class="tpl-mz-intro">
            <p class="tpl-mz-kicker">Professional profile</p>
            <h1 class="tpl-mz-name">${esc(d.fullName)}</h1>
            <p class="tpl-mz-title">${esc(d.headline)}</p>
            <p class="tpl-mz-contact">${contactParts(d).join(" · ")}</p>
          </div>
        </header>
        <div class="tpl-mz-grid">
          <section class="tpl-mz-col">
            <h2 class="tpl-mz-h2">Summary</h2>
            <p class="tpl-mz-lead">${esc(d.summary)}</p>
            <h2 class="tpl-mz-h2">Experience</h2>${experienceHtml(d, "tpl-job tpl-job--mz")}
          </section>
          <aside class="tpl-mz-aside">
            ${photoHtml(d, "tpl-mz-photo")}
            <h3 class="tpl-mz-h3">Skills</h3>
            <div class="tpl-mz-pills">${skillsPillsHtml(d)}</div>
            <h3 class="tpl-mz-h3">Education</h3>${educationHtml(d)}
            <h3 class="tpl-mz-h3">Languages</h3><ul class="tpl-bullets tpl-bullets--tight">${languagesHtml(d)}</ul>
            <h3 class="tpl-mz-h3">Certifications</h3>${certificationsHtml(d)}
            <h3 class="tpl-mz-h3">Interests</h3><p class="tpl-p">${esc(d.interests)}</p>
          </aside>
        </div>
      </div>`;
    },

    timeline(d) {
      return `<div class="tpl tpl-timeline">
        <header class="tpl-tl-head">
          <h1 class="tpl-tl-name">${esc(d.fullName)}</h1>
          <p class="tpl-tl-sub">${esc(d.headline)}</p>
          <p class="tpl-tl-contact">${contactParts(d).join(" · ")}</p>
        </header>
        <section class="tpl-sec"><h2 class="tpl-tl-section-title">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
        <section class="tpl-sec">
          <h2 class="tpl-tl-section-title">Experience</h2>
          <div class="tpl-tl-track">${experienceTimelineHtml(d)}</div>
        </section>
        <div class="tpl-tl-two">
          <section class="tpl-sec"><h2 class="tpl-tl-section-title">Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-tl-section-title">Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul></section>
        </div>
        <section class="tpl-sec"><h2 class="tpl-tl-section-title">Certifications</h2>${certificationsHtml(d)}</section>
        <section class="tpl-sec"><h2 class="tpl-tl-section-title">Languages</h2><ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
        <section class="tpl-sec"><h2 class="tpl-tl-section-title">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
      </div>`;
    },

    executive(d) {
      return `<div class="tpl tpl-executive">
        <aside class="tpl-ex-side">
          ${photoHtml(d, "tpl-ex-photo")}
          <h2 class="tpl-ex-h2">Contact</h2>
          <ul class="tpl-ex-list">${contactParts(d).map((x) => `<li>${x}</li>`).join("")}</ul>
          <h2 class="tpl-ex-h2">Core skills</h2>
          <ul class="tpl-bullets tpl-bullets--tight">${skillsListHtml(d)}</ul>
          <h2 class="tpl-ex-h2">Languages</h2>
          <ul class="tpl-bullets tpl-bullets--tight">${languagesHtml(d)}</ul>
        </aside>
        <div class="tpl-ex-main">
          <header class="tpl-ex-top">
            <h1 class="tpl-ex-name">${esc(d.fullName)}</h1>
            <p class="tpl-ex-title">${esc(d.headline)}</p>
          </header>
          <section class="tpl-sec"><h2 class="tpl-ex-h2-main">Executive summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-sec"><h2 class="tpl-ex-h2-main">Experience</h2>${experienceHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-ex-h2-main">Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-ex-h2-main">Certifications</h2>${certificationsHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-ex-h2-main">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    studio(d) {
      return `<div class="tpl tpl-studio">
        <header class="tpl-st-hero">
          <div class="tpl-st-hero-inner">
            ${photoHtml(d, "tpl-st-photo")}
            <div>
              <h1 class="tpl-st-name">${esc(d.fullName)}</h1>
              <p class="tpl-st-tagline">${esc(d.headline)}</p>
              <p class="tpl-st-contact">${contactParts(d).join(" · ")}</p>
            </div>
          </div>
          <div class="tpl-st-skills">${skillsPillsHtml(d)}</div>
        </header>
        <div class="tpl-st-body">
          <section class="tpl-st-card"><h2 class="tpl-st-h2">About</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-st-card"><h2 class="tpl-st-h2">Experience</h2>${experienceHtml(d, "tpl-job tpl-job--st")}</section>
          <div class="tpl-st-split">
            <section class="tpl-st-card"><h2 class="tpl-st-h2">Education</h2>${educationHtml(d)}</section>
            <section class="tpl-st-card"><h2 class="tpl-st-h2">Languages</h2><ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
          </div>
          <section class="tpl-st-card"><h2 class="tpl-st-h2">Certifications</h2>${certificationsHtml(d)}</section>
          <section class="tpl-st-card"><h2 class="tpl-st-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    nova(d) {
      return `<div class="tpl tpl-nova">
        <div class="tpl-nv-hero">
          <div class="tpl-nv-blob" aria-hidden="true"></div>
          <div class="tpl-nv-card">
            ${photoHtml(d, "tpl-nv-photo")}
            <div class="tpl-nv-intro">
              <h1 class="tpl-nv-name">${esc(d.fullName)}</h1>
              <p class="tpl-nv-tagline">${esc(d.headline)}</p>
              <p class="tpl-nv-contact">${contactParts(d).join(" · ")}</p>
            </div>
          </div>
        </div>
        <div class="tpl-nv-body">
          <section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Experience</h2>${experienceHtml(d)}</section>
          <div class="tpl-nv-split">
            <section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Education</h2>${educationHtml(d)}</section>
            <section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Skills</h2><div class="tpl-nv-pills">${skillsPillsHtml(d)}</div></section>
          </div>
          <section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Certifications &amp; languages</h2>${certificationsHtml(d)}<ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
          <section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },

    ledger(d) {
      return `<div class="tpl tpl-ledger">
        <header class="tpl-lg-head">
          <h1 class="tpl-lg-name">${esc(d.fullName)}</h1>
          <p class="tpl-lg-meta"><span class="tpl-lg-label">ROLE</span> ${esc(d.headline)}</p>
          <p class="tpl-lg-meta"><span class="tpl-lg-label">CONTACT</span> ${contactParts(d).join(" · ")}</p>
        </header>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Summary</h2><p class="tpl-lg-p">${esc(d.summary)}</p></section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Experience</h2>${experienceHtml(d, "tpl-job tpl-job--lg")}</section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Education</h2>${educationHtml(d)}</section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Skills</h2><ul class="tpl-lg-list">${skillsListHtml(d)}</ul></section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Certifications</h2>${certificationsHtml(d)}</section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Languages</h2><ul class="tpl-lg-list">${languagesHtml(d)}</ul></section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Interests</h2><p class="tpl-lg-p">${esc(d.interests)}</p></section>
      </div>`;
    },

    horizon(d) {
      return `<div class="tpl tpl-horizon">
        <header class="tpl-hz-head">
          <h1 class="tpl-hz-name">${esc(d.fullName)}</h1>
          <p class="tpl-hz-title">${esc(d.headline)}</p>
          <p class="tpl-hz-contact">${contactParts(d).join(" · ")}</p>
        </header>
        <section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
        <section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Experience</h2>${experienceHtml(d)}</section>
        <section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Education</h2>${educationHtml(d)}</section>
        <section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul></section>
        <section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Certifications</h2>${certificationsHtml(d)}</section>
        <section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Languages</h2><ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
        <section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
      </div>`;
    },

    folio(d) {
      return `<div class="tpl tpl-folio">
        <header class="tpl-fo-head">
          ${photoHtml(d, "tpl-fo-photo")}
          <div>
            <h1 class="tpl-fo-name">${esc(d.fullName)}</h1>
            <p class="tpl-fo-line">${esc(d.headline)}</p>
            <p class="tpl-fo-contact">${contactParts(d).join(" · ")}</p>
          </div>
        </header>
        <section class="tpl-fo-sec"><span class="tpl-fo-num">01</span><div class="tpl-fo-content"><h2 class="tpl-fo-h2">Profile</h2><p class="tpl-p">${esc(d.summary)}</p></div></section>
        <section class="tpl-fo-sec"><span class="tpl-fo-num">02</span><div class="tpl-fo-content"><h2 class="tpl-fo-h2">Experience</h2>${experienceHtml(d, "tpl-job tpl-job--fo")}</div></section>
        <section class="tpl-fo-sec"><span class="tpl-fo-num">03</span><div class="tpl-fo-content"><h2 class="tpl-fo-h2">Education</h2>${educationHtml(d)}</div></section>
        <section class="tpl-fo-sec"><span class="tpl-fo-num">04</span><div class="tpl-fo-content"><h2 class="tpl-fo-h2">Skills</h2><p class="tpl-p">${(d.skills || []).map((s) => esc(s.name)).join(" · ")}</p></div></section>
        <section class="tpl-fo-sec"><span class="tpl-fo-num">05</span><div class="tpl-fo-content"><h2 class="tpl-fo-h2">More</h2>${certificationsHtml(d)}<ul class="tpl-bullets">${languagesHtml(d)}</ul><p class="tpl-p">${esc(d.interests)}</p></div></section>
      </div>`;
    },

    vertex(d) {
      return `<div class="tpl tpl-vertex">
        <header class="tpl-vx-banner">
          <div class="tpl-vx-banner-inner">
            <h1 class="tpl-vx-name">${esc(d.fullName)}</h1>
            <p class="tpl-vx-title">${esc(d.headline)}</p>
            <p class="tpl-vx-contact">${contactParts(d).join(" · ")}</p>
          </div>
        </header>
        <div class="tpl-vx-body">
          <section class="tpl-sec"><h2 class="tpl-vx-h2">Summary</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          <section class="tpl-sec"><h2 class="tpl-vx-h2">Experience</h2>${experienceHtml(d)}</section>
          <div class="tpl-vx-grid">
            <section class="tpl-sec"><h2 class="tpl-vx-h2">Education</h2>${educationHtml(d)}</section>
            <section class="tpl-sec"><h2 class="tpl-vx-h2">Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul></section>
          </div>
          <section class="tpl-sec"><h2 class="tpl-vx-h2">Certifications</h2>${certificationsHtml(d)}</section>
          <section class="tpl-sec"><h2 class="tpl-vx-h2">Languages</h2><ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
          <section class="tpl-sec"><h2 class="tpl-vx-h2">Interests</h2><p class="tpl-p">${esc(d.interests)}</p></section>
        </div>
      </div>`;
    },
  };

  function renderPreview() {
    let tid = activeTemplateId;
    if (!RENDERERS[tid]) {
      const fb = (TEMPLATES[0] && TEMPLATES[0].id) || "classic-sidebar";
      tid = RENDERERS[fb] ? fb : "classic-sidebar";
      activeTemplateId = tid;
    }
    const fn = RENDERERS[tid];
    resumeMount.innerHTML = fn ? fn(resumeData) : esc("Unknown template");
    resumeEl.setAttribute("data-template", tid);
    updateScore();
  }

  function setDeep(obj, path, value) {
    const parts = path.split(".");
    let cur = obj;
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i];
      const n = parts[i + 1];
      if (cur[p] === undefined) cur[p] = /^\d+$/.test(n) ? [] : {};
      cur = cur[p];
    }
    cur[parts[parts.length - 1]] = value;
  }

  function getDeep(obj, path) {
    const parts = path.split(".");
    let cur = obj;
    for (const p of parts) {
      if (cur == null) return undefined;
      cur = cur[p];
    }
    return cur;
  }

  function renderEditor() {
    const d = resumeData;
    const expBlocks = (d.experience || []).map((exp, i) => {
      const bullets = (exp.bullets || []).join("\n");
      return `<div class="editor-block" data-array="experience" data-index="${i}">
        <div class="editor-block__head">
          <span>Job ${i + 1}</span>
          <button type="button" class="btn-mini btn-mini--danger" data-action="remove-exp" data-index="${i}">Remove</button>
        </div>
        <label>Title<input type="text" data-bind="experience.${i}.title" value="${esc(exp.title)}" /></label>
        <label>Company<input type="text" data-bind="experience.${i}.company" value="${esc(exp.company)}" /></label>
        <label>Location<input type="text" data-bind="experience.${i}.location" value="${esc(exp.location)}" /></label>
        <label>Dates<input type="text" data-bind="experience.${i}.dates" value="${esc(exp.dates)}" /></label>
        <label>Bullets (one per line)<textarea data-bind-bullets="experience.${i}" rows="4">${esc(bullets)}</textarea></label>
      </div>`;
    }).join("");

    const eduBlocks = (d.education || []).map((ed, i) => `<div class="editor-block" data-array="education" data-index="${i}">
      <div class="editor-block__head">
        <span>Education ${i + 1}</span>
        <button type="button" class="btn-mini btn-mini--danger" data-action="remove-edu" data-index="${i}">Remove</button>
      </div>
      <label>Degree<input type="text" data-bind="education.${i}.degree" value="${esc(ed.degree)}" /></label>
      <label>School<input type="text" data-bind="education.${i}.school" value="${esc(ed.school)}" /></label>
      <label>Dates<input type="text" data-bind="education.${i}.dates" value="${esc(ed.dates)}" /></label>
      <label>Detail<input type="text" data-bind="education.${i}.detail" value="${esc(ed.detail)}" /></label>
    </div>`).join("");

    const skillBlocks = (d.skills || []).map((s, i) => `<div class="editor-block editor-block--inline" data-array="skills" data-index="${i}">
      <label>Skill<input type="text" data-bind="skills.${i}.name" value="${esc(s.name)}" /></label>
      <label>Level (1–5)<input type="number" min="1" max="5" data-bind="skills.${i}.level" value="${esc(s.level)}" /></label>
      <button type="button" class="btn-mini btn-mini--danger" data-action="remove-skill" data-index="${i}">×</button>
    </div>`).join("");

    const certBlocks = (d.certifications || []).map((c, i) => `<div class="editor-block" data-array="certifications" data-index="${i}">
      <div class="editor-block__head">
        <span>Certificate ${i + 1}</span>
        <button type="button" class="btn-mini btn-mini--danger" data-action="remove-cert" data-index="${i}">Remove</button>
      </div>
      <label>Name<input type="text" data-bind="certifications.${i}.name" value="${esc(c.name)}" /></label>
      <label>Issuer<input type="text" data-bind="certifications.${i}.issuer" value="${esc(c.issuer)}" /></label>
      <label>Date<input type="text" data-bind="certifications.${i}.date" value="${esc(c.date)}" /></label>
    </div>`).join("");

    const langBlocks = (d.languages || []).map((l, i) => `<div class="editor-block editor-block--inline" data-array="languages" data-index="${i}">
      <label>Language<input type="text" data-bind="languages.${i}.name" value="${esc(l.name)}" /></label>
      <label>Level<input type="text" data-bind="languages.${i}.level" value="${esc(l.level)}" /></label>
      <button type="button" class="btn-mini btn-mini--danger" data-action="remove-lang" data-index="${i}">×</button>
    </div>`).join("");

    editorMount.innerHTML = `
      <fieldset class="editor-fs">
        <legend>Personal</legend>
        <label>Full name<input type="text" data-bind="fullName" value="${esc(d.fullName)}" /></label>
        <label>Professional title<input type="text" data-bind="headline" value="${esc(d.headline)}" /></label>
        <label>Email<input type="text" data-bind="email" value="${esc(d.email)}" /></label>
        <label>Phone<input type="text" data-bind="phone" value="${esc(d.phone)}" /></label>
        <label>Address<input type="text" data-bind="address" value="${esc(d.address)}" /></label>
        <label>LinkedIn<input type="text" data-bind="linkedin" value="${esc(d.linkedin)}" /></label>
        <label>Website<input type="text" data-bind="website" value="${esc(d.website)}" /></label>
        <label>Photo<input type="file" id="photoInput" accept="image/*" /></label>
        <p class="editor-note">Photo is optional. Use a square image for best results.</p>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Summary</legend>
        <label><textarea data-bind="summary" rows="5">${esc(d.summary)}</textarea></label>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Skills</legend>
        ${skillBlocks}
        <button type="button" class="btn-add" data-action="add-skill">+ Add skill</button>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Experience</legend>
        ${expBlocks}
        <button type="button" class="btn-add" data-action="add-exp">+ Add job</button>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Education</legend>
        ${eduBlocks}
        <button type="button" class="btn-add" data-action="add-edu">+ Add education</button>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Certifications</legend>
        ${certBlocks}
        <button type="button" class="btn-add" data-action="add-cert">+ Add certification</button>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Languages</legend>
        ${langBlocks}
        <button type="button" class="btn-add" data-action="add-lang">+ Add language</button>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Interests</legend>
        <label><textarea data-bind="interests" rows="3">${esc(d.interests)}</textarea></label>
      </fieldset>
      <div class="editor-actions">
        <button type="button" class="btn-reset" id="btnResetUserData">${
          window.__TT_RESUME_INITIAL && typeof window.__TT_RESUME_INITIAL === "object"
            ? "Reset to saved resume data"
            : "Reset to sample resume"
        }</button>
      </div>`;

    const photoInput = document.getElementById("photoInput");
    if (photoInput) {
      photoInput.addEventListener("change", async () => {
        const f = photoInput.files && photoInput.files[0];
        if (!f) return;
        // Upload to S3-backed ImageField so templates show the stored resume photo.
        const url = await uploadResumePhoto(f);
        if (url) {
          resumeData.photo = url;
          scheduleSave();
          renderPreview();
          return;
        }
        // Fallback: local preview only (not persisted to DB).
        const r = new FileReader();
        r.onload = () => {
          resumeData.photo = r.result;
          scheduleSave();
          renderPreview();
        };
        r.readAsDataURL(f);
      });
    }

    const btnResetUser = document.getElementById("btnResetUserData");
    if (btnResetUser) {
      btnResetUser.addEventListener("click", () => {
        const fromServer = window.__TT_RESUME_INITIAL && typeof window.__TT_RESUME_INITIAL === "object";
        const ok = confirm(
          fromServer
            ? "Restore all fields from your saved Top Teen resume? Preview will match your account data again."
            : "Replace all fields with the built-in sample resume?"
        );
        if (!ok) return;
        if (fromServer) {
          resumeData = deepMergeResume(defaultResume(), window.__TT_RESUME_INITIAL);
        } else {
          resumeData = defaultResume();
        }
        scheduleSave();
        renderEditor();
        renderPreview();
      });
    }
  }

  function bindEditorEvents() {
    editorMount.addEventListener("input", (e) => {
      const el = e.target;
      if (!(el instanceof HTMLElement)) return;
      const bind = el.getAttribute("data-bind");
      const bb = el.getAttribute("data-bind-bullets");
      if (bind) {
        const val = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement ? el.value : "";
        const num = el.getAttribute("type") === "number" ? Number(val) : val;
        setDeep(resumeData, bind, el.getAttribute("type") === "number" ? num : val);
        scheduleSave();
        renderPreview();
      }
      if (bb && el instanceof HTMLTextAreaElement) {
        const lines = el.value.split("\n").map((l) => l.trim()).filter(Boolean);
        const base = bb;
        const arr = getDeep(resumeData, base);
        if (arr && typeof arr === "object") arr.bullets = lines;
        scheduleSave();
        renderPreview();
      }
    });

    editorMount.addEventListener("click", (e) => {
      const t = e.target;
      if (!(t instanceof HTMLElement)) return;
      const act = t.getAttribute("data-action");
      const idx = Number(t.getAttribute("data-index"));
      if (act === "add-exp") {
        resumeData.experience.push({
          title: "",
          company: "",
          location: "",
          dates: "",
          bullets: [""],
        });
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "remove-exp" && !Number.isNaN(idx)) {
        resumeData.experience.splice(idx, 1);
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "add-edu") {
        resumeData.education.push({ degree: "", school: "", dates: "", detail: "" });
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "remove-edu" && !Number.isNaN(idx)) {
        resumeData.education.splice(idx, 1);
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "add-skill") {
        resumeData.skills.push({ name: "", level: 3 });
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "remove-skill" && !Number.isNaN(idx)) {
        resumeData.skills.splice(idx, 1);
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "add-cert") {
        resumeData.certifications.push({ name: "", issuer: "", date: "" });
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "remove-cert" && !Number.isNaN(idx)) {
        resumeData.certifications.splice(idx, 1);
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "add-lang") {
        resumeData.languages.push({ name: "", level: "" });
        scheduleSave();
        renderEditor();
        renderPreview();
      }
      if (act === "remove-lang" && !Number.isNaN(idx)) {
        resumeData.languages.splice(idx, 1);
        scheduleSave();
        renderEditor();
        renderPreview();
      }
    });
  }

  function hexToRgb(hex) {
    const n = hex.replace("#", "");
    const v = parseInt(n.length === 3 ? n.split("").map((c) => c + c).join("") : n, 16);
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
  }

  function applyColorScheme(scheme) {
    document.documentElement.style.setProperty("--accent", scheme.accent);
    document.documentElement.style.setProperty("--accent-contrast", scheme.contrast);
    const [r, g, b] = hexToRgb(scheme.accent);
    document.documentElement.style.setProperty("--accent-rgb", `${r}, ${g}, ${b}`);
  }

  function applyResumeTextAlign(cssValue) {
    document.documentElement.style.setProperty("--resume-text-align", cssValue);
  }

  function renderTextAlignOptions() {
    if (!textAlignEl) return;
    textAlignEl.innerHTML = "";
    TEXT_ALIGN_OPTIONS.forEach((opt) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "align-btn";
      b.textContent = opt.label;
      b.dataset.alignId = opt.id;
      b.setAttribute("aria-label", "Align text: " + opt.label);
      b.setAttribute("aria-pressed", opt.id === activeTextAlignId ? "true" : "false");
      b.addEventListener("click", () => {
        activeTextAlignId = opt.id;
        applyResumeTextAlign(opt.css);
        scheduleSave();
        textAlignEl.querySelectorAll(".align-btn").forEach((el) => {
          if (!(el instanceof HTMLElement)) return;
          const id = el.dataset.alignId;
          el.setAttribute("aria-pressed", id === activeTextAlignId ? "true" : "false");
        });
      });
      textAlignEl.appendChild(b);
    });
  }

  function renderColorSchemes() {
    colorSchemesEl.innerHTML = "";
    COLOR_SCHEMES.forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "color-swatch";
      b.style.backgroundColor = s.accent;
      b.style.color = s.accent;
      b.setAttribute("aria-label", s.label);
      b.setAttribute("aria-pressed", s.id === activeColorId ? "true" : "false");
      b.addEventListener("click", () => {
        activeColorId = s.id;
        applyColorScheme(s);
        scheduleSave();
        colorSchemesEl.querySelectorAll(".color-swatch").forEach((el, i) => {
          el.setAttribute("aria-pressed", COLOR_SCHEMES[i].id === activeColorId ? "true" : "false");
        });
      });
      colorSchemesEl.appendChild(b);
    });
  }

  function visibleTemplates() {
    if (activeFilterId === "all") return TEMPLATES;
    return TEMPLATES.filter((t) => t.category === activeFilterId);
  }

  function renderFilterNav() {
    filterNav.innerHTML = "";
    CATEGORIES.forEach((c) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "filter-btn" + (c.id === activeFilterId ? " is-active" : "");
      b.textContent = c.label;
      b.setAttribute("aria-pressed", c.id === activeFilterId ? "true" : "false");
      b.addEventListener("click", () => {
        activeFilterId = c.id;
        renderFilterNav();
        renderTemplateGrid();
      });
      filterNav.appendChild(b);
    });
  }

  function renderTemplateGrid() {
    templateGrid.innerHTML = "";
    visibleTemplates().forEach((t) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "template-card";
      card.dataset.template = t.id;
      card.setAttribute("aria-pressed", t.id === activeTemplateId ? "true" : "false");
      const mock = document.createElement("span");
      mock.className = `template-card__mock template-card__${t.mock}`;
      mock.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.className = "template-card__label";
      label.textContent = t.name;
      const choose = document.createElement("span");
      choose.className = "template-card__choose";
      choose.textContent = "Choose template";
      card.appendChild(mock);
      card.appendChild(label);
      card.appendChild(choose);
      card.addEventListener("click", () => {
        activeTemplateId = t.id;
        scheduleSave();
        renderTemplateGrid();
        renderPreview();
        notifyParentSelection();
      });
      templateGrid.appendChild(card);
    });
  }

  function renderFonts() {
    fontFamily.innerHTML = "";
    FONTS.forEach((f) => {
      const opt = document.createElement("option");
      opt.value = f.value;
      opt.textContent = f.label;
      fontFamily.appendChild(opt);
    });
    fontFamily.addEventListener("change", () => {
      document.documentElement.style.setProperty("--font-stack", fontFamily.value);
      scheduleSave();
    });
  }

  function computeScore(d) {
    let n = 0;
    const add = (cond, pts) => {
      if (cond) n += pts;
    };
    add(d.fullName && d.fullName.trim(), 12);
    add(d.headline && d.headline.trim(), 8);
    add(d.email && d.email.trim(), 6);
    add(d.phone && d.phone.trim(), 4);
    add(d.summary && d.summary.trim().length > 40, 12);
    add((d.skills || []).length >= 2, 8);
    add((d.experience || []).length >= 1, 14);
    add((d.education || []).length >= 1, 10);
    add((d.certifications || []).length >= 1, 6);
    add((d.languages || []).length >= 1, 6);
    add(d.interests && d.interests.trim(), 4);
    add(d.photo && String(d.photo).trim(), 6);
    return Math.min(100, n);
  }

  function updateScore() {
    const sc = computeScore(resumeData);
    scoreNum.textContent = String(sc);
    if (scoreArc) scoreArc.setAttribute("stroke-dasharray", `${sc}, 100`);
  }

  function safeFilename(name) {
    const s = String(name || "resume")
      .replace(/[^\w\s-]/g, "")
      .trim()
      .replace(/\s+/g, "-");
    return s || "resume";
  }

  function downloadPdf() {
    if (typeof window.html2pdf === "undefined") {
      alert("PDF library failed to load. Use Print and choose Save as PDF instead.");
      return;
    }
    const el = resumeEl;
    el.classList.add("pdf-exporting");
    const opt = {
      margin: [6, 6, 6, 6],
      filename: `${safeFilename(resumeData.fullName)}.pdf`,
      image: { type: "jpeg", quality: 0.93 },
      html2canvas: {
        scale: 2,
        useCORS: true,
        logging: false,
        letterRendering: true,
        scrollY: 0,
      },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["avoid-all", "css", "legacy"] },
    };
    const done = () => el.classList.remove("pdf-exporting");
    try {
      const worker = window.html2pdf().set(opt).from(el).save();
      if (worker && typeof worker.then === "function") {
        worker.then(done).catch(done);
      } else {
        setTimeout(done, 1000);
      }
    } catch (e) {
      done();
      alert("Could not create PDF. Try Print → Save as PDF.");
    }
  }

  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(persistState, 400);
  }

  function notifyParentSelection() {
    try {
      if (!window.parent || window.parent === window) return;
      const fontVal = fontFamily && fontFamily.value ? fontFamily.value : "";
      window.parent.postMessage(
        {
          type: "TT_STUDIO_TEMPLATE_PICK",
          template: activeTemplateId,
          color: activeColorId,
          font: fontVal,
          textAlign: activeTextAlignId,
        },
        "*"
      );
    } catch (_) {}
  }

  function getCookie(name) {
    try {
      const m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]+)"));
      return m ? decodeURIComponent(m[2]) : "";
    } catch (_) {
      return "";
    }
  }

  async function uploadResumePhoto(file) {
    try {
      if (!file || !window.__TT_RESUME_PK) return null;
      const u = `/user/resume-builder/studio/${window.__TT_RESUME_PK}/photo/`;
      const fd = new FormData();
      fd.append("photo", file);
      const r = await fetch(u, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: fd,
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) return null;
      return j && j.url ? String(j.url) : null;
    } catch (_) {
      return null;
    }
  }

  function persistState() {
    try {
      const fontVal = fontFamily && fontFamily.value ? fontFamily.value : "";
      const payload = window.__TT_RESUME_INITIAL
        ? {
            template: activeTemplateId,
            color: activeColorId,
            font: fontVal,
            textAlign: activeTextAlignId,
          }
        : {
            resume: resumeData,
            template: activeTemplateId,
            color: activeColorId,
            font: fontVal,
            textAlign: activeTextAlignId,
          };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (_) {}
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const o = JSON.parse(raw);
      if (!window.__TT_RESUME_INITIAL) {
        if (o.resume && typeof o.resume === "object") resumeData = o.resume;
      }
      if (o.template && RENDERERS[o.template]) activeTemplateId = o.template;
      if (o.color && COLOR_SCHEMES.some((c) => c.id === o.color)) activeColorId = o.color;
      if (o.textAlign && TEXT_ALIGN_OPTIONS.some((a) => a.id === o.textAlign)) activeTextAlignId = o.textAlign;
    } catch (_) {}
  }

  function init() {
    loadState();
    function qp(name) {
      try {
        return new URLSearchParams(window.location.search).get(name);
      } catch (_) {
        return null;
      }
    }
    const isPickerMode = String(qp("mode") || "").trim() === "picker";
    if (isPickerMode) {
      document.body.classList.add("tt-mode-picker");
    }
    if (window.__TT_STUDIO_PREFS_INITIAL && typeof window.__TT_STUDIO_PREFS_INITIAL === "object") {
      var si = window.__TT_STUDIO_PREFS_INITIAL;
      if (si.template && RENDERERS[si.template]) {
        activeTemplateId = si.template;
      }
      if (si.color && COLOR_SCHEMES.some(function (c) { return c.id === si.color; })) {
        activeColorId = si.color;
      }
      if (si.textAlign && TEXT_ALIGN_OPTIONS.some(function (a) { return a.id === si.textAlign; })) {
        activeTextAlignId = si.textAlign;
      }
      if (si.font && fontFamily) {
        var match = false;
        for (var fi = 0; fi < FONTS.length; fi++) {
          if (FONTS[fi].value === si.font) {
            fontFamily.value = si.font;
            document.documentElement.style.setProperty("--font-stack", si.font);
            match = true;
            break;
          }
        }
        if (!match && si.font) {
          fontFamily.value = si.font;
          document.documentElement.style.setProperty("--font-stack", si.font);
        }
      }
    }
    if (window.__TT_STUDIO_FORCE_TEMPLATE) {
      const fk = String(window.__TT_STUDIO_FORCE_TEMPLATE).trim();
      if (fk && RENDERERS[fk]) {
        activeTemplateId = fk;
      }
    }
    const scheme = COLOR_SCHEMES.find((c) => c.id === activeColorId) || COLOR_SCHEMES[0];
    applyColorScheme(scheme);
    const alignOpt = TEXT_ALIGN_OPTIONS.find((a) => a.id === activeTextAlignId) || TEXT_ALIGN_OPTIONS[0];
    applyResumeTextAlign(alignOpt.css);
    renderColorSchemes();
    renderTextAlignOptions();
    renderFilterNav();
    renderTemplateGrid();
    renderFonts();
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const o = JSON.parse(raw);
        if (o.font) {
          fontFamily.value = o.font;
          document.documentElement.style.setProperty("--font-stack", o.font);
        }
      }
    } catch (_) {}

    renderEditor();
    bindEditorEvents();
    renderPreview();

    var dupForm = document.getElementById("ttDupResumeForm");
    var snapField = document.getElementById("ttStudioSnapshotJson");
    if (dupForm && snapField) {
      dupForm.addEventListener("submit", function () {
        try {
          snapField.value = JSON.stringify({
            resume: resumeData,
            template: activeTemplateId,
            color: activeColorId,
            font: fontFamily && fontFamily.value ? fontFamily.value : "",
            textAlign: activeTextAlignId,
          });
        } catch (_) {
          snapField.value = "";
        }
      });
    }

    btnPdf.addEventListener("click", downloadPdf);
    btnPrint.addEventListener("click", () => window.print());
    btnFinish.addEventListener("click", () => {
      const finishUrl = window.__TT_EMBED_FINISH || qp("finish");
      if (finishUrl) {
        try {
          window.top.location.href = finishUrl;
        } catch (_) {
          window.location.href = finishUrl;
        }
        return;
      }
      window.print();
    });

  }

  init();
})();
