(function () {
  "use strict";

  var cfg = window.__RB2_STUDIO || {};
  var csrfToken = cfg.csrfToken;
  var payload = cfg.editorPayload || { skills: [], certificates: [], activities: [], internships: [] };
  var activeSection = "personal";
  var suggestTimer = null;
  var suggestIdx = -1;
  var previewReloadTimer = null;
  var editingProjectId = null;

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
  }

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function renderLists() {
    renderSkillList();
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
    }
    if (data.section_metrics) updateSectionNav(data.section_metrics);
    if (data.suggestions !== undefined) updateTips(data.suggestions);
    if (data.overall_completion !== undefined) updateProgress(data.overall_completion);
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

  function updateCompleteUI(pct) {
    var complete = pct >= 100;
    ["rb2CompleteBanner", "rb2CompleteSidebar", "rb2CompleteSticky"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.toggle("is-visible", complete);
    });
    var topbar = document.querySelector(".rb2-studio-topbar");
    if (topbar) topbar.classList.toggle("rb2-studio-topbar--complete", complete);
    var app = document.querySelector(".rb2-studio-app");
    if (app) app.classList.toggle("rb2-studio-app--complete", complete);
  }

  function bindCoachItems(root) {
    (root || document).querySelectorAll(".rb2-coach-item").forEach(function (btn) {
      if (btn._rb2Bound) return;
      btn._rb2Bound = true;
      btn.addEventListener("click", function () {
        if (btn.dataset.section) setActiveSection(btn.dataset.section);
        if (btn.dataset.coachAction) runCoachAction(btn.dataset.coachAction);
      });
    });
  }

  function updateTips(suggestions) {
    var card = document.getElementById("rb2TipsCard");
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
        "<h3 class=\"rb2-tips-card__title\"><i class='bx bx-bulb'></i> Tips for you</h3><div id=\"rb2TipsList\"></div>";
      steps.appendChild(card);
      list = document.getElementById("rb2TipsList");
    }
    if (!list) return;
    list.innerHTML = suggestions
      .map(function (s) {
        return (
          '<button type="button" class="rb2-coach-item" data-section="' +
          esc(s.section || "") +
          '" data-coach-action="' +
          esc(s.coach_action || "") +
          '">' +
          esc(s.text) +
          "</button>"
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
      apiPost(body).then(function (data) {
        onStudioUpdate(data);
        reloadPreview(cfg.prototypeKey, true);
      });
    });
  }

  var saveEduBtn = $("#rb2SaveEducation");
  if (saveEduBtn) {
    saveEduBtn.addEventListener("click", function () {
      var body = { action: "save_personal", headline: trimVal("rb2Headline") };
      var schoolEl = $("#rb2EduSchool");
      if (schoolEl && !schoolEl.readOnly) body.school = trimVal("rb2EduSchool");
      var gradeEl = $("#rb2EduGrade");
      if (gradeEl && !gradeEl.readOnly) body.grade = trimVal("rb2EduGrade");
      apiPost(body).then(function (data) {
        onStudioUpdate(data);
        reloadPreview(cfg.prototypeKey, true);
      });
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
