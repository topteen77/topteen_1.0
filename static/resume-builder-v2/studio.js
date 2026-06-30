(function () {
  "use strict";

  var cfg = window.__RB2_STUDIO || {};
  var csrfToken = cfg.csrfToken;
  var payload = cfg.editorPayload || { skills: [], certificates: [], activities: [], internships: [] };
  var sections = cfg.sectionsList || [];
  var activeSection = sections[0] || "personal";
  var suggestTimer = null;
  var suggestIdx = -1;
  var previewReloadTimer = null;
  var editingProjectId = null;
  var LANGUAGE_LEVELS = ["Native", "Fluent", "Advanced", "Intermediate", "Basic", "Beginner"];

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function apiPost(body) {
    return fetch(cfg.aiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) {
          var err = new Error((data && data.error) || "Request failed");
          err.payload = data;
          throw err;
        }
        return data;
      });
    });
  }

  function trimVal(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : "";
  }

  function clearFieldErrors(root) {
    (root || document).querySelectorAll(".rb2-field.is-invalid").forEach(function (field) {
      field.classList.remove("is-invalid");
      var hint = field.querySelector(".rb2-field-error");
      if (hint) hint.remove();
    });
  }

  function setFieldError(id, message) {
    var el = document.getElementById(id);
    if (!el) return;
    var field = el.closest(".rb2-field");
    if (!field) return;
    field.classList.add("is-invalid");
    var hint = field.querySelector(".rb2-field-error");
    if (!hint) {
      hint = document.createElement("p");
      hint.className = "rb2-field-error";
      field.appendChild(hint);
    }
    hint.textContent = message;
  }

  /* ——— Preview refresh ——— */
  function resizePreviewFrame() {
    var frame = $("#rb2PreviewFrame");
    if (!frame) return;
    var wrap = frame.closest(".rb2-preview-frame-wrap");
    function fit() {
      try {
        var win = frame.contentWindow;
        var doc = win && win.document;
        if (!doc) return;
        win.scrollTo(0, 0);
        doc.documentElement.scrollTop = 0;
        doc.body.scrollTop = 0;
        if (wrap) wrap.scrollTop = 0;
        var h = Math.max(
          doc.body.scrollHeight || 0,
          doc.documentElement.scrollHeight || 0,
          doc.body.offsetHeight || 0
        );
        frame.style.height = Math.max(520, h + 16) + "px";
      } catch (_) {}
    }
    fit();
    setTimeout(fit, 250);
    setTimeout(fit, 900);
  }

  function reloadPreview(prototypeKey, immediate) {
    var frame = $("#rb2PreviewFrame");
    if (!frame) return;
    if (immediate !== true) {
      clearTimeout(previewReloadTimer);
      previewReloadTimer = setTimeout(function () {
        reloadPreview(prototypeKey, true);
      }, 400);
      return;
    }
    var key = prototypeKey || cfg.prototypeKey || "";
    if (key) cfg.prototypeKey = key;
    var base = (frame.getAttribute("src") || "").split("?")[0];
    var qs = "mode=preview&t=" + Date.now();
    if (key) qs += "&template=" + encodeURIComponent(key);
    frame.setAttribute("src", base + "?" + qs);
    frame.addEventListener("load", resizePreviewFrame, { once: true });
  }

  function setActiveSection(id) {
    activeSection = id;
    document.querySelectorAll(".rb2-section-nav-item, .rb2-step-btn").forEach(function (el) {
      el.classList.toggle("is-active", el.dataset.section === id);
    });
    document.querySelectorAll(".rb2-editor-section").forEach(function (el) {
      el.style.display = el.dataset.section === id ? "block" : "none";
    });
    updateStudioNav();
    var formMain = document.querySelector(".rb2-studio-form");
    if (formMain) formMain.scrollTop = 0;
  }

  function sectionIndex(id) {
    return sections.indexOf(id || activeSection);
  }

  function updateStudioNav() {
    var idx = sectionIndex(activeSection);
    var backBtn = $("#rb2NavBack");
    var contBtn = $("#rb2NavContinue");
    var stepLabel = $("#rb2NavStepLabel");
    if (backBtn) backBtn.disabled = idx <= 0;
    if (contBtn) {
      var isLast = idx >= sections.length - 1;
      contBtn.innerHTML = isLast
        ? "<i class='bx bx-check'></i> Save &amp; Finish"
        : "Save &amp; Continue <i class='bx bx-chevron-right'></i>";
    }
    if (stepLabel) {
      var activeBtn = document.querySelector('.rb2-step-btn[data-section="' + activeSection + '"]');
      var textEl = activeBtn && activeBtn.querySelector(".rb2-step-btn__text");
      stepLabel.textContent = textEl ? textEl.textContent.trim() : activeSection;
    }
  }

  function goToPrevSection() {
    var idx = sectionIndex(activeSection);
    if (idx > 0) setActiveSection(sections[idx - 1]);
  }

  function goToNextSection() {
    var idx = sectionIndex(activeSection);
    if (idx < sections.length - 1) setActiveSection(sections[idx + 1]);
  }

  function savePersonalData() {
    var body = {
      action: "save_personal",
      headline: trimVal("rb2Headline"),
    };
    var nameEl = $("#rb2Name");
    if (nameEl && !nameEl.readOnly) body.name = trimVal("rb2Name");
    var phoneEl = $("#rb2Phone");
    if (phoneEl && !phoneEl.readOnly) body.phone = trimVal("rb2Phone");
    var schoolEl = $("#rb2School");
    if (schoolEl && !schoolEl.readOnly) body.school = trimVal("rb2School");
    return apiPost(body).then(function (data) {
      onStudioUpdate(data);
      reloadPreview(cfg.prototypeKey, true);
    });
  }

  function saveEducationData() {
    if (!$("#rb2SaveEducation")) return Promise.resolve();
    var body = { action: "save_personal", headline: trimVal("rb2Headline") };
    var schoolEl = $("#rb2EduSchool");
    if (schoolEl && !schoolEl.readOnly) body.school = trimVal("rb2EduSchool");
    var gradeEl = $("#rb2EduGrade");
    if (gradeEl && !gradeEl.readOnly) body.grade = trimVal("rb2EduGrade");
    return apiPost(body).then(function (data) {
      onStudioUpdate(data);
      reloadPreview(cfg.prototypeKey, true);
    });
  }

  function saveSummaryData() {
    var field = $("#rb2SummaryField");
    if (!field || !field.value.trim()) return Promise.resolve();
    return apiPost({ action: "save_summary", text: field.value.trim() }).then(onStudioUpdate);
  }

  function saveProjectIfFilled() {
    var title = trimVal("rb2ProjectTitle");
    var desc = trimVal("rb2ProjectDesc");
    if (!title && !desc) return Promise.resolve();
    if (!title || !desc) return Promise.resolve();
    var tech = trimVal("rb2ProjectTech");
    var fullDesc = tech ? "Technologies: " + tech + "\n" + desc : desc;
    var body = editingProjectId
      ? { action: "update_activity", item_id: editingProjectId, title: title, description: fullDesc }
      : { action: "add_activity", title: title, description: fullDesc };
    return apiPost(body).then(function (data) {
      onStudioUpdate(data);
      resetProjectForm();
    });
  }

  function saveCertIfFilled() {
    var title = trimVal("rb2CertTitle");
    if (!title) return Promise.resolve();
    return apiPost({
      action: "add_certificate",
      title: title,
      description: trimVal("rb2CertDesc"),
      issue_date: ($("#rb2CertDate") || {}).value || null,
    }).then(function (data) {
      onStudioUpdate(data);
      ["rb2CertTitle", "rb2CertDesc", "rb2CertDate"].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.value = "";
      });
    });
  }

  function saveAchieveIfFilled() {
    var title = trimVal("rb2AchieveTitle");
    var desc = trimVal("rb2AchieveDesc");
    if (!title && !desc) return Promise.resolve();
    if (!title || !desc) return Promise.resolve();
    return apiPost({
      action: "add_activity",
      title: title,
      description: desc,
    }).then(function (data) {
      onStudioUpdate(data);
      if ($("#rb2AchieveTitle")) $("#rb2AchieveTitle").value = "";
      if ($("#rb2AchieveDesc")) $("#rb2AchieveDesc").value = "";
    });
  }

  function saveLanguagesData() {
    var rows = document.querySelectorAll("#rb2LanguagesList .rb2-lang-row");
    var langs = [];
    rows.forEach(function (row) {
      var nameEl = row.querySelector("[data-lang-name]");
      var levelEl = row.querySelector("[data-lang-level]");
      var name = nameEl ? nameEl.value.trim() : "";
      var level = levelEl ? levelEl.value.trim() : "";
      if (name) langs.push({ name: name, level: level });
    });
    return apiPost({ action: "save_languages", languages: langs }).then(function (data) {
      onStudioUpdate(data);
    });
  }

  function saveHobbiesData() {
    var field = $("#rb2HobbiesField");
    if (!field) return Promise.resolve();
    return apiPost({ action: "save_hobbies", text: field.value.trim() }).then(function (data) {
      onStudioUpdate(data);
    });
  }

  function saveExpIfFilled() {
    var role = trimVal("rb2ExpRole");
    if (!role) return Promise.resolve();
    var provider = trimVal("rb2ExpProvider");
    var description = trimVal("rb2ExpDesc");
    var start = trimVal("rb2ExpStart");
    if (!provider || !description || !start) return Promise.resolve();
    var end = trimVal("rb2ExpEnd");
    return apiPost({
      action: "add_internship",
      role: role,
      provider: provider,
      description: description,
      start_date: start,
      end_date: end || null,
    }).then(function (data) {
      onStudioUpdate(data);
      ["rb2ExpRole", "rb2ExpProvider", "rb2ExpDesc", "rb2ExpStart", "rb2ExpEnd"].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.value = "";
      });
    });
  }

  function saveCurrentSection() {
    switch (activeSection) {
      case "personal":
        return savePersonalData();
      case "education":
        return saveEducationData();
      case "skills": {
        var skillInput = trimVal("rb2SkillInput");
        if (skillInput) return addSkill(skillInput).then(function () {
          if ($("#rb2SkillInput")) $("#rb2SkillInput").value = "";
        });
        return Promise.resolve();
      }
      case "projects":
        return saveProjectIfFilled();
      case "certificates":
        return saveCertIfFilled();
      case "languages":
        return saveLanguagesData();
      case "hobbies":
        return saveHobbiesData();
      case "achievements":
        return saveAchieveIfFilled();
      case "summary":
        return saveSummaryData();
      case "experience":
        return saveExpIfFilled();
      default:
        return Promise.resolve();
    }
  }

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function renderLanguagesList() {
    var container = $("#rb2LanguagesList");
    if (!container) return;
    var langs = payload.languages || [];
    if (!langs.length) langs = [{ name: "", level: "" }];
    container.innerHTML = "";
    langs.forEach(function (lg, idx) {
      var row = document.createElement("div");
      row.className = "rb2-lang-row";
      var levelOpts = LANGUAGE_LEVELS.map(function (lv) {
        var sel = (lg.level || "") === lv ? " selected" : "";
        return "<option value=\"" + esc(lv) + "\"" + sel + ">" + esc(lv) + "</option>";
      }).join("");
      row.innerHTML =
        "<div class=\"rb2-field\"><label>Language</label>" +
        "<input type=\"text\" data-lang-name placeholder=\"e.g. English\" value=\"" + esc(lg.name || "") + "\" /></div>" +
        "<div class=\"rb2-field\"><label>Level</label>" +
        "<select data-lang-level><option value=\"\">—</option>" + levelOpts + "</select></div>" +
        "<div class=\"rb2-lang-row__remove\">" +
        "<span class=\"rb2-lang-row__remove-label\" aria-hidden=\"true\">Remove</span>" +
        "<button type=\"button\" class=\"rb2-lang-remove\" title=\"Remove language\" aria-label=\"Remove language\">" +
        "<i class=\"bx bx-x\"></i></button></div>";
      container.appendChild(row);
    });
    container.querySelectorAll(".rb2-lang-remove").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var rows = container.querySelectorAll(".rb2-lang-row");
        if (rows.length <= 1) {
          var nameEl = container.querySelector("[data-lang-name]");
          var levelEl = container.querySelector("[data-lang-level]");
          if (nameEl) nameEl.value = "";
          if (levelEl) levelEl.value = "";
          return;
        }
        btn.closest(".rb2-lang-row").remove();
      });
    });
  }

  function renderLists() {
    renderSkillList();
    renderLanguagesList();
    renderActivityList("rb2ProjectsList", payload.activities || [], "project");
    renderCertList();
    renderActivityList("rb2AchieveList", payload.activities || [], "achievement");
    renderExpList();
  }

  function renderSkillList() {
    var ul = $("#rb2SkillsList");
    if (!ul) return;
    ul.innerHTML = "";
    (payload.skills || []).forEach(function (s) {
      var li = document.createElement("li");
      li.className = "rb2-item-list__row";
      li.innerHTML =
        "<span>" + esc(s.title) + "</span>" +
        '<button type="button" class="rb2-item-del" data-type="skill" data-id="' + s.id + '" title="Remove">×</button>';
      ul.appendChild(li);
    });
  }

  function renderActivityList(listId, items, kind) {
    var ul = $("#" + listId);
    if (!ul) return;
    ul.innerHTML = "";
    (items || []).forEach(function (a) {
      var li = document.createElement("li");
      li.className = "rb2-item-list__row";
      var actions =
        kind === "project"
          ? '<div class="rb2-item-list__actions">' +
            '<button type="button" class="rb2-item-edit" data-kind="project" data-id="' + a.id + '">Edit</button>' +
            '<button type="button" class="rb2-item-del" data-type="activity" data-id="' + a.id + '">Remove</button>' +
            "</div>"
          : '<button type="button" class="rb2-item-del" data-type="activity" data-id="' + a.id + '">Remove</button>';
      li.innerHTML =
        "<div><strong>" + esc(a.title) + "</strong>" +
        (a.description ? "<div class=\"fs-12 text-muted\">" + esc(a.description).slice(0, 120) + "</div>" : "") +
        "</div>" +
        actions;
      ul.appendChild(li);
    });
  }

  function parseProjectActivity(activity) {
    var desc = (activity && activity.description) || "";
    var tech = "";
    if (desc.indexOf("Technologies: ") === 0) {
      var nl = desc.indexOf("\n");
      if (nl >= 0) {
        tech = desc.slice("Technologies: ".length, nl);
        desc = desc.slice(nl + 1);
      } else {
        tech = desc.slice("Technologies: ".length);
        desc = "";
      }
    }
    return {
      title: (activity && activity.title) || "",
      tech: tech,
      desc: desc,
    };
  }

  function resetProjectForm() {
    editingProjectId = null;
    if ($("#rb2ProjectTitle")) $("#rb2ProjectTitle").value = "";
    if ($("#rb2ProjectTech")) $("#rb2ProjectTech").value = "";
    if ($("#rb2ProjectDesc")) $("#rb2ProjectDesc").value = "";
    var saveBtn = $("#rb2SaveProject");
    if (saveBtn) saveBtn.textContent = "Save project";
  }

  function startProjectEdit(activityId) {
    var activity = (payload.activities || []).find(function (a) {
      return String(a.id) === String(activityId);
    });
    if (!activity) return;
    var parsed = parseProjectActivity(activity);
    editingProjectId = activity.id;
    if ($("#rb2ProjectTitle")) $("#rb2ProjectTitle").value = parsed.title;
    if ($("#rb2ProjectTech")) $("#rb2ProjectTech").value = parsed.tech;
    if ($("#rb2ProjectDesc")) $("#rb2ProjectDesc").value = parsed.desc;
    var saveBtn = $("#rb2SaveProject");
    if (saveBtn) saveBtn.textContent = "Update project";
    setActiveSection("projects");
    if ($("#rb2ProjectTitle")) $("#rb2ProjectTitle").focus();
  }

  function renderCertList() {
    var ul = $("#rb2CertsList");
    if (!ul) return;
    ul.innerHTML = "";
    (payload.certificates || []).forEach(function (c) {
      var li = document.createElement("li");
      li.className = "rb2-item-list__row";
      li.innerHTML =
        "<div><strong>" + esc(c.title) + "</strong>" +
        (c.description ? "<div class=\"fs-12 text-muted\">" + esc(c.description).slice(0, 100) + "</div>" : "") +
        "</div>" +
        '<button type="button" class="rb2-item-del" data-type="certificate" data-id="' + c.id + '">Remove</button>';
      ul.appendChild(li);
    });
  }

  function renderExpList() {
    var ul = $("#rb2ExpList");
    if (!ul) return;
    ul.innerHTML = "";
    (payload.internships || []).forEach(function (e) {
      var li = document.createElement("li");
      li.className = "rb2-item-list__row";
      li.innerHTML =
        "<div><strong>" + esc(e.role) + "</strong> — " + esc(e.provider) +
        (e.description ? "<div class=\"fs-12 text-muted\">" + esc(e.description).slice(0, 100) + "</div>" : "") +
        "</div>" +
        '<button type="button" class="rb2-item-del" data-type="internship" data-id="' + e.id + '">Remove</button>';
      ul.appendChild(li);
    });
  }

  function onStudioUpdate(data, options) {
    options = options || {};
    if (!data) return;
    if (data.payload) {
      payload = data.payload;
      renderLists();
      if (data.payload.hobbies !== undefined && $("#rb2HobbiesField")) {
        $("#rb2HobbiesField").value = data.payload.hobbies || "";
      }
    }
    if (data.section_metrics) updateSectionNav(data.section_metrics);
    if (data.suggestions !== undefined) updateTips(data.suggestions);
    if (data.overall_completion !== undefined) updateProgress(data.overall_completion);
    if (data.strength) updateStrengthCard(data.strength);
    if (data.missing_keywords !== undefined) updateMissingKeywords(data.missing_keywords);
    if (data.resume_photo_url !== undefined) {
      setPhotoPreview(data.resume_photo_url);
    }
    if (data.prototype_key) cfg.prototypeKey = data.prototype_key;
    if (!options.skipPreviewReload) {
      reloadPreview(cfg.prototypeKey, !options.deferPreview);
    }
  }

  function setPhotoUploadLabel(hasPhoto) {
    var label = $("#rb2PhotoUploadLabel");
    if (label) label.textContent = hasPhoto ? "Change photo" : "Add photo";
    var removeBtn = $("#rb2PhotoRemove");
    if (removeBtn) removeBtn.hidden = !hasPhoto;
  }

  function setPhotoPreview(url) {
    var wrap = $("#rb2PhotoPreview");
    if (!wrap) return;
    cfg.resumePhotoUrl = url || "";
    if (url) {
      var img = $("#rb2PhotoImg");
      if (img) {
        img.src = url;
      } else {
        wrap.innerHTML =
          '<img src="' + esc(url) + '" alt="Your photo" class="rb2-photo-preview__img" id="rb2PhotoImg">';
      }
      setPhotoUploadLabel(true);
      return;
    }
    var initial = cfg.avatarInitial || "?";
    wrap.innerHTML =
      '<span class="rb2-photo-preview__avatar-initials" id="rb2PhotoPlaceholder">' + esc(initial) + "</span>";
    setPhotoUploadLabel(false);
  }

  function updatePhotoPreview(url) {
    setPhotoPreview(url);
  }

  function updateMissingKeywords(keywords) {
    var row = $("#rb2MissingKeywords");
    var section = row && row.closest(".rb2-suggest-chips");
    if (!keywords || !keywords.length) {
      if (section) section.remove();
      return;
    }
    if (!row) return;
    row.innerHTML = keywords
      .map(function (kw) {
        return '<button type="button" class="rb2-kw-chip" data-keyword="' + esc(kw) + '">+ ' + esc(kw) + "</button>";
      })
      .join("");
    row.querySelectorAll(".rb2-kw-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        setActiveSection("skills");
        addSkill(chip.dataset.keyword, chip);
      });
    });
  }

  function skillExists(title) {
    var key = (title || "").trim().toLowerCase();
    if (!key) return true;
    return (payload.skills || []).some(function (s) {
      return (s.title || "").trim().toLowerCase() === key;
    });
  }

  function addSkill(title, sourceEl) {
    title = (title || "").trim();
    if (!title || skillExists(title)) return Promise.resolve();

    var tempId = "tmp-" + Date.now();
    payload.skills = payload.skills || [];
    payload.skills.push({
      id: tempId,
      title: title,
      description: "",
      profficiency: 1,
    });
    renderSkillList();

    if (sourceEl) {
      sourceEl.classList.add("is-adding");
      sourceEl.disabled = true;
    }

    return apiPost({ action: "add_skill", title: title })
      .then(function (data) {
        onStudioUpdate(data, { deferPreview: true });
      })
      .catch(function () {
        payload.skills = (payload.skills || []).filter(function (s) {
          return String(s.id) !== tempId;
        });
        renderSkillList();
      })
      .finally(function () {
        if (sourceEl) {
          sourceEl.classList.remove("is-adding");
          sourceEl.disabled = false;
        }
      });
  }

  function stepIconHtml(status) {
    if (status === "complete") return "<i class='bx bx-check-circle'></i>";
    if (status === "partial") return "<i class='bx bx-time-five'></i>";
    return "<i class='bx bx-circle'></i>";
  }

  function stepTagHtml(status, percent) {
    if (status === "complete") {
      return '<span class="rb2-step-btn__tag rb2-step-btn__tag--done" title="Complete"><i class=\'bx bx-check\'></i></span>';
    }
    if (status === "partial") {
      return '<span class="rb2-step-btn__tag rb2-step-btn__tag--warn">' + percent + "%</span>";
    }
    if (status === "missing") {
      return '<span class="rb2-step-btn__tag">Add</span>';
    }
    return "";
  }

  function updateSectionNav(metrics) {
    document.querySelectorAll(".rb2-step-btn").forEach(function (btn) {
      var sec = btn.dataset.section;
      var m = metrics[sec];
      if (!m) return;
      var icon = btn.querySelector(".rb2-step-btn__icon");
      if (icon) icon.innerHTML = stepIconHtml(m.status);
      var oldTag = btn.querySelector(".rb2-step-btn__tag");
      if (oldTag) oldTag.remove();
      var tmp = document.createElement("div");
      tmp.innerHTML = stepTagHtml(m.status, m.percent);
      while (tmp.firstChild) btn.appendChild(tmp.firstChild);
    });
  }

  function updateProgress(pct) {
    var bar = document.getElementById("rb2ProgressBar");
    var label = document.getElementById("rb2ProgressLabel");
    if (bar) bar.style.width = pct + "%";
    if (label) {
      var level = "Good";
      var m = label.textContent.match(/·\s*(.+)$/);
      if (m) level = m[1].trim();
      if (pct >= 100) {
        label.textContent = "Resume complete!";
      } else {
        label.textContent = pct + "% done · " + level;
      }
    }
    updateCompleteUI(pct);
  }

  function updateStrengthCard(strength) {
    if (!strength) return;
    var overall = document.getElementById("rb2StrengthOverall");
    var complete = document.getElementById("rb2StrengthComplete");
    var details = document.getElementById("rb2StrengthDetails");
    if (overall) overall.textContent = strength.score != null ? strength.score : overall.textContent;
    if (complete) complete.textContent = (strength.completion != null ? strength.completion : 0) + "%";
    if (details) {
      details.textContent = (strength.ats_completeness != null ? strength.ats_completeness : 0) + "%";
    }
  }

  function updateCompleteUI(pct) {
    var complete = pct >= 100;
    ["rb2CompleteBanner", "rb2CompleteSidebar", "rb2CompleteSticky"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.toggle("is-visible", complete);
    });
    var nav = document.getElementById("rb2StudioNav");
    if (nav) nav.style.display = complete ? "none" : "";
    var topbar = document.querySelector(".rb2-studio-topbar");
    if (topbar) topbar.classList.toggle("rb2-studio-topbar--complete", complete);
    var app = document.querySelector(".rb2-studio-app");
    if (app) app.classList.toggle("rb2-studio-app--complete", complete);
  }

  function bindCoachItems(root) {
    (root || document).querySelectorAll(".rb2-tip-row").forEach(function (row) {
      if (row._rb2Bound) return;
      row._rb2Bound = true;
      function activate() {
        if (row.dataset.section) setActiveSection(row.dataset.section);
        if (row.dataset.coachAction) runCoachAction(row.dataset.coachAction);
      }
      row.addEventListener("click", activate);
      row.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });
    });
  }

  function tipCheckIconHtml() {
    return '<span class="rb2-tip-check" aria-hidden="true"><i class="bx bx-check"></i></span>';
  }

  function updateTips(suggestions) {
    var card = document.getElementById("rb2TipsCard");
    var tipsLampSvg =
      '<svg class="rb2-tips-lamp" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 113.79 122.88" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" fill-rule="evenodd" d="M75.64,27a35.42,35.42,0,0,1,8.58,7.07A32.54,32.54,0,0,1,90,43.34h0a37.48,37.48,0,0,1,1.85,5.93,35,35,0,0,1,.24,14,38.35,38.35,0,0,1-2.16,7.3l-.11.25c-2,5-5.58,9.84-9,14.62-1.74,2.42-3.47,4.81-4.92,7.13a4.71,4.71,0,0,1-4.33,2.18L44.05,98.84a4.7,4.7,0,0,1-5.21-3.41,38.85,38.85,0,0,0-2.53-5.8,24.22,24.22,0,0,0-3-4.48C31.89,83.53,30.44,81.87,29,80a40.57,40.57,0,0,1-4.14-6.92h0a41.19,41.19,0,0,1-2.8-8,35.59,35.59,0,0,1-.95-8.42v0a35.78,35.78,0,0,1,1.17-8.73,41.74,41.74,0,0,1,3.41-8.82l.2-.36A35.1,35.1,0,0,1,33,30.09a33.5,33.5,0,0,1,9.43-5.81l.29-.11a35.14,35.14,0,0,1,8-2.13,37.61,37.61,0,0,1,8.75-.2,38.63,38.63,0,0,1,8.37,1.71A37.79,37.79,0,0,1,75.64,27Zm-3.88,87.35a17.36,17.36,0,0,1-6.26,6.28,16.36,16.36,0,0,1-7.19,2.19,14.86,14.86,0,0,1-7.39-1.44,15.07,15.07,0,0,1-4.38-3.26l25.22-3.77Zm2.4-14.11,0,1.65,0,.57a23.51,23.51,0,0,1,0,3.25l-.5,2.38-30.56,4.54-.53-1.22-1.19-4.88,0-1.42,32.7-4.87Zm-18-96.51A3.84,3.84,0,0,1,60.07,0h0l.26,0A3.89,3.89,0,0,1,62.8,1.19a3.86,3.86,0,0,1,1.06,2.69h0a1.27,1.27,0,0,1,0,.2l-.21,8.19h0a2.28,2.28,0,0,1,0,.26,3.81,3.81,0,0,1-3.86,3.52h0l-.27,0a3.77,3.77,0,0,1-2.46-1.17A3.84,3.84,0,0,1,56,12.18h0a1.27,1.27,0,0,1,0-.2l.2-8.22ZM14,18.1a3.9,3.9,0,0,1-1.22-2.67,3.83,3.83,0,0,1,3.69-4,3.84,3.84,0,0,1,2.75,1l6.14,5.73a3.85,3.85,0,0,1,.21,5.42,3.91,3.91,0,0,1-2.68,1.22,3.82,3.82,0,0,1-2.74-1L14,18.1Zm-10,42.22A3.86,3.86,0,0,1,0,56.6a3.78,3.78,0,0,1,1-2.75,3.81,3.81,0,0,1,2.68-1.2l8.38-.28a3.83,3.83,0,0,1,4,3.71v.06h0v.14a3.86,3.86,0,0,1-1,2.55A3.81,3.81,0,0,1,12.34,60h-.15l-8.28.28ZM109.6,48.43h.13a3.84,3.84,0,0,1,2.65.85,3.91,3.91,0,0,1,1.4,2.59v0s0,.1,0,.12a3.84,3.84,0,0,1-3.44,4L102,57a3.84,3.84,0,0,1-4.21-3.42,3.84,3.84,0,0,1,3.43-4.21c2.78-.3,5.58-.62,8.37-.89ZM93.08,15.05A3.81,3.81,0,0,1,98.39,14h0A3.78,3.78,0,0,1,100,16.44a3.88,3.88,0,0,1-.57,2.88l-4.67,7A3.84,3.84,0,0,1,88.4,22l4.68-7ZM61.26,54.91h5.89a1.54,1.54,0,0,1,1.54,1.54,1.56,1.56,0,0,1-.26.86l-14,23.93a1.53,1.53,0,0,1-2.11.52,1.55,1.55,0,0,1-.72-1.63l2.07-14.68-7,.12a1.53,1.53,0,0,1-1.56-1.51,1.49,1.49,0,0,1,.21-.81L59.11,39.33a1.55,1.55,0,0,1,2.11-.54A1.52,1.52,0,0,1,62,40.33l-.7,14.58Z"/>' +
      "</svg>";
    if (!suggestions || !suggestions.length) {
      if (card) card.remove();
      return;
    }
    var list = document.getElementById("rb2TipsList");
    if (!card) {
      var steps = document.querySelector(".rb2-studio-steps");
      if (!steps) return;
      card = document.createElement("div");
      card.className = "rb2-tips-card";
      card.id = "rb2TipsCard";
      card.innerHTML =
        '<h3 class="rb2-tips-card__title">' + tipsLampSvg + " Tips for you</h3>" +
        '<ul class="rb2-tips-list" id="rb2TipsList"></ul>';
      steps.appendChild(card);
      list = document.getElementById("rb2TipsList");
    }
    if (!list) return;
    list.innerHTML = suggestions
      .map(function (s) {
        return (
          '<li class="rb2-tip-row" tabindex="0" role="button" data-section="' +
          esc(s.section || "") +
          '" data-coach-action="' +
          esc(s.coach_action || "") +
          '">' +
          tipCheckIconHtml() +
          '<span class="rb2-tip-text">' +
          esc(s.text) +
          "</span></li>"
        );
      })
      .join("");
    bindCoachItems(list);
  }

  /* ——— Skill autocomplete (Google-suggest style) ——— */
  function fetchSuggestions(q) {
    if (!cfg.suggestUrl) return Promise.resolve([]);
    var query = (q || "").trim();
    return fetch(cfg.suggestUrl + "?q=" + encodeURIComponent(query), {
      headers: { "X-CSRFToken": csrfToken },
    })
      .then(function (r) { return r.json(); })
      .then(function (d) { return d.suggestions || []; });
  }

  function highlightMatch(label, q) {
    var i = label.toLowerCase().indexOf(q.toLowerCase());
    if (i < 0) return esc(label);
    return esc(label.slice(0, i)) + "<strong>" + esc(label.slice(i, i + q.length)) + "</strong>" + esc(label.slice(i + q.length));
  }

  function showSuggestList(items, q) {
    var list = $("#rb2SkillSuggest");
    var input = $("#rb2SkillInput");
    if (!list || !input) return;
    suggestIdx = -1;
    if (!items.length) {
      list.hidden = true;
      list.innerHTML = "";
      return;
    }
    list.hidden = false;
    list.innerHTML = "";
    items.forEach(function (item, i) {
      var li = document.createElement("li");
      li.className = "rb2-suggest-item" + (item.already_added ? " is-added" : "");
      li.dataset.idx = String(i);
      li.dataset.label = item.label;
      li.innerHTML = highlightMatch(item.label, q) + (item.already_added ? ' <span class="fs-11 text-muted">added</span>' : "");
      list.appendChild(li);
    });
    list._items = items;
  }

  function bindSkillAutocomplete() {
    var input = $("#rb2SkillInput");
    var list = $("#rb2SkillSuggest");
    if (!input || !list) return;

    input.addEventListener("input", function () {
      var q = input.value.trim();
      clearTimeout(suggestTimer);
      suggestTimer = setTimeout(function () {
        fetchSuggestions(q).then(function (items) { showSuggestList(items, q); });
      }, q.length < 1 ? 0 : 180);
    });

    input.addEventListener("focus", function () {
      var q = input.value.trim();
      fetchSuggestions(q).then(function (items) { showSuggestList(items, q); });
    });

    input.addEventListener("keydown", function (e) {
      var items = list._items || [];
      if (!items.length || list.hidden) {
        if (e.key === "Enter") {
          e.preventDefault();
          addSkill(input.value).then(function () { input.value = ""; list.hidden = true; });
        }
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        suggestIdx = Math.min(suggestIdx + 1, items.length - 1);
        updateSuggestHighlight(list);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        suggestIdx = Math.max(suggestIdx - 1, 0);
        updateSuggestHighlight(list);
      } else if (e.key === "Enter") {
        e.preventDefault();
        var pick = suggestIdx >= 0 ? items[suggestIdx] : { label: input.value };
        if (pick && !pick.already_added) {
          addSkill(pick.label).then(function () { input.value = ""; list.hidden = true; });
        }
      } else if (e.key === "Escape") {
        list.hidden = true;
      }
    });

    list.addEventListener("click", function (e) {
      var li = e.target.closest(".rb2-suggest-item");
      if (!li || li.classList.contains("is-added")) return;
      addSkill(li.dataset.label).then(function () {
        input.value = "";
        list.hidden = true;
      });
    });

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".rb2-suggest-wrap")) list.hidden = true;
    });
  }

  function updateSuggestHighlight(list) {
    list.querySelectorAll(".rb2-suggest-item").forEach(function (li, i) {
      li.classList.toggle("is-active", i === suggestIdx);
    });
  }

  /* ——— Section nav ——— */
  document.querySelectorAll(".rb2-section-nav-item, .rb2-step-btn").forEach(function (el) {
    el.addEventListener("click", function () { setActiveSection(el.dataset.section); });
  });

  var navBackBtn = $("#rb2NavBack");
  if (navBackBtn) {
    navBackBtn.addEventListener("click", goToPrevSection);
  }

  var navContinueBtn = $("#rb2NavContinue");
  if (navContinueBtn) {
    navContinueBtn.addEventListener("click", function () {
      navContinueBtn.disabled = true;
      saveCurrentSection()
        .then(function () {
          var idx = sectionIndex(activeSection);
          if (idx < sections.length - 1) {
            goToNextSection();
          } else {
            var formMain = document.querySelector(".rb2-studio-form");
            if (formMain) formMain.scrollTop = 0;
          }
        })
        .catch(function () {})
        .finally(function () {
          navContinueBtn.disabled = false;
        });
    });
  }

  /* ——— AI Coach clickable items ——— */
  function runCoachAction(action) {
    switch (action) {
      case "focus_skill":
        $("#rb2SkillInput") && $("#rb2SkillInput").focus();
        break;
      case "focus_project":
        $("#rb2ProjectTitle") && $("#rb2ProjectTitle").focus();
        break;
      case "focus_certificate":
        $("#rb2CertTitle") && $("#rb2CertTitle").focus();
        break;
      case "focus_achievement":
        $("#rb2AchieveTitle") && $("#rb2AchieveTitle").focus();
        break;
      case "focus_languages":
        $("#rb2LanguagesList") && $("#rb2LanguagesList").focus();
        break;
      case "focus_hobbies":
        $("#rb2HobbiesField") && $("#rb2HobbiesField").focus();
        break;
      case "generate_summary":
        apiPost({ action: "generate_summary", career_goal: cfg.goal || "" }).then(function (data) {
          var field = $("#rb2SummaryField");
          if (field && data.text) field.value = data.text;
        });
        break;
      default:
        break;
    }
  }

  bindCoachItems();

  /* ——— Summary AI ——— */
  function bindAi(btnId, action, getPayload) {
    var btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener("click", function () {
      btn.disabled = true;
      var p = getPayload();
      p.action = action;
      apiPost(p).then(function (data) {
        if (data.text && $("#rb2SummaryField")) $("#rb2SummaryField").value = data.text;
        btn.disabled = false;
      }).catch(function () { btn.disabled = false; });
    });
  }

  bindAi("rb2GenSummary", "generate_summary", function () { return { career_goal: cfg.goal || "" }; });
  bindAi("rb2ImproveSummary", "improve_summary", function () {
    return { text: ($("#rb2SummaryField") || {}).value || "", mode: "professional" };
  });
  bindAi("rb2AtsSummary", "improve_summary", function () {
    return { text: ($("#rb2SummaryField") || {}).value || "", mode: "ats" };
  });

  var saveSummaryBtn = $("#rb2SaveSummary");
  if (saveSummaryBtn) {
    saveSummaryBtn.addEventListener("click", function () {
      saveSummaryBtn.disabled = true;
      apiPost({ action: "save_summary", text: ($("#rb2SummaryField") || {}).value || "" }).then(function (data) {
        saveSummaryBtn.textContent = "Saved!";
        onStudioUpdate(data);
        setTimeout(function () {
          saveSummaryBtn.textContent = "Save Summary";
          saveSummaryBtn.disabled = false;
        }, 1200);
      });
    });
  }

  /* ——— Add skill button ——— */
  var addSkillBtn = $("#rb2AddSkill");
  if (addSkillBtn) {
    addSkillBtn.addEventListener("click", function () {
      var input = $("#rb2SkillInput");
      addSkill(input ? input.value : "").then(function () {
        if (input) input.value = "";
        var list = $("#rb2SkillSuggest");
        if (list) list.hidden = true;
      });
    });
  }

  /* ——— Project ——— */
  var genProjBtn = $("#rb2GenProjectDesc");
  if (genProjBtn) {
    genProjBtn.addEventListener("click", function () {
      genProjBtn.disabled = true;
      apiPost({
        action: "generate_project",
        title: ($("#rb2ProjectTitle") || {}).value || "",
        technologies: ($("#rb2ProjectTech") || {}).value || "",
      }).then(function (data) {
        var desc = $("#rb2ProjectDesc");
        if (desc && data.bullets) desc.value = data.bullets.join("\n");
        genProjBtn.disabled = false;
      }).catch(function () { genProjBtn.disabled = false; });
    });
  }

  var saveProjBtn = $("#rb2SaveProject");
  if (saveProjBtn) {
    saveProjBtn.addEventListener("click", function () {
      var card = saveProjBtn.closest(".rb2-form-card");
      clearFieldErrors(card);
      var title = trimVal("rb2ProjectTitle");
      var desc = trimVal("rb2ProjectDesc");
      var ok = true;
      if (!title) {
        setFieldError("rb2ProjectTitle", "Enter a project title");
        ok = false;
      }
      if (!desc) {
        setFieldError("rb2ProjectDesc", "Describe what you did");
        ok = false;
      }
      if (!ok) return;
      var tech = trimVal("rb2ProjectTech");
      var fullDesc = tech ? "Technologies: " + tech + "\n" + desc : desc;
      var body = editingProjectId
        ? { action: "update_activity", item_id: editingProjectId, title: title, description: fullDesc }
        : { action: "add_activity", title: title, description: fullDesc };
      apiPost(body).then(function (data) {
        onStudioUpdate(data);
        resetProjectForm();
      }).catch(function (err) {
        if (err.payload && err.payload.error) setFieldError("rb2ProjectTitle", err.payload.error);
      });
    });
  }

  /* ——— Certificate ——— */
  var saveCertBtn = $("#rb2SaveCert");
  if (saveCertBtn) {
    saveCertBtn.addEventListener("click", function () {
      var card = saveCertBtn.closest(".rb2-form-card");
      clearFieldErrors(card);
      var title = trimVal("rb2CertTitle");
      if (!title) {
        setFieldError("rb2CertTitle", "Enter the certificate name");
        return;
      }
      apiPost({
        action: "add_certificate",
        title: title,
        description: trimVal("rb2CertDesc"),
        issue_date: ($("#rb2CertDate") || {}).value || null,
      }).then(function (data) {
        onStudioUpdate(data);
        ["rb2CertTitle", "rb2CertDesc", "rb2CertDate"].forEach(function (id) {
          var el = document.getElementById(id);
          if (el) el.value = "";
        });
      }).catch(function (err) {
        if (err.payload && err.payload.error) setFieldError("rb2CertTitle", err.payload.error);
      });
    });
  }

  /* ——— Achievement ——— */
  var saveAchBtn = $("#rb2SaveAchieve");
  if (saveAchBtn) {
    saveAchBtn.addEventListener("click", function () {
      var card = saveAchBtn.closest(".rb2-form-card");
      clearFieldErrors(card);
      var title = trimVal("rb2AchieveTitle");
      var desc = trimVal("rb2AchieveDesc");
      var ok = true;
      if (!title) {
        setFieldError("rb2AchieveTitle", "Enter a title");
        ok = false;
      }
      if (!desc) {
        setFieldError("rb2AchieveDesc", "Tell us a bit more");
        ok = false;
      }
      if (!ok) return;
      apiPost({
        action: "add_activity",
        title: title,
        description: desc,
      }).then(function (data) {
        onStudioUpdate(data);
        if ($("#rb2AchieveTitle")) $("#rb2AchieveTitle").value = "";
        if ($("#rb2AchieveDesc")) $("#rb2AchieveDesc").value = "";
      }).catch(function (err) {
        if (err.payload && err.payload.error) setFieldError("rb2AchieveTitle", err.payload.error);
      });
    });
  }

  /* ——— Experience ——— */
  var saveExpBtn = $("#rb2SaveExp");
  if (saveExpBtn) {
    saveExpBtn.addEventListener("click", function () {
      var card = saveExpBtn.closest(".rb2-form-card");
      clearFieldErrors(card);
      var role = trimVal("rb2ExpRole");
      var provider = trimVal("rb2ExpProvider");
      var description = trimVal("rb2ExpDesc");
      var start = trimVal("rb2ExpStart");
      var end = trimVal("rb2ExpEnd");
      var ok = true;
      if (!role) {
        setFieldError("rb2ExpRole", "Enter your role");
        ok = false;
      }
      if (!provider) {
        setFieldError("rb2ExpProvider", "Enter where you worked");
        ok = false;
      }
      if (!description) {
        setFieldError("rb2ExpDesc", "Describe what you did");
        ok = false;
      }
      if (!start) {
        setFieldError("rb2ExpStart", "Enter when you started");
        ok = false;
      }
      if (start && end && end < start) {
        setFieldError("rb2ExpEnd", "End date must be after start date");
        ok = false;
      }
      if (!ok) return;
      apiPost({
        action: "add_internship",
        role: role,
        provider: provider,
        description: description,
        start_date: start,
        end_date: end || null,
      }).then(function (data) {
        onStudioUpdate(data);
        ["rb2ExpRole", "rb2ExpProvider", "rb2ExpDesc", "rb2ExpStart", "rb2ExpEnd"].forEach(function (id) {
          var el = document.getElementById(id);
          if (el) el.value = "";
        });
      }).catch(function (err) {
        if (err.payload && err.payload.error) setFieldError("rb2ExpRole", err.payload.error);
      });
    });
  }

  var addLangBtn = $("#rb2AddLanguage");
  if (addLangBtn) {
    addLangBtn.addEventListener("click", function () {
      var container = $("#rb2LanguagesList");
      if (!container) return;
      var row = document.createElement("div");
      row.className = "rb2-lang-row";
      var levelOpts = LANGUAGE_LEVELS.map(function (lv) {
        return "<option value=\"" + esc(lv) + "\">" + esc(lv) + "</option>";
      }).join("");
      row.innerHTML =
        "<div class=\"rb2-field\"><label>Language</label>" +
        "<input type=\"text\" data-lang-name placeholder=\"e.g. Hindi\" /></div>" +
        "<div class=\"rb2-field\"><label>Level</label>" +
        "<select data-lang-level><option value=\"\">—</option>" + levelOpts + "</select></div>" +
        "<div class=\"rb2-lang-row__remove\">" +
        "<span class=\"rb2-lang-row__remove-label\" aria-hidden=\"true\">Remove</span>" +
        "<button type=\"button\" class=\"rb2-lang-remove\" title=\"Remove language\" aria-label=\"Remove language\">" +
        "<i class=\"bx bx-x\"></i></button></div>";
      container.appendChild(row);
      row.querySelector(".rb2-lang-remove").addEventListener("click", function () {
        row.remove();
      });
      var nameInput = row.querySelector("[data-lang-name]");
      if (nameInput) nameInput.focus();
    });
  }

  var saveLangBtn = $("#rb2SaveLanguages");
  if (saveLangBtn) {
    saveLangBtn.addEventListener("click", function () {
      saveLanguagesData();
    });
  }

  var saveHobbiesBtn = $("#rb2SaveHobbies");
  if (saveHobbiesBtn) {
    saveHobbiesBtn.addEventListener("click", function () {
      saveHobbiesData();
    });
  }

  /* ——— Delete items ——— */
  document.addEventListener("click", function (e) {
    var chip = e.target.closest(".rb2-kw-chip");
    if (chip && !chip.disabled) {
      setActiveSection("skills");
      addSkill(chip.dataset.keyword, chip);
      return;
    }
    var editBtn = e.target.closest(".rb2-item-edit");
    if (editBtn && editBtn.dataset.kind === "project") {
      startProjectEdit(editBtn.dataset.id);
      return;
    }
    var btn = e.target.closest(".rb2-item-del");
    if (!btn) return;
    if (btn.dataset.type === "activity" && editingProjectId && String(btn.dataset.id) === String(editingProjectId)) {
      resetProjectForm();
    }
    apiPost({
      action: "delete_item",
      item_type: btn.dataset.type,
      item_id: parseInt(btn.dataset.id, 10),
    }).then(onStudioUpdate);
  });

  /* ——— Theme options (color + font size) ——— */
  var THEME_FONT_SIZES = [
    { id: "compact", label: "Compact", css: "10.5 pt" },
    { id: "standard", label: "Standard", css: "11.5 pt" },
    { id: "readable", label: "Readable", css: "12.5 pt" },
    { id: "large", label: "Large", css: "13.5 pt" },
  ];
  var pendingColor = cfg.themeColor || "teal";
  var pendingFontSize = cfg.themeFontSize || "standard";
  var pendingFontId = cfg.themeFontId || "inter";

  function themeFontSizeIndex(id) {
    for (var i = 0; i < THEME_FONT_SIZES.length; i++) {
      if (THEME_FONT_SIZES[i].id === id) return i;
    }
    return 1;
  }

  function updateThemeColorSelection() {
    document.querySelectorAll(".rb2-theme-color").forEach(function (btn) {
      var selected = btn.dataset.colorId === pendingColor;
      btn.classList.toggle("is-selected", selected);
      btn.setAttribute("aria-selected", selected ? "true" : "false");
    });
  }

  function updateThemeFontSizeUi() {
    var idx = themeFontSizeIndex(pendingFontSize);
    var current = THEME_FONT_SIZES[idx] || THEME_FONT_SIZES[1];
    var labelEl = document.getElementById("rb2ThemeFontSizeLabel");
    if (labelEl) labelEl.textContent = current.label + " (" + current.css + ")";
    var decBtn = document.getElementById("rb2ThemeFontDecrease");
    var incBtn = document.getElementById("rb2ThemeFontIncrease");
    if (decBtn) decBtn.disabled = idx <= 0;
    if (incBtn) incBtn.disabled = idx >= THEME_FONT_SIZES.length - 1;
  }

  function updateThemeFontFamilyUi() {
    var selectEl = document.getElementById("rb2ThemeFontFamily");
    if (selectEl) selectEl.value = pendingFontId;
  }

  function saveThemePrefs() {
    return apiPost({
      action: "save_theme",
      color: pendingColor,
      font_size: pendingFontSize,
      font_id: pendingFontId,
    }).then(function (data) {
      if (data.theme_color) pendingColor = data.theme_color;
      if (data.theme_font_size) pendingFontSize = data.theme_font_size;
      if (data.theme_font_id) pendingFontId = data.theme_font_id;
      cfg.themeColor = pendingColor;
      cfg.themeFontSize = pendingFontSize;
      cfg.themeFontId = pendingFontId;
      updateThemeColorSelection();
      updateThemeFontSizeUi();
      updateThemeFontFamilyUi();
      reloadPreview(cfg.prototypeKey);
      return data;
    });
  }

  document.querySelectorAll(".rb2-theme-color").forEach(function (btn) {
    btn.addEventListener("click", function () {
      pendingColor = btn.dataset.colorId || pendingColor;
      updateThemeColorSelection();
      saveThemePrefs();
    });
  });

  var fontDecBtn = document.getElementById("rb2ThemeFontDecrease");
  var fontIncBtn = document.getElementById("rb2ThemeFontIncrease");
  if (fontDecBtn) {
    fontDecBtn.addEventListener("click", function () {
      var idx = themeFontSizeIndex(pendingFontSize);
      if (idx <= 0) return;
      pendingFontSize = THEME_FONT_SIZES[idx - 1].id;
      updateThemeFontSizeUi();
      saveThemePrefs();
    });
  }
  if (fontIncBtn) {
    fontIncBtn.addEventListener("click", function () {
      var idx = themeFontSizeIndex(pendingFontSize);
      if (idx >= THEME_FONT_SIZES.length - 1) return;
      pendingFontSize = THEME_FONT_SIZES[idx + 1].id;
      updateThemeFontSizeUi();
      saveThemePrefs();
    });
  }

  var fontFamilySelect = document.getElementById("rb2ThemeFontFamily");
  if (fontFamilySelect) {
    fontFamilySelect.addEventListener("change", function () {
      pendingFontId = fontFamilySelect.value || pendingFontId;
      saveThemePrefs();
    });
  }

  updateThemeColorSelection();
  updateThemeFontSizeUi();
  updateThemeFontFamilyUi();

  /* ——— Template picker modal ——— */
  var pendingTemplateId = cfg.selectedTemplateId || "";
  var pendingPrototypeKey = cfg.prototypeKey || "";

  function updateTemplateModalSelection(pick) {
    if (!pick) return;
    pendingTemplateId = pick.dataset.templateId || "";
    pendingPrototypeKey = pick.dataset.prototypeKey || "";
    document.querySelectorAll(".rb2-template-pick").forEach(function (b) {
      b.classList.toggle("is-selected", b === pick);
    });
    var nameEl = document.getElementById("rb2TemplateModalSelectedName");
    if (nameEl) nameEl.textContent = pick.dataset.templateName || pendingTemplateId;
  }

  document.querySelectorAll(".rb2-template-pick").forEach(function (btn) {
    btn.addEventListener("click", function () {
      updateTemplateModalSelection(btn);
    });
  });

  var applyTemplateBtn = document.getElementById("rb2ApplyTemplateBtn");
  if (applyTemplateBtn) {
    applyTemplateBtn.addEventListener("click", function () {
      if (!pendingTemplateId) return;
      applyTemplateBtn.disabled = true;
      applyTemplateBtn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Applying…";
      apiPost({ action: "select_template", template_id: pendingTemplateId })
        .then(function (data) {
          if (data.template_id) cfg.selectedTemplateId = data.template_id;
          if (data.prototype_key) pendingPrototypeKey = data.prototype_key;
          cfg.prototypeKey = pendingPrototypeKey;
          onStudioUpdate(data);
          reloadPreview(pendingPrototypeKey);
          var modalEl = document.getElementById("rb2TemplateModal");
          if (modalEl && window.bootstrap && bootstrap.Modal) {
            var inst = bootstrap.Modal.getInstance(modalEl);
            if (inst) inst.hide();
          }
        })
        .finally(function () {
          applyTemplateBtn.disabled = false;
          applyTemplateBtn.innerHTML = "<i class='bx bx-check'></i> Apply template";
        });
    });
  }

  bindSkillAutocomplete();
  bindPhotoUpload();
  renderLists();
  setActiveSection(activeSection);
  if (cfg.overallCompletion != null) updateCompleteUI(cfg.overallCompletion);

  var previewFrame = $("#rb2PreviewFrame");
  if (previewFrame) {
    previewFrame.addEventListener("load", resizePreviewFrame);
  }

  var savePersonalBtn = $("#rb2SavePersonal");
  if (savePersonalBtn) {
    savePersonalBtn.addEventListener("click", function () {
      var card = savePersonalBtn.closest(".rb2-form-card");
      clearFieldErrors(card);
      savePersonalData();
    });
  }

  var saveEduBtn = $("#rb2SaveEducation");
  if (saveEduBtn) {
    saveEduBtn.addEventListener("click", function () {
      saveEducationData();
    });
  }

  function bindPhotoUpload() {
    var input = $("#rb2PhotoInput");
    if (!input || !cfg.photoUploadUrl) return;
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      var btn = input.closest(".rb2-photo-upload-btn");
      if (btn) btn.classList.add("is-uploading");
      var fd = new FormData();
      fd.append("photo", file);
      fetch(cfg.photoUploadUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrfToken },
        body: fd,
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.ok) {
            setPhotoPreview(data.url || "");
            reloadPreview(cfg.prototypeKey, true);
          }
        })
        .finally(function () {
          input.value = "";
          if (btn) btn.classList.remove("is-uploading");
        });
    });

    var removeBtn = $("#rb2PhotoRemove");
    if (removeBtn) {
      removeBtn.addEventListener("click", function () {
        if (!confirm("Remove the photo from this resume?")) return;
        removeBtn.disabled = true;
        fetch(cfg.photoUploadUrl, {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "X-CSRFToken": csrfToken },
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data && data.ok) {
              setPhotoPreview("");
              reloadPreview(cfg.prototypeKey, true);
            }
          })
          .finally(function () {
            removeBtn.disabled = false;
          });
      });
    }
  }
})();
