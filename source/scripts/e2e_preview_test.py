import time
from playwright.sync_api import sync_playwright
U = "http://127.0.0.1:8899/index.html"
errs = []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = br.new_page(viewport={"width": 1440, "height": 950})
    pg.on("pageerror", lambda e: errs.append(f"PAGEERROR {e}"))
    pg.on("console", lambda m: m.type == "error" and errs.append(f"CONSOLE {m.text[:300]}"))
    t0 = time.time(); pg.goto(U)
    pg.wait_for_selector("text=Welcome to English Mastery", timeout=180000); print(f"engine booted in {time.time()-t0:.1f}s")
    pg.fill("input.input", "Preview User"); pg.click("text=Start learning"); pg.wait_for_selector("text=Today's plan"); print("onboarding ok")
    nav = lambda label: pg.click(f"nav >> text={label}")
    nav("Grammar Academy"); pg.click("text=Inversion for Emphasis"); pg.click("text=did they miss"); pg.wait_for_selector("text=Correct."); print("grammar ok")
    nav("Vocabulary"); pg.click("text=/Add all/"); pg.click("text=Show meaning"); pg.click("button:has-text('Good')"); print("vocab ok")
    nav("Reading"); pg.click("text=Why £9.99 Still Works"); pg.click("text=I've finished reading"); pg.wait_for_selector("text=Comprehension"); pg.click("text=The left-digit effect."); pg.wait_for_selector("text=/✓/"); print("reading ok")
    nav("Listening Laboratory"); pg.click("text=Opening a Bank Account"); pg.click("button:has-text('Dictation')"); pg.fill("div.card input.input >> nth=0", "Welcome! We have a newcomer package"); pg.click("button:has-text('Check') >> nth=0"); pg.wait_for_selector("text=/\\d+%/"); print("listening ok")
    nav("IELTS & TOEFL"); pg.click("button:has-text('TOEFL iBT (2026)')"); pg.click("button:has-text('Start')"); pg.wait_for_selector("text=Complete the Words")
    pg.fill("input.input >> nth=0", "oor"); pg.click("text=Submit Reading"); pg.wait_for_selector("text=/\\d+\\/\\d+ ·/"); print("toefl reading ok")
    nav("IELTS & TOEFL"); pg.click("button:has-text('Cambridge C1 Advanced')"); pg.click("button:has-text('Start')"); pg.wait_for_selector("text=Part 4: Key word transformation"); print("cambridge ok")
    nav("Tests & Assessments"); pg.click("text=Weekly check"); pg.wait_for_selector("text=Which word means"); print("weekly ok")
    nav("Progress Analytics"); pg.wait_for_selector("text=Learning history"); print("analytics ok")
    nav("My Learning Path"); pg.wait_for_selector("text=Week 1"); print("path ok")
    nav("AI Conversation"); pg.click("text=Start conversation"); pg.wait_for_timeout(800); pg.fill("input[placeholder^='Or type']", "I am agree"); pg.click("button:has-text('Send')"); pg.wait_for_selector("text=/API key/"); print("conversation message ok")
    pg.screenshot(path="/tmp/e2e/preview_conv.png")
    nav("Dashboard"); pg.wait_for_timeout(500); pg.screenshot(path="/tmp/e2e/preview_dash.png")
    # persistence: reload and check profile survives
    pg.reload(); pg.wait_for_selector("text=Today's plan", timeout=180000); print("persistence ok (profile survived reload)")
    br.close()
real = [e for e in errs if "412" not in e and "Failed to load resource" not in e and "data:audio" not in e]
print("ERRORS:", real or "none")
