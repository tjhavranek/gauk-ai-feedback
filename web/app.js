/* gauk-ai-feedback: the web page.
 *
 * Everything runs in the student's browser. The prompts come from data.js,
 * which tools/build.py generates from rules/ and src/, so the page cannot
 * drift from the chatbot prompts. The formal check runs the unchanged
 * checker/gauk_check.py in a Web Worker under Pyodide; the files never leave
 * the browser. Nothing is stored except the chosen language.
 */
(function () {
  "use strict";

  var D = window.GAUK;
  var S = D.strings;
  var SLOTS = [
    ["proposal", "navrh_projektu"],
    ["cv_pi", "cv_resitel"],
    ["cv_supervisor", "cv_vedouci"],
    ["references", "literatura"],
    ["ethics", "eticka_komise"]
  ];
  var lang = pickLang();
  var plang = lang;
  var plangTouched = false;
  var files = {};
  var shown = {};
  var report = null;
  var worker = null;
  var busy = false;
  var expired = today() >= D.meta.sunset;

  function $(id) { return document.getElementById(id); }

  function today() { return new Date().toISOString().slice(0, 10); }

  function pickLang() {
    var q = new URLSearchParams(location.search).get("lang");
    if (q === "cs" || q === "en") return q;
    try {
      var saved = localStorage.getItem("gauk-lang");
      if (saved === "cs" || saved === "en") return saved;
    } catch (e) { /* storage blocked: fall through */ }
    var nav = (navigator.language || "cs").toLowerCase();
    return (nav.indexOf("cs") === 0 || nav.indexOf("sk") === 0) ? "cs" : "en";
  }

  function t(key, vars) {
    var s = (S[lang] && S[lang][key] !== undefined) ? S[lang][key] : (S.cs[key] || "");
    if (vars) Object.keys(vars).forEach(function (k) { s = s.split("{" + k + "}").join(vars[k]); });
    return s;
  }

  function fmtDate(iso) {
    var p = iso.split("-");
    if (lang === "cs") return (+p[2]) + ". " + (+p[1]) + ". " + p[0];
    var months = ["January", "February", "March", "April", "May", "June", "July",
      "August", "September", "October", "November", "December"];
    return (+p[2]) + " " + months[+p[1] - 1] + " " + p[0];
  }

  // ---------------------------------------------------------------- language

  function applyLang() {
    document.documentElement.lang = lang;
    document.title = t("title");
    document.querySelectorAll("[data-t]").forEach(function (el) { el.textContent = t(el.dataset.t); });
    document.querySelectorAll("[data-t-html]").forEach(function (el) { el.innerHTML = t(el.dataset.tHtml); });
    document.querySelector('[data-t="res_en_note"]').hidden = !t("res_en_note");
    $("prompt-text").setAttribute("aria-label", t("prompt_label"));
    document.querySelectorAll("[data-lang]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.lang === lang));
    });
    if (!plangTouched) setPlang(lang);
    $("rules-line").textContent = t("rules_line", {
      round: D.meta.round, verified: fmtDate(D.meta.verified), sunset: fmtDate(D.meta.sunset)
    });
    // The two running-project lists come from the rules, like the reminders,
    // so the page cannot drift from rules/round24.yml.
    // An object, not an array of two strings: build.py reads a literal of that
    // shape as the name of a file slot and then asks for a string that does
    // not exist.
    var RUNNING = { cont: "continuation", final: "final" };
    Object.keys(RUNNING).forEach(function (part) {
      var blk = D.running[RUNNING[part]];
      $("running-" + part + "-deadline").textContent = blk.deadline[lang];
      fill($("running-" + part), blk.items[lang], function (s) { return s; });
    });
    var ex = $("expired");
    ex.hidden = !expired;
    if (expired) ex.textContent = t("expired_msg", { sunset: fmtDate(D.meta.sunset) });
    renderSlots();
    if (report) renderReport();
  }

  function setLang(l) {
    lang = l;
    try { localStorage.setItem("gauk-lang", l); } catch (e) { /* ignore */ }
    var url = new URL(location.href);
    if (l === "en") url.searchParams.set("lang", "en"); else url.searchParams.delete("lang");
    history.replaceState(null, "", url);
    applyLang();
  }

  // ---------------------------------------------------------------- panels

  function openPanel(name, scroll) {
    document.querySelectorAll(".choice").forEach(function (b) {
      var on = b.dataset.panel === name;
      b.setAttribute("aria-expanded", String(on));
      $("panel-" + b.dataset.panel).hidden = !on;
    });
    if (scroll) $("panel-" + name).scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------------------------------------------------------------- clipboard

  // Some browsers refuse the modern clipboard (older ones, embedded ones,
  // locked-down work machines). Try the older copy command before asking the
  // student to copy by hand.
  function legacyCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "0";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  function copy(text, statusEl, okMsg, onFail) {
    function fallback() {
      if (legacyCopy(text)) { statusEl.textContent = okMsg; return; }
      statusEl.textContent = t("copy_failed");
      if (onFail) onFail();
    }
    if (!navigator.clipboard || !window.isSecureContext) { fallback(); return; }
    navigator.clipboard.writeText(text).then(function () {
      statusEl.textContent = okMsg;
    }, fallback);
  }

  // ---------------------------------------------------------------- 1. chatbot

  function setPlang(l) {
    plang = l;
    document.querySelectorAll("[data-plang]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.plang === l));
    });
    $("prompt-text").value = D.prompt[l];
    var dl = $("dl-prompt");
    dl.href = D.promptFile[l];
    dl.setAttribute("download", l === "cs" ? "gauk_zadani_cs.txt" : "gauk_prompt_en.txt");
    $("copy-status").textContent = "";
  }

  function updateConsent() {
    var ok = $("consent").checked && !expired;
    $("copy-prompt").disabled = !ok;
    $("dl-prompt").hidden = !ok;
    $("fallback").hidden = !ok;
    $("consent-hint").hidden = $("consent").checked;
  }

  // ---------------------------------------------------------------- 2. files

  function renderSlots() {
    var ul = $("slots");
    ul.textContent = "";
    SLOTS.forEach(function (s) {
      var key = s[0];
      var f = files[key];
      var li = document.createElement("li");
      li.className = "slot";

      var name = document.createElement("span");
      name.className = "slot-name";
      name.id = "slot-" + key;
      name.textContent = t("slot_" + key);

      var file = document.createElement("span");
      file.className = "slot-file" + (f ? " has" : "");
      file.textContent = f ? f.name + " (" + kb(f.size) + ")" : t("not_selected");

      var input = document.createElement("input");
      input.type = "file";
      input.accept = ".pdf,.docx,application/pdf";
      input.tabIndex = -1;
      input.setAttribute("aria-hidden", "true");
      input.addEventListener("change", function () {
        if (input.files[0]) setFile(key, input.files[0]);
      });

      var pick = document.createElement("button");
      pick.type = "button";
      pick.className = "btn btn-ghost";
      pick.textContent = f ? t("replace_file") : t("choose_file");
      pick.setAttribute("aria-describedby", "slot-" + key);
      pick.addEventListener("click", function () { input.click(); });

      li.appendChild(name);
      li.appendChild(file);
      li.appendChild(input);
      li.appendChild(pick);
      if (f) {
        var rm = document.createElement("button");
        rm.type = "button";
        rm.className = "linkish";
        rm.textContent = t("remove");
        rm.addEventListener("click", function () { delete files[key]; renderSlots(); });
        li.appendChild(rm);
      }

      li.addEventListener("dragover", function (e) { e.preventDefault(); li.classList.add("over"); });
      li.addEventListener("dragleave", function () { li.classList.remove("over"); });
      li.addEventListener("drop", function (e) {
        e.preventDefault();
        li.classList.remove("over");
        if (e.dataTransfer.files[0]) setFile(key, e.dataTransfer.files[0]);
      });
      ul.appendChild(li);
    });
  }

  function setFile(key, file) {
    if (!/\.(pdf|docx)$/i.test(file.name)) { $("check-error").textContent = t("bad_type"); return; }
    $("check-error").textContent = "";
    files[key] = file;
    renderSlots();
  }

  function kb(n) { return n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " kB"; }

  function formData() {
    var map = {
      form_language: "f-form-language", duration_years: "f-duration",
      budget_total_year1: "f-total", budget_wages: "f-wages", budget_stipends: "f-stipends",
      budget_justification: "f-just", budget_table: "f-table",
      ai_used: "f-ai-used", ai_description: "f-ai-desc",
      other_projects: "f-other"
    };
    var out = {};
    Object.keys(map).forEach(function (k) {
      var v = $(map[k]).value.trim();
      if (v) out[k] = v;
    });
    return out;
  }

  function getWorker() {
    if (!worker) {
      worker = new Worker("worker.js", { type: "module" });
      worker.onmessage = onWorker;
      worker.onerror = function (e) { finish(); showError(e.message || "worker"); worker = null; };
    }
    return worker;
  }

  function run() {
    if (busy || expired) return;
    var chosen = SLOTS.filter(function (s) { return files[s[0]]; });
    if (!chosen.length) { $("progress").textContent = t("need_files"); return; }
    busy = true;
    $("run").disabled = true;
    $("check-error").textContent = "";
    $("progress").textContent = t("load_runtime");
    shown = {};
    Promise.all(chosen.map(function (s) {
      var f = files[s[0]];
      var ext = (f.name.match(/\.(pdf|docx)$/i) || [".pdf"])[0].toLowerCase();
      shown[s[1] + ext] = f.name;
      return f.arrayBuffer().then(function (buf) { return { name: s[1] + ext, buf: buf }; });
    })).then(function (items) {
      getWorker().postMessage({ type: "run", config: D.pyodide, files: items, form: formData() },
        items.map(function (i) { return i.buf; }));
    }, function (err) { finish(); showError(String(err)); });
  }

  function onWorker(e) {
    var m = e.data;
    if (m.type === "progress") {
      $("progress").textContent = t(m.stage === "checking" ? "checking" : "load_runtime");
    } else if (m.type === "result") {
      finish();
      report = JSON.parse(m.report);
      // not shown; lets anyone confirm in the console where the worker downloaded from
      document.documentElement.dataset.workerHosts = (m.hosts || []).join(" ");
      $("progress").textContent = t("done");
      renderReport();
      $("results").hidden = false;
      $("res-h").focus();
    } else if (m.type === "error") {
      finish();
      showError(m.message);
    }
  }

  function finish() { busy = false; $("run").disabled = expired; }

  function showError(msg) {
    $("progress").textContent = "";
    $("check-error").textContent = t("check_failed", { err: msg });
  }

  // The checker names the files after their slot (navrh_projektu.pdf); show
  // the student's own file names instead.
  function disp(s) {
    Object.keys(shown).forEach(function (k) { s = s.split(k).join(shown[k]); });
    return s;
  }

  // The fixed NOT CHECKED lines, and the ones this page produces, in Czech.
  // A line with no translation stays in English and is marked as such.
  function ncText(s) {
    if (lang !== "cs") return s;
    var map = S.cs.nc || {};
    if (map[s]) return map[s];
    var m = s.match(/^length of the form field '(.+)': read it off the character counter in the application$/);
    if (m) return t("nc_field", { name: D.fieldNames[m[1]] || m[1] });
    m = s.match(/^(.+) \(no file chosen\)$/);
    if (m) return t("nc_nofile", { name: D.attachNames[m[1]] || m[1] });
    m = s.match(/^the text of (.+), page\(s\) \[(.+)\]: there is no text layer/);
    if (m) return t("nc_textlayer", { file: m[1], pages: m[2] });
    return null;
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function ruleLabel(code) {
    if (code.indexOf("R10_") === 0) return t("rule_R10");
    return t("rule_" + code) || code;
  }

  function renderReport() {
    var r = report;
    var chips = $("chips");
    chips.textContent = "";
    [["BLOCKING", "chip-b"], ["ADVISORY", "chip-a"], ["UNKNOWN", "chip-u"]].forEach(function (k) {
      var n = r.counts[k[0]];
      if (n) chips.appendChild(el("span", "chip " + k[1], t("k_" + k[0]) + ": " + n));
    });

    var box = $("findings");
    box.textContent = "";
    if (!r.findings.length) box.appendChild(el("p", "aside", t("no_findings")));
    var order = { BLOCKING: 0, ADVISORY: 1, UNKNOWN: 2 };
    r.findings.slice().sort(function (a, b) { return order[a.kind] - order[b.kind]; }).forEach(function (f) {
      var card = el("div", "finding k-" + f.kind);
      var h = el("h4", null, ruleLabel(f.rule));
      h.appendChild(el("span", "kind", t("k_" + f.kind) + " · " + f.rule));
      card.appendChild(h);
      var dl = el("dl");
      [["d_measured", disp(f.where + ": " + f.measured)], ["d_expected", f.expected],
       ["d_confirm", f.confirm], ["d_source", f.source]].forEach(function (row) {
        dl.appendChild(el("dt", null, t(row[0])));
        var dd = el("dd", null, row[1]);
        if (row[0] !== "d_source") dd.lang = "en";
        dl.appendChild(dd);
      });
      card.appendChild(dl);
      box.appendChild(card);
    });

    fill($("notchecked"), r.not_checked.map(disp), ncText);
    fill($("measured"), r.measured.map(disp), function () { return null; });
    fill($("reminders"), D.reminders[lang], function (s) { return s; });
    var dl2 = $("dl-result");
    if (dl2.dataset.url) URL.revokeObjectURL(dl2.dataset.url);
    dl2.dataset.url = URL.createObjectURL(new Blob([disp(r.block) + "\n"],
      { type: "text/plain;charset=utf-8" }));
    dl2.href = dl2.dataset.url;
  }

  function fill(ul, items, translate) {
    ul.textContent = "";
    items.forEach(function (s) {
      var cs = translate(s);
      var li = el("li", null, cs || s);
      if (!cs && lang === "cs") li.lang = "en";
      ul.appendChild(li);
    });
  }

  function clearAll() {
    files = {};
    report = null;
    ["f-form-language", "f-duration", "f-total", "f-wages", "f-stipends", "f-just",
     "f-table", "f-ai-used", "f-ai-desc", "f-other"].forEach(function (id) { $(id).value = ""; });
    $("ai-desc-field").hidden = true;
    $("results").hidden = true;
    $("progress").textContent = "";
    $("check-error").textContent = "";
    shown = {};
    $("result-status").textContent = "";
    renderSlots();
  }

  // ---------------------------------------------------------------- wiring

  function init() {
    document.querySelectorAll("[data-lang]").forEach(function (b) {
      b.addEventListener("click", function () { setLang(b.dataset.lang); });
    });
    document.querySelectorAll(".choice").forEach(function (b) {
      b.addEventListener("click", function () { openPanel(b.dataset.panel, true); });
    });
    document.querySelectorAll("[data-plang]").forEach(function (b) {
      b.addEventListener("click", function () { plangTouched = true; setPlang(b.dataset.plang); });
    });
    $("consent").addEventListener("change", updateConsent);
    $("copy-prompt").addEventListener("click", function () {
      var text = D.prompt[plang];
      copy(text, $("copy-status"), t("copied", { n: text.length.toLocaleString(lang === "cs" ? "cs-CZ" : "en-GB") }),
        function () { $("fallback").open = true; $("prompt-text").select(); });
    });
    $("goto-check").addEventListener("click", function () { openPanel("check", true); });
    $("copy-selfreport").addEventListener("click", function () {
      copy(D.selfReport[plang], $("selfreport-status"), t("selfreport_copied"));
    });
    $("f-ai-used").addEventListener("change", function () {
      $("ai-desc-field").hidden = $("f-ai-used").value !== "yes";
    });
    $("run").addEventListener("click", run);
    $("clear").addEventListener("click", clearAll);
    $("copy-result").addEventListener("click", function () {
      if (report) copy(disp(report.block), $("result-status"), t("result_copied"));
    });
    // a file dropped outside a slot must not make the browser open it
    window.addEventListener("dragover", function (e) { e.preventDefault(); });
    window.addEventListener("drop", function (e) { e.preventDefault(); });

    applyLang();
    updateConsent();
    $("run").disabled = expired;
    var hash = location.hash.replace("#", "");
    openPanel(hash === "check" || hash === "agent" ? hash : "chat", false);
  }

  init();
})();
