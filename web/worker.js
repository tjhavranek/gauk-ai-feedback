/* gauk-ai-feedback: the formal check, in a module Web Worker.
 *
 * Loads Pyodide and pypdf from this site (tools/build.py puts them there),
 * lays out checker/ and rules/ in Pyodide's in-memory file system as in the
 * repository, writes the student's files next to them, and runs the unchanged
 * checker/gauk_check.py. The files exist only in this worker's memory and are
 * never sent anywhere.
 */
import { loadPyodide } from "./pyodide/pyodide.mjs";

var ready = null;

var RUN = [
  "import dataclasses, json, yaml",
  "from pathlib import Path",
  "import gauk_check as gc",
  "app = Path('/work/your_application')",
  "form = json.loads(FORM_JSON)",
  "index, criteria, rnd = gc.load_rules()",
  "form_path = None",
  "if form:",
  "    form_path = app / 'form.yml'",
  "    form_path.write_text(yaml.safe_dump(form, allow_unicode=True), encoding='utf-8')",
  "rep = gc.check_one(app, form_path, None, index, criteria, rnd)",
  "# The checker speaks of form.yml and its field names; on this page the",
  "# student filled in boxes, so say it in their terms. Only wording changes.",
  "WEB = [",
  "    (' (not in the form file)', ': read it off the character counter in the application'),",
  "    ('(pdfplumber not installed)', '(not measured on this page; check the style in your document)'),",
  "    ('the form file carries only the first-year totals', 'this page asks only for the first-year totals'),",
  "    ('duration_years is not in the form file', 'the duration was not entered'),",
  "    ('form_language is not in the form file', 'the version of the form was not entered'),",
  "    ('no readable budget_total_year1 in the form file', 'no first-year total entered'),",
  "    ('no readable budget_wages and budget_stipends', 'wages and stipends not entered'),",
  "    ('no budget justification in the form file', 'no budget justification entered'),",
  "    ('no table amounts in the form file', 'no table amounts entered'),",
  "    ('budget_total_year1 = ', 'total = '), ('budget_wages = ', 'wages = '),",
  "    ('budget_stipends = ', 'stipends = '),",
  "    ('the form file', 'this page'), ('in the form file', 'on this page'),",
  "]",
  "def web(s):",
  "    if 'templates/form.yml' in s:",
  "        return 'every rule about the web-form fields: none were entered on this page'",
  "    for a, b in WEB:",
  "        s = s.replace(a, b)",
  "    return s",
  "rep.not_checked = [web(s) for s in rep.not_checked]",
  "# An attachment the student did not choose is not a finding on this page;",
  "# it goes to the list of what was not checked.",
  "kept = []",
  "for f in rep.findings:",
  "    f.measured = web(f.measured)",
  "    if f.rule == 'R01_ATTACHMENT_SET' and f.measured.startswith('no file whose name'):",
  "        name = f.expected.split(\"'\")[1] if \"'\" in f.expected else f.expected",
  "        rep.not_checked.insert(0, name + ' (no file chosen)')",
  "    else:",
  "        kept.append(f)",
  "rep.findings = kept",
  "payload = dataclasses.asdict(rep)",
  "payload['counts'] = rep.counts()",
  "payload['not_checked'] = rep.not_checked + gc.NOT_CHECKED_ALWAYS",
  "payload['block'] = gc.render_block(rep)",
  "json.dumps(payload, ensure_ascii=False)"
].join("\n");

function abs(u) { return new URL(u, self.location.href).href; }

function load(config) {
  if (ready) return ready;
  ready = (async function () {
    var py = await loadPyodide({ indexURL: abs(config.index) });
    await py.loadPackage(config.packages.concat(config.wheels.map(abs)));
    for (var i = 0; i < config.files.length; i++) {
      var f = config.files[i];
      var resp = await fetch(abs(f.url));
      if (!resp.ok) throw new Error("missing " + f.url);
      var buf = new Uint8Array(await resp.arrayBuffer());
      py.FS.mkdirTree(f.path.substring(0, f.path.lastIndexOf("/")));
      py.FS.writeFile(f.path, buf);
    }
    py.runPython("import sys\nsys.path.insert(0, '/work/checker')\nimport gauk_check");
    return py;
  })();
  ready.catch(function () { ready = null; });
  return ready;
}

self.onmessage = async function (e) {
  var m = e.data;
  if (m.type !== "run") return;
  try {
    self.postMessage({ type: "progress", stage: "runtime" });
    var py = await load(m.config);
    self.postMessage({ type: "progress", stage: "checking" });
    py.runPython([
      "import shutil, pathlib",
      "d = pathlib.Path('/work/your_application')",
      "shutil.rmtree(d, ignore_errors=True)",
      "d.mkdir(parents=True)"
    ].join("\n"));
    m.files.forEach(function (f) {
      py.FS.writeFile("/work/your_application/" + f.name, new Uint8Array(f.buf));
    });
    py.globals.set("FORM_JSON", JSON.stringify(m.form || {}));
    var out = py.runPython(RUN);
    self.postMessage({ type: "result", report: out });
  } catch (err) {
    self.postMessage({ type: "error", message: String((err && err.message) || err).slice(0, 300) });
  }
};
