"""Run: python3 -m unittest discover -s tests -v   (needs the skill's Python packages; browser tests skip without Chrome)"""
import functools, http.server, json, os, shutil, sys, tempfile, threading, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import capture, journal, plan  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
SERVER = None


def setUpModule():
    global SERVER
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=FIX)
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    h.keywords["directory"] = FIX
    threading.Thread(target=SERVER.serve_forever, daemon=True).start()


def tearDownModule():
    SERVER.shutdown()


def url(name):
    return f"http://127.0.0.1:{SERVER.server_address[1]}/{name}"


class Pure(unittest.TestCase):
    def test_env(self):
        self.assertEqual(capture.infer_env("http://localhost:3000"), "local")
        self.assertEqual(capture.infer_env("https://hrms-dev.acme.in"), "staging")
        self.assertEqual(capture.infer_env("https://hrms.acme.in"), "production")
        self.assertEqual(capture.infer_env("https://contest.acme.com"), "production")

    def test_samples(self):
        f = {"type": "text", "label": "Code", "placeholder": "e.g. AB-1234", "auto": ""}
        self.assertEqual(capture.sample_for(f), "AB-1234")
        self.assertEqual(capture.sample_for({"type": "email", "label": "", "placeholder": "", "auto": ""}), "sample.user@example.com")
        self.assertTrue(capture.SENSITIVE.search("card number"))
        self.assertFalse(capture.SENSITIVE.search("employee name"))

    def test_steps_must_do_something(self):
        task = {"steps": [{"text": "a", "goto": "/", "marks": [{"target": "#a"}]}, {"text": "b", "marks": [{"target": "#b"}]},
                          {"text": "c", "marks": [{"target": "#c"}]}, {"text": "d", "shot": True}]}
        self.assertTrue(capture.check_steps(task, "staging"))
        self.assertEqual(capture.check_steps(task, "production"), [])

    def test_look_cap(self):
        steps = [{"text": str(i), "look": True, "marks": [{"target": "#x"}]} for i in range(8)]
        self.assertTrue(capture.check_steps({"steps": steps}, "staging"))

    def test_plan_ranks(self):
        items = [{"task": "Punch in (Home)", "page": "Home", "position": 0, "total": 5, "fields": 0},
                 {"task": "Add role (Roles)", "page": "Roles", "position": 4, "total": 5, "fields": 1}]
        r = plan.build(items)
        self.assertEqual(r[0]["task"], "Punch in (Home)")
        r = plan.build(items, {"role": 100, "punch": 1})
        self.assertEqual(r[0]["task"], "Add role (Roles)")

    def test_journal_versions(self):
        ws = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(ws, "modules"))
            json.dump({"app": "A", "order": [], "modules": {}}, open(os.path.join(ws, "state.json"), "w"))
            mp = os.path.join(ws, "modules", "m.json")
            json.dump({"features": [{"title": "T", "steps": [{"text": "one"}]}]}, open(mp, "w"))
            journal.refresh(ws)
            json.dump({"features": [{"title": "T", "steps": [{"text": "two"}]}]}, open(mp, "w"))
            journal.refresh(ws)
            md = open(os.path.join(ws, "docyfy.md")).read()
            self.assertIn("Version 2", md)
            self.assertIn('Changed task "T"', md)
        finally:
            shutil.rmtree(ws)


def browser_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            capture.launch(p).close()
        return True
    except BaseException:
        return False


@unittest.skipUnless(browser_ok(), "no browser")
class Draft(unittest.TestCase):
    def draft(self, page, *extra):
        out = tempfile.mktemp(suffix=".json")
        import argparse
        capture.cmd_draft(argparse.Namespace(url=url(page), title="T", out=out, state=None, pre=None, confirm="", advance="", finish="", env=None, frame=None, **{}))
        return json.load(open(out))["tasks"][0]

    def kinds(self, t):
        return [next((k for k in ("fill", "select", "click", "look") if k in s), "shot") for s in t["steps"]]

    def test_wizard_goes_through_every_section(self):
        t = self.draft("wiz.html")
        k = self.kinds(t)
        self.assertEqual(k.count("select"), 2)
        self.assertIn("Next", " ".join(s["text"] for s in t["steps"]))
        self.assertIn("Save employee", t["steps"][-2]["text"])
        self.assertEqual(capture.check_steps(t, "staging"), [])

    def test_non_english_labels(self):
        t = self.draft("hi.html")
        self.assertGreaterEqual(self.kinds(t).count("fill"), 3)
        self.assertEqual(self.kinds(t)[-2], "click")

    def test_custom_dropdown_shadow_and_card(self):
        t = self.draft("custom.html")
        text = " ".join(s["text"] for s in t["steps"])
        self.assertIn("Choose **HR**", text)
        self.assertIn("City", text)                     # inside a shadow root
        self.assertTrue(any(s.get("look") == "password" for s in t["steps"]))   # card number

    def test_iframe(self):
        t = self.draft("frame.html")
        self.assertTrue(all("enter-frame" in s["fill"][0] for s in t["steps"] if "fill" in s))

    def test_run_custom_form(self):
        t = self.draft("custom.html")
        ws = tempfile.mkdtemp()
        try:
            spec = {"env": "local", "base": url("").rstrip("/"), "viewport": [1440, 900], "tasks": [t]}
            sp = os.path.join(ws, "spec.json")
            json.dump(spec, open(sp, "w"))
            import argparse
            capture.cmd_run(argparse.Namespace(spec=sp, ws=ws, no_video=True, only=None, preview=False))
            mod = json.load(open(os.path.join(ws, "modules", "tasks.json")))
            self.assertEqual(len(mod["features"][0]["steps"]), len(t["steps"]))
        finally:
            shutil.rmtree(ws)


if __name__ == "__main__":
    unittest.main()
