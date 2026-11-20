# End-to-end browser test (Playwright). Start the app first, then: python scripts/e2e_browser_test.py
# Uses a fresh profile, so run it against an empty data folder (set EMA_DATA_DIR) to avoid touching your progress.
import json, sys
from playwright.sync_api import sync_playwright
B = "http://127.0.0.1:8765"
errors = []
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    ctx = br.new_context(viewport={"width": 1440, "height": 950})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"PAGEERROR {pg.url}: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"CONSOLE {pg.url}: {m.text}"))
    # Onboarding through the real UI
    pg.goto(B); pg.wait_for_selector("text=Welcome to English Mastery")
    pg.fill("input.input", "Nadia"); pg.click("text=Start learning")
    pg.wait_for_selector("text=Today's plan"); print("onboarding ok")
    # Grammar: answer an MCQ
    pg.goto(B + "/#/grammar/inversion-emphasis"); pg.click("text=did they miss"); pg.wait_for_selector("text=Correct."); print("grammar ok")
    pg.click("text=☆ Bookmark"); pg.wait_for_selector("text=★ Bookmarked"); print("bookmark ok")
    # Vocabulary: add all, review one card
    pg.goto(B + "/#/vocabulary"); pg.click("text=/Add all/"); pg.click("text=Show meaning"); pg.click("button:has-text('Good')"); print("vocab ok")
    # Reading: finish + answer
    pg.goto(B + "/#/reading/four-day-week"); pg.click("text=I've finished reading"); pg.wait_for_selector("text=Comprehension")
    pg.click("text=It fell from 18% to 4%."); pg.wait_for_selector("text=/✓/"); print("reading ok")
    # Listening dictation
    pg.goto(B + "/#/listening/budget-meeting"); pg.click("button:has-text('Dictation')"); pg.fill("div.card input.input >> nth=0", "Can I just come in there"); pg.click("button:has-text('Check') >> nth=0"); pg.wait_for_selector("text=/\\d+%/"); print("dictation ok")
    # Weekly check
    pg.goto(B + "/#/tests"); pg.click("text=Weekly check"); pg.wait_for_selector("text=Which word means")
    for card in pg.query_selector_all("div.card > div"):
        lab = card.query_selector("label"); inp = card.query_selector("input.input")
        if lab: lab.click()
        elif inp: inp.fill("x")
    pg.click("button:has-text('Submit')"); pg.wait_for_selector("text=/^\\d+%$/"); print("weekly ok")
    # Exam: start, submit listening empty
    pg.goto(B + "/#/exams"); pg.click("text=Start the mock exam"); pg.wait_for_selector("text=/part 1 of 4/i")
    for _ in range(3): pg.click("text=Next part →")
    pg.click("text=Submit listening"); pg.wait_for_selector("text=/Band ≈/"); print("exam listening ok")
    # Video: add YouTube item with transcript, open player
    pg.goto(B + "/#/video"); pg.click("text=/My video library/")
    pg.fill("input[placeholder=Title]", "Test talk"); pg.fill("input[placeholder^='https://www.youtube.com']", "https://youtu.be/abcdefghijk")
    pg.fill("textarea", "First sentence here. Second sentence there."); pg.click("text=Add to my library")
    pg.wait_for_selector("text=Interactive transcript"); print("video ok")
    # Visit all remaining routes for runtime errors
    for r in ["/", "/path", "/analytics", "/search?q=inversion", "/business", "/pronunciation", "/video/scene/budget-meeting", "/settings", "/conversation", "/writing", "/listening", "/reading", "/grammar"]:
        pg.goto(B + "/#" + r); pg.wait_for_timeout(700)
    pg.goto(B + "/#/analytics"); pg.wait_for_timeout(800); pg.screenshot(path="./e2e-screenshots-analytics.png", full_page=False)
    pg.goto(B + "/#/path"); pg.wait_for_timeout(800); pg.screenshot(path="./e2e-screenshots-path.png")
    pg.goto(B + "/#/video/scene/budget-meeting"); pg.wait_for_timeout(600); pg.screenshot(path="./e2e-screenshots-scene.png")
    pg.goto(B + "/#/business"); pg.wait_for_timeout(600); pg.screenshot(path="./e2e-screenshots-business.png")
    pg.goto(B + "/#/exams"); pg.wait_for_timeout(600); pg.screenshot(path="./e2e-screenshots-exams.png")
    # Conversation start: no key -> clear error
    pg.goto(B + "/#/conversation?mode=mba"); pg.click("text=Start conversation"); pg.wait_for_timeout(500)
    pg.fill("input[placeholder^='Or type']", "I am agree"); pg.click("button:has-text('Send')"); pg.wait_for_selector("text=/API key/"); print("conversation key message ok")
    pg.screenshot(path="./e2e-screenshots-conversation.png")
    br.close()
# Filter expected 412/404 network noise
real = [e for e in errors if "412" not in e and "Failed to load resource" not in e and "youtube" not in e.lower()]
print("ERRORS:", json.dumps(real, indent=1) if real else "none")
