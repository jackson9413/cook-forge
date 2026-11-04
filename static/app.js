/* cook-forge - vanilla JS front end */
(function () {
  "use strict";

  var state = {
    result: null,
    sessionId: null,
    severity: "all",
    axis: "all",
    rating: 0,
    samples: []
  };

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = String(text); }
    return n;
  }

  function clock(mins) {
    if (mins === null || mins === undefined) { return "-"; }
    var m = Math.round(Number(mins));
    var h = Math.floor(m / 60);
    var r = m % 60;
    if (h) { return h + "h" + (r < 10 ? "0" + r : r) + "m"; }
    return m + "m";
  }

  function scoreClass(v) {
    if (v >= 85) { return "ready_to_cook"; }
    if (v >= 70) { return "mostly_ready"; }
    if (v >= 55) { return "needs_tweaks"; }
    if (v >= 40) { return "tight_but_usable"; }
    return "needs_rework";
  }

  function axisTone(score) {
    if (score >= 85) { return "good"; }
    if (score >= 70) { return "ok"; }
    if (score >= 55) { return "warn"; }
    return "bad";
  }

  function q(s) { return el("span", null, s); }

  /* ------------------------------------------------------------------ */
  /* tabs                                                                */
  /* ------------------------------------------------------------------ */
  function wireTabs() {
    var tabs = document.querySelectorAll(".tab");
    Array.prototype.forEach.call(tabs, function (tab) {
      tab.addEventListener("click", function () {
        Array.prototype.forEach.call(tabs, function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
        var panes = document.querySelectorAll(".tabpane");
        Array.prototype.forEach.call(panes, function (p) { p.classList.add("hidden"); });
        var pane = $("tab-" + tab.getAttribute("data-tab"));
        if (pane) { pane.classList.remove("hidden"); }
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* rendering                                                           */
  /* ------------------------------------------------------------------ */
  function render(res) {
    state.result = res;
    state.sessionId = res.session_id || null;
    state.rating = 0;
    setStars(0);

    $("emptyState").classList.add("hidden");
    $("results").classList.remove("hidden");

    $("scoreValue").textContent = Math.round(res.score);
    var vd = $("verdict");
    vd.textContent = res.verdict_label;
    vd.className = "verdict v-" + scoreClass(res.score);
    $("summary").textContent = res.summary || "";

    var comp = res.computed || {};
    var stats = $("statRow");
    stats.innerHTML = "";
    var statData = [
      ["End to end", clock(comp.total_minutes)],
      ["Hands-on", clock(comp.hands_on_minutes)],
      ["Recipe claims", res.claimed_minutes ? clock(res.claimed_minutes) : "none"],
      ["Steps", comp.steps],
      ["Serves", res.servings ? res.servings : (res.yield_text || "not stated")]
    ];
    statData.forEach(function (pair) {
      var box = el("div", "stat");
      box.appendChild(el("b", null, pair[1]));
      box.appendChild(el("span", null, pair[0]));
      stats.appendChild(box);
    });

    var pills = $("axisPills");
    pills.innerHTML = "";
    (res.axes || []).forEach(function (a) {
      var p = el("div", "axis-pill " + axisTone(a.score));
      p.appendChild(el("div", "an", a.axis));
      p.appendChild(el("div", "av", Math.round(a.score)));
      p.appendChild(el("div", "aw", "weight " + Math.round(a.weight * 100) + "%"));
      pills.appendChild(p);
    });

    var caps = $("capNote");
    if (res.caps && res.caps.length) {
      caps.textContent = "Score caps applied: " + res.caps.join(" ");
      caps.classList.remove("hidden");
    } else {
      caps.classList.add("hidden");
    }

    renderTimeline(res);
    renderFindings(res);
    renderFixPlan(res);
    renderIngredients(res);
    renderKit(res);
    renderStrengths(res);

    $("findingCount").textContent = (res.findings || []).length;
    $("sessionTag").textContent = state.sessionId ? ("saved as #" + state.sessionId) : "not saved";
    if (state.sessionId) {
      $("exportMd").href = "/api/export/" + state.sessionId + "?fmt=md";
      $("exportJson").href = "/api/export/" + state.sessionId + "?fmt=json";
    } else {
      $("exportMd").href = "#";
      $("exportJson").href = "#";
    }
    loadHistory();
  }

  function renderTimeline(res) {
    var box = $("timelineList");
    box.innerHTML = "";
    (res.timeline || []).forEach(function (row) {
      var r = el("div", "tl-row");
      r.appendChild(el("div", "tl-time", clock(row.start) + " -> " + clock(row.end)));
      var st = el("div", "tl-station " + row.station, row.station);
      r.appendChild(st);
      var t = el("div", "tl-text");
      t.appendChild(el("span", null, row.text));
      var notes = [];
      if (row.passive) { notes.push("unattended"); }
      if (row.estimated) { notes.push("no time given - estimated 2 min"); }
      if (row.indefinite) { notes.push("no clock time"); }
      if (row.oven_temp_f) { notes.push(row.oven_temp_f + "F"); }
      if (row.oven_temp_c) { notes.push(row.oven_temp_c + "C"); }
      if (notes.length) { t.appendChild(el("span", "tl-note", notes.join(" | "))); }
      r.appendChild(t);
      box.appendChild(r);
    });
    if (!(res.timeline || []).length) {
      box.appendChild(el("p", "tl-text", "No steps to schedule."));
    }

    var ma = $("makeAheadBox");
    ma.innerHTML = "";
    if ((res.make_ahead || []).length) {
      ma.appendChild(el("h3", null, "Make ahead"));
      (res.make_ahead || []).forEach(function (m) {
        ma.appendChild(el("div", "strength", "Step " + m.step + " (" + m.when + "): " + m.text));
      });
    }
  }

  function renderFindings(res) {
    var box = $("findingList");
    box.innerHTML = "";
    var list = (res.findings || []).filter(function (f) {
      if (state.severity !== "all" && f.severity !== state.severity) { return false; }
      if (state.axis !== "all" && f.axis !== state.axis) { return false; }
      return true;
    });
    if (!list.length) {
      box.appendChild(el("p", "tl-text", "Nothing matches this filter. That is good news."));
      return;
    }
    list.forEach(function (f) {
      var card = el("div", "finding " + f.severity);
      var head = el("div", "f-head");
      head.appendChild(el("span", "sev " + f.severity, f.severity));
      head.appendChild(el("span", "axis-tag", f.axis));
      card.appendChild(head);
      card.appendChild(el("div", "f-title", f.title));
      if (f.evidence) { card.appendChild(el("div", "f-evidence", f.evidence)); }
      card.appendChild(el("div", "f-why", f.why));
      var fix = el("div", "f-fix");
      fix.appendChild(el("b", null, "Fix: "));
      fix.appendChild(el("span", null, f.fix));
      card.appendChild(fix);
      box.appendChild(card);
    });
  }

  function renderFixPlan(res) {
    var box = $("fixPlan");
    box.innerHTML = "";
    var plan = res.fix_plan || [];
    if (!plan.length) {
      box.appendChild(el("div", "strength", "Nothing to fix. Cook it as written."));
      return;
    }
    plan.forEach(function (f, i) {
      var row = el("div", "fix-item");
      row.appendChild(el("div", "fix-num", i + 1));
      var mid = el("div");
      var head = el("div", "f-head");
      head.appendChild(el("span", "sev " + f.severity, f.severity));
      head.appendChild(el("span", "axis-tag", f.axis));
      mid.appendChild(head);
      mid.appendChild(el("div", "f-title", f.title));
      mid.appendChild(el("div", "f-why", f.fix));
      row.appendChild(mid);
      row.appendChild(el("div", "fix-gain", "+~" + f.gain + " pts"));
      box.appendChild(row);
    });
  }

  function renderIngredients(res) {
    var box = $("scaleBox");
    box.innerHTML = "";
    var scale = res.scale || {};
    if (scale.note) {
      box.appendChild(el("div", "scale-note", scale.note));
    }
    (scale.warnings || []).forEach(function (w) {
      box.appendChild(el("div", "scale-note", w));
    });
    if (scale.ingredients && scale.ingredients.length) {
      var head = el("h3", null, "Scaled for " + scale.target + " servings (x" + scale.factor + ")");
      box.appendChild(head);
    }

    var list = $("ingredientList");
    list.innerHTML = "";
    var rows = (scale.ingredients && scale.ingredients.length) ? scale.ingredients : (res.ingredients || []);
    rows.forEach(function (i) {
      var card = el("div", "ing");
      var label = (scale.ingredients && scale.ingredients.length) ? i.scaled : i.raw;
      card.appendChild(el("span", "qty", label));
      if (i.prep) { card.appendChild(el("span", null, " - " + i.prep)); }
      list.appendChild(card);
    });
  }

  function renderKit(res) {
    var box = $("kitBox");
    box.innerHTML = "";
    var missing = res.equipment_missing || [];
    var needed = res.equipment_needed || [];
    if (!needed.length) {
      box.appendChild(el("div", "kit-item", "No special equipment called for by this recipe."));
    }
    missing.forEach(function (m) {
      var card = el("div", "kit-item missing");
      card.appendChild(el("b", null, "Missing: " + m.tool));
      card.appendChild(el("p", null, m.workaround));
      box.appendChild(card);
    });
    var have = needed.filter(function (n) {
      for (var i = 0; i < missing.length; i++) {
        if (missing[i].tool === n.tool) { return false; }
      }
      return true;
    });
    have.forEach(function (n) {
      var card = el("div", "kit-item");
      card.appendChild(el("b", null, "On your kit: " + n.tool));
      box.appendChild(card);
    });
  }

  function renderStrengths(res) {
    var box = $("strengthList");
    box.innerHTML = "";
    var list = res.strengths || [];
    if (!list.length) {
      box.appendChild(el("div", "strength", "Nothing stood out as a strength - check the findings tab."));
      return;
    }
    list.forEach(function (s) { box.appendChild(el("div", "strength", s)); });
  }

  /* ------------------------------------------------------------------ */
  /* actions                                                             */
  /* ------------------------------------------------------------------ */
  function setStars(n) {
    state.rating = n;
    var buttons = document.querySelectorAll("#stars button");
    Array.prototype.forEach.call(buttons, function (b, i) {
      b.classList.toggle("on", i < n);
    });
  }

  function analyze() {
    var text = $("recipe").value.trim();
    if (!text) {
      $("status").textContent = "Paste a recipe first.";
      return;
    }
    $("analyzeBtn").disabled = true;
    $("status").textContent = "analysing...";
    var body = {
      recipe: text,
      gear: $("gear").value.trim(),
      intent: $("intent").value,
      target_servings: $("targetServings").value || null,
      time_available: $("timeAvailable").value || null
    };
    fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(function (data) {
      $("analyzeBtn").disabled = false;
      if (data.error) {
        $("status").textContent = data.error;
        return;
      }
      $("status").textContent = "done - " + (data.findings || []).length + " findings";
      render(data);
    }).catch(function (err) {
      $("analyzeBtn").disabled = false;
      $("status").textContent = "error: " + err;
    });
  }

  function loadSamples() {
    return fetch("/api/samples").then(function (r) { return r.json(); }).then(function (list) {
      state.samples = list;
      var sel = $("sampleSelect");
      list.forEach(function (s) {
        var o = document.createElement("option");
        o.value = s.id;
        o.textContent = s.name;
        sel.appendChild(o);
      });
      sel.addEventListener("change", function () {
        if (!sel.value) { return; }
        fetch("/api/sample?id=" + encodeURIComponent(sel.value)).then(function (r) { return r.json(); })
          .then(function (s) {
            $("recipe").value = s.text;
            $("status").textContent = "sample loaded - press Analyse";
            sel.value = "";
          });
      });
    });
  }

  function loadHistory() {
    return fetch("/api/sessions?limit=25").then(function (r) { return r.json(); }).then(function (rows) {
      var box = $("history");
      box.innerHTML = "";
      if (!rows.length) {
        box.appendChild(el("p", "tl-text", "No runs saved yet."));
        return;
      }
      rows.forEach(function (row) {
        var r = el("div", "hist-row");
        r.appendChild(el("div", "hist-score", Math.round(row.score) + "/100"));
        var mid = el("div");
        mid.appendChild(el("div", null, row.title));
        var vr = el("div", "hist-verdict " + scoreClass(row.verdict), (row.verdict || "").replace(/_/g, " "));
        mid.appendChild(vr);
        r.appendChild(mid);
        r.appendChild(el("div", "hist-date", (row.created_at || "").replace("T", " ")));
        r.appendChild(el("div", "hist-notes", row.notes || ""));
        var stars = el("div", "stars-mini", row.rating ? new Array(row.rating + 1).join("*") : "");
        r.appendChild(stars);
        r.addEventListener("click", function () { openSession(row.id); });
        box.appendChild(r);
      });
    });
  }

  function openSession(id) {
    fetch("/api/sessions/" + id).then(function (r) { return r.json(); }).then(function (row) {
      if (!row.result) { return; }
      render(row.result);
      $("recipe").value = row.recipe || "";
      $("status").textContent = "reopened session #" + id;
    });
  }

  function saveFeedback() {
    if (!state.sessionId) { return; }
    var notes = $("notes").value;
    fetch("/api/sessions/" + state.sessionId, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating: state.rating || null, notes: notes })
    }).then(function () { loadHistory(); });
  }

  /* ------------------------------------------------------------------ */
  /* init                                                                */
  /* ------------------------------------------------------------------ */
  function init() {
    wireTabs();
    $("analyzeBtn").addEventListener("click", analyze);
    $("clearBtn").addEventListener("click", function () {
      $("recipe").value = "";
      $("status").textContent = "cleared";
    });
    $("refreshHistory").addEventListener("click", loadHistory);

    var chips = document.querySelectorAll(".chip");
    Array.prototype.forEach.call(chips, function (chip) {
      chip.addEventListener("click", function () {
        Array.prototype.forEach.call(chips, function (c) { c.classList.remove("active"); });
        chip.classList.add("active");
        state.severity = chip.getAttribute("data-sev");
        if (state.result) { renderFindings(state.result); }
      });
    });
    $("axisFilter").addEventListener("change", function () {
      state.axis = $("axisFilter").value;
      if (state.result) { renderFindings(state.result); }
    });

    var starButtons = document.querySelectorAll("#stars button");
    Array.prototype.forEach.call(starButtons, function (b) {
      b.addEventListener("click", function () {
        setStars(parseInt(b.getAttribute("data-star"), 10));
        saveFeedback();
      });
    });
    $("notes").addEventListener("change", saveFeedback);

    fetch("/api/health").then(function (r) { return r.json(); }).then(function (h) {
      var pill = $("health");
      pill.textContent = "engine ready";
      pill.className = "pill pill-ok";
    }).catch(function () {
      $("health").textContent = "offline";
    });

    loadSamples();
    loadHistory();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
