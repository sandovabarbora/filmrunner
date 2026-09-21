"""Live run of everything merged on 2026-09-21 against the deployed stack (Pages + Fly + Supabase).
Token read from disk, never printed. Creates one production owned by the service (invisible to users)."""
import json, os, re, uuid, urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

PAGES = "https://sandovabarbora.github.io/filmrunner"
API = "https://filmrunner-api.fly.dev"
TOKEN = Path(os.path.expanduser("~/.config/filmrunner/api_token")).read_text().strip()
results = []

def rec(step, ok, note=""):
    results.append((step, ok, note)); print(("PASS " if ok else "FAIL ") + step + (f" — {note}" if note else ""))

def api(method, path, body=None, auth=True):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {TOKEN}"} if auth else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(); return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read(); return e.code, (json.loads(raw) if raw else None)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script("localStorage.setItem('filmrunner.editor.connection', JSON.stringify(" + json.dumps({"apiBase": API, "token": TOKEN}) + "))")
    page = ctx.new_page()
    page.goto(f"{PAGES}/editor.html"); page.wait_for_selector("#newProduction", timeout=20000)
    name = f"Live check {uuid.uuid4().hex[:6]}"
    page.fill("#newProduction", name); page.click("#createProduction"); page.wait_for_selector("#newDay", timeout=20000)
    rec("editor: create production on live API", True)

    # FR-31 paste crew
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#pasteCrew", timeout=15000); page.click("#pasteCrew")
    page.fill("#pasteCrewText", "Electric:\nTomáš Novák, Gaffer, 777 123 456, HoD\nCamera:\nEva Malá, 1st AC")
    expect(page.locator("#importCrew")).to_have_text("Add 2 people"); page.click("#importCrew")
    expect(page.locator("#notice")).to_contain_text("Added 2 people", timeout=20000)
    rec("FR-31 paste crew list live", page.locator("#crew li").count() == 2)
    wa = page.get_by_label("Send link to Tomáš Novák on WhatsApp").get_attribute("href")
    rec("FR-37 onboarding WhatsApp link (stable link)", wa.startswith("https://wa.me/420777123456?text=") and "&me=" in parse_qs(urlparse(wa).query)["text"][0])

    # FR-33 cast
    page.click("role=tab[name='Cast']"); page.wait_for_selector("#castName", timeout=15000)
    page.fill("#castName", "Anna Geislerová"); page.fill("#castCharacter", "MARTA"); page.fill("#castPickup", "05:30"); page.click("#addCast")
    expect(page.locator("#cast")).to_contain_text("MARTA", timeout=20000); rec("FR-33 cast member live", True)

    # FR-19/35 location with real geocode
    page.click("role=tab[name='Locations']"); page.wait_for_selector("#locName", timeout=15000)
    page.fill("#locName", "Riverbank, Troja"); page.fill("#locAddress", "Trojská 1, Praha 7"); page.fill("#locParking", "Gravel lot by the boathouse") if page.locator("#locParking").count() else None
    page.click("#addLocation"); expect(page.locator("#locations")).to_contain_text("Riverbank, Troja", timeout=25000)
    geocoded = "resolved:" in page.locator("#locations").inner_text()
    rec("location geocoded live (Nominatim from Fly)", geocoded, "" if geocoded else "no 'resolved:' shown")

    # Day 1 with scene, cast call, personal call
    page.click("role=tab[name='Days']"); page.click("#newDay"); page.wait_for_selector("#general_crew_call", timeout=15000)
    rec("FR-27 hint before a location is picked", page.locator("#sunHint").get_attribute("data-state") == "none")
    page.fill("#shoot_date", "2026-09-30"); page.fill("#general_crew_call", "06:30")
    page.click("#addScene"); item = page.locator("#items .item").nth(0)
    item.get_by_label("Scene").fill("42"); item.get_by_label("Set").fill("EXT. RIVERBANK"); item.get_by_label("Location").select_option(label="Riverbank, Troja")
    if geocoded:
        expect(page.locator("#sunrise")).to_have_value(re.compile(r"^\d{2}:\d{2}$"), timeout=15000); rec("FR-27 sunrise filled from location live", True)
    page.wait_for_selector("#addPersonalCall", timeout=15000)
    page.select_option("#addPersonalCall", page.locator("#addPersonalCall option", has_text="Tomáš Novák").get_attribute("value"))
    page.get_by_label("Call for Tomáš Novák").fill("05:15")
    page.get_by_label("Anna Geislerová works today").check(); page.get_by_label("Status for Anna Geislerová").select_option("SW"); page.get_by_label("Call for Anna Geislerová").fill("06:00")
    page.click("#publish"); expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=25000)
    page.wait_for_selector("#shareLink", timeout=15000)
    rec("publish REV A live", True)
    day_link = page.locator("#shareLink").get_attribute("href")
    tomas_link = page.locator("#personalLinks li", has_text="Tomáš Novák").get_by_role("link", name="Open").get_attribute("href")
    wa_day = page.locator("#dayWhatsapp").get_attribute("href")
    rec("FR-29 day WhatsApp text has crew call + link", "Crew call: *06:30*" in parse_qs(urlparse(wa_day).query)["text"][0])
    wa_t = page.get_by_label("WhatsApp Tomáš Novák").get_attribute("href")
    rec("FR-29 personal WhatsApp carries the day's own call", "Your call: *05:15*" in parse_qs(urlparse(wa_t).query)["text"][0])
    expect(page.locator("#seenPanel")).to_contain_text("REV A opened by 0 of 2", timeout=15000); rec("FR-36 seen panel 0 of 2", True)

    # Crew view through the stable link
    v = ctx.new_page(); v.goto(tomas_link); v.wait_for_selector("#you", timeout=25000)
    rec("FR-32 stable link resolves to the day", v.locator("#yourCall").inner_text().strip() == "05:15", v.locator("#yourCall").inner_text())
    rec("FR-35 Where block on the sheet", v.locator("#locations .location").count() == 1)
    rec("FR-33 cast table on the sheet", v.locator("#castTable tbody tr").count() == 1)
    rec("REV A: no 'replaces' line", v.locator("#revReplaces").count() == 0)
    v.close()
    page.reload(); page.wait_for_selector("#seenPanel", timeout=20000)
    expect(page.locator("#seenPanel")).to_contain_text("REV A opened by 1 of 2", timeout=15000); rec("FR-36 read receipt recorded live", True)
    nudge = page.get_by_label("Nudge Eva Malá on WhatsApp").count()
    rec("FR-36 no nudge link for a person without phone", nudge == 0)

    # REV B + diff
    page.fill("#general_crew_call", "07:00"); page.click("#publish"); expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=25000)
    v = ctx.new_page(); v.goto(tomas_link); v.wait_for_selector("#revChanges", timeout=25000)
    rec("FR-23 REV B replaces A + crew call diff", "replaces A" in v.locator("#revReplaces").inner_text() and "07:00" in v.locator("#revChanges li[data-field='crew_call']").inner_text())
    rec("FR-24 personal call carried to REV B", v.locator("#yourCall").inner_text().strip() == "05:15")
    v.close()

    # FR-30 next day
    page.click("#startNextDay"); page.wait_for_url(re.compile(r"day/new$"), timeout=15000)
    expect(page.locator("#day_number")).to_have_value("2", timeout=15000)
    rec("FR-30 next day prefilled", page.locator("#shoot_date").input_value() == "2026-10-01" and page.locator("#general_crew_call").input_value() == "07:00")
    page.click("#publish"); expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=25000); page.wait_for_url(re.compile(r"day/(?!new)"), timeout=15000)
    # stable link now opens day 1 (2026-09-30 is the next date >= today) and lists both
    v = ctx.new_page(); v.goto(tomas_link); v.wait_for_selector("#otherDays", timeout=25000)
    rec("FR-32 other-days nav lists both days", v.locator("#otherDays .day").count() == 2)
    v.close()

    # FR-34 cancel day 2
    page.click("#cancelDayBtn"); page.click("#confirmCancelDay"); expect(page.locator("#notice")).to_contain_text("Day 2 cancelled", timeout=20000)
    rec("FR-34 cancel live", page.locator("#cancelledBanner").count() == 1)
    day2 = page.url.split("/day/")[1]
    s, body = api("GET", f"/api/v1/public/call-sheets/{day2}", auth=False)
    rec("FR-34 public read says cancelled", body and body.get("status") == "cancelled")
    page.click("#restoreDay"); expect(page.locator("#notice")).to_contain_text("back on", timeout=20000); rec("FR-34 restore live", True)

    # Settings: wrap it so it is clearly a test production
    page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']"); page.wait_for_selector("#newDay", timeout=15000)
    page.click("role=tab[name='Settings']"); page.wait_for_selector("#productionName", timeout=15000)
    page.select_option("#productionStatus", "wrapped"); page.click("#saveProduction"); expect(page.locator("#notice")).to_contain_text("is wrapped", timeout=20000)
    rec("FR-34 production wrapped via Settings", True)

    # public endpoints
    s, _ = api("POST", f"/api/v1/public/call-sheets/{day2}/seen/not-a-token", auth=False); rec("seen with unknown token → 404", s == 404)
    s, _ = api("GET", "/api/v1/public/crew/not-a-token/next", auth=False); rec("next with unknown token → 404", s == 404)
    b.close()

print(f"\n{sum(1 for _, ok, _ in results if ok)} pass, {sum(1 for _, ok, _ in results if not ok)} fail of {len(results)}")
