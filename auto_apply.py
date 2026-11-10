import json
import random
import re
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

# ===================== SETTINGS: edit these =====================
KEYWORDS = [".NET Angular Developer", "Full Stack Developer .NET"]
POSTED_WITHIN = "r604800"       # r86400 = 24h, r604800 = 1 week
PAGES_PER_KEYWORD = 2           # each page = about 25 jobs
MAX_PER_RUN = 20               # stop after this many applications (keep it low)
DRY_RUN = True                  # True = never submits. Set False only after a good dry run.

RESUME_PDF = "resume/Pugazh_M_Resume.pdf"   # used to match jobs to your skills (optional)
MIN_SKILL_MATCHES = 3              # job must mention at least this many of your resume skills
TITLE_MUST_HAVE = ["developer", "engineer", "lead", ".net", "dot net", "dotnet", "full stack",
                   "fullstack", "architect", "angular"]
TITLE_MUST_NOT_HAVE = ["intern", "trainee", "java ", "php", "sales", "tester", "qa "]

# Answers to screening questions. Use TRUE information only.
# A question that is not matched here makes the script SKIP that job (it never guesses).
ANSWERS = {
    "notice period": "30",
    "authorized": "Yes",
    "sponsorship": "No",
    "relocate": "Yes",
    "city": "Bengaluru",
    # "years of experience": "",
    # "expected ctc": "",
    # "current ctc": "",
}
# ================================================================

DB_FILE = Path("applied.json")
db = json.loads(DB_FILE.read_text()) if DB_FILE.exists() else {}

SKILLS = ["angular", "typescript", "javascript", "rxjs", "c#", ".net", "asp.net", "web api",
          "entity framework", "linq", "microservices", "azure", "sql", "docker", "kubernetes",
          "rest", "rag", "openai", "python", "git", "html", "css", "react", "node"]


def resume_skills():
    path = Path(RESUME_PDF)
    if not path.exists():
        print("No resume found, skill matching is OFF.")
        return []
    from pypdf import PdfReader
    text = " ".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages).lower()
    found = [s for s in SKILLS if s in text]
    print("Resume skills:", ", ".join(found))
    return found


def save(job_id, status, title, reason=""):
    db[job_id] = {"status": status, "title": title, "reason": reason}
    DB_FILE.write_text(json.dumps(db, indent=2))
    print(f"  [{status}] {title} {('- ' + reason) if reason else ''}")


def pause(a=1.0, b=2.5):
    import time
    time.sleep(random.uniform(a, b))


def answer_for(label):
    l = label.lower()
    for key, val in ANSWERS.items():
        if key in l and val != "":
            return val
    return None


LABEL_JS = """e => {
  const f = e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`);
  return ((f && f.innerText) || e.getAttribute('aria-label') || '').trim();
}"""


def fill_dialog(dialog):
    """Fills empty fields. Returns a list of questions we could not answer."""
    missing = []
    for el in dialog.locator(
            "input:not([type=hidden]):not([type=file]):not([type=checkbox]):not([type=radio]), textarea").all():
        if not el.is_visible() or el.input_value().strip():
            continue
        label = el.evaluate(LABEL_JS)
        ans = answer_for(label)
        if ans is None:
            missing.append(label)
        else:
            el.fill(ans)
            if el.get_attribute("role") == "combobox":
                dialog.page.keyboard.press("ArrowDown")
                dialog.page.keyboard.press("Enter")
    for sel in dialog.locator("select").all():
        if not sel.is_visible() or sel.evaluate("e => e.selectedOptions[0] ? e.selectedOptions[0].value : ''"):
            continue
        label = sel.evaluate(LABEL_JS)
        ans = answer_for(label)
        pick = next((o for o in sel.locator("option").all_inner_texts() if ans and ans.lower() in o.lower()), None)
        if pick:
            sel.select_option(label=pick)
        else:
            missing.append(label)
    for fs in dialog.locator("fieldset").all():
        if fs.locator("input[type=radio]:checked").count() or not fs.locator("input[type=radio]").count():
            continue
        q = fs.locator("legend, span").first.inner_text().strip()
        ans = answer_for(q)
        choice = fs.locator("label").filter(has_text=re.compile(rf"^\s*{re.escape(ans)}\s*$", re.I)) if ans else None
        if choice is not None and choice.count():
            choice.first.click()
        else:
            missing.append(q)
    return missing


def collect_job_ids(page):
    """Works with both the old and the new LinkedIn layout: reads job ids straight from the page."""
    page.mouse.move(300, 450)   # hover the results list so the wheel scrolls it, not the page
    html = ""
    ids = []
    for _ in range(6):
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(900)
        html = page.content()
        # newest layout: componentkey="job-card-component-ref-<id>"
        ids += [(a, b, c) for a, b, c in re.findall(
            r"currentJobId=(\d+)|/jobs/view/(?:[^/\"?]*?-)?(\d{8,})|job-card-component-ref-(\d+)", html)]
    seen = []
    for a, b, c in ids:
        jid = a or b or c
        if jid and jid not in seen:
            seen.append(jid)
    return seen


def close_dialog(page):
    page.keyboard.press("Escape")
    pause(0.5, 1)
    discard = page.get_by_role("button", name=re.compile("discard", re.I))
    if discard.count():
        discard.first.click()


def apply_job(page, job_id, skills):
    page.goto(f"https://www.linkedin.com/jobs/view/{job_id}/", wait_until="domcontentloaded")
    pause(2, 3.5)
    title = page.title().split("|")[0].strip() or job_id

    t = title.lower()
    if any(x in t for x in TITLE_MUST_NOT_HAVE) or not any(x in t for x in TITLE_MUST_HAVE):
        return save(job_id, "skipped", title, "title not a match")
    if skills:
        body = page.inner_text("body").lower()
        hits = [s for s in skills if s in body]
        if len(hits) < MIN_SKILL_MATCHES:
            return save(job_id, "skipped", title, f"only {len(hits)} resume skills matched")

    btn = page.locator("button:has-text('Easy Apply')").first
    if not btn.is_visible():
        return save(job_id, "skipped", title, "no Easy Apply (already applied or external)")
    btn.click()
    # New LinkedIn layout uses a native <dialog>; old one used div[role=dialog].
    dialog = page.locator("dialog[open], div.jobs-easy-apply-modal, div[role=dialog]:visible").first
    dialog.wait_for(state="visible", timeout=10000)

    for _ in range(12):
        pause(1, 1.8)
        missing = fill_dialog(dialog)
        if missing:
            close_dialog(page)
            return save(job_id, "skipped", title, f"unanswered: {missing[0][:60]}")

        follow = dialog.locator("#follow-company-checkbox")
        if follow.count() and follow.is_checked():
            dialog.locator("label[for='follow-company-checkbox']").click()

        submit = dialog.get_by_role("button", name=re.compile("submit application", re.I))
        if submit.count():
            if DRY_RUN:
                close_dialog(page)
                return save(job_id, "dry-run", title, "reached Submit")
            submit.click()
            pause(2, 3)
            done = page.get_by_role("button", name=re.compile(r"^(done|dismiss)", re.I))
            if done.count():
                done.first.click()
            return save(job_id, "applied", title)

        nxt = dialog.get_by_role("button", name=re.compile(r"^(next|continue|review)", re.I))
        if not nxt.count():
            break
        nxt.first.click()
        if dialog.locator(".artdeco-inline-feedback--error").count():
            close_dialog(page)
            return save(job_id, "skipped", title, "form validation error")
    close_dialog(page)
    save(job_id, "skipped", title, "could not reach Submit")


def main():
    if not DRY_RUN:
        if input("LIVE MODE: this will submit real applications. Type YES to continue: ") != "YES":
            return
    skills = resume_skills()
    count = 0
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            ".sessions/linkedin", headless=False, no_viewport=True, args=["--start-maximized"])
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            for kw in KEYWORDS:
                for pg in range(PAGES_PER_KEYWORD):
                    qs = urlencode({"keywords": kw, "location": "Bengaluru, Karnataka, India",
                                    "f_AL": "true", "f_TPR": POSTED_WITHIN, "start": pg * 25})
                    page.goto(f"https://www.linkedin.com/jobs/search/?{qs}", wait_until="domcontentloaded")
                    pause(3, 5)
                    if re.search(r"login|authwall|checkpoint", page.url):
                        print("Not logged in. Run login.py first.")
                        return
                    ids = [i for i in collect_job_ids(page) if i not in db]
                    print(f'"{kw}" page {pg + 1}: {len(ids)} new jobs')
                    if not ids:
                        break
                    for jid in ids:
                        if count >= MAX_PER_RUN:
                            print("Reached MAX_PER_RUN, stopping.")
                            return
                        try:
                            apply_job(page, jid, skills)
                        except Exception as e:
                            save(jid, "error", jid, str(e)[:80])
                            try:
                                close_dialog(page)
                            except Exception:
                                pass
                        if db.get(jid, {}).get("status") in ("applied", "dry-run"):
                            count += 1
                        pause(3, 6)
        finally:
            ctx.close()
            print("Finished. Results are in applied.json")


if __name__ == "__main__":
    main()