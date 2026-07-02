(function () {
  "use strict";

  const STORAGE_KEY =
    typeof window.__TT_STORAGE_KEY === "string" && window.__TT_STORAGE_KEY.trim()
      ? window.__TT_STORAGE_KEY.trim()
      : "resume-builder-data-v2";

  const CAREER_OBJECTIVE_TITLE = "Career Objective";
  const ACHIEVEMENTS_ACTIVITIES_TITLE = "Achievements & Activities";
  const PROJECTS_TITLE = "Projects";
  const WORK_EXPERIENCE_TITLE = "Work Experience";

  function deepMergeResume(def, srv) {
    if (!srv || typeof srv !== "object") return { ...def };
    const o = { ...def, ...srv };
    const arrKeys = ["skills", "experience", "projects", "achievements", "workExperience", "education", "certifications", "languages"];
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
  const fontSize = document.getElementById("fontSize");
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

  const FONT_SIZES = [
    { id: "compact", label: "Compact (10.5 pt)", css: "10.5pt", scale: 0.94 },
    { id: "standard", label: "Standard (11.5 pt)", css: "11.5pt", scale: 1 },
    { id: "readable", label: "Readable (12.5 pt)", css: "12.5pt", scale: 1.08 },
    { id: "large", label: "Large (13.5 pt)", css: "13.5pt", scale: 1.16 },
  ];

  const CATEGORIES = [
    { id: "all", label: "All templates" },
    { id: "modern", label: "Modern" },
    { id: "professional", label: "Professional" },
    { id: "creative", label: "Creative" },
    { id: "simple", label: "Simple" },
    { id: "international", label: "International" },
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
    { id: "global-elegance", name: "Global Elegance", category: "international", mock: "mock-magazine" },
    { id: "euro-corporate", name: "Euro Corporate", category: "international", mock: "mock-executive" },
    { id: "tokyo-minimal", name: "Tokyo Minimal", category: "international", mock: "mock-minimalist" },
    { id: "nordic-clean", name: "Nordic Clean", category: "international", mock: "mock-horizon" },
    { id: "atlantic-pro", name: "Atlantic Pro", category: "international", mock: "mock-atlantic-pro" },
    { id: "zen-column", name: "Zen Column", category: "international", mock: "mock-zen-column" },
    { id: "global-grid", name: "Global Grid", category: "international", mock: "mock-global-grid" },
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
  let activeFontSizeId = "standard";
  let saveTimer = null;
  let pdfBusy = false;
  let forceClientPreview = false;

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
      hobbies: "Cricket, music, volunteering",
    };
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function ordinalSuffix(n) {
    const mod100 = n % 100;
    if (mod100 >= 11 && mod100 <= 13) return "th";
    return ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
  }

  /** School grades: 10 → 10<sup>th</sup>, 12 → 12<sup>th</sup>, etc. */
  function formatEducationDegree(text) {
    const raw = String(text ?? "").trim();
    if (!raw) return "";
    const m = raw.match(/^(?:(?:class|grade)\s+)?(\d{1,2})(?:\s*(?:st|nd|rd|th))?$/i);
    if (m) {
      const n = parseInt(m[1], 10);
      if (n >= 1 && n <= 12) {
        return `${n}<sup>${ordinalSuffix(n)}</sup>`;
      }
    }
    return esc(raw);
  }

  /** Studio v2 saves hobbies; some templates label the section Interests. */
  function interestsText(d) {
    const interests = String((d && d.interests) || "").trim();
    if (interests) return interests;
    return String((d && d.hobbies) || "").trim();
  }

  function hobbiesDisplayText(d) {
    const hobbies = String((d && d.hobbies) || "").trim();
    if (hobbies) return hobbies;
    return String((d && d.interests) || "").trim();
  }

  function hasDisplayText(v) {
    if (v == null) return false;
    const s = String(v).trim();
    return s && s !== "—" && s !== "-" && s !== "–";
  }

  function joinDisplayParts(parts, sep) {
    return parts.filter(hasDisplayText).map((p) => esc(p)).join(sep || " · ");
  }

  function tplHeadline(className, d) {
    if (!hasDisplayText(d.headline)) return "";
    return `<p class="${className}">${esc(d.headline)}</p>`;
  }

  function photoInitialLetter(d) {
    const fromField = String((d && d.photoInitial) || "").trim();
    if (fromField) return fromField.charAt(0).toUpperCase();
    const name = String((d && d.fullName) || "").trim();
    if (name) return name.charAt(0).toUpperCase();
    return "?";
  }

  function photoHtml(d, className) {
    if (d.photo && String(d.photo).trim()) {
      return `<img class="${className}" src="${esc(d.photo)}" alt="" />`;
    }
    const initial = esc(photoInitialLetter(d));
    return `<div class="${className} tpl-photo tpl-photo--placeholder" aria-hidden="true"><span class="tpl-photo-initial">${initial}</span></div>`;
  }

  function contactParts(d) {
    function contactIconSvg(kind) {
      const icons = {
        phone:
          '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.654 1.328a.678.678 0 0 1 .737-.124l2.522 1.01c.289.116.445.423.365.723l-.547 2.05a.68.68 0 0 1-.59.5l-1.12.112a11.77 11.77 0 0 0 5.38 5.38l.112-1.12a.68.68 0 0 1 .5-.59l2.05-.547a.678.678 0 0 1 .723.365l1.01 2.522a.678.678 0 0 1-.124.737l-1.14 1.14a1.745 1.745 0 0 1-1.81.422c-1.93-.644-4.54-2.382-6.56-4.402-2.02-2.02-3.758-4.63-4.402-6.56a1.745 1.745 0 0 1 .422-1.81l1.14-1.14z"/></svg>',
        email:
          '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v.217L8 8.94.001 4.217V4z"/><path d="M0 5.383v6.617a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V5.383l-7.445 4.654a1 1 0 0 1-1.11 0L0 5.383z"/></svg>',
        location:
          '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 16s6-5.686 6-10A6 6 0 1 0 2 6c0 4.314 6 10 6 10zm0-7.5A2.5 2.5 0 1 1 8 3a2.5 2.5 0 0 1 0 5.5z"/></svg>',
        linkedin:
          '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M0 1.146C0 .513.526 0 1.175 0h13.65C15.474 0 16 .513 16 1.146v13.708c0 .633-.526 1.146-1.175 1.146H1.175A1.16 1.16 0 0 1 0 14.854V1.146zM4.943 13.5V6.169H2.542V13.5h2.401zM3.742 5.163c.837 0 1.358-.554 1.358-1.248-.015-.71-.52-1.248-1.342-1.248S2.4 3.205 2.4 3.915c0 .694.521 1.248 1.326 1.248h.016zM13.5 13.5V9.359c0-2.217-1.183-3.248-2.762-3.248-1.274 0-1.845.7-2.165 1.193v.026h-.016a5.54 5.54 0 0 1 .016-.026V6.169H6.17c.03.752 0 7.331 0 7.331h2.401V9.405c0-.219.016-.438.08-.594.176-.438.578-.892 1.253-.892.884 0 1.237.673 1.237 1.66V13.5H13.5z"/></svg>',
        website:
          '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0zm5.939 7h-2.027a13.54 13.54 0 0 0-.65-3.145A6.02 6.02 0 0 1 13.939 7zM8 1.018c.655 0 1.58 1.23 2.027 3.982H5.973C6.42 2.248 7.345 1.018 8 1.018zM4.738 3.855A13.54 13.54 0 0 0 4.088 7H2.061a6.02 6.02 0 0 1 2.677-3.145zM2.061 9h2.027c.112 1.118.34 2.19.65 3.145A6.02 6.02 0 0 1 2.061 9zM8 14.982c-.655 0-1.58-1.23-2.027-3.982h4.054C9.58 13.752 8.655 14.982 8 14.982zM10.26 12.145c.31-.955.538-2.027.65-3.145h2.028a6.02 6.02 0 0 1-2.678 3.145z"/></svg>',
      };
      return icons[kind] || "";
    }

    const iconFallback = {
      phone: "☎",
      email: "@",
      location: "•",
      linkedin: "in",
      website: "WWW",
    };
    function contactIconHtml(kind) {
      return `<span class="tpl-contact-icon" data-icon-kind="${kind}" aria-hidden="true"><span class="tpl-contact-fallback">${iconFallback[kind] || "•"}</span>${contactIconSvg(kind)}</span>`;
    }

    const out = [];
    if (d.phone) out.push(`<span class="tpl-contact-item">${contactIconHtml("phone")}<span class="tpl-contact-text">${esc(d.phone)}</span></span>`);
    if (d.email) out.push(`<span class="tpl-contact-item">${contactIconHtml("email")}<span class="tpl-contact-text">${esc(d.email)}</span></span>`);
    if (d.address) out.push(`<span class="tpl-contact-item">${contactIconHtml("location")}<span class="tpl-contact-text">${esc(d.address)}</span></span>`);
    if (d.linkedin) out.push(`<span class="tpl-contact-item">${contactIconHtml("linkedin")}<span class="tpl-contact-text">${esc(d.linkedin)}</span></span>`);
    if (d.website) out.push(`<span class="tpl-contact-item">${contactIconHtml("website")}<span class="tpl-contact-text">${esc(d.website)}</span></span>`);
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

  function isProjectBlock(exp) {
    if (!exp || typeof exp !== "object") return false;
    return String(exp.company || "").trim() === "Project";
  }

  function isWorkExperienceBlock(exp) {
    if (!exp || typeof exp !== "object") return false;
    const c = String(exp.company || "").trim();
    if (!c || c === "Project" || c === "Activity" || c.startsWith("Volunteer")) return false;
    return true;
  }

  const PROFILE_INTEREST_MARKER = "extracurricular interest from profile";

  function isProfileInterestAchievement(exp) {
    if (!exp || typeof exp !== "object") return false;
    const bullets = (exp.bullets || []).map((b) =>
      String(b).trim().replace(/\.$/, "").toLowerCase()
    );
    return bullets.length === 1 && bullets[0] === PROFILE_INTEREST_MARKER;
  }

  function projectsFromData(d) {
    if (Array.isArray(d.projects)) return d.projects;
    return (d.experience || []).filter(isProjectBlock);
  }

  function achievementsFromData(d) {
    let items;
    if (Array.isArray(d.achievements)) items = d.achievements;
    else {
      items = (d.experience || []).filter((exp) => !isProjectBlock(exp) && !isWorkExperienceBlock(exp));
    }
    return (items || []).filter((exp) => !isProfileInterestAchievement(exp));
  }

  function workExperienceFromData(d) {
    if (Array.isArray(d.workExperience)) return d.workExperience;
    return (d.experience || []).filter(isWorkExperienceBlock);
  }

  function jobBlocksHtml(items, classJob) {
    const cj = classJob || "tpl-job";
    return (items || [])
      .map((exp) => {
        const bullets = (exp.bullets || []).map((b) => `<li>${esc(b)}</li>`).join("");
        const dates = hasDisplayText(exp.dates)
          ? `<span class="tpl-job-dates">${esc(exp.dates)}</span>`
          : "";
        const subParts = joinDisplayParts([exp.company, exp.location]);
        const sub = subParts ? `<div class="tpl-job-sub">${subParts}</div>` : "";
        return `<div class="${cj}">
          <div class="tpl-job-head">
            <strong>${esc(exp.title)}</strong>
            ${dates}
          </div>
          ${sub}
          ${bullets ? `<ul class="tpl-bullets">${bullets}</ul>` : ""}
        </div>`;
      })
      .join("");
  }

  function projectsHtml(d, classJob) {
    return jobBlocksHtml(projectsFromData(d), classJob);
  }

  function achievementsHtml(d, classJob) {
    return jobBlocksHtml(achievementsFromData(d), classJob);
  }

  function workExperienceHtml(d, classJob) {
    return jobBlocksHtml(workExperienceFromData(d), classJob);
  }

  function experienceHtml(d, classJob) {
    return achievementsHtml(d, classJob);
  }

  function projectsSection(d, opts) {
    opts = opts || {};
    const inner = projectsHtml(d, opts.jobClass);
    if (!String(inner || "").trim()) return "";
    const wrap = opts.wrap || "tpl-sec";
    const h2 = opts.h2 || "tpl-h2";
    const prefix = opts.titlePrefix || "";
    return `<section class="${wrap}"><h2 class="${h2}">${prefix}${PROJECTS_TITLE}</h2>${inner}</section>`;
  }

  function achievementsSection(d, opts) {
    opts = opts || {};
    const inner = achievementsHtml(d, opts.jobClass);
    if (!String(inner || "").trim()) return "";
    const wrap = opts.wrap || "tpl-sec";
    const h2 = opts.h2 || "tpl-h2";
    const prefix = opts.titlePrefix || "";
    return `<section class="${wrap}"><h2 class="${h2}">${prefix}${ACHIEVEMENTS_ACTIVITIES_TITLE}</h2>${inner}</section>`;
  }

  function workExperienceSection(d, opts) {
    opts = opts || {};
    const inner = workExperienceHtml(d, opts.jobClass);
    if (!String(inner || "").trim()) return "";
    const wrap = opts.wrap || "tpl-sec";
    const h2 = opts.h2 || "tpl-h2";
    const prefix = opts.titlePrefix || "";
    return `<section class="${wrap}"><h2 class="${h2}">${prefix}${WORK_EXPERIENCE_TITLE}</h2>${inner}</section>`;
  }

  function resumeJobSections(d, opts) {
    opts = opts || {};
    return (
      projectsSection(d, opts) +
      achievementsSection(d, opts) +
      workExperienceSection(d, opts)
    );
  }

  function hzBarSection(title, inner) {
    if (!String(inner || "").trim()) return "";
    return `<section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">${title}</h2>${inner}</section>`;
  }

  function hzJobSection(title, inner) {
    if (!String(inner || "").trim()) return "";
    return `<section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">${title}</h2>${inner}</section>`;
  }

  function educationHtml(d) {
    return (d.education || [])
      .map(
        (ed) => {
          const dates = hasDisplayText(ed.dates)
            ? `<span class="tpl-job-dates">${esc(ed.dates)}</span>`
            : "";
          const school = hasDisplayText(ed.school) ? esc(ed.school) : "";
          const detail = hasDisplayText(ed.detail) ? esc(ed.detail) : "";
          const sub = school || detail
            ? `<div class="tpl-job-sub">${school}${school && detail ? " — " : ""}${detail}</div>`
            : "";
          return `<div class="tpl-edu-block">
        <div class="tpl-job-head">
          <strong>${formatEducationDegree(ed.degree)}</strong>
          ${dates}
        </div>
        ${sub}
      </div>`;
        }
      )
      .join("");
  }

  function certificationsHtml(d) {
    return (d.certifications || [])
      .map(
        (c) => {
          const meta = joinDisplayParts([c.issuer, c.date]);
          return `<div class="tpl-cert">
        <strong>${esc(c.name)}</strong>
        ${meta ? `<span class="tpl-cert-meta">${meta}</span>` : ""}
      </div>`;
        }
      )
      .join("");
  }

  function languagesHtml(d) {
    return (d.languages || [])
      .map((l) => {
        const level = hasDisplayText(l.level) ? ` — ${esc(l.level)}` : "";
        return `<li><span class="tpl-lang-name">${esc(l.name)}</span>${level}</li>`;
      })
      .join("");
  }

  function skillsPillsHtml(d) {
    return (d.skills || [])
      .map((s) => `<span class="tpl-pill">${esc(s.name)}</span>`)
      .join("");
  }

  function languagesPillsHtml(d) {
    return (d.languages || [])
      .filter((l) => hasDisplayText(l.name))
      .map((l) => {
        const level = hasDisplayText(l.level) ? ` · ${esc(l.level)}` : "";
        return `<span class="tpl-pill tpl-pill--lang">${esc(l.name)}${level}</span>`;
      })
      .join("");
  }

  function languagesChipsHtml(d) {
    const chips = (d.languages || [])
      .filter((l) => hasDisplayText(l.name))
      .map((l) => {
        const level = hasDisplayText(l.level) ? `<span class="tpl-ch-lang-level">${esc(l.level)}</span>` : "";
        return `<span class="tpl-ch-lang-chip"><span class="tpl-ch-lang-name">${esc(l.name)}</span>${level}</span>`;
      })
      .join("");
    return chips ? `<div class="tpl-ch-lang-list">${chips}</div>` : "";
  }

  function coloredHeaderJobsColumn(d) {
    const parts = [];
    const add = (title, html) => {
      if (String(html || "").trim()) {
        parts.push(`<div class="tpl-ch-subsec"><h2 class="tpl-h2">${title}</h2>${html}</div>`);
      }
    };
    add(PROJECTS_TITLE, projectsHtml(d));
    add(ACHIEVEMENTS_ACTIVITIES_TITLE, achievementsHtml(d));
    add(WORK_EXPERIENCE_TITLE, workExperienceHtml(d));
    if (!parts.length) return "";
    return `<section class="tpl-sec tpl-sec--half"><div class="tpl-ch-stack">${parts.join("")}</div></section>`;
  }

  function coloredHeaderEduSkillsColumn(d) {
    const parts = [];
    const eduInner = educationHtml(d);
    const skillsInner = skillsListHtml(d);
    if (String(eduInner || "").trim()) {
      parts.push(`<div class="tpl-ch-subsec"><h2 class="tpl-h2">Education</h2>${eduInner}</div>`);
    }
    if (String(skillsInner || "").trim()) {
      parts.push(
        `<div class="tpl-ch-subsec"><h2 class="tpl-h2">Skills</h2><ul class="tpl-bullets tpl-bullets--tight">${skillsInner}</ul></div>`
      );
    }
    if (!parts.length) return "";
    return `<section class="tpl-sec tpl-sec--half"><div class="tpl-ch-stack">${parts.join("")}</div></section>`;
  }

  function coloredHeaderCertsLangsRow(d) {
    const certsInner = certificationsHtml(d);
    const langsInner = languagesChipsHtml(d);
    const sections = [];
    if (String(certsInner || "").trim()) {
      sections.push(
        `<section class="tpl-sec tpl-sec--half"><h2 class="tpl-h2">Certifications</h2><div class="tpl-ch-cert-list">${certsInner}</div></section>`
      );
    }
    if (String(langsInner || "").trim()) {
      sections.push(`<section class="tpl-sec tpl-sec--half"><h2 class="tpl-h2">Languages</h2>${langsInner}</section>`);
    }
    if (!sections.length) return "";
    if (sections.length === 1) {
      return sections[0].replace("tpl-sec--half", "tpl-sec tpl-sec--full");
    }
    return `<div class="tpl-ch-row tpl-ch-row--bottom">${sections.join("")}</div>`;
  }

  function contactRowHtml(d, wrapClass) {
    const parts = contactParts(d);
    if (!parts.length) return "";
    return `<div class="${wrapClass || "tpl-min-contact-row"}">${parts.join("")}</div>`;
  }

  function experienceTimelineHtml(d, items) {
    const rows = items || achievementsFromData(d);
    return rows
      .map((exp) => {
        const bullets = (exp.bullets || []).map((b) => `<li>${esc(b)}</li>`).join("");
        const dates = hasDisplayText(exp.dates)
          ? `<span class="tpl-job-dates">${esc(exp.dates)}</span>`
          : "";
        const subParts = joinDisplayParts([exp.company, exp.location]);
        const sub = subParts ? `<div class="tpl-job-sub">${subParts}</div>` : "";
        return `<div class="tpl-tl-item">
          <span class="tpl-tl-dot"></span>
          <div class="tpl-tl-inner">
            <div class="tpl-job-head">
              <strong>${esc(exp.title)}</strong>
              ${dates}
            </div>
            ${sub}
            ${bullets ? `<ul class="tpl-bullets">${bullets}</ul>` : ""}
          </div>
        </div>`;
      })
      .join("");
  }

  function msRow() {
    const sections = Array.from(arguments).filter((x) => String(x || "").trim());
    if (!sections.length) return "";
    if (sections.length === 1) return sections[0];
    return `<div class="tpl-ms-row">${sections.join("")}</div>`;
  }

  function hobbiesSection(d, opts) {
    opts = opts || {};
    const text = hobbiesDisplayText(d);
    if (!text) return "";
    const wrap = opts.wrap || "tpl-sec";
    const h2 = opts.h2 || "tpl-h2";
    const pClass = opts.pClass || "tpl-p";
    return `<section class="${wrap}"><h2 class="${h2}">Hobbies</h2><p class="${pClass}">${esc(text)}</p></section>`;
  }

  function interestsSection(d, opts) {
    opts = opts || {};
    const text = interestsText(d);
    if (!text) return "";
    const wrap = opts.wrap || "tpl-sec";
    const h2 = opts.h2 || "tpl-h2";
    const pClass = opts.pClass || "tpl-p";
    return `<section class="${wrap}"><h2 class="${h2}">Interests</h2><p class="${pClass}">${esc(text)}</p></section>`;
  }

  const RENDERERS = {
    minimalist(d) {
      const h2 = "tpl-h2";
      const sections = [];
      if (hasDisplayText(d.summary)) {
        sections.push(
          `<section class="tpl-sec"><h2 class="${h2}">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
        );
      }
      const jobs = resumeJobSections(d, { h2, jobClass: "tpl-job tpl-job--min" });
      if (String(jobs || "").trim()) sections.push(jobs);
      const edu = educationHtml(d);
      if (String(edu || "").trim()) {
        sections.push(`<section class="tpl-sec"><h2 class="${h2}">Education</h2>${edu}</section>`);
      }
      const skills = skillsPillsHtml(d);
      if (String(skills || "").trim()) {
        sections.push(`<section class="tpl-sec"><h2 class="${h2}">Skills</h2><div class="tpl-min-tags">${skills}</div></section>`);
      }
      const certs = certificationsHtml(d);
      if (String(certs || "").trim()) {
        sections.push(`<section class="tpl-sec"><h2 class="${h2}">Certifications</h2>${certs}</section>`);
      }
      const langs = languagesPillsHtml(d);
      if (String(langs || "").trim()) {
        sections.push(`<section class="tpl-sec"><h2 class="${h2}">Languages</h2><div class="tpl-min-tags">${langs}</div></section>`);
      }
      const hob = hobbiesSection(d, { h2, pClass: "tpl-p" });
      if (hob) sections.push(hob);
      const hobText = String(d.hobbies || "").trim();
      const intrText = interestsText(d);
      if (intrText && (!hobText || intrText !== hobText)) {
        const intr = interestsSection(d, { h2, pClass: "tpl-p" });
        if (intr) sections.push(intr);
      }
      const body = sections.filter(Boolean).join('<hr class="tpl-min-rule" />');
      const bodyBlock = body ? `<hr class="tpl-min-rule" />${body}` : "";
      const contactRow = contactRowHtml(d, "tpl-min-contact-row");
      return `<div class="tpl tpl-minimalist">
        <header class="tpl-min-head">
          <h1 class="tpl-min-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-min-title", d)}
          ${contactRow}
        </header>${bodyBlock}
      </div>`;
    },

    "classic-sidebar"(d) {
      const skillsInner = skillsListHtml(d);
      const langsInner = languagesHtml(d);
      const eduInner = educationHtml(d);
      const certsInner = certificationsHtml(d);
      const mainParts = [];
      if (hasDisplayText(d.summary)) {
        mainParts.push(
          `<section class="tpl-sec"><h2 class="tpl-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
        );
      }
      const jobs = resumeJobSections(d, { h2: "tpl-h2" });
      if (String(jobs || "").trim()) mainParts.push(jobs);
      if (String(eduInner || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="tpl-h2">Education</h2>${eduInner}</section>`);
      }
      if (String(certsInner || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="tpl-h2">Certifications</h2>${certsInner}</section>`);
      }
      const hob = hobbiesSection(d, { h2: "tpl-h2" });
      if (hob) mainParts.push(hob);
      const sideSkills = String(skillsInner || "").trim()
        ? `<h3 class="tpl-cs-h3">Skills</h3><ul class="tpl-bullets tpl-bullets--tight">${skillsInner}</ul>`
        : "";
      const sideLangs = String(langsInner || "").trim()
        ? `<h3 class="tpl-cs-h3">Languages</h3><ul class="tpl-bullets tpl-bullets--tight">${langsInner}</ul>`
        : "";
      const contactItems = contactParts(d)
        .map((x) => `<li>${x}</li>`)
        .join("");
      return `<div class="tpl tpl-classic-sidebar">
        <aside class="tpl-cs-side">
          ${photoHtml(d, "tpl-avatar")}
          <h1 class="tpl-cs-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-cs-title", d)}
          ${contactItems ? `<ul class="tpl-cs-contact">${contactItems}</ul>` : ""}
          ${sideSkills}
          ${sideLangs}
        </aside>
        <div class="tpl-cs-main">
          ${mainParts.join("")}
        </div>
      </div>`;
    },

    "colored-header"(d) {
      const contactRow = contactRowHtml(d, "tpl-ch-contact-row");
      const bodyParts = [];
      if (hasDisplayText(d.summary)) {
        bodyParts.push(
          `<section class="tpl-sec"><h2 class="tpl-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
        );
      }
      const topCol = [coloredHeaderJobsColumn(d), coloredHeaderEduSkillsColumn(d)].filter((x) =>
        String(x || "").trim()
      );
      if (topCol.length) {
        bodyParts.push(`<div class="tpl-ch-row">${topCol.join("")}</div>`);
      }
      const certsLangs = coloredHeaderCertsLangsRow(d);
      if (certsLangs) bodyParts.push(certsLangs);
      const hob = hobbiesSection(d, { h2: "tpl-h2" });
      if (hob) bodyParts.push(hob);
      return `<div class="tpl tpl-colored-header">
        <div class="tpl-ch-bar">
          <h1 class="tpl-ch-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-ch-title", d)}
          ${contactRow}
        </div>
        <div class="tpl-ch-body">${bodyParts.join("")}</div>
      </div>`;
    },

    "modern-split"(d) {
      const contactRow = contactRowHtml(d, "tpl-ms-contact-row");
      const gridParts = [];
      let summarySec = "";
      if (hasDisplayText(d.summary)) {
        summarySec = `<section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">📋</span> Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`;
      }
      const eduInner = educationHtml(d);
      let eduSec = "";
      if (String(eduInner || "").trim()) {
        eduSec = `<section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">🎓</span> Education</h2>${eduInner}</section>`;
      }
      const topRow = msRow(summarySec, eduSec);
      if (topRow) gridParts.push(topRow);
      const jobs = resumeJobSections(d, {
        h2: "tpl-h2",
        wrap: "tpl-sec tpl-ms-span2",
        titlePrefix: '<span class="tpl-ico">💼</span> ',
      });
      if (String(jobs || "").trim()) gridParts.push(jobs);
      const skillsInner = skillsListHtml(d);
      let skillsSec = "";
      if (String(skillsInner || "").trim()) {
        skillsSec = `<section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">⚡</span> Skills</h2><ul class="tpl-bullets">${skillsInner}</ul></section>`;
      }
      const langsInner = languagesHtml(d);
      let langsSec = "";
      if (String(langsInner || "").trim()) {
        langsSec = `<section class="tpl-sec"><h2 class="tpl-h2"><span class="tpl-ico">🌐</span> Languages</h2><ul class="tpl-bullets">${langsInner}</ul></section>`;
      }
      const skillsLangsRow = msRow(skillsSec, langsSec);
      if (skillsLangsRow) gridParts.push(skillsLangsRow);
      const certsInner = certificationsHtml(d);
      if (String(certsInner || "").trim()) {
        gridParts.push(
          `<section class="tpl-sec tpl-ms-span2"><h2 class="tpl-h2"><span class="tpl-ico">🏅</span> Certifications</h2>${certsInner}</section>`
        );
      }
      const hobbiesText = hobbiesDisplayText(d);
      if (hobbiesText) {
        gridParts.push(
          `<section class="tpl-sec tpl-ms-span2"><h2 class="tpl-h2"><span class="tpl-ico">🎯</span> Hobbies</h2><p class="tpl-p">${esc(hobbiesText)}</p></section>`
        );
      }
      return `<div class="tpl tpl-modern-split">
        <div class="tpl-ms-top">
          <div class="tpl-ms-brand">
            ${photoHtml(d, "tpl-ms-photo")}
            <div>
              <h1 class="tpl-ms-name">${esc(d.fullName)}</h1>
              ${tplHeadline("tpl-ms-title", d)}
            </div>
          </div>
          ${contactRow}
        </div>
        <div class="tpl-ms-grid">${gridParts.join("")}</div>
      </div>`;
    },

    "professional-border"(d) {
      const contactRow = contactRowHtml(d, "tpl-pb-contact-row");
      const mainParts = [];
      if (hasDisplayText(d.summary)) {
        mainParts.push(
          `<section class="tpl-sec"><h2 class="tpl-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
        );
      }
      const jobs = resumeJobSections(d, { h2: "tpl-h2" });
      if (String(jobs || "").trim()) mainParts.push(jobs);
      const eduInner = educationHtml(d);
      if (String(eduInner || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="tpl-h2">Education</h2>${eduInner}</section>`);
      }
      const certsInner = certificationsHtml(d);
      if (String(certsInner || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="tpl-h2">Certifications</h2>${certsInner}</section>`);
      }
      const hobbiesText = hobbiesDisplayText(d);
      if (hobbiesText) {
        mainParts.push(`<section class="tpl-sec"><h2 class="tpl-h2">Hobbies</h2><p class="tpl-p">${esc(hobbiesText)}</p></section>`);
      }
      const skillsInner = skillsListHtml(d);
      const sideSkills = String(skillsInner || "").trim()
        ? `<h3 class="tpl-pb-h3">Skills</h3><ul class="tpl-bullets tpl-bullets--tight">${skillsInner}</ul>`
        : "";
      const langsInner = languagesHtml(d);
      const sideLangs = String(langsInner || "").trim()
        ? `<h3 class="tpl-pb-h3">Languages</h3><ul class="tpl-bullets tpl-bullets--tight">${langsInner}</ul>`
        : "";
      return `<div class="tpl tpl-professional-border">
        <div class="tpl-pb-main">
          <div class="tpl-pb-header">
            <h1 class="tpl-pb-name">${esc(d.fullName)}</h1>
            ${tplHeadline("tpl-pb-title", d)}
            ${contactRow}
          </div>
          ${mainParts.join("")}
        </div>
        <aside class="tpl-pb-side">
          ${photoHtml(d, "tpl-pb-avatar")}
          ${sideSkills}
          ${sideLangs}
        </aside>
      </div>`;
    },

    "bold-header"(d) {
      const h2 = "tpl-h2";
      const sections = [];
      if (hasDisplayText(d.summary)) {
        sections.push(
          `<section class="tpl-sec"><h2 class="${h2}">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
        );
      }
      const jobs = resumeJobSections(d, { h2 });
      if (String(jobs || "").trim()) sections.push(jobs);
      const edu = educationHtml(d);
      if (String(edu || "").trim()) {
        sections.push(`<section class="tpl-sec"><h2 class="${h2}">Education</h2>${edu}</section>`);
      }
      const skills = skillsListHtml(d);
      if (String(skills || "").trim()) {
        sections.push(`<section class="tpl-sec"><h2 class="${h2}">Skills</h2><ul class="tpl-bullets">${skills}</ul></section>`);
      }
      const certs = certificationsHtml(d);
      if (String(certs || "").trim()) {
        sections.push(`<section class="tpl-sec"><h2 class="${h2}">Certifications</h2>${certs}</section>`);
      }
      const langs = languagesHtml(d);
      if (String(langs || "").trim()) {
        sections.push(`<section class="tpl-sec"><h2 class="${h2}">Languages</h2><ul class="tpl-bullets">${langs}</ul></section>`);
      }
      const hob = hobbiesSection(d, { h2, pClass: "tpl-p" });
      if (hob) sections.push(hob);
      const contactRow = contactRowHtml(d, "tpl-bh-contact-row");
      return `<div class="tpl tpl-bold-header">
        <header class="tpl-bh-bar">
          <h1 class="tpl-bh-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-bh-title", d)}
          ${contactRow}
        </header>
        <div class="tpl-bh-body">${sections.join("")}</div>
      </div>`;
    },

    "tech-focus"(d) {
      const h2 = "tpl-h2";
      const sideParts = [];
      const skills = skillBarsHtml(d);
      if (String(skills || "").trim()) {
        sideParts.push(`<h2 class="tpl-tf-h2">Skills</h2>${skills}`);
      }
      const langsInner = languagesHtml(d);
      if (String(langsInner || "").trim()) {
        sideParts.push(
          `<h2 class="tpl-tf-h2">Languages</h2><ul class="tpl-bullets tpl-bullets--tight">${langsInner}</ul>`
        );
      }
      const contactItems = contactParts(d)
        .map((x) => `<li>${x}</li>`)
        .join("");
      if (contactItems) {
        sideParts.push(
          `<h2 class="tpl-tf-h2">Contact</h2><ul class="tpl-bullets tpl-bullets--tight tpl-tf-contact">${contactItems}</ul>`
        );
      }
      const mainParts = [];
      if (hasDisplayText(d.summary)) {
        mainParts.push(
          `<section class="tpl-sec"><h2 class="${h2}">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
        );
      }
      const jobs = resumeJobSections(d, { h2 });
      if (String(jobs || "").trim()) mainParts.push(jobs);
      const edu = educationHtml(d);
      if (String(edu || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="${h2}">Education</h2>${edu}</section>`);
      }
      const certs = certificationsHtml(d);
      if (String(certs || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="${h2}">Certifications</h2>${certs}</section>`);
      }
      const hob = hobbiesSection(d, { h2, pClass: "tpl-p" });
      if (hob) mainParts.push(hob);
      return `<div class="tpl tpl-tech-focus">
        <aside class="tpl-tf-side">${sideParts.join("")}</aside>
        <div class="tpl-tf-main">
          <header class="tpl-tf-head">
            <h1 class="tpl-tf-name">${esc(d.fullName)}</h1>
            ${tplHeadline("tpl-tf-title", d)}
          </header>
          ${mainParts.join("")}
        </div>
      </div>`;
    },

    "elegant-serif"(d) {
      const contact = contactParts(d).join(" · ");
      return `<div class="tpl tpl-elegant-serif">
        <header class="tpl-el-head">
          <h1 class="tpl-el-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-el-title", d)}
          <p class="tpl-el-contact">${contact}</p>
        </header>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Career Objective</h2><p class="tpl-el-p">${esc(d.summary)}</p></section>
        ${resumeJobSections(d, { h2: "tpl-el-h2", jobClass: "tpl-job tpl-job--elegant" })}
        <section class="tpl-sec"><h2 class="tpl-el-h2">Education</h2>${educationHtml(d)}</section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Skills</h2><p class="tpl-el-p">${(d.skills || []).map((s) => esc(s.name)).join(" · ")}</p></section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Certifications</h2>${certificationsHtml(d)}</section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Languages</h2><ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
        <section class="tpl-sec"><h2 class="tpl-el-h2">Interests</h2><p class="tpl-el-p">${esc(interestsText(d))}</p></section>
      </div>`;
    },

    geometric(d) {
      const h2 = "tpl-geo-h2";
      const pills = skillsPillsHtml(d);
      const skillsAside = String(pills || "").trim()
        ? `<aside class="tpl-geo-aside"><h2 class="${h2}">Skills</h2><div class="tpl-geo-pills">${pills}</div></aside>`
        : "";
      const mainParts = [];
      const edu = educationHtml(d);
      if (String(edu || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="${h2}">Education</h2>${edu}</section>`);
      }
      const certs = certificationsHtml(d);
      if (String(certs || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="${h2}">Certifications</h2>${certs}</section>`);
      }
      const langsInner = languagesHtml(d);
      if (String(langsInner || "").trim()) {
        mainParts.push(
          `<section class="tpl-sec"><h2 class="${h2}">Languages</h2><ul class="tpl-bullets">${langsInner}</ul></section>`
        );
      }
      const hob = hobbiesSection(d, { h2 });
      if (hob) mainParts.push(hob);
      const layout =
        mainParts.length || skillsAside
          ? `<div class="tpl-geo-layout"><div class="tpl-geo-main">${mainParts.join("")}</div>${skillsAside}</div>`
          : "";
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-geo-contact-row">${contactItems.join('<span class="tpl-geo-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const topParts = [];
      if (hasDisplayText(d.summary)) {
        topParts.push(
          `<section class="tpl-sec"><h2 class="${h2}">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
        );
      }
      const jobs = resumeJobSections(d, { h2 });
      if (String(jobs || "").trim()) topParts.push(jobs);
      return `<div class="tpl tpl-geometric">
        <header class="tpl-geo-head">
          ${photoHtml(d, "tpl-geo-photo")}
          <div class="tpl-geo-text">
            <h1 class="tpl-geo-name">${esc(d.fullName)}</h1>
            ${tplHeadline("tpl-geo-title", d)}
            ${contactHtml}
          </div>
        </header>
        ${topParts.join("")}
        ${layout}
      </div>`;
    },

    "high-contrast"(d) {
      const h2 = "tpl-h2 tpl-h2--hc";
      const sideParts = [];
      const skills = skillsListHtml(d);
      if (String(skills || "").trim()) {
        sideParts.push(`<h3 class="tpl-hc-h3">Skills</h3><ul class="tpl-bullets">${skills}</ul>`);
      }
      const langs = languagesHtml(d);
      if (String(langs || "").trim()) {
        sideParts.push(`<h3 class="tpl-hc-h3">Languages</h3><ul class="tpl-bullets">${langs}</ul>`);
      }
      const hob = hobbiesDisplayText(d);
      if (hob) {
        sideParts.push(`<h3 class="tpl-hc-h3">Hobbies</h3><p class="tpl-hc-small">${esc(hob)}</p>`);
      }
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-hc-contact-row">${contactItems.join('<span class="tpl-hc-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const mainParts = [];
      if (hasDisplayText(d.summary)) {
        mainParts.push(
          `<section class="tpl-sec"><h2 class="${h2}">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
        );
      }
      const jobs = resumeJobSections(d, { h2 });
      if (String(jobs || "").trim()) mainParts.push(jobs);
      const edu = educationHtml(d);
      if (String(edu || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="${h2}">Education</h2>${edu}</section>`);
      }
      const certs = certificationsHtml(d);
      if (String(certs || "").trim()) {
        mainParts.push(`<section class="tpl-sec"><h2 class="${h2}">Certifications</h2>${certs}</section>`);
      }
      return `<div class="tpl tpl-high-contrast">
        <header class="tpl-hc-top">
          <h1 class="tpl-hc-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-hc-title", d)}
          ${contactHtml}
        </header>
        <div class="tpl-hc-body">
          <aside class="tpl-hc-side">${sideParts.join("")}</aside>
          <div class="tpl-hc-main">${mainParts.join("")}</div>
        </div>
      </div>`;
    },

    aurora(d) {
      const h2 = "tpl-au-h2";
      const wrap = "tpl-au-card";
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-au-contact-row">${contactItems.join('<span class="tpl-au-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const jobs = resumeJobSections(d, { h2, wrap });
      const rowParts = [];
      const edu = educationHtml(d);
      if (String(edu || "").trim()) {
        rowParts.push(
          `<section class="${wrap} ${wrap}--half"><h2 class="${h2}">Education</h2>${edu}</section>`
        );
      }
      const skills = skillsListHtml(d);
      if (String(skills || "").trim()) {
        rowParts.push(
          `<section class="${wrap} ${wrap}--half"><h2 class="${h2}">Skills</h2><ul class="tpl-bullets">${skills}</ul></section>`
        );
      }
      const rowHtml = rowParts.length ? `<div class="tpl-au-row">${rowParts.join("")}</div>` : "";
      const certs = certificationsHtml(d);
      const langs = languagesHtml(d);
      const certRowParts = [];
      if (String(certs || "").trim()) {
        certRowParts.push(
          `<section class="${wrap} ${wrap}--half"><h2 class="${h2}">Certifications</h2>${certs}</section>`
        );
      }
      if (String(langs || "").trim()) {
        certRowParts.push(
          `<section class="${wrap} ${wrap}--half"><h2 class="${h2}">Languages</h2><ul class="tpl-bullets">${langs}</ul></section>`
        );
      }
      const certRowHtml = certRowParts.length
        ? `<div class="tpl-au-row">${certRowParts.join("")}</div>`
        : "";
      const hob = hobbiesSection(d, { h2, wrap, pClass: "tpl-p" });
      const bodyHtml = [
        hasDisplayText(d.summary)
          ? `<section class="${wrap}"><h2 class="${h2}">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>`
          : "",
        jobs,
        rowHtml,
        certRowHtml,
        hob,
      ]
        .filter((part) => String(part || "").trim())
        .join("");
      return `<div class="tpl tpl-aurora">
        <div class="tpl-au-hero">
          ${photoHtml(d, "tpl-au-photo")}
          <div class="tpl-au-hero-text">
            <h1 class="tpl-au-name">${esc(d.fullName)}</h1>
            ${tplHeadline("tpl-au-tagline", d)}
            ${contactHtml}
          </div>
        </div>
        <div class="tpl-au-body">${bodyHtml}</div>
      </div>`;
    },

    magazine(d) {
      const jobClass = "tpl-job tpl-job--mz";
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-mz-contact-row">${contactItems.join('<span class="tpl-mz-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const mainParts = [];
      if (hasDisplayText(d.summary)) {
        mainParts.push(
          `<h2 class="tpl-mz-h2">Career Objective</h2><p class="tpl-mz-lead">${esc(d.summary)}</p>`
        );
      }
      const addMain = (title, html) => {
        if (String(html || "").trim()) {
          mainParts.push(`<h2 class="tpl-mz-h2">${title}</h2>${html}`);
        }
      };
      addMain(PROJECTS_TITLE, projectsHtml(d, jobClass));
      addMain(ACHIEVEMENTS_ACTIVITIES_TITLE, achievementsHtml(d, jobClass));
      addMain(WORK_EXPERIENCE_TITLE, workExperienceHtml(d, jobClass));
      const asideParts = [photoHtml(d, "tpl-mz-photo")];
      const skills = skillsPillsHtml(d);
      if (String(skills || "").trim()) {
        asideParts.push(`<h3 class="tpl-mz-h3">Skills</h3><div class="tpl-mz-pills">${skills}</div>`);
      }
      const edu = educationHtml(d);
      if (String(edu || "").trim()) {
        asideParts.push(`<h3 class="tpl-mz-h3">Education</h3>${edu}`);
      }
      const langs = languagesHtml(d);
      if (String(langs || "").trim()) {
        asideParts.push(
          `<h3 class="tpl-mz-h3">Languages</h3><ul class="tpl-bullets tpl-bullets--tight">${langs}</ul>`
        );
      }
      const certs = certificationsHtml(d);
      if (String(certs || "").trim()) {
        asideParts.push(`<h3 class="tpl-mz-h3">Certifications</h3>${certs}`);
      }
      const hob = hobbiesDisplayText(d);
      if (hob) {
        asideParts.push(`<h3 class="tpl-mz-h3">Hobbies</h3><p class="tpl-p">${esc(hob)}</p>`);
      }
      return `<div class="tpl tpl-magazine">
        <header class="tpl-mz-header">
          <div class="tpl-mz-accent"></div>
          <div class="tpl-mz-intro">
            <p class="tpl-mz-kicker">Professional profile</p>
            <h1 class="tpl-mz-name">${esc(d.fullName)}</h1>
            ${tplHeadline("tpl-mz-title", d)}
            ${contactHtml}
          </div>
        </header>
        <div class="tpl-mz-grid">
          <section class="tpl-mz-col">${mainParts.join("")}</section>
          <aside class="tpl-mz-aside">${asideParts.join("")}</aside>
        </div>
      </div>`;
    },

    timeline(d) {
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-tl-contact-row">${contactItems.join('<span class="tpl-tl-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const edu = educationHtml(d);
      const skills = skillsListHtml(d);
      const twoColParts = [];
      if (String(edu || "").trim()) {
        twoColParts.push(
          `<section class="tpl-sec"><h2 class="tpl-tl-section-title">Education</h2>${edu}</section>`
        );
      }
      if (String(skills || "").trim()) {
        twoColParts.push(
          `<section class="tpl-sec"><h2 class="tpl-tl-section-title">Skills</h2><ul class="tpl-bullets tpl-tl-skills-list">${skills}</ul></section>`
        );
      }
      const twoCol = twoColParts.length ? `<div class="tpl-tl-two">${twoColParts.join("")}</div>` : "";
      const certs = certificationsHtml(d);
      const langs = languagesHtml(d);
      return `<div class="tpl tpl-timeline">
        <header class="tpl-tl-head">
          <h1 class="tpl-tl-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-tl-sub", d)}
          ${contactHtml}
        </header>
        ${hasDisplayText(d.summary) ? `<section class="tpl-sec"><h2 class="tpl-tl-section-title">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>` : ""}
        ${projectsFromData(d).length ? `<section class="tpl-sec"><h2 class="tpl-tl-section-title">${PROJECTS_TITLE}</h2><div class="tpl-tl-track">${experienceTimelineHtml(d, projectsFromData(d))}</div></section>` : ""}
        ${achievementsFromData(d).length ? `<section class="tpl-sec"><h2 class="tpl-tl-section-title">${ACHIEVEMENTS_ACTIVITIES_TITLE}</h2><div class="tpl-tl-track">${experienceTimelineHtml(d, achievementsFromData(d))}</div></section>` : ""}
        ${workExperienceFromData(d).length ? `<section class="tpl-sec"><h2 class="tpl-tl-section-title">${WORK_EXPERIENCE_TITLE}</h2><div class="tpl-tl-track">${experienceTimelineHtml(d, workExperienceFromData(d))}</div></section>` : ""}
        ${twoCol}
        ${String(certs || "").trim() ? `<section class="tpl-sec"><h2 class="tpl-tl-section-title">Certifications</h2>${certs}</section>` : ""}
        ${String(langs || "").trim() ? `<section class="tpl-sec"><h2 class="tpl-tl-section-title">Languages</h2><ul class="tpl-bullets">${langs}</ul></section>` : ""}
        ${hobbiesSection(d, { h2: "tpl-tl-section-title" })}
      </div>`;
    },

    executive(d) {
      const contactItems = contactParts(d);
      const contactBlock = contactItems.length
        ? `<h2 class="tpl-ex-h2">Contact</h2><ul class="tpl-ex-list tpl-ex-contact">${contactItems.map((x) => `<li>${x}</li>`).join("")}</ul>`
        : "";
      const skills = skillsListHtml(d);
      const skillsBlock = String(skills || "").trim()
        ? `<h2 class="tpl-ex-h2">Core skills</h2><ul class="tpl-bullets tpl-bullets--tight">${skills}</ul>`
        : "";
      const langs = languagesHtml(d);
      const langsBlock = String(langs || "").trim()
        ? `<h2 class="tpl-ex-h2">Languages</h2><ul class="tpl-bullets tpl-bullets--tight">${langs}</ul>`
        : "";
      const edu = educationHtml(d);
      const certs = certificationsHtml(d);
      return `<div class="tpl tpl-executive">
        <aside class="tpl-ex-side">
          ${photoHtml(d, "tpl-ex-photo")}
          ${contactBlock}
          ${skillsBlock}
          ${langsBlock}
        </aside>
        <div class="tpl-ex-main">
          <header class="tpl-ex-top">
            <h1 class="tpl-ex-name">${esc(d.fullName)}</h1>
            ${tplHeadline("tpl-ex-title", d)}
          </header>
          ${hasDisplayText(d.summary) ? `<section class="tpl-sec"><h2 class="tpl-ex-h2-main">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>` : ""}
          ${resumeJobSections(d, { h2: "tpl-ex-h2-main" })}
          ${String(edu || "").trim() ? `<section class="tpl-sec"><h2 class="tpl-ex-h2-main">Education</h2>${edu}</section>` : ""}
          ${String(certs || "").trim() ? `<section class="tpl-sec"><h2 class="tpl-ex-h2-main">Certifications</h2>${certs}</section>` : ""}
          ${hobbiesSection(d, { h2: "tpl-ex-h2-main" })}
        </div>
      </div>`;
    },

    studio(d) {
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-st-contact-row">${contactItems.join('<span class="tpl-st-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const pills = skillsPillsHtml(d);
      const pillsHtml = String(pills || "").trim()
        ? `<div class="tpl-st-skills">${pills}</div>`
        : "";
      const edu = educationHtml(d);
      const langs = languagesHtml(d);
      const splitParts = [];
      if (String(edu || "").trim()) {
        splitParts.push(
          `<section class="tpl-st-card"><h2 class="tpl-st-h2">Education</h2>${edu}</section>`
        );
      }
      if (String(langs || "").trim()) {
        splitParts.push(
          `<section class="tpl-st-card"><h2 class="tpl-st-h2">Languages</h2><ul class="tpl-bullets">${langs}</ul></section>`
        );
      }
      const splitHtml = splitParts.length ? `<div class="tpl-st-split">${splitParts.join("")}</div>` : "";
      const certs = certificationsHtml(d);
      return `<div class="tpl tpl-studio">
        <header class="tpl-st-hero">
          <div class="tpl-st-hero-inner">
            ${photoHtml(d, "tpl-st-photo")}
            <div>
              <h1 class="tpl-st-name">${esc(d.fullName)}</h1>
              ${tplHeadline("tpl-st-tagline", d)}
              ${contactHtml}
            </div>
          </div>
          ${pillsHtml}
        </header>
        <div class="tpl-st-body">
          ${hasDisplayText(d.summary) ? `<section class="tpl-st-card"><h2 class="tpl-st-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>` : ""}
          ${resumeJobSections(d, { h2: "tpl-st-h2", wrap: "tpl-st-card", jobClass: "tpl-job tpl-job--st" })}
          ${splitHtml}
          ${String(certs || "").trim() ? `<section class="tpl-st-card"><h2 class="tpl-st-h2">Certifications</h2>${certs}</section>` : ""}
          ${hobbiesSection(d, { h2: "tpl-st-h2", wrap: "tpl-st-card" })}
        </div>
      </div>`;
    },

    nova(d) {
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-nv-contact-row">${contactItems.join('<span class="tpl-nv-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const edu = educationHtml(d);
      const pills = skillsPillsHtml(d);
      const splitParts = [];
      if (String(edu || "").trim()) {
        splitParts.push(
          `<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Education</h2>${edu}</section>`
        );
      }
      if (String(pills || "").trim()) {
        splitParts.push(
          `<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Skills</h2><div class="tpl-nv-pills">${pills}</div></section>`
        );
      }
      const splitHtml = splitParts.length ? `<div class="tpl-nv-split">${splitParts.join("")}</div>` : "";
      const certs = certificationsHtml(d);
      const langs = languagesHtml(d);
      return `<div class="tpl tpl-nova">
        <div class="tpl-nv-hero">
          <div class="tpl-nv-blob" aria-hidden="true"></div>
          <div class="tpl-nv-card">
            ${photoHtml(d, "tpl-nv-photo")}
            <div class="tpl-nv-intro">
              <h1 class="tpl-nv-name">${esc(d.fullName)}</h1>
              ${tplHeadline("tpl-nv-tagline", d)}
              ${contactHtml}
            </div>
          </div>
        </div>
        <div class="tpl-nv-body">
          ${hasDisplayText(d.summary) ? `<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>` : ""}
          ${resumeJobSections(d, { h2: "tpl-nv-h2", wrap: "tpl-nv-panel" })}
          ${splitHtml}
          ${String(certs || "").trim() ? `<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Certifications</h2>${certs}</section>` : ""}
          ${String(langs || "").trim() ? `<section class="tpl-nv-panel"><h2 class="tpl-nv-h2">Languages</h2><ul class="tpl-bullets">${langs}</ul></section>` : ""}
          ${hobbiesSection(d, { h2: "tpl-nv-h2", wrap: "tpl-nv-panel" })}
        </div>
      </div>`;
    },

    ledger(d) {
      return `<div class="tpl tpl-ledger">
        <header class="tpl-lg-head">
          <h1 class="tpl-lg-name">${esc(d.fullName)}</h1>
          ${hasDisplayText(d.headline) ? `<p class="tpl-lg-meta"><span class="tpl-lg-label">ROLE</span> ${esc(d.headline)}</p>` : ""}
          <p class="tpl-lg-meta"><span class="tpl-lg-label">CONTACT</span> ${contactParts(d).join(" · ")}</p>
        </header>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Career Objective</h2><p class="tpl-lg-p">${esc(d.summary)}</p></section>
        ${projectsSection(d, { h2: "tpl-lg-h2", wrap: "tpl-lg-block", titlePrefix: '<span class="tpl-lg-hash">#</span> ', jobClass: "tpl-job tpl-job--lg" })}
        ${achievementsSection(d, { h2: "tpl-lg-h2", wrap: "tpl-lg-block", titlePrefix: '<span class="tpl-lg-hash">#</span> ', jobClass: "tpl-job tpl-job--lg" })}
        ${workExperienceSection(d, { h2: "tpl-lg-h2", wrap: "tpl-lg-block", titlePrefix: '<span class="tpl-lg-hash">#</span> ', jobClass: "tpl-job tpl-job--lg" })}
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Education</h2>${educationHtml(d)}</section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Skills</h2><ul class="tpl-lg-list">${skillsListHtml(d)}</ul></section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Certifications</h2>${certificationsHtml(d)}</section>
        <section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Languages</h2><ul class="tpl-lg-list">${languagesHtml(d)}</ul></section>
        ${hasDisplayText(d.hobbies) ? `<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Hobbies</h2><p class="tpl-lg-p">${esc(d.hobbies)}</p></section>` : ""}
        ${hasDisplayText(interestsText(d)) ? `<section class="tpl-lg-block"><h2 class="tpl-lg-h2"><span class="tpl-lg-hash">#</span> Interests</h2><p class="tpl-lg-p">${esc(interestsText(d))}</p></section>` : ""}
      </div>`;
    },

    horizon(d) {
      const pills = skillsPillsHtml(d);
      const splitParts = [];
      if ((d.education || []).length) {
        splitParts.push(
          `<section class="tpl-hz-panel"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Education</h2>${educationHtml(d)}</section>`
        );
      }
      if (pills) {
        splitParts.push(
          `<section class="tpl-hz-panel"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Skills</h2><div class="tpl-hz-pills">${pills}</div></section>`
        );
      }
      const splitHtml = splitParts.length
        ? `<div class="tpl-hz-split">${splitParts.join("")}</div>`
        : "";
      return `<div class="tpl tpl-horizon">
        <header class="tpl-hz-head">
          <h1 class="tpl-hz-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-hz-title", d)}
          <p class="tpl-hz-contact">${contactParts(d).join(" · ")}</p>
        </header>
        <section class="tpl-hz-sec"><div class="tpl-hz-bar"></div><h2 class="tpl-hz-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>
        ${hzJobSection(ACHIEVEMENTS_ACTIVITIES_TITLE, achievementsHtml(d))}
        ${hzJobSection(PROJECTS_TITLE, projectsHtml(d))}
        ${hzJobSection(WORK_EXPERIENCE_TITLE, workExperienceHtml(d))}
        ${splitHtml}
        ${hzBarSection("Certifications", certificationsHtml(d))}
        ${hzBarSection("Languages", `<ul class="tpl-bullets">${languagesHtml(d)}</ul>`)}
        ${hzBarSection("Hobbies", hasDisplayText(d.hobbies) ? `<p class="tpl-p">${esc(d.hobbies)}</p>` : "")}
        ${hzBarSection("Interests", hasDisplayText(interestsText(d)) ? `<p class="tpl-p">${esc(interestsText(d))}</p>` : "")}
      </div>`;
    },

    folio(d) {
      let foNum = 0;
      function nextFoNum() {
        foNum += 1;
        return String(foNum).padStart(2, "0");
      }
      function foSec(title, inner) {
        if (!String(inner || "").trim()) return "";
        return `<section class="tpl-fo-sec"><span class="tpl-fo-num">${nextFoNum()}</span><div class="tpl-fo-content"><h2 class="tpl-fo-h2">${title}</h2>${inner}</div></section>`;
      }
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-fo-contact-row">${contactItems.join('<span class="tpl-fo-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const skillNames = (d.skills || []).map((s) => esc(s.name)).filter(Boolean).join(" · ");
      const langs = languagesHtml(d);
      const hobbiesText = hobbiesDisplayText(d);
      return `<div class="tpl tpl-folio">
        <header class="tpl-fo-head">
          ${photoHtml(d, "tpl-fo-photo")}
          <div class="tpl-fo-head-text">
            <h1 class="tpl-fo-name">${esc(d.fullName)}</h1>
            ${tplHeadline("tpl-fo-line", d)}
            ${contactHtml}
          </div>
        </header>
        ${foSec("Career Objective", hasDisplayText(d.summary) ? `<p class="tpl-p">${esc(d.summary)}</p>` : "")}
        ${foSec(PROJECTS_TITLE, projectsHtml(d, "tpl-job tpl-job--fo"))}
        ${foSec(ACHIEVEMENTS_ACTIVITIES_TITLE, achievementsHtml(d, "tpl-job tpl-job--fo"))}
        ${foSec(WORK_EXPERIENCE_TITLE, workExperienceHtml(d, "tpl-job tpl-job--fo"))}
        ${foSec("Education", educationHtml(d))}
        ${foSec("Skills", skillNames ? `<p class="tpl-fo-skills">${skillNames}</p>` : "")}
        ${foSec("Certifications", certificationsHtml(d))}
        ${foSec("Languages", langs ? `<ul class="tpl-bullets">${langs}</ul>` : "")}
        ${foSec("Hobbies", hobbiesText ? `<p class="tpl-p">${esc(hobbiesText)}</p>` : "")}
      </div>`;
    },

    vertex(d) {
      const contactItems = contactParts(d);
      const contactHtml = contactItems.length
        ? `<div class="tpl-vx-contact-row">${contactItems.join('<span class="tpl-vx-contact-sep" aria-hidden="true"> · </span>')}</div>`
        : "";
      const edu = educationHtml(d);
      const skills = skillsListHtml(d);
      const gridParts = [];
      if (String(edu || "").trim()) {
        gridParts.push(
          `<section class="tpl-sec"><h2 class="tpl-vx-h2">Education</h2>${edu}</section>`
        );
      }
      if (String(skills || "").trim()) {
        gridParts.push(
          `<section class="tpl-sec tpl-vx-skills"><h2 class="tpl-vx-h2">Skills</h2><ul class="tpl-bullets">${skills}</ul></section>`
        );
      }
      const gridHtml = gridParts.length ? `<div class="tpl-vx-grid">${gridParts.join("")}</div>` : "";
      const certs = certificationsHtml(d);
      const langs = languagesHtml(d);
      return `<div class="tpl tpl-vertex">
        <header class="tpl-vx-banner">
          <div class="tpl-vx-banner-inner">
            <div class="tpl-vx-banner-row">
              <div class="tpl-vx-banner-main">
                <div class="tpl-vx-banner-text">
                  <h1 class="tpl-vx-name">${esc(d.fullName)}</h1>
                  ${tplHeadline("tpl-vx-title", d)}
                  ${contactHtml}
                </div>
                <div class="tpl-vx-banner-photo">${photoHtml(d, "tpl-vx-photo")}</div>
              </div>
            </div>
          </div>
        </header>
        <div class="tpl-vx-body">
          ${hasDisplayText(d.summary) ? `<section class="tpl-sec"><h2 class="tpl-vx-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>` : ""}
          ${resumeJobSections(d, { h2: "tpl-vx-h2" })}
          ${gridHtml}
          ${String(certs || "").trim() ? `<section class="tpl-sec"><h2 class="tpl-vx-h2">Certifications</h2>${certs}</section>` : ""}
          ${String(langs || "").trim() ? `<section class="tpl-sec"><h2 class="tpl-vx-h2">Languages</h2><ul class="tpl-bullets">${langs}</ul></section>` : ""}
          ${hobbiesSection(d, { h2: "tpl-vx-h2" })}
        </div>
      </div>`;
    },

    "atlantic-pro"(d) {
      return `<div class="tpl tpl-atlantic-pro">
        <header class="tpl-ap-head">
          <h1 class="tpl-ap-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-ap-title", d)}
          <p class="tpl-ap-contact">${contactParts(d).join(" · ")}</p>
        </header>
        <section class="tpl-sec"><h2 class="tpl-ap-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>
        <div class="tpl-ap-grid">
          ${resumeJobSections(d, { h2: "tpl-ap-h2" })}
          <aside class="tpl-ap-side">
            <h3 class="tpl-ap-h3">Skills</h3>
            <ul class="tpl-bullets tpl-bullets--tight">${skillsListHtml(d)}</ul>
            <h3 class="tpl-ap-h3">Languages</h3>
            <ul class="tpl-bullets tpl-bullets--tight">${languagesHtml(d)}</ul>
            <h3 class="tpl-ap-h3">Certifications</h3>
            ${certificationsHtml(d)}
          </aside>
        </div>
        <section class="tpl-sec"><h2 class="tpl-ap-h2">Education</h2>${educationHtml(d)}</section>
        <section class="tpl-sec"><h2 class="tpl-ap-h2">Interests</h2><p class="tpl-p">${esc(interestsText(d))}</p></section>
      </div>`;
    },

    "zen-column"(d) {
      return `<div class="tpl tpl-zen-column">
        <header class="tpl-zc-head">
          <h1 class="tpl-zc-name">${esc(d.fullName)}</h1>
          ${tplHeadline("tpl-zc-title", d)}
          <p class="tpl-zc-contact">${contactParts(d).join(" · ")}</p>
        </header>
        <section class="tpl-sec"><h2 class="tpl-zc-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>
        ${resumeJobSections(d, { h2: "tpl-zc-h2", jobClass: "tpl-job tpl-job--zc" })}
        <section class="tpl-sec"><h2 class="tpl-zc-h2">Education</h2>${educationHtml(d)}</section>
        <section class="tpl-sec"><h2 class="tpl-zc-h2">Skills</h2><div class="tpl-zc-pills">${skillsPillsHtml(d)}</div></section>
        <section class="tpl-sec"><h2 class="tpl-zc-h2">Certifications &amp; Languages</h2>${certificationsHtml(d)}<ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
        <section class="tpl-sec"><h2 class="tpl-zc-h2">Interests</h2><p class="tpl-p">${esc(interestsText(d))}</p></section>
      </div>`;
    },

    "global-grid"(d) {
      return `<div class="tpl tpl-global-grid">
        <header class="tpl-gg-head">
          <div>
            <h1 class="tpl-gg-name">${esc(d.fullName)}</h1>
            ${tplHeadline("tpl-gg-title", d)}
          </div>
          ${photoHtml(d, "tpl-gg-photo")}
        </header>
        <p class="tpl-gg-contact">${contactParts(d).join(" · ")}</p>
        <div class="tpl-gg-layout">
          <section class="tpl-sec tpl-gg-main"><h2 class="tpl-gg-h2">Career Objective</h2><p class="tpl-p">${esc(d.summary)}</p></section>
          ${resumeJobSections(d, { h2: "tpl-gg-h2", wrap: "tpl-sec tpl-gg-main" })}
          <section class="tpl-sec tpl-gg-half"><h2 class="tpl-gg-h2">Education</h2>${educationHtml(d)}</section>
          <section class="tpl-sec tpl-gg-half"><h2 class="tpl-gg-h2">Skills</h2><ul class="tpl-bullets">${skillsListHtml(d)}</ul></section>
          <section class="tpl-sec tpl-gg-half"><h2 class="tpl-gg-h2">Languages</h2><ul class="tpl-bullets">${languagesHtml(d)}</ul></section>
          <section class="tpl-sec tpl-gg-half"><h2 class="tpl-gg-h2">Certifications</h2>${certificationsHtml(d)}</section>
          <section class="tpl-sec tpl-gg-main"><h2 class="tpl-gg-h2">Interests</h2><p class="tpl-p">${esc(interestsText(d))}</p></section>
        </div>
      </div>`;
    },
  };

  RENDERERS["global-elegance"] = RENDERERS.magazine;
  RENDERERS["euro-corporate"] = RENDERERS.executive;
  RENDERERS["tokyo-minimal"] = RENDERERS.minimalist;
  RENDERERS["nordic-clean"] = RENDERERS.horizon;

  function applyStudioDraftUpdate(draft) {
    if (!draft || typeof draft !== "object" || !draft.resume || typeof draft.resume !== "object") return;
    resumeData = deepMergeResume(resumeData, draft.resume);
    forceClientPreview = true;
    renderPreview();
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ type: "TT_STUDIO_PREVIEW_UPDATED" }, "*");
      }
    } catch (_) {}
  }

  function renderPreview() {
    const serverTpl = document.getElementById("tt-server-mount-html");
    if (serverTpl && String(serverTpl.innerHTML || "").trim() && !forceClientPreview) {
      resumeMount.innerHTML = serverTpl.innerHTML;
      const tid = serverTpl.getAttribute("data-template") || activeTemplateId;
      activeTemplateId = tid;
      resumeEl.setAttribute("data-template", tid);
      updateScore();
      return;
    }
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
        <legend>Career Objective</legend>
        <label><textarea data-bind="summary" rows="5">${esc(d.summary)}</textarea></label>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Skills</legend>
        ${skillBlocks}
        <button type="button" class="btn-add" data-action="add-skill">+ Add skill</button>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Achievements & Activities</legend>
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
        <legend>Hobbies</legend>
        <label><textarea data-bind="hobbies" rows="3">${esc(d.hobbies)}</textarea></label>
      </fieldset>
      <fieldset class="editor-fs">
        <legend>Interests</legend>
        <label><textarea data-bind="interests" rows="3">${esc(interestsText(d))}</textarea></label>
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

  function applyBodyFontSize(cssValue) {
    document.documentElement.style.setProperty("--body-size", cssValue);
    if (resumeEl) resumeEl.style.fontSize = cssValue;
    var picked = FONT_SIZES.find(function (s) { return s.css === cssValue; }) || FONT_SIZES[1];
    document.documentElement.style.setProperty("--font-scale", String(picked.scale || 1));
  }

  function renderFontSizes() {
    if (!fontSize) return;
    fontSize.innerHTML = "";
    FONT_SIZES.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.label;
      fontSize.appendChild(opt);
    });
    fontSize.value = activeFontSizeId;
    fontSize.addEventListener("change", () => {
      const chosen = FONT_SIZES.find((s) => s.id === fontSize.value) || FONT_SIZES[1];
      activeFontSizeId = chosen.id;
      applyBodyFontSize(chosen.css);
      renderPreview();
      scheduleSave();
    });
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
    add(interestsText(d), 4);
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
    if (pdfBusy) return;
    pdfBusy = true;
    if (typeof window.html2pdf === "undefined") {
      pdfBusy = false;
      alert("PDF library failed to load. Use Print and choose Save as PDF instead.");
      return;
    }
    // Ensure the latest selected template and edits are painted before export.
    renderPreview();
    const el = resumeEl;
    const heavyTemplates = new Set([
      "aurora",
      "magazine",
      "executive",
      "global-elegance",
      "euro-corporate",
      "atlantic-pro",
    ]);
    const currentTemplateId = String(activeTemplateId || "");
    const isHeavyTemplate = heavyTemplates.has(currentTemplateId);
    const clone = el.cloneNode(true);
    const pdfMarginMm = 4;
    const pdfContentWidthMm = 210 - pdfMarginMm * 2;
    // Avoid cross-origin image failures that can stop html2canvas/PDF generation.
    clone.querySelectorAll("img").forEach((img) => {
      try {
        img.setAttribute("crossorigin", "anonymous");
        img.setAttribute("referrerpolicy", "no-referrer");
      } catch (_) {}
    });
    const holder = document.createElement("div");
    holder.style.position = "fixed";
    holder.style.left = "-99999px";
    holder.style.top = "0";
    holder.style.width = `${pdfContentWidthMm}mm`;
    holder.style.background = "#fff";
    holder.appendChild(clone);
    document.body.appendChild(holder);
    clone.classList.add("pdf-exporting");
    // Keep icon visuals in PDF: convert inline SVGs to data-image nodes for html2canvas.
    clone.querySelectorAll(".tpl-contact-icon svg").forEach((svg) => {
      try {
        const computedColor = getComputedStyle(svg).color || "#111111";
        const svgClone = svg.cloneNode(true);
        svgClone.setAttribute("fill", computedColor);
        svgClone.setAttribute("color", computedColor);
        svgClone.querySelectorAll("[fill='currentColor']").forEach((el) => {
          el.setAttribute("fill", computedColor);
        });
        const serialized = new XMLSerializer()
          .serializeToString(svgClone)
          .replace(/currentColor/g, computedColor);
        const img = document.createElement("img");
        img.className = "tpl-contact-icon-img";
        img.setAttribute("alt", "");
        img.setAttribute("aria-hidden", "true");
        img.setAttribute("src", `data:image/svg+xml;charset=utf-8,${encodeURIComponent(serialized)}`);
        svg.replaceWith(img);
      } catch (_) {}
    });
    const opt = {
      margin: [pdfMarginMm, pdfMarginMm, pdfMarginMm, pdfMarginMm],
      filename: `${safeFilename(resumeData.fullName)}.pdf`,
      image: { type: "jpeg", quality: 0.93 },
      html2canvas: {
        scale: isHeavyTemplate ? 1.6 : 2,
        useCORS: true,
        logging: false,
        letterRendering: true,
        scrollY: 0,
      },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      // avoid-all can force large white gaps for complex template blocks
      pagebreak: { mode: ["css", "legacy"], avoid: [".tpl-sec", ".tpl-job", ".tpl-edu-block", ".tpl-cert"] },
    };
    const done = () => {
      if (watchdog) {
        clearTimeout(watchdog);
        watchdog = null;
      }
      try {
        clone.classList.remove("pdf-exporting");
      } catch (_) {}
      try {
        holder.remove();
      } catch (_) {}
      pdfBusy = false;
    };
    const failToPrint = () => {
      done();
      try {
        window.print();
      } catch (_) {}
    };
    let watchdog = setTimeout(() => {
      failToPrint();
      alert("PDF generation took too long for this template. Print dialog opened; choose Save as PDF.");
    }, 25000);
    try {
      const worker = window.html2pdf().set(opt).from(clone).save();
      if (worker && typeof worker.then === "function") {
        worker.then(done).catch(failToPrint);
      } else {
        setTimeout(done, 1000);
      }
    } catch (e) {
      failToPrint();
      alert("Could not create PDF directly. Print dialog opened; choose Save as PDF.");
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
          fontSize: activeFontSizeId,
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
            fontSize: activeFontSizeId,
          }
        : {
            resume: resumeData,
            template: activeTemplateId,
            color: activeColorId,
            font: fontVal,
            textAlign: activeTextAlignId,
            fontSize: activeFontSizeId,
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
      if (o.template && RENDERERS[o.template]) {
        if (!window.__TT_RESUME_INITIAL) {
          activeTemplateId = o.template;
        }
      }
      if (o.color && COLOR_SCHEMES.some((c) => c.id === o.color)) activeColorId = o.color;
      if (o.textAlign && TEXT_ALIGN_OPTIONS.some((a) => a.id === o.textAlign)) activeTextAlignId = o.textAlign;
      if (o.fontSize) {
        if (FONT_SIZES.some((s) => s.id === o.fontSize)) {
          activeFontSizeId = o.fontSize;
        } else {
          var byCss = FONT_SIZES.find((s) => s.css === o.fontSize);
          if (byCss) activeFontSizeId = byCss.id;
        }
      }
    } catch (_) {}
  }

  window.addEventListener("message", function (event) {
    const data = event.data;
    if (!data || data.type !== "TT_STUDIO_DRAFT_UPDATE") return;
    applyStudioDraftUpdate(data);
  });

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
    const isPreviewOnly =
      String(qp("mode") || "").trim() === "preview" || window.__TT_PREVIEW_ONLY === true;
    if (isPreviewOnly) {
      document.body.classList.add("tt-mode-preview-only");
      try {
        if (window.self === window.top) {
          document.body.classList.add("tt-mode-preview-standalone");
        }
      } catch (_) {
        document.body.classList.add("tt-mode-preview-standalone");
      }
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
      if (si.fontSize && FONT_SIZES.some(function (s) { return s.id === si.fontSize; })) {
        activeFontSizeId = si.fontSize;
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
    const fontSizeOpt = FONT_SIZES.find((s) => s.id === activeFontSizeId) || FONT_SIZES[1];
    applyBodyFontSize(fontSizeOpt.css);
    renderColorSchemes();
    renderTextAlignOptions();
    renderFilterNav();
    renderTemplateGrid();
    renderFonts();
    renderFontSizes();
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw && !isPreviewOnly) {
        const o = JSON.parse(raw);
        if (o.font) {
          fontFamily.value = o.font;
          document.documentElement.style.setProperty("--font-stack", o.font);
        }
        if (o.fontSize && FONT_SIZES.some((s) => s.id === o.fontSize)) {
          activeFontSizeId = o.fontSize;
          if (fontSize) fontSize.value = o.fontSize;
          const chosen = FONT_SIZES.find((s) => s.id === o.fontSize);
          if (chosen) applyBodyFontSize(chosen.css);
        }
      }
    } catch (_) {}

    renderEditor();
    bindEditorEvents();
    renderPreview();

    if (isPreviewOnly) {
      try {
        window.scrollTo(0, 0);
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
      } catch (_) {}
    }

    if (isPreviewOnly && window.__TT_RESUME_INITIAL) {
      try {
        persistState();
      } catch (_) {}
    }

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
            fontSize: activeFontSizeId,
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
