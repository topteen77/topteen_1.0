(function () {
  "use strict";

  var cfg = window.__RB2_STUDIO || {};
  var csrfToken = cfg.csrfToken;
  var payload = cfg.editorPayload || { skills: [], certificates: [], activities: [], internships: [], education: [] };
  var sections = cfg.sectionsList || [];
  var activeSection = sections[0] || "personal";
  var previewReloadTimer = null;
  var draftPreviewTimer = null;
  var editingProjectId = null;
  var editingEducationId = null;
  var editingCertId = null;
  var editingAchieveId = null;
  var savePending = 0;
  var profileSyncBatchDepth = 0;
  var queuedProfileSyncOffers = [];
  var LANGUAGE_LEVELS = ["Native", "Fluent", "Advanced", "Intermediate", "Basic", "Beginner"];

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function setSavingState(active) {
    if (active) savePending += 1;
    else savePending = Math.max(0, savePending - 1);
    var app = document.querySelector(".rb2-studio-app");
    if (app) app.classList.toggle("is-saving", savePending > 0);
    var activeCard = document.querySelector('.rb2-editor-section[data-section="' + activeSection + '"] .rb2-form-card');
    if (activeCard) activeCard.classList.toggle("is-saving", savePending > 0);
    var continueBtn = $("#rb2NavContinue");
    if (continueBtn) {
      if (savePending > 0) {
        if (!continueBtn.dataset.prevHtml) continueBtn.dataset.prevHtml = continueBtn.innerHTML;
        continueBtn.disabled = true;
        continueBtn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Saving…";
      } else if (continueBtn.dataset.prevHtml) {
        continueBtn.innerHTML = continueBtn.dataset.prevHtml;
        continueBtn.disabled = false;
        delete continueBtn.dataset.prevHtml;
      }
    }
  }

  function collectProfileSyncOffers(data) {
    var offers = [];
    if (!data) return offers;
    if (data.profile_sync_offer) offers.push(data.profile_sync_offer);
    if (data.profile_sync_offers && data.profile_sync_offers.length) {
      offers = offers.concat(data.profile_sync_offers);
    }
    return offers;
  }

  function mergeProfileSyncOffers(offers) {
    var byKind = {};
    (offers || []).forEach(function (offer) {
      if (!offer || !offer.kind) return;
      var kind = offer.kind;
      if (!byKind[kind]) {
        byKind[kind] = { kind: kind, labels: [], payload: {} };
      }
      var merged = byKind[kind];
      (offer.labels || []).forEach(function (label) {
        if (merged.labels.indexOf(label) === -1) merged.labels.push(label);
      });
      var payload = offer.payload || {};
      if (kind === "skills" && payload.titles) {
        merged.payload.titles = merged.payload.titles || [];
        payload.titles.forEach(function (title) {
          if (merged.payload.titles.indexOf(title) === -1) merged.payload.titles.push(title);
        });
      } else {
        Object.keys(payload).forEach(function (key) {
          merged.payload[key] = payload[key];
        });
      }
    });
    return Object.keys(byKind).map(function (key) {
      return byKind[key];
    });
  }

  function profileSyncPromptMessage(offer) {
    var labels = offer.labels || [];
    if (!labels.length) {
      return "Do you want to update this information on your TopTeen profile?";
    }
    if (labels.length === 1) {
      return "Do you want to update " + labels[0] + " on your TopTeen profile?";
    }
    return (
      "Do you want to update the following on your TopTeen profile? " + labels.join(", ")
    );
  }

  function promptProfileSyncOffers(offers) {
    offers = mergeProfileSyncOffers(offers);
    if (!offers.length) return Promise.resolve();
    var msgs = window.RB2Messages;
    if (!msgs || !msgs.confirm) return Promise.resolve();
    return offers.reduce(function (chain, offer) {
      return chain.then(function () {
        return msgs
          .confirm({
            title: "Update profile?",
            message: profileSyncPromptMessage(offer),
            confirmLabel: "Yes",
            cancelLabel: "No",
          })
          .then(function (yes) {
            if (!yes) return;
            return apiPost(
              { action: "sync_to_profile", offer: offer },
              { skipProfileSyncPrompt: true }
            ).then(function (data) {
              if (data && data.profile_synced && msgs.toast) {
                msgs.toast("Your TopTeen profile was updated.", {
                  type: "success",
                  title: "Profile updated",
                });
              }
            });
          });
      });
    }, Promise.resolve());
  }

  function queueProfileSyncOffersFromResponse(data, options) {
    options = options || {};
    if (options.skipProfileSyncPrompt) return Promise.resolve(data);
    var offers = collectProfileSyncOffers(data);
    if (!offers.length) return Promise.resolve(data);
    if (profileSyncBatchDepth > 0) {
      queuedProfileSyncOffers = queuedProfileSyncOffers.concat(offers);
      return Promise.resolve(data);
    }
    return promptProfileSyncOffers(offers).then(function () {
      return data;
    });
  }

  function apiPost(body, options) {
    options = options || {};
    setSavingState(true);
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
        return queueProfileSyncOffersFromResponse(data, options).then(function () {
          return data;
        });
      });
    }).finally(function () {
      setSavingState(false);
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

  function setFieldErrorOnElement(el, message) {
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

  function setFieldError(id, message) {
    setFieldErrorOnElement(document.getElementById(id), message);
  }

  function validationReject() {
    return Promise.reject(new Error("validation"));
  }

  function focusFirstInvalidInSection() {
    var card = activeFormCard();
    if (!card) return;
    var firstInvalid = card.querySelector(
      ".rb2-field.is-invalid input, .rb2-field.is-invalid select, .rb2-field.is-invalid textarea"
    );
    if (firstInvalid) firstInvalid.focus();
  }

  function showValidationToast() {
    var msgs = window.RB2Messages;
    if (msgs) {
      msgs.toast("Please fix the highlighted fields before continuing.", {
        type: "warning",
        title: "Check your entries",
      });
    }
  }

  function validateLanguagesSection() {
    var container = $("#rb2LanguagesList");
    if (!container) return true;
    var card = container.closest(".rb2-form-card");
    if (card) clearFieldErrors(card);
    var ok = true;
    container.querySelectorAll(".rb2-lang-row").forEach(function (row) {
      var nameEl = row.querySelector("[data-lang-name]");
      var levelEl = row.querySelector("[data-lang-level]");
      var name = nameEl ? nameEl.value.trim() : "";
      var level = levelEl ? levelEl.value.trim() : "";
      if (!name && !level) return;
      if (name && !level) {
        setFieldErrorOnElement(levelEl, "Select a level");
        ok = false;
      }
      if (!name && level) {
        setFieldErrorOnElement(nameEl, "Enter a language");
        ok = false;
      }
    });
    return ok;
  }

  function parseClassLevel(gradeStr) {
    var g = (gradeStr || "").trim().toLowerCase();
    if (!g) return null;
    if (/\b12\b|12th|xii|twelfth/.test(g)) return 12;
    if (/\b10\b|10th|tenth/.test(g)) return 10;
    return null;
  }

  function normalizeGradeKey(gradeStr) {
    var level = parseClassLevel(gradeStr);
    if (level) return "class-" + level;
    return (gradeStr || "").trim().toLowerCase();
  }

  function formatPercentageStore(val) {
    var s = (val || "").trim();
    if (!s) return "";
    var n = parseFloat(s);
    if (isNaN(n)) return s;
    return (Math.round(n * 100) / 100).toFixed(2);
  }

  function validatePercentageValue(val) {
    var s = (val || "").trim();
    if (!s) return "Enter your percentage";
    var n = parseFloat(s);
    if (isNaN(n)) return "Enter a valid percentage";
    if (n < 0 || n > 100) return "Percentage must be between 0 and 100";
    if (Math.abs(n - Math.round(n * 100) / 100) > 1e-9) {
      return "Percentage can have at most 2 decimal places";
    }
    return null;
  }

  function normalizeEducationEntryForValidation(ed) {
    var entry = {
      id: ed.id,
      grade: ed.grade || "",
      passing_year: ed.passing_year || inferPassingYearFromDates(ed.dates || ""),
      result_type: ed.result_type || "",
      result_value: ed.result_value || "",
    };
    if (!entry.result_type && ed.detail) {
      var parsed = parseResultFromDetail(ed.detail);
      entry.result_type = parsed.result_type;
      entry.result_value = parsed.result_value;
    }
    return entry;
  }

  function educationEntryHasMarks(entry) {
    var e = normalizeEducationEntryForValidation(entry);
    if (e.result_type === "percentage") {
      return validatePercentageValue(e.result_value) === null;
    }
    if (e.result_type === "grade") {
      return !!(e.result_value || "").trim();
    }
    return false;
  }

  function buildEducationEntriesForValidation() {
    var entries = (payload.education || []).map(function (ed) {
      if (editingEducationId && String(ed.id) === String(editingEducationId)) {
        var draft = collectEducationFormData();
        draft.id = ed.id;
        return draft;
      }
      return ed;
    });
    var form = collectEducationFormData();
    if (educationFormHasInput(form) && !editingEducationId) {
      entries.push(form);
    }
    return entries;
  }

  function validateEducationMarks(data) {
    if (data.passing_year === "studying") return null;
    if (data.result_type === "percentage") {
      var pctErr = validatePercentageValue(data.result_value);
      if (pctErr) return { field: "rb2EduPercentage", message: pctErr };
    }
    if (data.result_type === "grade" && !(data.result_value || "").trim()) {
      return { field: "rb2EduResultGrade", message: "Select a grade" };
    }
    return null;
  }

  function validateEducationListDuplicates(entries) {
    var gradeKeys = {};
    var passingYears = {};
    for (var i = 0; i < entries.length; i++) {
      var ed = normalizeEducationEntryForValidation(entries[i]);
      var gradeKey = normalizeGradeKey(ed.grade);
      if (gradeKey) {
        if (gradeKeys[gradeKey]) {
          return { field: "rb2EduGrade", message: "This class or grade is already added" };
        }
        gradeKeys[gradeKey] = true;
      }
      var py = (ed.passing_year || "").trim();
      if (py) {
        if (passingYears[py]) {
          return {
            field: "rb2EduPassingYear",
            message: py === "studying"
              ? 'Only one entry can use "Currently studying"'
              : "This passing year is already used for another entry",
          };
        }
        passingYears[py] = true;
      }
    }
    return null;
  }

  function validateClass12RequiresClass10Marks(entries) {
    var normalized = entries.map(normalizeEducationEntryForValidation);
    var has12 = normalized.some(function (e) {
      return parseClassLevel(e.grade) === 12;
    });
    if (!has12) return null;
    var class10 = normalized.find(function (e) {
      return parseClassLevel(e.grade) === 10;
    });
    if (!class10) {
      return {
        message: "Add a Class 10 entry with your marks when you are in Class 12.",
        entryId: null,
      };
    }
    if (!educationEntryHasMarks(class10)) {
      return {
        message: "Class 10 percentage or grade is required when you are in Class 12.",
        entryId: class10.id || null,
      };
    }
    return null;
  }

  function syncPassingYearSelectOptions() {
    populatePassingYearSelect();
    var sel = $("#rb2EduPassingYear");
    if (!sel) return;
    var studyingOpt = sel.querySelector('option[value="studying"]');
    if (!studyingOpt) return;
    var otherStudying = (payload.education || []).some(function (ed) {
      if (editingEducationId && String(ed.id) === String(editingEducationId)) return false;
      var py = ed.passing_year || inferPassingYearFromDates(ed.dates || "");
      return py === "studying";
    });
    studyingOpt.disabled = otherStudying;
    if (otherStudying && sel.value === "studying") {
      var editingStudying = editingEducationId && (payload.education || []).some(function (ed) {
        if (String(ed.id) !== String(editingEducationId)) return false;
        var py = ed.passing_year || inferPassingYearFromDates(ed.dates || "");
        return py === "studying";
      });
      if (!editingStudying) sel.value = "";
    }
  }

  function validateEducationSection() {
    var card = sectionFormCard("education");
    if (card) clearFieldErrors(card);
    var data = collectEducationFormData();
    var formActive = educationFormHasInput(data);
    var entries = buildEducationEntriesForValidation();
    var ok = true;

    if (formActive) {
      if (!data.school) {
        setFieldError("rb2EduSchool", "Enter school name");
        ok = false;
      }
      if (!data.grade) {
        setFieldError("rb2EduGrade", "Enter class or grade");
        ok = false;
      }
      if (data.result_type && data.passing_year !== "studying") {
        var marksErr = validateEducationMarks(data);
        if (marksErr) {
          setFieldError(marksErr.field, marksErr.message);
          ok = false;
        }
      }
    }

    var listDupErr = validateEducationListDuplicates(entries);
    if (listDupErr) {
      setFieldError(listDupErr.field, listDupErr.message);
      ok = false;
    }

    var class10Err = validateClass12RequiresClass10Marks(entries);
    if (class10Err) {
      var formLevel = formActive ? parseClassLevel(data.grade) : null;
      var editingClass10 =
        formActive &&
        formLevel === 10 &&
        (!editingEducationId || String(class10Err.entryId) === String(editingEducationId));
      if (editingClass10) {
        if (!data.result_type) {
          setFieldError("rb2EduResultType", "Add Class 10 percentage or grade");
          ok = false;
        } else {
          var class10MarksErr = validateEducationMarks(data);
          if (class10MarksErr) {
            setFieldError(class10MarksErr.field, class10MarksErr.message);
            ok = false;
          } else if (!educationEntryHasMarks(data)) {
            setFieldError("rb2EduResultType", "Add Class 10 percentage or grade");
            ok = false;
          }
        }
      } else if (class10Err.entryId) {
        var msgs = window.RB2Messages;
        if (msgs) {
          msgs.toast(class10Err.message, { type: "warning", title: "Class 10 marks needed" });
        }
        startEducationEdit(class10Err.entryId);
        ok = false;
      } else {
        setFieldError("rb2EduGrade", class10Err.message);
        ok = false;
      }
    }

    if (!formActive && entries.length === 0) return true;
    return ok;
  }

  function validateProjectSection() {
    var card = sectionFormCard("projects");
    if (card) clearFieldErrors(card);
    var title = trimVal("rb2ProjectTitle");
    var desc = trimVal("rb2ProjectDesc");
    if (!title && !desc) return true;
    var ok = true;
    if (!title) {
      setFieldError("rb2ProjectTitle", "Enter a project title");
      ok = false;
    }
    if (!desc) {
      setFieldError("rb2ProjectDesc", "Describe what you did");
      ok = false;
    }
    return ok;
  }

  function validateCertSection() {
    var card = sectionFormCard("certificates");
    if (card) clearFieldErrors(card);
    var title = trimVal("rb2CertTitle");
    var issuer = trimVal("rb2CertDesc");
    if (!title && !issuer) return true;
    var ok = true;
    if (!title) {
      setFieldError("rb2CertTitle", "Enter the certificate name");
      ok = false;
    }
    if (!issuer) {
      setFieldError("rb2CertDesc", "Enter who gave the certificate");
      ok = false;
    }
    return ok;
  }

  function validateAchieveSection() {
    var card = sectionFormCard("achievements");
    if (card) clearFieldErrors(card);
    var title = trimVal("rb2AchieveTitle");
    var desc = trimVal("rb2AchieveDesc");
    if (!title && !desc) return true;
    var ok = true;
    if (!title) {
      setFieldError("rb2AchieveTitle", "Enter a title");
      ok = false;
    }
    if (!desc) {
      setFieldError("rb2AchieveDesc", "Tell us a bit more");
      ok = false;
    }
    return ok;
  }

  function validateExpSection() {
    var card = sectionFormCard("experience");
    if (card) clearFieldErrors(card);
    var role = trimVal("rb2ExpRole");
    var provider = trimVal("rb2ExpProvider");
    var description = trimVal("rb2ExpDesc");
    var start = trimVal("rb2ExpStart");
    var end = trimVal("rb2ExpEnd");
    if (!role && !provider && !description && !start && !end) return true;
    var ok = true;
    if (!role) {
      setFieldError("rb2ExpRole", "Enter your role");
      ok = false;
    }
    if (!provider) {
      setFieldError("rb2ExpProvider", "Enter the organization");
      ok = false;
    }
    return ok;
  }

  function validateCurrentSection() {
    switch (activeSection) {
      case "education":
        return validateEducationSection();
      case "projects":
        return validateProjectSection();
      case "certificates":
        return validateCertSection();
      case "languages":
        return validateLanguagesSection();
      case "achievements":
        return validateAchieveSection();
      case "experience":
        return validateExpSection();
      default:
        return true;
    }
  }

  var SECTION_VALIDATORS = [
    { id: "education", fn: validateEducationSection },
    { id: "projects", fn: validateProjectSection },
    { id: "certificates", fn: validateCertSection },
    { id: "languages", fn: validateLanguagesSection },
    { id: "achievements", fn: validateAchieveSection },
    { id: "experience", fn: validateExpSection },
  ];

  function validateAllSections() {
    for (var i = 0; i < SECTION_VALIDATORS.length; i++) {
      var check = SECTION_VALIDATORS[i];
      if (!check.fn()) {
        setActiveSection(check.id);
        focusFirstInvalidInSection();
        showValidationToast();
        return false;
      }
    }
    return true;
  }

  function navigateToSection(id) {
    if (!id || id === activeSection) return;
    if (!validateCurrentSection()) {
      focusFirstInvalidInSection();
      showValidationToast();
      return;
    }
    setActiveSection(id);
  }

  function activeFormCard() {
    return sectionFormCard(activeSection);
  }

  function sectionFormCard(sectionId) {
    return document.querySelector('.rb2-editor-section[data-section="' + sectionId + '"] .rb2-form-card');
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

  function proficiencyLabel(level) {
    var map = { 1: "Beginner", 2: "Basic", 3: "Intermediate", 4: "Advanced", 5: "Expert" };
    return map[level] || "";
  }

  function descToBullets(desc) {
    var text = (desc || "").trim();
    if (!text) return [];
    return text.split(/\n+/).map(function (line) { return line.trim(); }).filter(Boolean);
  }

  function formatIsoRange(start, end) {
    if (start && end) return start + " — " + end;
    return start || end || "";
  }

  function populatePassingYearSelect() {
    var sel = $("#rb2EduPassingYear");
    if (!sel || sel.dataset.rb2YearsPopulated) return;
    var year = new Date().getFullYear();
    var html = '<option value="">—</option><option value="studying">Currently studying</option>';
    for (var i = 1; i <= 10; i++) {
      var y = year - i;
      html += '<option value="' + y + '">' + y + "</option>";
    }
    sel.innerHTML = html;
    sel.dataset.rb2YearsPopulated = "1";
  }

  function syncEduResultFields() {
    var typeEl = $("#rb2EduResultType");
    var pctWrap = $("#rb2EduPercentageWrap");
    var gradeWrap = $("#rb2EduResultGradeWrap");
    var passingYear = ($("#rb2EduPassingYear") || {}).value || "";
    var studying = passingYear === "studying";
    var resultTypeField = typeEl ? typeEl.closest(".rb2-field") : null;
    if (resultTypeField) resultTypeField.hidden = studying;
    if (!typeEl) return;
    var type = studying ? "" : (typeEl.value || "");
    if (pctWrap) pctWrap.hidden = studying || type !== "percentage";
    if (gradeWrap) gradeWrap.hidden = studying || type !== "grade";
  }

  function syncEduStudyingState() {
    var passingYear = ($("#rb2EduPassingYear") || {}).value || "";
    if (passingYear === "studying") {
      var typeEl = $("#rb2EduResultType");
      var pctEl = $("#rb2EduPercentage");
      var gradeSel = $("#rb2EduResultGrade");
      if (typeEl) typeEl.value = "";
      if (pctEl) pctEl.value = "";
      if (gradeSel) gradeSel.value = "";
    }
    syncEduResultFields();
  }

  function populateEduSchoolSuggestions() {
    var list = $("#rb2EduSchoolSuggestions");
    if (!list) return;
    var schools = [];
    var profileSchool = trimVal("rb2School") || cfg.profileSchool || "";
    if (profileSchool) schools.push(profileSchool);
    (payload.education || []).forEach(function (ed) {
      var name = (ed.school || "").trim();
      if (name && schools.indexOf(name) === -1) schools.push(name);
    });
    list.innerHTML = schools
      .map(function (name) {
        return "<option value=\"" + esc(name) + "\"></option>";
      })
      .join("");
    var schoolInput = $("#rb2EduSchool");
    if (schoolInput && profileSchool && !schoolInput.value) {
      schoolInput.placeholder = profileSchool;
    }
  }

  function inferPassingYearFromDates(dates) {
    var d = (dates || "").trim();
    if (!d) return "";
    var low = d.toLowerCase();
    if (low === "present" || low.indexOf("currently studying") >= 0 || low === "studying" || low === "current") {
      return "studying";
    }
    var match = d.match(/\b(19|20)\d{2}\b/);
    if (match) return match[0];
    if (/^\d{4}$/.test(d)) return d;
    return "";
  }

  function parseResultFromDetail(detail) {
    var d = (detail || "").trim();
    if (!d) return { result_type: "", result_value: "" };
    if (d.slice(-1) === "%") {
      return { result_type: "percentage", result_value: d.slice(0, -1).trim() };
    }
    if (d.toLowerCase().indexOf("grade:") === 0) {
      return { result_type: "grade", result_value: d.split(":")[1].trim() };
    }
    if (d.toLowerCase().indexOf("grade ") === 0) {
      return { result_type: "grade", result_value: d.slice(6).trim() };
    }
    return { result_type: "", result_value: "" };
  }

  function formatEduPassingDisplay(entry) {
    if (!entry) return "";
    var py = entry.passing_year || inferPassingYearFromDates(entry.dates || "");
    if (py === "studying") return "Currently studying";
    if (py) return py;
    return entry.dates || "";
  }

  function formatEduMarksDisplay(entry) {
    if (!entry) return "";
    if (entry.result_type === "percentage" && entry.result_value) {
      return formatPercentageStore(entry.result_value) + "%";
    }
    if (entry.result_type === "grade" && entry.result_value) {
      return "Grade " + entry.result_value;
    }
    if (entry.detail) {
      var parsed = parseResultFromDetail(entry.detail);
      if (parsed.result_type === "percentage" && parsed.result_value) return parsed.result_value + "%";
      if (parsed.result_type === "grade" && parsed.result_value) return "Grade " + parsed.result_value;
      return entry.detail;
    }
    return "";
  }

  function collectEducationFormData() {
    var school = trimVal("rb2EduSchool");
    var grade = trimVal("rb2EduGrade");
    var passingYear = ($("#rb2EduPassingYear") || {}).value || "";
    var resultType = "";
    var resultValue = "";
    if (passingYear !== "studying") {
      resultType = ($("#rb2EduResultType") || {}).value || "";
      if (resultType === "percentage") {
        resultValue = formatPercentageStore(trimVal("rb2EduPercentage"));
      } else if (resultType === "grade") {
        resultValue = ($("#rb2EduResultGrade") || {}).value || "";
      }
    }
    var dates = passingYear === "studying" ? "Currently studying" : passingYear;
    var detail = "";
    if (resultType === "percentage" && resultValue) detail = resultValue + "%";
    else if (resultType === "grade" && resultValue) detail = "Grade: " + resultValue;
    return {
      school: school,
      grade: grade,
      dates: dates,
      detail: detail,
      passing_year: passingYear,
      result_type: resultType,
      result_value: resultValue,
    };
  }

  function educationFormHasInput(data) {
    data = data || collectEducationFormData();
    return !!(data.school || data.grade || data.passing_year);
  }

  function fillEducationForm(entry) {
    populatePassingYearSelect();
    var schoolEl = $("#rb2EduSchool");
    var gradeEl = $("#rb2EduGrade");
    var yearEl = $("#rb2EduPassingYear");
    var typeEl = $("#rb2EduResultType");
    var pctEl = $("#rb2EduPercentage");
    var gradeSel = $("#rb2EduResultGrade");
    if (schoolEl) schoolEl.value = (entry && entry.school) || "";
    if (gradeEl) gradeEl.value = (entry && entry.grade) || "";
    var passingYear = (entry && entry.passing_year) || inferPassingYearFromDates((entry && entry.dates) || "");
    if (yearEl) yearEl.value = passingYear;
    var resultType = (entry && entry.result_type) || "";
    var resultValue = (entry && entry.result_value) || "";
    if (!resultType && entry && entry.detail) {
      var parsed = parseResultFromDetail(entry.detail);
      resultType = parsed.result_type;
      resultValue = parsed.result_value;
    }
    if (typeEl) typeEl.value = resultType;
    if (pctEl) pctEl.value = resultType === "percentage" ? resultValue : "";
    if (gradeSel) gradeSel.value = resultType === "grade" ? resultValue : "";
    syncEduStudyingState();
    syncPassingYearSelectOptions();
  }

  function resetEducationForm() {
    editingEducationId = null;
    fillEducationForm(null);
    updateMultiAddButtons();
  }

  function buildEducationPreview() {
    var rows = (payload.education || []).map(function (ed) {
      return {
        degree: ed.grade || "",
        school: ed.school || "",
        dates: formatEduPassingDisplay(ed),
        detail: formatEduMarksDisplay(ed),
      };
    });
    var data = collectEducationFormData();
    if (educationFormHasInput(data)) {
      var draft = {
        degree: data.grade,
        school: data.school,
        dates: data.dates,
        detail: data.detail,
      };
      if (editingEducationId) {
        rows = rows.map(function (row, idx) {
          var src = (payload.education || [])[idx];
          return src && String(src.id) === String(editingEducationId) ? draft : row;
        });
      } else {
        rows.push(draft);
      }
    }
    var schoolEl = $("#rb2School");
    if (schoolEl && !schoolEl.readOnly) {
      var profileSchool = trimVal("rb2School");
      if (profileSchool) {
        if (rows.length) rows[0] = Object.assign({}, rows[0], { school: profileSchool });
        else rows.push({ degree: "Student", school: profileSchool, dates: "", detail: "" });
      }
    }
    return rows;
  }

  function buildCertificationsPreview() {
    var rows = (payload.certificates || []).map(function (c) {
      return {
        name: c.title || "",
        issuer: c.description || "",
        date: c.issue_date || "",
      };
    });
    var title = trimVal("rb2CertTitle");
    var issuer = trimVal("rb2CertDesc");
    var dateEl = $("#rb2CertDate");
    var date = dateEl ? dateEl.value : "";
    if (title || issuer || date) {
      var draft = { name: title, issuer: issuer, date: date };
      if (editingCertId) {
        rows = rows.map(function (row, idx) {
          var src = (payload.certificates || [])[idx];
          return src && String(src.id) === String(editingCertId) ? draft : row;
        });
      } else {
        rows.push(draft);
      }
    }
    return rows;
  }

  function buildProjectsPreview() {
    var rows = (payload.activities || []).filter(isProjectActivity).map(function (a) {
      var parsed = parseProjectActivity(a);
      return projectToPreviewBlock(a.title, parsed.tech, parsed.desc, a.issue_date);
    });
    var projTitle = trimVal("rb2ProjectTitle");
    var projTech = trimVal("rb2ProjectTech");
    var projDesc = trimVal("rb2ProjectDesc");
    if (projTitle || projTech || projDesc) {
      var draftProj = projectToPreviewBlock(projTitle, projTech, projDesc, "");
      if (editingProjectId) {
        var replaced = false;
        rows = rows.map(function (item, idx) {
          var src = (payload.activities || []).filter(isProjectActivity)[idx];
          if (!replaced && src && String(src.id) === String(editingProjectId)) {
            replaced = true;
            return draftProj;
          }
          return item;
        });
        if (!replaced) rows.push(draftProj);
      } else {
        rows.push(draftProj);
      }
    }
    return rows;
  }

  function buildAchievementsPreview() {
    var rows = (payload.activities || []).filter(function (a) {
      return !isProjectActivity(a);
    }).map(function (a) {
      return {
        title: a.title || "",
        company: "",
        location: "",
        dates: a.issue_date || "",
        bullets: descToBullets(a.description),
      };
    });
    var achTitle = trimVal("rb2AchieveTitle");
    var achDesc = trimVal("rb2AchieveDesc");
    if (achTitle || achDesc) {
      var draftAch = {
        title: achTitle,
        company: "",
        location: "",
        dates: "",
        bullets: descToBullets(achDesc),
      };
      if (editingAchieveId) {
        var achReplaced = false;
        var achRows = (payload.activities || []).filter(function (a) {
          return !isProjectActivity(a);
        });
        rows = rows.map(function (item, idx) {
          var src = achRows[idx];
          if (!achReplaced && src && String(src.id) === String(editingAchieveId)) {
            achReplaced = true;
            return draftAch;
          }
          return item;
        });
        if (!achReplaced) rows.push(draftAch);
      } else {
        rows.push(draftAch);
      }
    }
    return rows;
  }

  function buildWorkExperiencePreview() {
    var ex = (payload.internships || []).map(function (it) {
      return {
        title: it.role || "",
        company: it.provider || "",
        location: "",
        dates: formatIsoRange(it.start_date, it.end_date),
        bullets: descToBullets(it.description),
      };
    });
    var role = trimVal("rb2ExpRole");
    var provider = trimVal("rb2ExpProvider");
    var expDesc = trimVal("rb2ExpDesc");
    var start = trimVal("rb2ExpStart");
    var end = trimVal("rb2ExpEnd");
    if (role || provider || expDesc || start || end) {
      ex.push({
        title: role,
        company: provider,
        location: "",
        dates: formatIsoRange(start, end),
        bullets: descToBullets(expDesc),
      });
    }
    return ex;
  }

  function buildExperiencePreview() {
    return buildAchievementsPreview();
  }

  function buildPreviewResumeFromForms() {
    var base = cfg.prototypePayload && typeof cfg.prototypePayload === "object"
      ? JSON.parse(JSON.stringify(cfg.prototypePayload))
      : {};
    var nameEl = $("#rb2Name");
    if (nameEl && !nameEl.readOnly) {
      var name = trimVal("rb2Name");
      if (name) base.fullName = name;
    }
    base.headline = trimVal("rb2Headline");
    var phoneEl = $("#rb2Phone");
    if (phoneEl && !phoneEl.readOnly) base.phone = trimVal("rb2Phone");
    var emailEl = $("#rb2Email");
    if (emailEl) base.email = emailEl.value.trim();
    var summaryField = $("#rb2SummaryField");
    if (summaryField) base.summary = summaryField.value.trim();
    var hobbiesField = $("#rb2HobbiesField");
    if (hobbiesField) base.hobbies = hobbiesField.value.trim();
    base.languages = collectLanguageRows();
    var skills = (payload.skills || []).map(function (s) {
      return { name: s.title || "", level: proficiencyLabel(s.profficiency) };
    });
    var pendingSkill = trimVal("rb2SkillInput");
    if (pendingSkill) skills.push({ name: pendingSkill, level: "" });
    base.skills = skills;
    base.education = buildEducationPreview();
    base.certifications = buildCertificationsPreview();
    base.projects = buildProjectsPreview();
    base.achievements = buildAchievementsPreview();
    base.workExperience = buildWorkExperiencePreview();
    base.experience = base.achievements;
    base.photo = cfg.resumePhotoUrl || "";
    if (!base.photo) {
      base.photoInitial = cfg.avatarInitial || "";
    } else {
      delete base.photoInitial;
    }
    return base;
  }

  function pushDraftToPreview() {
    var frame = $("#rb2PreviewFrame");
    if (!frame || !frame.contentWindow) return;
    try {
      frame.contentWindow.postMessage(
        { type: "TT_STUDIO_DRAFT_UPDATE", resume: buildPreviewResumeFromForms() },
        "*"
      );
    } catch (_) {}
  }

  var AI_ELABORATE_MIN_CHARS = 12;

  function hasElaboratableText(value) {
    return (value || "").trim().length >= AI_ELABORATE_MIN_CHARS;
  }

  function syncAiWriteButtons() {
    var summary = ($("#rb2SummaryField") || {}).value || "";
    var showImproveSummary = hasElaboratableText(summary);
    var genSummary = $("#rb2GenSummary");
    var impSummary = $("#rb2ImproveSummary");
    if (genSummary) genSummary.hidden = showImproveSummary;
    if (impSummary) impSummary.hidden = !showImproveSummary;

    var achieveDesc = ($("#rb2AchieveDesc") || {}).value || "";
    var showImproveAchieve = hasElaboratableText(achieveDesc);
    var genAchieve = $("#rb2GenAchieve");
    var impAchieve = $("#rb2ImproveAchieve");
    if (genAchieve) genAchieve.hidden = showImproveAchieve;
    if (impAchieve) impAchieve.hidden = !showImproveAchieve;
  }

  function localItemCounts(draft) {
    var projects = (payload.activities || []).filter(isProjectActivity).length;
    var achievements = (payload.activities || []).filter(function (a) {
      return !isProjectActivity(a);
    }).length;
    if (trimVal("rb2ProjectTitle") || trimVal("rb2ProjectDesc") || trimVal("rb2ProjectTech")) {
      if (!editingProjectId) projects += 1;
    }
    if (trimVal("rb2AchieveTitle") || trimVal("rb2AchieveDesc")) {
      if (!editingAchieveId) achievements += 1;
    }
    var skills = (draft.skills || []).filter(function (s) {
      return (s.name || "").trim();
    }).length;
    var certificates = (draft.certifications || []).filter(function (c) {
      return (c.name || "").trim();
    }).length;
    var education = (draft.education || []).filter(function (ed) {
      return (ed.school || "").trim() || (ed.degree || "").trim();
    }).length;
    var internships = (payload.internships || []).length;
    if (trimVal("rb2ExpRole") || trimVal("rb2ExpProvider") || trimVal("rb2ExpDesc")) {
      internships += 1;
    }
    return {
      skills: skills,
      projects: projects,
      achievements: achievements,
      certificates: certificates,
      education: education,
      internships: internships,
    };
  }

  function localSectionStatus(section, draft, counts) {
    if (section === "personal") {
      var hasName = !!(draft.fullName || "").trim();
      var hasEmail = !!(draft.email || "").trim();
      var hasPhone = !!(draft.phone || "").trim();
      if (hasName && hasEmail && hasPhone) return [100, "complete"];
      if (hasName && hasEmail) return [70, "partial"];
      return [40, "partial"];
    }
    if (section === "education") {
      var eduOk = counts.education > 0;
      return [eduOk ? 100 : 0, eduOk ? "complete" : "missing"];
    }
    if (section === "skills") {
      var n = counts.skills;
      if (n >= 3) return [100, "complete"];
      if (n >= 1) return [Math.min(90, 40 + n * 15), "partial"];
      return [0, "missing"];
    }
    if (section === "projects") {
      var pn = counts.projects;
      if (pn >= 2) return [100, "complete"];
      if (pn >= 1) return [60, "partial"];
      return [0, "missing"];
    }
    if (section === "certificates") {
      return counts.certificates >= 1 ? [100, "complete"] : [0, "missing"];
    }
    if (section === "languages") {
      var ln = (draft.languages || []).length;
      return ln >= 1 ? [100, "complete"] : [0, "missing"];
    }
    if (section === "hobbies") {
      var hobOk = !!(draft.hobbies || "").trim();
      return [hobOk ? 100 : 0, hobOk ? "complete" : "missing"];
    }
    if (section === "achievements") {
      return counts.achievements >= 1 ? [100, "complete"] : [0, "missing"];
    }
    if (section === "summary") {
      var sumOk = !!(draft.summary || "").trim();
      return [sumOk ? 100 : 0, sumOk ? "complete" : "missing"];
    }
    if (section === "experience") {
      return counts.internships >= 1 ? [100, "complete"] : [0, "missing"];
    }
    return [0, "missing"];
  }

  function sectionMetricLabel(section) {
    var fromCfg = cfg.sectionMetrics && cfg.sectionMetrics[section];
    if (fromCfg && fromCfg.label) return fromCfg.label;
    return section.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function computeLocalSectionMetrics() {
    var draft = buildPreviewResumeFromForms();
    var counts = localItemCounts(draft);
    var result = {};
    var total = 0;
    sections.forEach(function (sec) {
      var st = localSectionStatus(sec, draft, counts);
      result[sec] = {
        percent: st[0],
        status: st[1],
        label: sectionMetricLabel(sec),
      };
      total += st[0];
    });
    var overall = sections.length ? Math.round(total / sections.length) : 0;
    return { sections: result, overall: overall };
  }

  function updateLocalUiFromForms() {
    var metrics = computeLocalSectionMetrics();
    updateSectionNav(metrics.sections);
    updateProgress(metrics.overall);
    var complete = document.getElementById("rb2StrengthComplete");
    var details = document.getElementById("rb2StrengthDetails");
    if (complete) complete.textContent = metrics.overall + "%";
    if (details) details.textContent = metrics.overall + "%";
    pushDraftToPreview();
  }

  function scheduleLocalUiSync() {
    syncAiWriteButtons();
    clearTimeout(draftPreviewTimer);
    draftPreviewTimer = setTimeout(updateLocalUiFromForms, 150);
  }

  function bindLivePreview() {
    var form = document.querySelector(".rb2-studio-form");
    if (!form) return;
    form.addEventListener("input", function (e) {
      var field = e.target.closest(".rb2-field");
      if (field && field.classList.contains("is-invalid")) {
        field.classList.remove("is-invalid");
        var hint = field.querySelector(".rb2-field-error");
        if (hint) hint.remove();
      }
      scheduleLocalUiSync();
    });
    form.addEventListener("change", scheduleLocalUiSync);
  }

  function setActiveSection(id) {
    activeSection = id;
    document.querySelectorAll(".rb2-section-nav-item, .rb2-step-btn").forEach(function (el) {
      el.classList.toggle("is-active", el.dataset.section === id);
    });
    document.querySelectorAll(".rb2-editor-section").forEach(function (el) {
      el.style.display = el.dataset.section === id ? "block" : "none";
    });
    if (savePending > 0) {
      var activeCard = document.querySelector('.rb2-editor-section[data-section="' + id + '"] .rb2-form-card');
      document.querySelectorAll(".rb2-form-card.is-saving").forEach(function (card) {
        card.classList.remove("is-saving");
      });
      if (activeCard) activeCard.classList.add("is-saving");
    }
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
        : "Continue <i class='bx bx-chevron-right'></i>";
    }
    if (stepLabel) {
      var activeBtn = document.querySelector('.rb2-step-btn[data-section="' + activeSection + '"]');
      var textEl = activeBtn && activeBtn.querySelector(".rb2-step-btn__text");
      stepLabel.textContent = textEl ? textEl.textContent.trim() : activeSection;
    }
  }

  function goToPrevSection() {
    var idx = sectionIndex(activeSection);
    if (idx <= 0) return;
    navigateToSection(sections[idx - 1]);
  }

  function goToNextSection() {
    var idx = sectionIndex(activeSection);
    if (idx >= sections.length - 1) return;
    navigateToSection(sections[idx + 1]);
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

  function saveEducationIfFilled() {
    var card = activeFormCard();
    if (card) clearFieldErrors(card);
    var data = collectEducationFormData();
    if (!educationFormHasInput(data)) return Promise.resolve();
    if (!validateEducationSection()) return validationReject();
    var syncProfileSchool = false;
    if (editingEducationId) {
      var existing = (payload.education || []).find(function (ed) {
        return String(ed.id) === String(editingEducationId);
      });
      syncProfileSchool = !!(existing && existing.is_profile_school);
    }
    var body = editingEducationId
      ? {
          action: "update_education",
          entry_id: editingEducationId,
          school: data.school,
          grade: data.grade,
          dates: data.dates,
          detail: data.detail,
          passing_year: data.passing_year,
          result_type: data.result_type,
          result_value: data.result_value,
        }
      : {
          action: "add_education",
          school: data.school,
          grade: data.grade,
          dates: data.dates,
          detail: data.detail,
          passing_year: data.passing_year,
          result_type: data.result_type,
          result_value: data.result_value,
        };
    return apiPost(body).then(function (resp) {
      onStudioUpdate(resp);
      if (syncProfileSchool) {
        var schoolEl = $("#rb2School");
        if (schoolEl) schoolEl.value = data.school;
      }
      resetEducationForm();
      reloadPreview(cfg.prototypeKey, true);
    }).catch(function (err) {
      if (err.payload && err.payload.error) setFieldError("rb2EduSchool", err.payload.error);
      return validationReject();
    });
  }

  function saveSummaryData() {
    var field = $("#rb2SummaryField");
    if (!field) return Promise.resolve();
    return apiPost({ action: "save_summary", text: field.value.trim() }).then(onStudioUpdate);
  }

  function saveProjectIfFilled() {
    var card = activeFormCard();
    if (card) clearFieldErrors(card);
    var title = trimVal("rb2ProjectTitle");
    var desc = trimVal("rb2ProjectDesc");
    if (!title && !desc) return Promise.resolve();
    if (!title) {
      setFieldError("rb2ProjectTitle", "Enter a project title");
      return validationReject();
    }
    if (!desc) {
      setFieldError("rb2ProjectDesc", "Describe what you did");
      return validationReject();
    }
    var tech = trimVal("rb2ProjectTech");
    var fullDesc = formatProjectStorage(tech, desc);
    var body = editingProjectId
      ? { action: "update_activity", item_id: editingProjectId, title: title, description: fullDesc }
      : { action: "add_activity", title: title, description: fullDesc };
    return apiPost(body).then(function (data) {
      onStudioUpdate(data);
      resetProjectForm();
      reloadPreview(cfg.prototypeKey, true);
    }).catch(function (err) {
      if (err.payload && err.payload.error) setFieldError("rb2ProjectTitle", err.payload.error);
      return validationReject();
    });
  }

  function saveCertIfFilled() {
    var card = activeFormCard();
    if (card) clearFieldErrors(card);
    var title = trimVal("rb2CertTitle");
    var issuer = trimVal("rb2CertDesc");
    if (!title && !issuer) return Promise.resolve();
    var ok = true;
    if (!title) {
      setFieldError("rb2CertTitle", "Enter the certificate name");
      ok = false;
    }
    if (!issuer) {
      setFieldError("rb2CertDesc", "Enter who gave the certificate");
      ok = false;
    }
    if (!ok) return validationReject();
    var certBody = {
      title: title,
      description: issuer,
      issue_date: ($("#rb2CertDate") || {}).value || null,
    };
    if (editingCertId) {
      certBody.action = "update_certificate";
      certBody.item_id = editingCertId;
    } else {
      certBody.action = "add_certificate";
    }
    return apiPost(certBody).then(function (data) {
      onStudioUpdate(data);
      resetCertForm();
    }).catch(function (err) {
      if (err.payload && err.payload.error) {
        var fieldId = err.payload.error.toLowerCase().indexOf("who gave") >= 0 ? "rb2CertDesc" : "rb2CertTitle";
        setFieldError(fieldId, err.payload.error);
      }
      return validationReject();
    });
  }

  function saveAchieveIfFilled() {
    var card = activeFormCard();
    if (card) clearFieldErrors(card);
    var title = trimVal("rb2AchieveTitle");
    var desc = trimVal("rb2AchieveDesc");
    if (!title && !desc) return Promise.resolve();
    var ok = true;
    if (!title) {
      setFieldError("rb2AchieveTitle", "Enter a title");
      ok = false;
    }
    if (!desc) {
      setFieldError("rb2AchieveDesc", "Tell us a bit more");
      ok = false;
    }
    if (!ok) return validationReject();
    var achieveBody = editingAchieveId
      ? { action: "update_activity", item_id: editingAchieveId, title: title, description: desc }
      : { action: "add_activity", title: title, description: desc };
    return apiPost(achieveBody).then(function (data) {
      onStudioUpdate(data);
      resetAchieveForm();
    }).catch(function (err) {
      if (err.payload && err.payload.error) setFieldError("rb2AchieveTitle", err.payload.error);
      return validationReject();
    });
  }

  function saveLanguagesData(langsOverride) {
    if (!validateLanguagesSection()) return validationReject();
    var langs = langsOverride || collectLanguageRows();
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
    var card = activeFormCard();
    if (card) clearFieldErrors(card);
    var role = trimVal("rb2ExpRole");
    var provider = trimVal("rb2ExpProvider");
    var description = trimVal("rb2ExpDesc");
    var start = trimVal("rb2ExpStart");
    var end = trimVal("rb2ExpEnd");
    if (!role && !provider && !description && !start && !end) return Promise.resolve();
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
    if (!ok) return validationReject();
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
    }).catch(function (err) {
      if (err.payload && err.payload.error) setFieldError("rb2ExpRole", err.payload.error);
      return validationReject();
    });
  }

  function saveCurrentSection() {
    switch (activeSection) {
      case "personal":
        return savePersonalData();
      case "education":
        return saveEducationIfFilled();
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

  /** Persist every section with unsaved form input — used only on Save & Finish. */
  function saveAllSections() {
    /* Snapshot languages before earlier saves trigger renderLists() and wipe the form. */
    var languagesSnapshot = collectLanguageRows();
    profileSyncBatchDepth += 1;
    queuedProfileSyncOffers = [];
    var steps = [
      savePersonalData,
      saveEducationIfFilled,
      function () {
        var skillInput = trimVal("rb2SkillInput");
        if (skillInput) {
          return addSkill(skillInput).then(function () {
            if ($("#rb2SkillInput")) $("#rb2SkillInput").value = "";
          });
        }
        return Promise.resolve();
      },
      saveProjectIfFilled,
      saveCertIfFilled,
      function () {
        return saveLanguagesData(languagesSnapshot);
      },
      saveHobbiesData,
      saveAchieveIfFilled,
      saveSummaryData,
      saveExpIfFilled,
    ];
    return steps.reduce(function (chain, step) {
      return chain.then(function () {
        return step();
      });
    }, Promise.resolve()).then(function (result) {
      profileSyncBatchDepth = Math.max(0, profileSyncBatchDepth - 1);
      var offers = queuedProfileSyncOffers.slice();
      queuedProfileSyncOffers = [];
      return promptProfileSyncOffers(offers).then(function () {
        return result;
      });
    }, function (err) {
      profileSyncBatchDepth = Math.max(0, profileSyncBatchDepth - 1);
      queuedProfileSyncOffers = [];
      throw err;
    });
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
          scheduleLocalUiSync();
          return;
        }
        btn.closest(".rb2-lang-row").remove();
        scheduleLocalUiSync();
      });
    });
    bindLangNameSuggestions(container);
  }

  var langListEl = $("#rb2LanguagesList");
  if (langListEl) {
    function clearLangFieldError(e) {
      var field = e.target.closest(".rb2-field");
      if (!field) return;
      field.classList.remove("is-invalid");
      var hint = field.querySelector(".rb2-field-error");
      if (hint) hint.remove();
    }
    langListEl.addEventListener("input", clearLangFieldError);
    langListEl.addEventListener("change", clearLangFieldError);
  }

  function collectLanguageRows() {
    var rows = document.querySelectorAll("#rb2LanguagesList .rb2-lang-row");
    var langs = [];
    rows.forEach(function (row) {
      var nameEl = row.querySelector("[data-lang-name]");
      var levelEl = row.querySelector("[data-lang-level]");
      var name = nameEl ? nameEl.value.trim() : "";
      var level = levelEl ? levelEl.value.trim() : "";
      if (name) langs.push({ name: name, level: level });
    });
    return langs;
  }

  function renderLists() {
    renderSkillList();
    renderLanguagesList();
    renderEduList();
    renderActivityList("rb2ProjectsList", payload.activities || [], "project");
    renderCertList();
    renderActivityList("rb2AchieveList", payload.activities || [], "achievement");
    renderExpList();
  }

  function itemActionButtons(delType, id, editKind, opts) {
    opts = opts || {};
    var removeBtn = opts.hideRemove
      ? ""
      : '<button type="button" class="rb2-item-del" data-type="' +
        delType +
        '" data-kind="' +
        (editKind || "") +
        '" data-id="' +
        id +
        '">Remove</button>';
    return (
      '<div class="rb2-item-list__actions">' +
      '<button type="button" class="rb2-item-edit" data-kind="' +
      editKind +
      '" data-id="' +
      id +
      '">Edit</button>' +
      removeBtn +
      "</div>"
    );
  }

  function isProjectActivity(a) {
    return String((a && a.description) || "").trim().indexOf("Technologies:") === 0;
  }

  function formatProjectStorage(tech, desc) {
    var tools = (tech || "").trim();
    var body = (desc || "").trim();
    if (!body) return "";
    return "Technologies: " + tools + "\n" + body;
  }

  function projectToPreviewBlock(title, tech, desc, dates) {
    return {
      title: title || "",
      company: (tech || "").trim(),
      location: "",
      dates: dates || "",
      bullets: descToBullets((desc || "").trim()),
    };
  }

  function activityMatchesKind(a, kind) {
    if (kind === "project") return isProjectActivity(a);
    if (kind === "achievement") return !isProjectActivity(a);
    return true;
  }

  function updateMultiAddButtons() {
    var eduBtn = $("#rb2AddEducation");
    if (eduBtn) eduBtn.textContent = editingEducationId ? "Save changes" : "Add";
    var projBtn = $("#rb2AddProject");
    if (projBtn) projBtn.textContent = editingProjectId ? "Save changes" : "Add";
    var certBtn = $("#rb2AddCertificate");
    if (certBtn) certBtn.textContent = editingCertId ? "Save changes" : "Add";
    var achBtn = $("#rb2AddAchievement");
    if (achBtn) achBtn.textContent = editingAchieveId ? "Save changes" : "Add";
  }

  function resetCertForm() {
    editingCertId = null;
    ["rb2CertTitle", "rb2CertDesc", "rb2CertDate"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = "";
    });
    updateMultiAddButtons();
  }

  function resetAchieveForm() {
    editingAchieveId = null;
    if ($("#rb2AchieveTitle")) $("#rb2AchieveTitle").value = "";
    if ($("#rb2AchieveDesc")) $("#rb2AchieveDesc").value = "";
    updateMultiAddButtons();
  }

  function renderEduList() {
    var ul = $("#rb2EduList");
    if (!ul) return;
    ul.innerHTML = "";
    (payload.education || []).forEach(function (ed) {
      var li = document.createElement("li");
      li.className = "rb2-item-list__row";
      var parts = [ed.grade, formatEduPassingDisplay(ed), formatEduMarksDisplay(ed)].filter(Boolean);
      var subtitle = parts.join(" · ");
      li.innerHTML =
        "<div><strong>" + esc(ed.school) + "</strong>" +
        (subtitle ? "<div class=\"fs-12 text-muted\">" + esc(subtitle) + "</div>" : "") +
        "</div>" +
        itemActionButtons("education", ed.id || "", "education", {
          hideRemove: !!ed.is_profile_school,
        });
      ul.appendChild(li);
    });
    syncPassingYearSelectOptions();
    populateEduSchoolSuggestions();
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
      if (!activityMatchesKind(a, kind)) return;
      var li = document.createElement("li");
      li.className = "rb2-item-list__row";
      var snippet = "";
      if (kind === "project") {
        var parsed = parseProjectActivity(a);
        snippet = parsed.tech && parsed.desc
          ? parsed.tech + " — " + parsed.desc
          : (parsed.desc || parsed.tech || "");
      } else {
        snippet = (a.description || "").trim();
      }
      li.innerHTML =
        "<div><strong>" + esc(a.title) + "</strong>" +
        (snippet ? "<div class=\"fs-12 text-muted\">" + esc(snippet).slice(0, 140) + "</div>" : "") +
        "</div>" +
        itemActionButtons("activity", a.id, kind);
      ul.appendChild(li);
    });
  }

  function parseProjectActivity(activity) {
    var desc = String((activity && activity.description) || "").trim();
    var tech = "";
    if (desc.indexOf("Technologies:") === 0) {
      var nl = desc.indexOf("\n");
      if (nl >= 0) {
        tech = desc.slice("Technologies:".length, nl).trim();
        desc = desc.slice(nl + 1).trim();
      } else {
        tech = desc.slice("Technologies:".length).trim();
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
    updateMultiAddButtons();
  }

  function startProjectEdit(activityId) {
    var activity = (payload.activities || []).find(function (a) {
      return String(a.id) === String(activityId) && isProjectActivity(a);
    });
    if (!activity) return;
    var parsed = parseProjectActivity(activity);
    editingProjectId = activity.id;
    if ($("#rb2ProjectTitle")) $("#rb2ProjectTitle").value = parsed.title;
    if ($("#rb2ProjectTech")) $("#rb2ProjectTech").value = parsed.tech;
    if ($("#rb2ProjectDesc")) $("#rb2ProjectDesc").value = parsed.desc;
    updateMultiAddButtons();
    setActiveSection("projects");
    if ($("#rb2ProjectTitle")) $("#rb2ProjectTitle").focus();
    scheduleLocalUiSync();
  }

  function startEducationEdit(entryId) {
    var entry = (payload.education || []).find(function (ed) {
      return String(ed.id) === String(entryId);
    });
    if (!entry) return;
    editingEducationId = entry.id;
    fillEducationForm(entry);
    updateMultiAddButtons();
    setActiveSection("education");
    if ($("#rb2EduSchool")) $("#rb2EduSchool").focus();
    scheduleLocalUiSync();
  }

  function startCertEdit(certId) {
    var cert = (payload.certificates || []).find(function (c) {
      return String(c.id) === String(certId);
    });
    if (!cert) return;
    editingCertId = cert.id;
    if ($("#rb2CertTitle")) $("#rb2CertTitle").value = cert.title || "";
    if ($("#rb2CertDesc")) $("#rb2CertDesc").value = cert.description || "";
    if ($("#rb2CertDate")) $("#rb2CertDate").value = cert.issue_date || "";
    updateMultiAddButtons();
    setActiveSection("certificates");
    if ($("#rb2CertTitle")) $("#rb2CertTitle").focus();
    scheduleLocalUiSync();
  }

  function startAchieveEdit(activityId) {
    var activity = (payload.activities || []).find(function (a) {
      return String(a.id) === String(activityId) && !isProjectActivity(a);
    });
    if (!activity) return;
    editingAchieveId = activity.id;
    if ($("#rb2AchieveTitle")) $("#rb2AchieveTitle").value = activity.title || "";
    if ($("#rb2AchieveDesc")) $("#rb2AchieveDesc").value = activity.description || "";
    updateMultiAddButtons();
    setActiveSection("achievements");
    if ($("#rb2AchieveTitle")) $("#rb2AchieveTitle").focus();
    scheduleLocalUiSync();
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
        itemActionButtons("certificate", c.id, "certificate");
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
    if (data.suggestions !== undefined) updateTips(data.suggestions);
    if (data.strength) updateStrengthCard(data.strength);
    if (data.applied_fields) applyGeneratedFieldsToForms(data.applied_fields);
    if (data.resume_photo_url !== undefined) {
      setPhotoPreview(data.resume_photo_url);
    }
    if (data.prototype_key) cfg.prototypeKey = data.prototype_key;
    if (!options.skipPreviewReload) {
      reloadPreview(cfg.prototypeKey, !options.deferPreview);
    }
    scheduleLocalUiSync();
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
      scheduleLocalUiSync();
      return;
    }
    var initial = cfg.avatarInitial || "?";
    wrap.innerHTML =
      '<span class="rb2-photo-preview__avatar-initials" id="rb2PhotoPlaceholder">' + esc(initial) + "</span>";
    setPhotoUploadLabel(false);
    scheduleLocalUiSync();
  }

  function updatePhotoPreview(url) {
    setPhotoPreview(url);
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
    scheduleLocalUiSync();

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

  function currentProgressPct() {
    var bar = document.getElementById("rb2ProgressBar");
    if (bar && bar.style.width) {
      var fromBar = parseInt(bar.style.width, 10);
      if (!isNaN(fromBar)) return fromBar;
    }
    var pctEl = document.getElementById("rb2ProgressPct");
    if (pctEl) {
      var m = pctEl.textContent.match(/(\d+)/);
      if (m) return parseInt(m[1], 10);
    }
    return 0;
  }

  function progressLevelKey(level) {
    return (level || "good").trim().toLowerCase();
  }

  function setProgressLabel(pct, level) {
    var label = document.getElementById("rb2ProgressLabel");
    var pctEl = document.getElementById("rb2ProgressPct");
    var levelEl = document.getElementById("rb2ProgressLevel");
    var barWrap = document.getElementById("rb2ProgressBarWrap");
    var key = progressLevelKey(level);
    if (label) label.dataset.level = key;
    if (barWrap) {
      barWrap.dataset.level = key;
      barWrap.setAttribute("aria-valuenow", String(pct));
    }
    if (pct >= 100) {
      if (label) {
        label.innerHTML = '<span class="rb2-progress-pct rb2-progress-pct--complete">Resume complete!</span>';
      }
      return;
    }
    if (pctEl) pctEl.textContent = pct + "% done";
    if (levelEl) levelEl.textContent = level || levelEl.textContent || "Good";
  }

  function updateProgress(pct, level) {
    var bar = document.getElementById("rb2ProgressBar");
    if (bar) bar.style.width = pct + "%";
    if (level == null) {
      var levelEl = document.getElementById("rb2ProgressLevel");
      level = levelEl ? levelEl.textContent.trim() : "Good";
    }
    setProgressLabel(pct, level);
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
    if (strength.level != null && strength.completion != null) {
      updateProgress(strength.completion, strength.level);
    } else if (strength.level != null) {
      setProgressLabel(strength.completion != null ? strength.completion : currentProgressPct(), strength.level);
    }
  }

  function updateCompleteUI(pct) {
    var complete = pct >= 100;
    ["rb2CompleteBanner", "rb2CompleteSidebar"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.toggle("is-visible", complete);
    });
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
        if (row.dataset.section) navigateToSection(row.dataset.section);
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

  /* ——— Full resume AI generation ——— */
  function collectResumeSectionsSnapshot() {
    var projects = (payload.activities || []).filter(function (a) {
      return (a.description || "").indexOf("Technologies: ") === 0;
    }).map(function (a) { return parseProjectActivity(a); });

    var achievements = (payload.activities || []).filter(function (a) {
      return (a.description || "").indexOf("Technologies: ") !== 0;
    }).map(function (a) {
      return { title: a.title || "", description: a.description || "" };
    });

    return {
      personal: {
        name: trimVal("rb2Name"),
        headline: trimVal("rb2Headline"),
        phone: trimVal("rb2Phone"),
        school: trimVal("rb2School"),
        email: trimVal("rb2Email"),
      },
      summary: ($("#rb2SummaryField") || {}).value || "",
      skills: (payload.skills || []).map(function (s) { return s.title; }),
      education: payload.education || [],
      projects: projects,
      certificates: (payload.certificates || []).map(function (c) {
        return { title: c.title, issuer: c.description, issue_date: c.issue_date || "" };
      }),
      achievements: achievements,
      experience: (payload.internships || []).map(function (e) {
        return {
          role: e.role,
          provider: e.provider,
          description: e.description,
          start_date: e.start_date || "",
          end_date: e.end_date || "",
        };
      }),
      languages: collectLanguageRows(),
      hobbies: ($("#rb2HobbiesField") || {}).value || "",
      draft: {
        project: {
          title: trimVal("rb2ProjectTitle"),
          technologies: trimVal("rb2ProjectTech"),
          description: trimVal("rb2ProjectDesc"),
        },
        certificate: {
          title: trimVal("rb2CertTitle"),
          issuer: trimVal("rb2CertDesc"),
          issue_date: ($("#rb2CertDate") || {}).value || "",
        },
        achievement: {
          title: trimVal("rb2AchieveTitle"),
          description: trimVal("rb2AchieveDesc"),
        },
        education: collectEducationFormData(),
        experience: {
          role: trimVal("rb2ExpRole"),
          provider: trimVal("rb2ExpProvider"),
          description: trimVal("rb2ExpDesc"),
          start_date: trimVal("rb2ExpStart"),
          end_date: trimVal("rb2ExpEnd"),
        },
      },
    };
  }

  function applyGeneratedFieldsToForms(applied) {
    if (!applied) return;
    if (applied.headline && $("#rb2Headline")) $("#rb2Headline").value = applied.headline;
    if (applied.summary !== undefined && $("#rb2SummaryField")) $("#rb2SummaryField").value = applied.summary || "";
    if (applied.hobbies !== undefined && $("#rb2HobbiesField")) $("#rb2HobbiesField").value = applied.hobbies || "";
    ["rb2ProjectTitle", "rb2ProjectTech", "rb2ProjectDesc", "rb2CertTitle", "rb2CertDesc", "rb2CertDate",
      "rb2AchieveTitle", "rb2AchieveDesc",
      "rb2ExpRole", "rb2ExpProvider", "rb2ExpDesc", "rb2ExpStart", "rb2ExpEnd"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = "";
    });
    resetEducationForm();
    resetProjectForm();
    scheduleLocalUiSync();
  }

  function formatAiError(err) {
    var msg = (err && err.payload && err.payload.error) || (err && err.message) || "";
    if (!msg) return "Something went wrong. Please try again.";
    return msg;
  }

  function handleAiError(err, fallbackTitle) {
    var payload = (err && err.payload) || {};
    var msgs = window.RB2Messages;
    if (payload.quota_exceeded) {
      cfg.aiQuotaLocked = true;
      applyAiQuotaLockUI();
      var headline = payload.headline || payload.message || cfg.aiQuotaMessage || "AI tokens need to recharge — Buy now.";
      var body = payload.body || payload.detail || headline;
      if (msgs && typeof msgs.confirm === "function") {
        msgs
          .confirm({
            title: headline,
            message: body,
            confirmLabel: payload.cta_label || "Buy now",
            cancelLabel: "Not now",
          })
          .then(function (ok) {
            if (ok) {
              window.location.href = payload.cta_url || payload.shop_url || cfg.aiQuotaShopUrl || "/ai-tokens/";
            }
          });
      } else if (window.confirm(headline)) {
        window.location.href = payload.cta_url || payload.shop_url || cfg.aiQuotaShopUrl || "/ai-tokens/";
      }
      return;
    }
    if (msgs) {
      msgs.toast(formatAiError(err), { type: "error", title: fallbackTitle || "AI writing" });
    }
  }

  var AI_QUOTA_BTN_IDS = [
    "rb2GenSummary",
    "rb2ImproveSummary",
    "rb2AtsSummary",
    "rb2GenAchieve",
    "rb2ImproveAchieve",
    "rb2GenerateResumeAI",
  ];

  function updateAiBadgeUI() {
    var badge = document.getElementById("rb2AiEditsBadge");
    if (!badge) return;
    var rem;
    if (cfg.aiQuotaUnlimited) {
      badge.textContent = "∞";
      rem = null;
    } else {
      rem = cfg.aiQuotaRemaining;
      if (rem === null || rem === undefined) rem = 0;
      rem = Math.max(0, Number(rem) || 0);
      badge.textContent = rem > 99 ? "99+" : String(rem);
    }
    badge.classList.toggle("is-empty", !cfg.aiQuotaUnlimited && rem === 0);
    badge.classList.toggle("is-low", !cfg.aiQuotaUnlimited && rem > 0 && rem <= 1);
    badge.setAttribute(
      "aria-label",
      cfg.aiQuotaUnlimited ? "Unlimited AI edits" : rem + " AI edits left"
    );
  }

  function refreshAiQuotaStatus() {
    if (!cfg.aiQuotaApplies || !cfg.aiQuotaStatusUrl) {
      updateAiBadgeUI();
      return Promise.resolve();
    }
    return fetch(cfg.aiQuotaStatusUrl, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        if (!r.ok) throw new Error("status failed");
        return r.json();
      })
      .then(function (payload) {
        var feat = (payload && payload.features && payload.features.resume_ai) || {};
        cfg.aiQuotaLocked = !!feat.locked;
        cfg.aiQuotaUnlimited = !!feat.unlimited;
        cfg.aiQuotaRemaining = feat.unlimited ? null : feat.remaining;
        applyAiQuotaLockUI();
      })
      .catch(function () {
        updateAiBadgeUI();
      });
  }

  function applyAiQuotaLockUI() {
    var locked = !!cfg.aiQuotaLocked;
    var msg = cfg.aiQuotaMessage || "AI tokens need to recharge — Buy now.";
    var shop = cfg.aiQuotaShopUrl || "/ai-tokens/";
    AI_QUOTA_BTN_IDS.forEach(function (id) {
      var btn = document.getElementById(id);
      if (!btn) return;
      // Keep Generate button hoverable when locked (native disabled blocks mouse events).
      if (id === "rb2GenerateResumeAI") {
        btn.disabled = false;
        btn.classList.toggle("rb2-ai-locked", locked);
        if (locked) {
          btn.setAttribute("aria-disabled", "true");
          btn.removeAttribute("title");
        } else {
          btn.removeAttribute("aria-disabled");
          btn.setAttribute("title", "Enhance entire resume with AI for your goal");
        }
        return;
      }
      btn.disabled = locked;
      btn.classList.toggle("rb2-ai-locked", locked);
      if (locked) {
        btn.setAttribute("aria-disabled", "true");
        btn.setAttribute("title", msg);
      } else {
        btn.removeAttribute("aria-disabled");
      }
    });
    var wrap = document.getElementById("rb2AiGenWrap");
    if (wrap) {
      wrap.classList.toggle("is-locked", locked);
      if (!locked) wrap.classList.remove("is-open");
    }
    var infoIcon = document.getElementById("rb2AiQuotaInfoIcon");
    if (infoIcon) infoIcon.hidden = !locked;
    var msgEl = document.querySelector("#rb2AiQuotaInfoPop .rb2-ai-gen-info__msg");
    if (msgEl) msgEl.textContent = msg;
    var cta = document.getElementById("rb2AiQuotaInfoCta");
    if (cta) cta.href = shop;
    updateAiBadgeUI();
  }

  function bindAiQuotaInfoHover() {
    var wrap = document.getElementById("rb2AiGenWrap");
    if (!wrap || wrap.dataset.bound === "1") return;
    wrap.dataset.bound = "1";
    var genBtn = document.getElementById("rb2GenerateResumeAI");
    var closeTimer = null;
    function openPop() {
      if (!wrap.classList.contains("is-locked")) return;
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
      wrap.classList.add("is-open");
    }
    function scheduleClose() {
      if (closeTimer) clearTimeout(closeTimer);
      closeTimer = setTimeout(function () {
        wrap.classList.remove("is-open");
      }, 140);
    }
    wrap.addEventListener("mouseenter", openPop);
    wrap.addEventListener("mouseleave", scheduleClose);
    if (genBtn) {
      genBtn.addEventListener("focus", openPop);
      genBtn.addEventListener("blur", scheduleClose);
    }
    var pop = document.getElementById("rb2AiQuotaInfoPop");
    if (pop) {
      pop.addEventListener("mouseenter", openPop);
      pop.addEventListener("mouseleave", scheduleClose);
    }
  }

  function hideAiPendingBanner() {
    var banner = $("#rb2AiPendingBanner");
    if (banner) banner.hidden = true;
    cfg.hasAiPending = false;
  }

  function openAiReviewModal(data) {
    if (!data || !data.comparison || !window.RB2AiReviewModal) return;
    window.RB2AiReviewModal.open({
      comparison: data.comparison,
      original: data.original,
      generated: data.generated,
      goalLabel: data.goal_label || cfg.goalLabel || cfg.goal || "",
      resumeTitle: (document.querySelector(".rb2-studio-topbar__title-badge") || {}).textContent || "My Resume",
      aiUrl: cfg.aiUrl,
      csrfToken: csrfToken,
      resumeId: cfg.resumeId,
      onApplied: function (appliedData) {
        hideAiPendingBanner();
        onStudioUpdate(appliedData);
        if (appliedData.applied_fields) applyGeneratedFieldsToForms(appliedData.applied_fields);
        reloadPreview(cfg.prototypeKey, true);
      },
      onDiscarded: hideAiPendingBanner,
    });
  }

  function openPendingAiReview() {
    return apiPost({ action: "get_ai_pending_review" }).then(function (data) {
      if (data && data.has_pending && data.comparison) {
        openAiReviewModal(data);
      } else {
        hideAiPendingBanner();
      }
    });
  }

  function runGenerateResumeAI(btn) {
    var goalLabel = cfg.goalLabel || cfg.goal || "your goal";
    var msgs = window.RB2Messages;
    if (!msgs) {
      console.error("RB2Messages failed to load");
      return;
    }
    if (cfg.aiQuotaLocked) {
      var wrapLocked = document.getElementById("rb2AiGenWrap");
      if (wrapLocked) wrapLocked.classList.add("is-open");
      return;
    }

    function startGeneration() {
      var defaultHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Generating…";

      apiPost({
        action: "generate_resume",
        career_goal: cfg.goal || "",
        sections: collectResumeSectionsSnapshot(),
      })
        .then(function (data) {
          btn.disabled = false;
          btn.innerHTML = defaultHtml;
          if (data.comparison) {
            openAiReviewModal(data);
          } else if (data.message) {
            msgs.toast(data.message, { type: "info", title: "AI generation" });
          }
          refreshAiQuotaStatus();
        })
        .catch(function (err) {
          btn.disabled = false;
          btn.innerHTML = defaultHtml;
          if (err && err.message === "validation") return;
          handleAiError(err, "AI generation");
        });
    }

    apiPost({ action: "get_ai_pending_review" })
      .then(function (pending) {
        if (pending && pending.has_pending && pending.comparison) {
          return msgs
            .confirm({
              title: "Unsaved AI draft",
              message:
                "You already have an AI draft for this resume. Review it now, or create a fresh one?",
              confirmLabel: "Review draft",
              cancelLabel: "Generate new",
            })
            .then(function (wantReview) {
              if (wantReview) {
                openAiReviewModal(pending);
                return;
              }
              return msgs
                .confirm({
                  title: "Generate AI-enhanced resume?",
                  message:
                    "We'll create a new improved draft for \"" +
                    goalLabel +
                    "\" using all your current sections.",
                  confirmLabel: "Generate draft",
                  cancelLabel: "Not now",
                })
                .then(function (ok) {
                  if (ok) startGeneration();
                });
            });
        }
        return msgs
          .confirm({
            title: "Generate AI-enhanced resume?",
            message:
              "We'll create an improved draft for \"" +
              goalLabel +
              "\" using all your current sections. You can compare old vs new before applying anything.",
            confirmLabel: "Generate draft",
            cancelLabel: "Not now",
          })
          .then(function (ok) {
            if (ok) startGeneration();
          });
      })
      .catch(function () {
        msgs
          .confirm({
            title: "Generate AI-enhanced resume?",
            message:
              "We'll create an improved draft for \"" +
              goalLabel +
              "\" using all your current sections. You can compare old vs new before applying anything.",
            confirmLabel: "Generate draft",
            cancelLabel: "Not now",
          })
          .then(function (ok) {
            if (ok) startGeneration();
          });
      });
  }

  function bindLangNameSuggestions() {
    /* autocomplete removed */
  }

  /* ——— Section nav ——— */
  document.querySelectorAll(".rb2-section-nav-item, .rb2-step-btn").forEach(function (el) {
    el.addEventListener("click", function () { navigateToSection(el.dataset.section); });
  });

  var navBackBtn = $("#rb2NavBack");
  if (navBackBtn) {
    navBackBtn.addEventListener("click", goToPrevSection);
  }

  var navContinueBtn = $("#rb2NavContinue");
  if (navContinueBtn) {
    navContinueBtn.addEventListener("click", function () {
      var idx = sectionIndex(activeSection);
      var isLast = idx >= sections.length - 1;
      if (!isLast) {
        goToNextSection();
        return;
      }
      if (!validateAllSections()) return;
      saveAllSections()
        .then(function () {
          var msgs = window.RB2Messages;
          if (msgs) {
            msgs.toast("Your resume has been saved.", { type: "success", title: "Saved" });
          }
          var formMain = document.querySelector(".rb2-studio-form");
          if (formMain) formMain.scrollTop = 0;
        })
        .catch(function () {});
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
          scheduleLocalUiSync();
        });
        break;
      default:
        break;
    }
  }

  function hobbyNamesInField() {
    var field = $("#rb2HobbiesField");
    if (!field) return [];
    return field.value.split(/[,;\n]+/).map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function syncProfileHobbyChips() {
    var selected = hobbyNamesInField().map(function (s) { return s.toLowerCase(); });
    document.querySelectorAll("#rb2ProfileHobbies .rb2-kw-chip").forEach(function (chip) {
      var name = (chip.dataset.hobby || "").trim().toLowerCase();
      var picked = name && selected.indexOf(name) >= 0;
      chip.classList.toggle("is-added", picked);
      chip.disabled = picked;
    });
  }

  var hobbiesSaveTimer = null;

  function scheduleHobbiesAutoSave() {
    clearTimeout(hobbiesSaveTimer);
    hobbiesSaveTimer = setTimeout(function () {
      saveHobbiesData().catch(function () {});
    }, 900);
  }

  function bindProfileHobbyChips() {
    var row = $("#rb2ProfileHobbies");
    if (!row) return;
    row.querySelectorAll(".rb2-kw-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var field = $("#rb2HobbiesField");
        if (!field || chip.disabled) return;
        var name = (chip.dataset.hobby || "").trim();
        if (!name) return;
        var current = hobbyNamesInField();
        if (current.some(function (h) { return h.toLowerCase() === name.toLowerCase(); })) return;
        current.push(name);
        field.value = current.join(", ");
        syncProfileHobbyChips();
        scheduleLocalUiSync();
        scheduleHobbiesAutoSave();
      });
    });
    syncProfileHobbyChips();
    var hobbiesField = $("#rb2HobbiesField");
    if (hobbiesField) {
      hobbiesField.addEventListener("input", function () {
        syncProfileHobbyChips();
        scheduleHobbiesAutoSave();
      });
    }
  }

  function prefillHobbiesFieldIfEmpty() {
    var field = $("#rb2HobbiesField");
    if (!field || field.value.trim()) return;
    var chips = document.querySelectorAll("#rb2ProfileHobbies .rb2-kw-chip");
    if (!chips.length) return;
    var names = [];
    chips.forEach(function (chip) {
      var name = (chip.dataset.hobby || "").trim();
      if (name) names.push(name);
    });
    if (!names.length) return;
    field.value = names.join(", ");
    scheduleLocalUiSync();
    scheduleHobbiesAutoSave();
  }

  bindProfileHobbyChips();
  prefillHobbiesFieldIfEmpty();
  bindCoachItems();

  /* ——— Summary AI ——— */
  function bindAi(btnId, action, getPayload, targetId) {
    var btn = document.getElementById(btnId);
    if (!btn) return;
    var defaultHtml = btn.innerHTML;
    btn.addEventListener("click", function () {
      if (cfg.aiQuotaLocked) {
        handleAiError({ payload: { quota_exceeded: true, message: cfg.aiQuotaMessage } }, "AI writing");
        return;
      }
      btn.disabled = true;
      btn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Writing…";
      var p = getPayload();
      p.action = action;
      apiPost(p).then(function (data) {
        var fieldId = targetId || "rb2SummaryField";
        if (data.text && $("#" + fieldId)) $("#" + fieldId).value = data.text;
        if (data.bullets && $("#" + fieldId)) $("#" + fieldId).value = data.bullets.join("\n");
        scheduleLocalUiSync();
        btn.disabled = false;
        btn.innerHTML = defaultHtml;
        refreshAiQuotaStatus();
      }).catch(function (err) {
        btn.disabled = false;
        btn.innerHTML = defaultHtml;
        handleAiError(err, "AI writing");
      });
    });
  }

  applyAiQuotaLockUI();
  bindAiQuotaInfoHover();
  refreshAiQuotaStatus();

  bindAi("rb2GenSummary", "generate_summary", function () { return { career_goal: cfg.goal || "" }; });
  bindAi("rb2ImproveSummary", "improve_summary", function () {
    return { text: ($("#rb2SummaryField") || {}).value || "", mode: "professional" };
  });
  bindAi("rb2AtsSummary", "improve_summary", function () {
    return { text: ($("#rb2SummaryField") || {}).value || "", mode: "ats" };
  });
  bindAi("rb2GenAchieve", "generate_achievement", function () {
    return { title: ($("#rb2AchieveTitle") || {}).value || "" };
  }, "rb2AchieveDesc");
  bindAi("rb2ImproveAchieve", "improve_achievement", function () {
    return {
      title: ($("#rb2AchieveTitle") || {}).value || "",
      text: ($("#rb2AchieveDesc") || {}).value || "",
      mode: "professional",
    };
  }, "rb2AchieveDesc");

  /* ——— Add skill button ——— */
  var addSkillBtn = $("#rb2AddSkill");
  if (addSkillBtn) {
    addSkillBtn.addEventListener("click", function () {
      var input = $("#rb2SkillInput");
      addSkill(input ? input.value : "").then(function () {
        if (input) input.value = "";
      });
    });
  }

  var skillInput = $("#rb2SkillInput");
  if (skillInput) {
    skillInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        addSkill(skillInput.value).then(function () { skillInput.value = ""; });
      }
    });
  }

  var generateAiBtn = document.getElementById("rb2GenerateResumeAI");
  if (generateAiBtn) {
    generateAiBtn.addEventListener("click", function () { runGenerateResumeAI(generateAiBtn); });
  }

  var reviewDraftBtn = $("#rb2ReviewAiDraft");
  if (reviewDraftBtn) {
    reviewDraftBtn.addEventListener("click", function () {
      openPendingAiReview();
    });
  }
  var dismissAiBanner = $("#rb2DismissAiBanner");
  if (dismissAiBanner) {
    dismissAiBanner.addEventListener("click", hideAiPendingBanner);
  }

  var addEduBtn = $("#rb2AddEducation");
  if (addEduBtn) {
    addEduBtn.addEventListener("click", function () {
      saveEducationIfFilled();
    });
  }

  var addProjBtn = $("#rb2AddProject");
  if (addProjBtn) {
    addProjBtn.addEventListener("click", function () {
      saveProjectIfFilled();
    });
  }

  var addCertBtn = $("#rb2AddCertificate");
  if (addCertBtn) {
    addCertBtn.addEventListener("click", function () {
      saveCertIfFilled().then(function () {
        reloadPreview(cfg.prototypeKey, true);
      });
    });
  }

  var addAchieveBtn = $("#rb2AddAchievement");
  if (addAchieveBtn) {
    addAchieveBtn.addEventListener("click", function () {
      saveAchieveIfFilled();
    });
  }

  /* ——— Project ——— */
  var genProjBtn = $("#rb2GenProjectDesc");
  if (genProjBtn) {
    var genProjDefaultHtml = genProjBtn.innerHTML;
    genProjBtn.addEventListener("click", function () {
      genProjBtn.disabled = true;
      genProjBtn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Writing…";
      apiPost({
        action: "generate_project",
        title: ($("#rb2ProjectTitle") || {}).value || "",
        technologies: ($("#rb2ProjectTech") || {}).value || "",
      }).then(function (data) {
        var desc = $("#rb2ProjectDesc");
        if (desc && data.bullets) desc.value = data.bullets.join("\n");
        scheduleLocalUiSync();
        genProjBtn.disabled = false;
        genProjBtn.innerHTML = genProjDefaultHtml;
      }).catch(function (err) {
        genProjBtn.disabled = false;
        genProjBtn.innerHTML = genProjDefaultHtml;
        handleAiError(err, "AI writing");
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
        scheduleLocalUiSync();
      });
      var nameInput = row.querySelector("[data-lang-name]");
      if (nameInput) nameInput.focus();
      bindLangNameSuggestions(row);
    });
  }
  function deleteItemConfirmOpts(btn) {
    var type = btn.dataset.type || "";
    var kind = btn.dataset.kind || "";
    if (type === "skill") {
      return {
        title: "Remove skill?",
        message: "This skill will be removed from your resume.",
        confirmLabel: "Remove skill",
        cancelLabel: "Keep skill",
      };
    }
    if (type === "education") {
      return {
        title: "Remove education?",
        message: "This school entry will be removed from your resume.",
        confirmLabel: "Remove entry",
        cancelLabel: "Keep entry",
      };
    }
    if (type === "certificate") {
      return {
        title: "Remove certificate?",
        message: "This certificate will be removed from your resume.",
        confirmLabel: "Remove certificate",
        cancelLabel: "Keep certificate",
      };
    }
    if (type === "internship") {
      return {
        title: "Remove experience?",
        message: "This experience entry will be removed from your resume.",
        confirmLabel: "Remove entry",
        cancelLabel: "Keep entry",
      };
    }
    if (type === "activity" && kind === "project") {
      return {
        title: "Remove project?",
        message: "This project will be removed from your resume.",
        confirmLabel: "Remove project",
        cancelLabel: "Keep project",
      };
    }
    if (type === "activity" && kind === "achievement") {
      return {
        title: "Remove achievement?",
        message: "This achievement will be removed from your resume.",
        confirmLabel: "Remove achievement",
        cancelLabel: "Keep achievement",
      };
    }
    if (type === "activity") {
      return {
        title: "Remove entry?",
        message: "This item will be removed from your resume.",
        confirmLabel: "Remove",
        cancelLabel: "Keep",
      };
    }
    return {
      title: "Remove item?",
      message: "This cannot be undone.",
      confirmLabel: "Remove",
      cancelLabel: "Keep",
    };
  }

  function performDeleteItem(btn) {
    if (btn.disabled || btn.classList.contains("is-processing")) return;
    if (btn.dataset.type === "education" && btn.dataset.id) {
      var eduEntry = (payload.education || []).find(function (ed) {
        return String(ed.id) === String(btn.dataset.id);
      });
      if (eduEntry && eduEntry.is_profile_school) {
        var msgs = window.RB2Messages;
        if (msgs) {
          msgs.toast("Your current school is linked to your profile. Edit it instead of removing.", {
            type: "info",
            title: "Cannot remove",
          });
        }
        return;
      }
    }
    var prevHtml = btn.innerHTML;
    btn.disabled = true;
    btn.classList.add("is-processing");
    btn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Removing…";
    if (btn.dataset.type === "activity" && editingProjectId && String(btn.dataset.id) === String(editingProjectId)) {
      resetProjectForm();
    }
    if (btn.dataset.type === "activity" && editingAchieveId && String(btn.dataset.id) === String(editingAchieveId)) {
      resetAchieveForm();
    }
    if (btn.dataset.type === "education" && editingEducationId && String(btn.dataset.id) === String(editingEducationId)) {
      resetEducationForm();
    }
    if (btn.dataset.type === "certificate" && editingCertId && String(btn.dataset.id) === String(editingCertId)) {
      resetCertForm();
    }
    apiPost({
      action: "delete_item",
      item_type: btn.dataset.type,
      item_id: btn.dataset.type === "education" ? btn.dataset.id : parseInt(btn.dataset.id, 10),
    }).then(function (data) {
      onStudioUpdate(data);
      if (btn.dataset.type === "education") reloadPreview(cfg.prototypeKey, true);
    }).catch(function (err) {
      var msg = (err && err.payload && err.payload.error) || "";
      if (msg) {
        var msgs = window.RB2Messages;
        if (msgs) msgs.toast(msg, { type: "warning", title: "Could not remove" });
      }
    }).finally(function () {
      if (btn.isConnected) {
        btn.disabled = false;
        btn.classList.remove("is-processing");
        btn.innerHTML = prevHtml;
      }
    });
  }

  /* ——— Delete items ——— */
  document.addEventListener("click", function (e) {
    var editBtn = e.target.closest(".rb2-item-edit");
    if (editBtn) {
      var kind = editBtn.dataset.kind;
      var itemId = editBtn.dataset.id;
      if (kind === "project") startProjectEdit(itemId);
      else if (kind === "education") startEducationEdit(itemId);
      else if (kind === "certificate") startCertEdit(itemId);
      else if (kind === "achievement") startAchieveEdit(itemId);
      return;
    }
    var btn = e.target.closest(".rb2-item-del");
    if (!btn) return;
    var msgs = window.RB2Messages;
    var confirmOpts = Object.assign({ variant: "danger" }, deleteItemConfirmOpts(btn));
    if (!msgs || typeof msgs.confirm !== "function") {
      performDeleteItem(btn);
      return;
    }
    msgs.confirm(confirmOpts).then(function (ok) {
      if (ok) performDeleteItem(btn);
    });
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

  bindPhotoUpload();
  bindLivePreview();
  populatePassingYearSelect();
  populateEduSchoolSuggestions();
  fillEducationForm(null);
  var eduResultTypeEl = $("#rb2EduResultType");
  if (eduResultTypeEl) {
    eduResultTypeEl.addEventListener("change", function () {
      syncEduResultFields();
      scheduleLocalUiSync();
    });
  }
  var eduPassingYearEl = $("#rb2EduPassingYear");
  if (eduPassingYearEl) {
    eduPassingYearEl.addEventListener("change", function () {
      syncEduStudyingState();
      syncPassingYearSelectOptions();
      scheduleLocalUiSync();
    });
  }
  window.addEventListener("message", function (event) {
    if (event.data && event.data.type === "TT_STUDIO_PREVIEW_UPDATED") {
      resizePreviewFrame();
    }
  });
  renderLists();
  updateMultiAddButtons();
  setActiveSection(activeSection);
  syncAiWriteButtons();
  updateLocalUiFromForms();

  var previewFrame = $("#rb2PreviewFrame");
  if (previewFrame) {
    previewFrame.addEventListener("load", function () {
      pushDraftToPreview();
      resizePreviewFrame();
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
            scheduleLocalUiSync();
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
        var msgs = window.RB2Messages;
        if (!msgs) return;
        msgs
          .confirm({
            title: "Remove resume photo?",
            message: "The photo will be removed from this resume only.",
            confirmLabel: "Remove photo",
            cancelLabel: "Keep photo",
            variant: "danger",
          })
          .then(function (ok) {
            if (!ok) return;
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
                  scheduleLocalUiSync();
                  msgs.toast("Photo removed from this resume.", { type: "info", title: "Photo updated" });
                }
              })
              .finally(function () {
                removeBtn.disabled = false;
              });
          });
      });
    }
  }

  function openResumePdf() {
    var pdfBtn = $("#rb2DownloadPdf");
    var url = (cfg.pdfUrl || (pdfBtn && pdfBtn.getAttribute("href")) || "").trim();
    if (!url) return;
    if (savePending > 0) return;
    setSavingState(true);
    saveAllSections()
      .then(function () {
        window.open(url, "_blank", "noopener");
      })
      .finally(function () {
        setSavingState(false);
      });
  }

  function initStudioSplitter() {
    var body = document.querySelector(".rb2-studio-body");
    var splitter = document.getElementById("rb2StudioSplitter");
    if (!body || !splitter) return;

    var mq = window.matchMedia("(min-width: 1101px)");
    var STORAGE_KEY = "rb2StudioPreviewRatio";
    var STEPS = 220;
    var SPLITTER = 10;
    var MIN_EDITOR = 280;
    var MIN_PREVIEW = 280;
    var dragging = false;

    function getAvailableWidth() {
      return body.getBoundingClientRect().width - STEPS - SPLITTER;
    }

    function clampPreview(width) {
      var available = getAvailableWidth();
      return Math.max(MIN_PREVIEW, Math.min(available - MIN_EDITOR, Math.round(width)));
    }

    function applyPreviewWidth(width) {
      if (!mq.matches) return;
      body.style.setProperty("--rb2-preview-col", clampPreview(width) + "px");
    }

    function applyRatio(ratio) {
      if (!mq.matches || !(ratio > 0 && ratio < 1)) return;
      applyPreviewWidth(getAvailableWidth() * ratio);
    }

    function loadSavedWidth() {
      if (!mq.matches) return;
      var saved = parseFloat(localStorage.getItem(STORAGE_KEY));
      if (!isNaN(saved) && saved > 0 && saved < 1) {
        applyRatio(saved);
        return;
      }
      body.style.removeProperty("--rb2-preview-col");
    }

    function saveCurrentWidth() {
      var previewPane = body.querySelector(".rb2-studio-preview-pane");
      var available = getAvailableWidth();
      if (!previewPane || available <= 0) return;
      var preview = previewPane.getBoundingClientRect().width;
      localStorage.setItem(STORAGE_KEY, String(preview / available));
    }

    function stopDrag(e) {
      if (!dragging) return;
      dragging = false;
      body.classList.remove("is-resizing");
      splitter.classList.remove("is-active");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      if (e && splitter.hasPointerCapture(e.pointerId)) {
        try {
          splitter.releasePointerCapture(e.pointerId);
        } catch (_) {}
      }
      saveCurrentWidth();
    }

    splitter.addEventListener("pointerdown", function (e) {
      if (!mq.matches || e.button !== 0) return;
      dragging = true;
      body.classList.add("is-resizing");
      splitter.classList.add("is-active");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      splitter.setPointerCapture(e.pointerId);
      e.preventDefault();
    });

    splitter.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      var rect = body.getBoundingClientRect();
      applyPreviewWidth(rect.right - e.clientX);
    });

    splitter.addEventListener("pointerup", stopDrag);
    splitter.addEventListener("pointercancel", stopDrag);

    splitter.addEventListener("keydown", function (e) {
      if (!mq.matches) return;
      var step = e.shiftKey ? 48 : 20;
      var previewPane = body.querySelector(".rb2-studio-preview-pane");
      if (!previewPane) return;
      var current = previewPane.getBoundingClientRect().width;
      var next = current;
      if (e.key === "ArrowLeft") next = current + step;
      else if (e.key === "ArrowRight") next = current - step;
      else return;
      e.preventDefault();
      applyPreviewWidth(next);
      saveCurrentWidth();
    });

    splitter.addEventListener("dblclick", function () {
      localStorage.removeItem(STORAGE_KEY);
      body.style.removeProperty("--rb2-preview-col");
    });

    loadSavedWidth();
    window.addEventListener("resize", function () {
      var saved = parseFloat(localStorage.getItem(STORAGE_KEY));
      if (!isNaN(saved) && saved > 0 && saved < 1) applyRatio(saved);
    });
    mq.addEventListener("change", loadSavedWidth);
  }

  initStudioSplitter();

  var pdfBtn = $("#rb2DownloadPdf");
  if (pdfBtn) {
    pdfBtn.addEventListener("click", function (e) {
      e.preventDefault();
      openResumePdf();
    });
  }
})();
