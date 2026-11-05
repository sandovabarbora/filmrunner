"""End-to-end: the AD editor against the real API (FR-10 dod).

Starts uvicorn on the test database (same URL the backend tests use),
serves the built frontend, and drives the editor like an AD on a phone:
connect, create a production, fill a day, publish A, change the crew
call, publish B, open the crew link and see REV B.
"""

import re
import uuid

from playwright.sync_api import Page, expect

from conftest import E2E_TOKEN


def _connect(page: Page, frontend_url: str, api_url: str) -> None:
    """Inject the service connection the way a tool would (no sign-in UI), so the
    suite runs the same against a build with or without Supabase configured."""
    page.add_init_script(
        "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
        + f"{{apiBase: {api_url!r}, token: {E2E_TOKEN!r}}}))"
    )
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#newProduction", timeout=10_000)


def _pick_personal_call(page: Page, name: str) -> None:
    """FR-44: personal calls list only the people with one; pick the person first."""
    value = page.locator("#addPersonalCall option", has_text=name).get_attribute("value")
    page.select_option("#addPersonalCall", value)
    page.wait_for_selector("#personalCalls .pcall", timeout=10_000)


def _create_production(page: Page, name: str) -> None:
    page.fill("#newProduction", name)
    page.click("#createProduction")
    page.wait_for_selector("#newDay", timeout=10_000)  # lands on the production's Days tab


def test_connected_app_production_crew_day_reopen_publish_b(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-17 dod: create production, add a HoD, create a day, reopen the editor,
    open the day from the list, publish REV B with a head of day, crew link shows B and the contact."""
    production = f"E2E {uuid.uuid4().hex[:6]}"
    _connect(page, frontend_url, api_url)
    _create_production(page, production)

    # Crew tab: one head of department.
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Eva Dvořáková")
    page.fill("#crewPhone", "+420 777 111 222")
    page.fill("#crewDept", "AD")
    page.fill("#crewPos", "1st AD")
    page.check("#crewHod")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Eva Dvořáková", timeout=10_000)

    # New day.
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#shoot_date", "2026-09-22")
    page.fill("#day_number", "7")
    page.fill("#day_count", "24")
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("42")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("RIVERBANK, TROJA.")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    assert "/day/new" not in page.url  # moved to the real day's URL

    # Close and reopen: the day is found from the list, loaded from the server.
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#productions", timeout=10_000)
    page.click(f"#productions >> text={production}")
    page.wait_for_selector("#days", timeout=10_000)
    expect(page.locator("#days")).to_contain_text("Day 7 of 24")
    expect(page.locator("#days")).to_contain_text("REV A")
    page.click("#days >> text=Day 7 of 24")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    assert page.locator("#general_crew_call").input_value() == "06:30"
    assert page.locator("#items .item").count() == 1
    assert page.locator("#shoot_date").is_disabled()

    # Hot revision with a head of day.
    page.fill("#general_crew_call", "07:30")
    page.select_option("#headOfDay", label="Eva Dvořáková · 1st AD (HoD)")
    expect(page.locator("#publishState")).to_contain_text("Publish to send REV B")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    share = page.locator("#shareLink").get_attribute("href")
    assert share

    # FR-11: a scannable QR code for the crew link sits next to it.
    expect(page.locator("#shareQr svg")).to_be_visible()
    assert page.locator("#shareQr svg rect").count() > 20  # a real QR code, not a placeholder

    # Crew link: REV B, new call, head of day and HoD with tap-to-call.
    page.goto(share)
    page.wait_for_selector("#sheet.visible", timeout=15_000)
    assert page.locator("#revBadgeWrap").inner_text().strip() == "REV B"
    assert page.locator("#crewCall").inner_text().strip() == "07:30"
    assert "Eva Dvořáková" in page.locator("#contacts .hod").inner_text()
    assert page.locator("#contacts a.phone").first.get_attribute("href") == "tel:+420777111222"


def test_publish_without_network_keeps_the_draft(page: Page, frontend_url: str, api_url: str) -> None:
    """Failure case (FR-10 dod): losing the network must not lose the draft."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E offline {uuid.uuid4().hex[:6]}")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "05:45")
    page.fill("#safety_notes", "draft must survive")

    page.route(f"{api_url}/**", lambda route: route.abort())
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("draft is safe", timeout=15_000)

    page.unroute(f"{api_url}/**")
    page.reload()
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    assert page.locator("#general_crew_call").input_value() == "05:45"
    assert page.locator("#safety_notes").input_value() == "draft must survive"
    expect(page.locator("#publishState")).to_contain_text("Not published yet")


def test_opening_a_published_day_offline_is_read_only(page: Page, frontend_url: str, api_url: str) -> None:
    """Failure case (FR-17 dod): offline, a published day shows the last copy read-only, never a blank publishable form."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E ro {uuid.uuid4().hex[:6]}")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:00")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.route(f"{api_url}/**", lambda route: route.abort())
    page.reload()
    page.wait_for_selector("#publishState", timeout=10_000)
    expect(page.locator("#publishState")).to_contain_text("Read-only while offline")
    assert page.locator("#publish").is_disabled()
    assert page.locator("#general_crew_call").input_value() == "06:00"


def test_five_taps_on_the_logo_open_admin_access(page: Page, frontend_url: str, api_url: str) -> None:
    """Founder's gesture: 5 taps on the logo within 3 s reveal the service-token screen; the token then bypasses sign-in."""
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#logo", timeout=10_000)
    for _ in range(5):
        page.click("#logo")
    page.wait_for_selector("#adminScreen", timeout=5_000)
    assert "Admin access" in (page.locator("#adminScreen h2").text_content() or "")
    page.fill("#apiBase", api_url)
    page.fill("#token", E2E_TOKEN)
    page.click("#connect")
    page.wait_for_selector("#newProduction", timeout=10_000)
    assert "Admin" in page.locator(".masthead .sub").inner_text()


def test_four_taps_do_nothing(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#logo", timeout=10_000)
    for _ in range(4):
        page.click("#logo")
    page.wait_for_timeout(300)
    assert page.locator("#adminScreen").count() == 0


def test_owner_invites_members_and_sees_role_chip(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-15: the Members tab (owner only) invites by email; a viewer row shows 'not signed in yet' until they do."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E roles {uuid.uuid4().hex[:6]}")
    assert page.locator("#myRole").inner_text().strip().lower() == "owner"
    page.click("role=tab[name='Members']")
    page.wait_for_selector("#memberEmail", timeout=10_000)
    page.fill("#memberEmail", "viewer@example.com")
    page.select_option("#memberRole", "viewer")
    page.click("#addMember")
    expect(page.locator("#members")).to_contain_text("viewer@example.com", timeout=10_000)
    expect(page.locator("#members")).to_contain_text("not signed in yet")
    page.click("#members >> role=button[name='Remove viewer@example.com']")
    expect(page.locator("#members li")).to_have_count(0, timeout=10_000)


def test_personal_link_shows_your_call_and_department_first(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-13: a crew member's personal link shows their name, own call and their department's HoD first;
    an invalid token falls back to the general sheet with a note."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E me {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    for name, phone, dept, pos, hod in (("Eva Dvořáková", "+420 777 111 222", "AD", "1st AD", True), ("Petr Malý", "+420 602 000 000", "Electric", "Best boy", False), ("Tomáš Novák", "+420 601 234 567", "Electric", "Gaffer", True)):
        page.fill("#crewName", name); page.fill("#crewPhone", phone); page.fill("#crewDept", dept); page.fill("#crewPos", pos)
        if hod:
            page.check("#crewHod")
        page.click("#addCrew")
        expect(page.locator("#crew")).to_contain_text(name, timeout=10_000)
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    petr_link = page.locator("#personalLinks li", has_text="Petr Malý").get_by_role("link", name="Open").get_attribute("href")
    assert petr_link and "&me=" in petr_link
    day_link = page.locator("#shareLink").get_attribute("href")

    page.goto(petr_link)
    page.wait_for_selector("#you", timeout=15_000)
    assert "Petr Malý" in page.locator("#you").inner_text()
    assert page.locator("#yourCall").inner_text().strip() == "06:30"  # no own call time: general crew call
    assert "Tomáš Novák" in page.locator("#yourDepartment").inner_text()  # Electric HoD first
    assert "Eva Dvořáková" not in page.locator("#yourDepartment").inner_text()
    assert page.locator("#otherDepartments").count() == 1

    # FR-32: the link is the stable one (no sheet id); it resolved to this day. Other-days nav only appears with 2+ days.
    assert "sheet=" not in petr_link
    assert page.locator("#otherDays").count() == 0

    # A day link with an unknown token still shows the general sheet (FR-13 failure case)...
    page.goto(f"{day_link}&me=bogus")
    page.wait_for_selector("#sheet.visible", timeout=15_000)
    page.wait_for_selector("#personalInvalid", timeout=10_000)
    assert page.locator("#you").count() == 0
    # ...while the stable link with an unknown token says so plainly instead of guessing a day (FR-32 failure case).
    page.goto(petr_link.replace("&me=", "&me=bogus"))
    expect(page.locator("#status")).to_contain_text("not on any crew list", timeout=15_000)
    assert page.locator("#sheet.visible").count() == 0


def test_crew_edit_personal_call_and_remove(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-18: edit a person (phone, personal call, HoD), see it on the sheet, remove another."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E crew {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    for name, dept, pos in (("Petr Malý", "Electric", "Best boy"), ("Jana Bílá", "Production", "UPM")):
        page.fill("#crewName", name); page.fill("#crewDept", dept); page.fill("#crewPos", pos); page.click("#addCrew")
        expect(page.locator("#crew")).to_contain_text(name, timeout=10_000)

    page.click("#crew >> role=button[name='Edit Petr Malý']")
    expect(page.locator("#crewFormTitle")).to_contain_text("Editing Petr Malý")
    page.fill("#crewPhone", "+420 777 000 111")
    page.fill("#crewCall", "05:45")
    page.check("#crewHod")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("call 05:45", timeout=10_000)
    expect(page.locator("#crew")).to_contain_text("+420 777 000 111")
    expect(page.locator("#crewFormTitle")).to_contain_text("Add a person")

    page.once("dialog", lambda d: d.accept())
    page.click("#crew >> role=button[name='Remove Jana Bílá']")
    expect(page.locator("#crew")).not_to_contain_text("Jana Bílá", timeout=10_000)

    # The personal sheet uses the edited call time.
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    link = page.locator("#personalLinks li", has_text="Petr Malý").get_by_role("link", name="Open").get_attribute("href")
    page.goto(link)
    page.wait_for_selector("#you", timeout=15_000)
    assert page.locator("#yourCall").inner_text().strip() == "05:45"


def test_crew_edit_offline_queues_locally_and_shows_not_saved(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-18 failure case: editing an existing crew member offline must not fall into the
    generic "No connection, try again" notice (nothing would be queued for that). The
    change is kept on the phone, the row shows "not saved", and it syncs once back online."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E crew offline {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Petr Malý")
    page.fill("#crewDept", "Electric")
    page.fill("#crewPos", "Best boy")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Petr Malý", timeout=10_000)

    page.click("#crew >> role=button[name='Edit Petr Malý']")
    expect(page.locator("#crewFormTitle")).to_contain_text("Editing Petr Malý")
    page.fill("#crewPhone", "+420 777 000 111")
    page.fill("#crewCall", "05:45")

    page.route(f"{api_url}/**", lambda route: route.abort())
    page.click("#addCrew")
    expect(page.locator("#notice")).to_contain_text("kept on this phone", timeout=10_000)
    expect(page.locator("#crew")).to_contain_text("not saved", timeout=10_000)
    # The optimistic overlay shows the edit immediately, not the stale server copy.
    expect(page.locator("#crew")).to_contain_text("+420 777 000 111")
    expect(page.locator("#crew")).to_contain_text("call 05:45")
    # The form closed: there is nothing further to submit, the edit is already queued.
    expect(page.locator("#crewFormTitle")).to_contain_text("Add a person")

    # Back online: reopening the tab retries the queued edit on its own.
    page.unroute(f"{api_url}/**")
    page.reload()
    page.wait_for_selector("#crewName", timeout=10_000)
    expect(page.locator("#crew")).to_contain_text("+420 777 000 111", timeout=10_000)
    expect(page.locator("#crew")).not_to_contain_text("not saved", timeout=10_000)


def test_photo_upload_failure_does_not_block_other_edits(page: Page, frontend_url: str, api_url: str, tmp_path) -> None:
    """FR-18 failure case: this test API has no Supabase Storage credentials, the same
    state production is in until the founder does INBOX's bucket item, so the upload
    503s for real. Saving the rest of the person must still work after that."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E photo {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Petr Malý")
    page.fill("#crewDept", "Electric")
    page.fill("#crewPos", "Best boy")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Petr Malý", timeout=10_000)

    page.click("#crew >> role=button[name='Edit Petr Malý']")
    expect(page.locator("#crewPhotoField")).to_be_visible()

    photo = tmp_path / "avatar.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    page.locator("#crewPhotoInput").set_input_files(str(photo))
    expect(page.locator("#notice")).to_contain_text("Could not upload the photo", timeout=10_000)

    page.fill("#crewPhone", "+420 777 000 111")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("+420 777 000 111", timeout=10_000)


def test_first_run_checklist_guides_and_disappears(page: Page, frontend_url: str, api_url: str) -> None:
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E first {uuid.uuid4().hex[:6]}")
    page.wait_for_selector("#checklist", timeout=10_000)
    items = page.locator("#checklist li")
    assert items.count() == 4
    assert "done" in (items.nth(0).get_attribute("class") or "")
    assert "next" in (items.nth(1).get_attribute("class") or "")  # add the crew is the next step
    items.nth(1).locator("a").click()
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Eva"); page.fill("#crewDept", "AD"); page.fill("#crewPos", "1st AD"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Eva", timeout=10_000)
    page.click("role=tab[name='Days']")
    expect(page.locator("#checklist li").nth(2)).to_have_class("next", timeout=10_000)  # now: create the first day
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.click("text=Productions")
    page.wait_for_selector("#productions", timeout=10_000)
    page.click(f"#productions >> text=E2E first")
    page.wait_for_selector("#days", timeout=10_000)
    expect(page.locator("#checklist")).to_have_count(0, timeout=10_000)  # everything done: the guide is gone


def test_personal_call_for_the_day_beats_standing_time_and_carries_forward(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-24: set one person's call for the day; their personal link shows it; REV B keeps it prefilled."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E pcall {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Tomáš Novák"); page.fill("#crewDept", "Electric"); page.fill("#crewPos", "Gaffer"); page.fill("#crewCall", "06:00"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Tomáš Novák", timeout=10_000)
    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.wait_for_selector("#addPersonalCall", timeout=10_000)
    _pick_personal_call(page, "Tomáš Novák")
    page.get_by_label("Call for Tomáš Novák").fill("05:15")
    page.get_by_label("Pickup for Tomáš Novák").fill("04:45")
    page.get_by_label("Note for Tomáš Novák").fill("generator first")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    link = page.locator("#personalLinks li", has_text="Tomáš Novák").get_by_role("link", name="Open").get_attribute("href")

    v = page.context.new_page()
    v.goto(link); v.wait_for_selector("#you", timeout=15_000)
    assert v.locator("#yourCall").inner_text().strip() == "05:15"
    assert "04:45" in v.locator("#yourExtra").inner_text() and "generator first" in v.locator("#yourExtra").inner_text()
    v.emulate_media(media="print")
    assert v.locator("#personalCallsTable").is_visible()
    v.close()

    # Reopen the day: the entry is prefilled; publish B without touching it; still there.
    page.reload(); page.wait_for_selector("#personalCalls .pcall", timeout=10_000)
    expect(page.get_by_label("Call for Tomáš Novák")).to_have_value("05:15", timeout=10_000)
    assert page.locator("#addPersonalCall").count() == 0  # FR-44: everyone with an entry is listed, nobody left to pick

    page.fill("#general_crew_call", "07:00"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#you", timeout=15_000)
    assert v.locator("#yourCall").inner_text().strip() == "05:15"
    assert v.locator("#revBadgeWrap").inner_text().strip() == "REV B"


def test_whatsapp_message_carries_the_days_personal_call_and_waits_for_publish(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-29: one tap opens WhatsApp with the person's own call; with unpublished edits the buttons wait for publish;
    a phone that is not a number gets the copy/share path, never a broken wa.me link."""
    from urllib.parse import parse_qs, urlparse

    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E wa {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Tomáš Novák"); page.fill("#crewPhone", "777 123 456"); page.fill("#crewDept", "Electric"); page.fill("#crewPos", "Gaffer"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Tomáš Novák", timeout=10_000)
    page.fill("#crewName", "Eva Malá"); page.fill("#crewPhone", "ask Petra"); page.fill("#crewDept", "Camera"); page.fill("#crewPos", "1st AC"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Eva Malá", timeout=10_000)

    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.wait_for_selector("#addPersonalCall", timeout=10_000)
    _pick_personal_call(page, "Tomáš Novák")
    page.get_by_label("Call for Tomáš Novák").fill("05:15")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)

    wa = page.get_by_label("WhatsApp Tomáš Novák")
    href = wa.get_attribute("href")
    assert href.startswith("https://wa.me/420777123456?text=")
    text = parse_qs(urlparse(href).query)["text"][0]
    assert "Hi Tomáš," in text and "Your call: *05:15*" in text and "REV A" in text
    personal_link = page.locator("#personalLinks li", has_text="Tomáš Novák").get_by_role("link", name="Open").get_attribute("href")
    assert personal_link in text

    # Failure case: an unusable phone falls back to the share/copy button, no wa.me link.
    assert page.get_by_label("Send message to Eva Malá").is_visible()
    assert page.locator("#personalLinks li", has_text="Eva Malá").locator("a.whatsapp").count() == 0

    day_text = parse_qs(urlparse(page.locator("#dayWhatsapp").get_attribute("href")).query)["text"][0]
    assert "Crew call: *06:30*" in day_text and page.locator("#shareLink").get_attribute("href") in day_text
    assert page.locator("#sendDayAsText").is_enabled()

    # Unpublished edit: the text would no longer match the link, so sharing waits for the next publish.
    page.fill("#general_crew_call", "07:00")
    expect(page.locator("#shareTextHint")).to_contain_text("Publish first", timeout=5_000)
    assert page.locator("#sendDayAsText").is_disabled()
    assert page.get_by_label("WhatsApp Tomáš Novák").count() == 0
    assert page.get_by_label("Send message to Tomáš Novák").is_disabled()

    # Without a share sheet (headless Chromium), "Send day as text" copies and shows the text.
    page.evaluate("() => { delete navigator.share; }")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    page.click("#sendDayAsText")
    expect(page.locator("#shareTextPreview")).to_have_value(re.compile(r"Crew call: \*07:00\*"), timeout=5_000)


def test_rev_b_shows_what_changed_and_rev_a_shows_no_diff(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-23: the sheet says what B changed against A; a sheet with only A has no "replaces" line at all."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E diff {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#shareLink", timeout=10_000)
    link = page.locator("#shareLink").get_attribute("href")

    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#sheet", timeout=15_000)
    assert v.locator("#revReplaces").count() == 0  # failure case: no empty "replaces" sentence on A
    v.close()

    page.fill("#general_crew_call", "07:30"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#revChanges", timeout=15_000)
    assert re.search(r"REV B replaces A, issued \d{1,2}:\d{2}", v.locator("#revReplaces").inner_text())
    crew = v.locator("#revChanges li[data-field='crew_call']")
    assert crew.count() == 1 and "06:30" in crew.inner_text() and "07:30" in crew.inner_text()
    assert v.locator("#revChanges li[data-field='shooting_call']").count() == 0


def test_paste_a_crew_list_previews_and_adds_everyone_skipping_duplicates(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-31: a pasted list (headers, commas, tabs, HoD) is previewed and added in one go; someone already on the crew is skipped, not duplicated."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E paste {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Jan Novák"); page.fill("#crewDept", "Camera"); page.fill("#crewPos", "DoP"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Jan Novák", timeout=10_000)

    page.click("#pasteCrew")
    page.fill("#pasteCrewText", "Camera:\nJan Novák, DoP, 777 123 456\nPetra K.\t1st AC\t+420 602 111 222\nElectric:\nTomáš Novák, Gaffer, HoD\nKarel")
    preview = page.locator("#pastePreview li")
    expect(preview).to_have_count(4)
    expect(preview.nth(0)).to_contain_text("already on the crew")
    expect(preview.nth(3)).to_contain_text("no position, using Crew")
    expect(page.locator("#importCrew")).to_have_text("Add 3 people")
    page.click("#importCrew")
    expect(page.locator("#notice")).to_contain_text("Added 3 people", timeout=15_000)
    expect(page.locator("#crew li")).to_have_count(4, timeout=10_000)
    tomas = page.locator("#crew li", has_text="Tomáš Novák")
    expect(tomas).to_contain_text("HoD")
    expect(tomas).to_contain_text("Electric · Gaffer")
    expect(page.locator("#crew li", has_text="Petra K.")).to_contain_text("+420 602 111 222")
    assert page.locator("#pasteCrewPanel").count() == 0  # closed after a clean import
def test_next_day_starts_from_this_one_and_a_plain_new_day_continues_the_numbering(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-30: "Start Day 2 from this one" copies calls, scenes and personal calls to an unpublished Day 2 one date on;
    an unpublished new day is never replaced silently; a plain "+ New day" after Day 2 offers Day 3."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E next {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Tomáš Novák"); page.fill("#crewDept", "Electric"); page.fill("#crewPos", "Gaffer"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Tomáš Novák", timeout=10_000)

    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#shoot_date", "2026-09-30"); page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("7")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("COURTYARD")
    page.wait_for_selector("#addPersonalCall", timeout=10_000)
    _pick_personal_call(page, "Tomáš Novák")
    page.get_by_label("Call for Tomáš Novák").fill("05:15")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)

    page.click("#startNextDay")
    expect(page.locator("#notice")).to_contain_text("Day 2 started from Day 1", timeout=10_000)
    page.wait_for_url(re.compile(r"day/new$"), timeout=10_000)
    expect(page.locator("#day_number")).to_have_value("2", timeout=10_000)
    assert page.locator("#shoot_date").input_value() == "2026-10-01"
    assert page.locator("#general_crew_call").input_value() == "06:30"
    assert page.locator("#items .item").nth(0).get_by_label("Scene").input_value() == "7"
    expect(page.get_by_label("Call for Tomáš Novák")).to_have_value("05:15", timeout=10_000)
    assert page.locator("#publishState").inner_text().startswith("Not published yet")

    # Back on Day 1, starting Day 2 again must not silently discard the Day 2 draft.
    page.go_back(); page.wait_for_selector("#startNextDay", timeout=10_000)
    page.click("#startNextDay")
    expect(page.locator("#nextDayClash")).to_be_visible(timeout=5_000)
    page.click("#replaceNextDay")
    page.wait_for_url(re.compile(r"day/new$"), timeout=10_000)
    page.fill("#general_crew_call", "07:00"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_url(re.compile(r"day/(?!new)"), timeout=10_000)

    # A plain new day now continues: Day 3 on 2 October.
    page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']")
    page.wait_for_selector("#newDay", timeout=10_000); page.click("#newDay")
    expect(page.locator("#day_number")).to_have_value("3", timeout=10_000)
    assert page.locator("#shoot_date").input_value() == "2026-10-02"
    assert page.locator("#general_crew_call").input_value() == ""


def test_one_link_for_the_whole_shoot_opens_the_next_day_and_lists_the_others(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-32: a person's stable link opens their next shoot day (not a past one) and lets them reach the other days."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E mine {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Petr Malý"); page.fill("#crewDept", "Grip"); page.fill("#crewPos", "Key grip"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Petr Malý", timeout=10_000)

    for shoot_date, day_number, call in (("2026-01-05", "1", "06:00"), ("2099-01-06", "2", "07:15")):
        page.click("role=tab[name='Days']"); page.click("#newDay")
        page.wait_for_selector("#general_crew_call", timeout=10_000)
        page.fill("#shoot_date", shoot_date); page.fill("#day_number", day_number); page.fill("#general_crew_call", call)
        page.click("#publish")
        expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
        page.wait_for_url(re.compile(r"day/(?!new)"), timeout=10_000)
        page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']")
        page.wait_for_selector("#newDay", timeout=10_000)

    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crew", timeout=10_000)
    page.click("role=tab[name='Days']")
    page.locator("#days a.row").first.click()
    page.wait_for_selector("#personalLinks", timeout=10_000)
    link = page.locator("#personalLinks li", has_text="Petr Malý").get_by_role("link", name="Open").get_attribute("href")

    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#you", timeout=15_000)
    assert v.locator("#yourCall").inner_text().strip() == "07:15"  # day 2 in 2099, not the January day
    days = v.locator("#otherDays .day")
    expect(days).to_have_count(2)
    assert "Day 2" in v.locator("#otherDays .day.on").inner_text()
    v.locator("#otherDays a.day", has_text="Day 1").click()
    v.wait_for_selector("#you", timeout=15_000)
    expect(v.locator("#yourCall")).to_have_text("06:00", timeout=10_000)


def test_cast_member_with_a_days_times_appears_on_the_sheet_and_carries_to_rev_b(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-33: add an actor once, tick them on the day with status and times, the sheet shows the cast table; REV B keeps it prefilled."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E cast {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Cast']")
    page.wait_for_selector("#castName", timeout=10_000)
    page.fill("#castName", "Anna Geislerová"); page.fill("#castCharacter", "MARTA"); page.fill("#castPickup", "05:30"); page.click("#addCast")
    expect(page.locator("#cast")).to_contain_text("Anna Geislerová", timeout=10_000)
    expect(page.locator("#cast")).to_contain_text("MARTA")

    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.wait_for_selector("#castCalls .pcall", timeout=10_000)
    page.get_by_label("Anna Geislerová works today").check()
    expect(page.get_by_label("Pickup for Anna Geislerová")).to_have_value("05:30")  # usual pickup prefilled
    page.get_by_label("Status for Anna Geislerová").select_option("SW")
    page.get_by_label("Call for Anna Geislerová").fill("06:00")
    page.get_by_label("Make-up for Anna Geislerová").fill("06:15")
    page.get_by_label("On set for Anna Geislerová").fill("08:00")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#shareLink", timeout=10_000)
    link = page.locator("#shareLink").get_attribute("href")

    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#castTable", timeout=15_000)
    row = v.locator("#castTable tbody tr")
    expect(row).to_have_count(1)
    assert [c.strip() for c in row.locator("td").all_inner_texts()] == ["Anna Geislerová", "MARTA", "SW", "05:30", "06:00", "06:15", "08:00"]
    v.close()

    page.reload(); page.wait_for_selector("#castCalls .pcall", timeout=10_000)
    expect(page.get_by_label("Status for Anna Geislerová")).to_have_value("SW", timeout=10_000)
    page.fill("#general_crew_call", "07:00"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#castTable", timeout=15_000)
    expect(v.locator("#castTable tbody tr")).to_have_count(1)
    v.close()

    # Failure case: removing the actor drops their line; the sheet still loads.
    page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']")
    page.wait_for_selector("#newDay", timeout=10_000)
    page.click("role=tab[name='Cast']")
    page.wait_for_selector("#cast", timeout=10_000)
    page.get_by_label("Remove Anna Geislerová").click()
    expect(page.locator("#notice")).to_contain_text("removed from the cast", timeout=10_000)
    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#sheet.visible", timeout=15_000)
    assert v.locator("#castTable").count() == 0


def test_cancel_a_day_shows_the_banner_everywhere_and_restore_brings_it_back(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-34: cancelling asks first, then the sheet, the days list and the stable link all say CANCELLED; restore + publish puts it back."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E cancel {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#shareLink", timeout=10_000)
    link = page.locator("#shareLink").get_attribute("href")

    page.click("#cancelDayBtn")
    expect(page.locator("#confirmCancelDay")).to_be_visible()
    page.click("#confirmCancelDay")
    expect(page.locator("#notice")).to_contain_text("Day 1 cancelled", timeout=10_000)
    expect(page.locator("#cancelledBanner")).to_be_visible()
    assert page.locator("#cancelDayBtn").count() == 0

    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#sheet.visible", timeout=15_000)
    expect(v.locator("#cancelledBanner")).to_contain_text("CANCELLED")
    v.close()

    page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']")
    page.wait_for_selector("#days", timeout=10_000)
    expect(page.locator("#days li").first).to_contain_text("CANCELLED")
    expect(page.locator("#days li").first).to_contain_text("call 06:30")  # FR-43: the list says the call at a glance

    page.locator("#days a.row").first.click()
    page.wait_for_selector("#restoreDay", timeout=10_000)
    page.click("#restoreDay")
    expect(page.locator("#notice")).to_contain_text("back on", timeout=10_000)
    assert page.locator("#cancelledBanner").count() == 0
    page.fill("#general_crew_call", "07:00"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#sheet.visible", timeout=15_000)
    assert v.locator("#cancelledBanner").count() == 0
    assert v.locator("#crewCall").inner_text().strip() == "07:00"


def test_production_can_be_renamed_and_wrapped_from_settings(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-34: an owner renames the production and marks it wrapped; the list shows both."""
    _connect(page, frontend_url, api_url)
    name = f"E2E rename {uuid.uuid4().hex[:6]}"
    _create_production(page, name)
    page.click("role=tab[name='Settings']")
    page.wait_for_selector("#productionName", timeout=10_000)
    page.fill("#productionName", f"{name} (final)")
    page.select_option("#productionStatus", "wrapped")
    page.click("#saveProduction")
    expect(page.locator("#notice")).to_contain_text("is wrapped", timeout=10_000)
    expect(page.locator(".crumbs")).to_contain_text(f"{name} (final)")
    page.click("role=link[name='Productions']")
    page.wait_for_selector("#productions", timeout=10_000)
    row = page.locator("#productions li", has_text=f"{name} (final)")
    expect(row).to_contain_text("wrapped")


def test_ad_sees_who_opened_the_revision_and_can_nudge_the_rest(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-36: after publish the day screen says "REV A opened by 0 of 2"; a crew member opening their personal link live moves
    them across; the one who has not gets a WhatsApp nudge; REV B starts the count over. A cached (offline) open does not count."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E seen {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    for name, phone in (("Tomáš Novák", "777 123 456"), ("Eva Malá", "")):
        page.fill("#crewName", name); page.fill("#crewPhone", phone); page.fill("#crewDept", "Electric"); page.fill("#crewPos", "x"); page.click("#addCrew")
        expect(page.locator("#crew")).to_contain_text(name, timeout=10_000)
    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    expect(page.locator("#seenPanel")).to_contain_text("REV A opened by 0 of 2", timeout=10_000)
    expect(page.locator("#confirmedCount")).to_contain_text("0 of 2 confirmed")
    expect(page.locator("#unconfirmed li")).to_have_count(2)
    assert page.get_by_label("Nudge Tomáš Novák on WhatsApp").get_attribute("href").startswith("https://wa.me/420777123456?text=")
    assert page.get_by_label("Nudge Eva Malá on WhatsApp").count() == 0  # no phone, no broken link

    eva_link = page.locator("#personalLinks li", has_text="Eva Malá").get_by_role("link", name="Open").get_attribute("href")
    v = page.context.new_page(); v.goto(eva_link); v.wait_for_selector("#you", timeout=15_000); v.close()
    page.reload(); page.wait_for_selector("#seenPanel", timeout=10_000)
    expect(page.locator("#seenPanel")).to_contain_text("REV A opened by 1 of 2", timeout=10_000)
    # Opened is not confirmed: Eva stays on the list, now as having opened it, and Tomáš is chased first.
    expect(page.locator("#unconfirmed li").first).to_contain_text("Tomáš Novák")
    expect(page.locator("#unconfirmed li", has_text="Eva Malá")).to_contain_text("not confirmed")
    v = page.context.new_page(); v.goto(eva_link); v.click("#confirmBtn"); v.wait_for_selector("#confirmDone", timeout=15_000); v.close()
    page.reload(); page.wait_for_selector("#seenPanel", timeout=10_000)
    expect(page.locator("#confirmedCount")).to_contain_text("1 of 2 confirmed", timeout=10_000)
    expect(page.locator("#unconfirmed")).not_to_contain_text("Eva Malá")
    # FR-43: the days list carries the same count without opening the day.
    page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']")
    page.wait_for_selector("#days", timeout=10_000)
    expect(page.locator("#days li").first).to_contain_text("opened 1/2")
    page.locator("#days a.row").first.click(); page.wait_for_selector("#general_crew_call", timeout=10_000)

    page.fill("#general_crew_call", "07:00"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    expect(page.locator("#seenPanel")).to_contain_text("REV B opened by 0 of 2", timeout=10_000)


def test_day_screen_shows_a_collapsed_publish_history(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-50: a collapsed "History" list on the day screen shows one line per revision — who published it,
    when, what changed versus the one before, and how many crew opened it. REV A alone shows no diff."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E history {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.click("#historyPanel summary")
    history = page.locator("#historyList")
    entries = history.locator("> li")
    expect(entries.first).to_contain_text("REV A")
    expect(entries.first).to_contain_text("0 opened")
    expect(entries.first.locator(".history-changes")).to_have_count(0)  # REV A has nothing to diff against

    page.fill("#general_crew_call", "07:00"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    expect(entries).to_have_count(2)
    expect(entries.first).to_contain_text("REV B")  # most recent first
    b_changes = entries.first.locator(".history-changes")
    expect(b_changes).to_contain_text("Crew call")
    expect(b_changes).to_contain_text("06:30")
    expect(b_changes).to_contain_text("07:00")
    expect(entries.nth(1)).to_contain_text("REV A")


def test_crew_tab_sends_each_person_their_own_link_on_whatsapp(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-37: from the Crew tab the AD sends each person their stable link with one tap; no phone means no WhatsApp link;
    "Copy all links" copies one line per person."""
    _connect(page, frontend_url, api_url)
    name = f"E2E onboard {uuid.uuid4().hex[:6]}"
    _create_production(page, name)
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Tomáš Novák"); page.fill("#crewPhone", "+420 777 123 456"); page.fill("#crewDept", "Electric"); page.fill("#crewPos", "Gaffer"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Tomáš Novák", timeout=10_000)
    page.fill("#crewName", "Eva Malá"); page.fill("#crewPhone", ""); page.fill("#crewDept", "Camera"); page.fill("#crewPos", "AC"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Eva Malá", timeout=10_000)

    from urllib.parse import parse_qs, urlparse
    href = page.get_by_label("Send link to Tomáš Novák on WhatsApp").get_attribute("href")
    assert href.startswith("https://wa.me/420777123456?text=")
    text = parse_qs(urlparse(href).query)["text"][0]
    assert text.startswith("Hi Tomáš, here is your call sheet link for *" + name + "*:")
    assert "&me=" in text and "sheet=" not in text  # the stable link, not a day link
    assert page.get_by_label("Send link to Eva Malá on WhatsApp").count() == 0
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.click("#copyAllLinks")
    expect(page.locator("#notice")).to_contain_text("2 links copied", timeout=5_000)
    copied = page.evaluate("() => navigator.clipboard.readText()")
    assert copied.count("\n") == 1 and "Tomáš Novák · Electric: " in copied and "Eva Malá · Camera: " in copied


def test_tomorrow_at_a_glance_on_a_personal_link(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-42: through a personal link, day 1 says what tomorrow is (crew call, location); a gap says "day off";
    a cancelled tomorrow says cancelled, never its old call time."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E tmrw {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Locations']"); page.wait_for_selector("#locName", timeout=10_000)
    page.fill("#locName", "Studio B"); page.click("#addLocation")
    expect(page.locator("#locations")).to_contain_text("Studio B", timeout=15_000)
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Petr Malý"); page.fill("#crewDept", "Grip"); page.fill("#crewPos", "Key grip"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Petr Malý", timeout=10_000)

    def publish_day(date: str, number: str, call: str, with_location: bool) -> str:
        page.click("role=tab[name='Days']"); page.click("#newDay")
        page.wait_for_selector("#general_crew_call", timeout=10_000)
        page.fill("#shoot_date", date); page.fill("#day_number", number); page.fill("#general_crew_call", call)
        if with_location:
            page.click("#addScene")
            page.locator("#items .item").nth(0).get_by_label("Scene").fill("1")
            page.locator("#items .item").nth(0).get_by_label("Location").select_option(label="Studio B")
        page.click("#publish"); expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
        page.wait_for_url(re.compile(r"day/(?!new)"), timeout=10_000)
        url = page.url
        page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']"); page.wait_for_selector("#newDay", timeout=10_000)
        return url

    publish_day("2099-01-05", "1", "06:00", False)
    day2_url = publish_day("2099-01-06", "2", "07:15", True)
    publish_day("2099-01-08", "3", "08:00", False)  # 7 Jan is a day off

    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crew", timeout=10_000)
    page.click("role=tab[name='Days']"); page.locator("#days a.row").first.click(); page.wait_for_selector("#personalLinks", timeout=10_000)
    link = page.locator("#personalLinks li", has_text="Petr Malý").get_by_role("link", name="Open").get_attribute("href")

    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#tomorrow", timeout=15_000)
    expect(v.locator("#tomorrow")).to_have_attribute("data-kind", "day")
    expect(v.locator("#tomorrow")).to_contain_text("Day 2 · Tue 6 Jan 2099 · crew call 07:15 · Studio B")
    v.locator("#tomorrow a").click(); v.wait_for_selector("#tomorrow", timeout=15_000)
    expect(v.locator("#tomorrow")).to_have_attribute("data-kind", "off")
    expect(v.locator("#tomorrow")).to_contain_text("day off · next is Day 3")
    v.close()

    # Cancel day 2: from day 1 tomorrow now reads "cancelled", without 07:15.
    page.goto(day2_url)  # hash-only change: day 1's screen stays mounted until day 2 loads, so wait for day 2 itself
    expect(page.locator("#day_number")).to_have_value("2", timeout=10_000)
    page.wait_for_selector("#cancelDayBtn", timeout=10_000)
    page.click("#cancelDayBtn"); page.click("#confirmCancelDay"); expect(page.locator("#notice")).to_contain_text("Day 2 cancelled", timeout=10_000)
    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#tomorrow", timeout=15_000)
    expect(v.locator("#tomorrow")).to_have_attribute("data-kind", "cancelled")
    assert "07:15" not in v.locator("#tomorrow").inner_text()
    v.close()


def test_a_person_is_one_contact_across_productions(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-45: on a second production the name field offers people already in FilmRunner; picking one reuses the contact,
    so a phone corrected on production B shows on production A's sheet. Two same names with different phones stay two people."""
    _connect(page, frontend_url, api_url)
    tag = uuid.uuid4().hex[:6]
    _create_production(page, f"E2E share A {tag}")
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", f"Tom{tag} Novák"); page.fill("#crewPhone", "777 111 111"); page.fill("#crewDept", "Electric"); page.fill("#crewPos", "Gaffer"); page.check("#crewHod"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("777 111 111", timeout=10_000)
    page.click("role=tab[name='Days']"); page.click("#newDay"); page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#shareLink", timeout=10_000)
    sheet_a = page.locator("#shareLink").get_attribute("href")

    page.click("role=link[name='Productions']"); page.wait_for_selector("#newProduction", timeout=10_000)
    _create_production(page, f"E2E share B {tag}")
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crewName", timeout=10_000)
    page.locator("#crewName").press_sequentially(f"Tom{tag}")
    item = page.locator(".picker-item", has_text=f"Tom{tag} Novák")
    expect(item).to_be_visible(timeout=10_000)
    expect(item).to_contain_text("777 111 111"); expect(item).to_contain_text(f"E2E share A {tag}")
    item.click()
    assert page.locator("#crewPhone").input_value() == "777 111 111"
    page.fill("#crewPhone", "777 222 222")  # corrected here
    page.fill("#crewDept", "Electric"); page.fill("#crewPos", "Gaffer"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("777 222 222", timeout=10_000)

    v = page.context.new_page(); v.goto(sheet_a); v.wait_for_selector("#contacts", timeout=15_000)
    expect(v.locator("#contacts")).to_contain_text("777 222 222")  # one person, one number, every production
    v.close()

    # Same name, different phone, typed without picking: a second person, and the picker shows both.
    page.fill("#crewName", f"Tom{tag} Novák"); page.fill("#crewPhone", "777 333 333"); page.fill("#crewDept", "Grip"); page.fill("#crewPos", "Grip"); page.click("#addCrew")
    expect(page.locator("#crew li")).to_have_count(2, timeout=10_000)
    page.locator("#crewName").press_sequentially(f"Tom{tag}")
    expect(page.locator(".picker-item", has_text=f"Tom{tag} Novák")).to_have_count(2, timeout=10_000)


def test_copy_the_crew_from_another_production(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-46: "Copy crew from…" previews another production's crew with checkboxes (all on), skips
    anyone already on this crew, and never copies standing call times (they belong to a production)."""
    _connect(page, frontend_url, api_url)
    tag = uuid.uuid4().hex[:6]
    prod_a = f"E2E copy A {tag}"
    _create_production(page, prod_a)
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crewName", timeout=10_000)
    for name, dept, pos, hod, call in (
        ("Eva Dvořáková", "AD", "1st AD", True, "05:30"),
        ("Petr Malý", "Electric", "Best boy", False, ""),
        ("Tomáš Novák", "Electric", "Gaffer", True, ""),
    ):
        page.fill("#crewName", name); page.fill("#crewDept", dept); page.fill("#crewPos", pos)
        if call:
            page.fill("#crewCall", call)
        if hod:
            page.check("#crewHod")
        page.click("#addCrew")
        expect(page.locator("#crew")).to_contain_text(name, timeout=10_000)
    expect(page.locator("#crew li")).to_have_count(3)

    page.click("role=link[name='Productions']"); page.wait_for_selector("#newProduction", timeout=10_000)
    _create_production(page, f"E2E copy B {tag}")
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crewName", timeout=10_000)
    expect(page.locator("section[aria-label='Crew']")).to_contain_text("copy the crew from another production")

    page.click("#copyCrew")
    page.wait_for_selector("#copySource", timeout=10_000)
    page.select_option("#copySource", label=prod_a)
    preview = page.locator("#copyPreview li")
    expect(preview).to_have_count(3, timeout=10_000)
    expect(page.locator("#copyPreview input[type=checkbox]:checked")).to_have_count(3)
    expect(page.locator("#copyCrewSubmit")).to_have_text("Add 3 people")
    page.click("#copyCrewSubmit")
    expect(page.locator("#notice")).to_contain_text(f"Added 3 people from {prod_a}", timeout=15_000)
    expect(page.locator("#crew li")).to_have_count(3, timeout=10_000)
    hods = page.locator("#crew li", has_text="HoD")
    expect(hods).to_have_count(2)
    # Standing call times belong to a production, not the person: never copied.
    expect(page.locator("#crew li", has_text="Eva Dvořáková")).not_to_contain_text("call 05:30")

    # Copying the same production again shows every one of them as already here, none selected.
    page.click("#copyCrew")
    page.wait_for_selector("#copySource", timeout=10_000)
    page.select_option("#copySource", label=prod_a)
    preview = page.locator("#copyPreview li")
    expect(preview).to_have_count(3, timeout=10_000)
    expect(page.locator("#copyPreview li", has_text="already on this crew")).to_have_count(3)
    expect(page.locator("#copyPreview input[type=checkbox]:checked")).to_have_count(0)
    expect(page.locator("#copyCrewSubmit")).to_have_text("Add 0 people")
    expect(page.locator("#copyCrewSubmit")).to_be_disabled()


def test_import_the_crew_from_an_excel_file(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-55: a Czech production-office .xlsx (title row, Czech headers, HoD column, an odd phone, a name-only row)
    is detected, previewed with warnings, and imported; the file never leaves the browser."""
    import pathlib
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E xlsx {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crewName", timeout=10_000)
    page.click("#pasteCrew")
    page.set_input_files("#crewFile", str(pathlib.Path(__file__).parent / "fixtures" / "crew-12.xlsx"))
    page.wait_for_selector("#columnMap", timeout=15_000)
    assert page.locator("#col-name option:checked").inner_text() == "Jméno a příjmení"
    assert page.locator("#col-phone option:checked").inner_text() == "Telefon"
    assert page.locator("#col-department option:checked").inner_text() == "Oddělení"
    preview = page.locator("#pastePreview li")
    expect(preview).to_have_count(12)
    expect(preview.filter(has_text="Filip Rychlý")).to_contain_text("does not look like a number")
    expect(preview.filter(has_text="Karel")).to_contain_text("no position, using Crew")
    expect(preview.filter(has_text="Tomáš Novák")).to_contain_text("HoD")
    expect(page.locator("#importCrew")).to_have_text("Add 12 people")
    page.click("#importCrew")
    expect(page.locator("#notice")).to_contain_text("Added 12 people", timeout=30_000)
    expect(page.locator("#crew li")).to_have_count(12, timeout=10_000)
    expect(page.locator("#crew li", has_text="Eva Dvořáková")).to_contain_text("Režie · 1. AD · +420 777 111 222")
    expect(page.locator("#crew li", has_text="Eva Dvořáková")).to_contain_text("HoD")
    expect(page.locator("#crew li", has_text="Karel")).to_contain_text("Produkce · Crew")


def test_import_the_shooting_schedule_creates_planned_days(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-56: a Czech schedule .xlsx becomes three planned (draft) days with scenes, locations created by name, cast matched;
    the crew sees nothing until a day is published; publishing keeps REV A; a draft can be deleted; a second import skips existing dates."""
    import pathlib
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E sched {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Cast']"); page.wait_for_selector("#castName", timeout=10_000)
    page.fill("#castName", "Anna Geislerová"); page.fill("#castCharacter", "MARTA"); page.click("#addCast")
    expect(page.locator("#cast")).to_contain_text("MARTA", timeout=10_000)
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Petr Malý"); page.fill("#crewDept", "Grip"); page.fill("#crewPos", "Key grip"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Petr Malý", timeout=10_000)

    page.click("role=tab[name='Days']"); page.wait_for_selector("#scheduleFile", timeout=10_000)
    fixture = str(pathlib.Path(__file__).parent / "fixtures" / "schedule-3-days.xlsx")
    page.set_input_files("#scheduleFile", fixture)
    page.wait_for_selector("#schedulePreview", timeout=15_000)
    rows = page.locator("#schedulePreview li")
    expect(rows).to_have_count(3)
    expect(rows.nth(0)).to_contain_text("Day 1 · 2099-01-05 · 2 scenes · 42, 43")
    expect(rows.nth(2)).to_contain_text("Day 3 · 2099-01-08 · 1 scene · 7")
    expect(page.locator("#createImportedDays")).to_have_text("Create 3 days")
    page.click("#createImportedDays")
    expect(page.locator("#notice")).to_contain_text("3 planned days created as drafts", timeout=30_000)
    expect(page.locator("#notice")).to_contain_text("Cast not on the Cast tab yet: Jiří Mádl, Iva Janžurová")
    expect(page.locator("#days li")).to_have_count(3, timeout=10_000)
    expect(page.locator("#days li").first).to_contain_text("DRAFT")

    # Locations were created by name.
    page.click("role=tab[name='Locations']"); page.wait_for_selector("#locations", timeout=10_000)
    expect(page.locator("#locations")).to_contain_text("Nábřeží Troja"); expect(page.locator("#locations")).to_contain_text("Karlštejn")

    # The crew's stable link sees no planned day.
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crew", timeout=10_000)
    page.get_by_label("Copy link for Petr Malý").click()
    page.click("role=tab[name='Days']"); page.wait_for_selector("#days", timeout=10_000)
    page.locator("#days a.row").first.click(); page.wait_for_selector("#publishState", timeout=10_000)
    expect(page.locator("#publishState")).to_contain_text("Planned day, not published")
    assert page.locator("#personalLinks").count() == 0
    assert page.locator("#items .item").count() == 2
    assert page.locator("#items .item").nth(0).get_by_label("Scene").input_value() == "42"
    assert page.locator("#items .item").nth(0).get_by_label("Location").evaluate("el => el.selectedOptions[0].text") == "Nábřeží Troja"
    expect(page.get_by_label("Anna Geislerová works today")).to_be_checked()
    day1_url = page.url

    page.fill("#general_crew_call", "06:30"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    link = page.locator("#personalLinks li", has_text="Petr Malý").get_by_role("link", name="Open").get_attribute("href")
    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#you", timeout=15_000)
    assert v.locator("#revBadgeWrap").inner_text().strip() == "REV A"
    assert v.locator("#revReplaces").count() == 0
    assert v.locator("#otherDays").count() == 0  # days 2 and 3 are still drafts: invisible
    v.close()

    # Delete planned day 3; re-importing the file skips every date that exists.
    page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']"); page.wait_for_selector("#days", timeout=10_000)
    page.locator("#days a.row").nth(2).click(); page.wait_for_selector("#deleteDraftDay", timeout=10_000)
    page.click("#deleteDraftDay"); expect(page.locator("#notice")).to_contain_text("Planned Day 3 deleted", timeout=10_000)
    page.wait_for_selector("#days", timeout=10_000)
    expect(page.locator("#days li")).to_have_count(2, timeout=10_000)
    page.set_input_files("#scheduleFile", fixture); page.wait_for_selector("#schedulePreview", timeout=15_000)
    expect(page.locator("#schedulePreview li").nth(0)).to_contain_text("a day with this date exists, skipped")
    expect(page.locator("#createImportedDays")).to_have_text("Create 1 day")
    assert day1_url


def test_import_contacts_from_an_old_call_sheet_pdf(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-57: a Czech call sheet PDF is read (plain-text pass in the test API: no key), previewed with departments and phones,
    and added; the hospital line is not a person; nothing is created before "Add"."""
    import pathlib
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E pdf {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#crewName", timeout=10_000)
    page.click("#pasteCrew")
    page.set_input_files("#callSheetPdf", str(pathlib.Path(__file__).parent / "fixtures" / "call-sheet-cz.pdf"))
    page.wait_for_selector("#pdfHint", timeout=30_000)
    expect(page.locator("#pdfHint")).to_contain_text("6 people found")
    preview = page.locator("#pastePreview li")
    expect(preview).to_have_count(6)
    expect(preview.filter(has_text="Tomáš Novák")).to_contain_text("OSVĚTLOVAČI · Hlavní osvětlovač · 601 234 567")
    assert page.locator("#pastePreview", has_text="Nemocnice").count() == 0
    assert page.locator("#crew li").count() == 0
    page.click("#importCrew")
    expect(page.locator("#notice")).to_contain_text("Added 6 people", timeout=30_000)
    expect(page.locator("#crew li")).to_have_count(6, timeout=10_000)
    expect(page.locator("#crew li", has_text="Eva Dvořáková")).to_contain_text("REŽIE · 1. asistent režie · +420 777 111 222")


def test_czech_browser_gets_a_czech_editor_and_the_toggle_is_shared_with_the_sheet(browser, frontend_url: str, api_url: str) -> None:
    """FR-58: a cs-CZ browser reads the editor in Czech — productions, a day screen, the crew tab, notices;
    the toggle flips to English and the choice carries over to the crew's sheet (same storage key)."""
    ctx = browser.new_context(locale="cs-CZ", viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    _connect(page, frontend_url, api_url)
    assert page.locator("#createProduction").inner_text().strip() == "Založit"  # the intro shows only with no productions; the test DB has many
    _create_production(page, f"E2E cz {uuid.uuid4().hex[:6]}")
    expect(page.locator("#checklist")).to_contain_text("Produkce založena")
    assert [t.strip() for t in page.locator(".tabs a").all_inner_texts()][:4] == ["Dny", "Štáb", "Herci", "Lokace"]
    page.click("role=tab[name='Štáb']"); page.wait_for_selector("#crewName", timeout=10_000)
    assert page.locator("#addCrew").inner_text().strip() == "Přidat do štábu"
    page.fill("#crewName", "Tomáš Novák"); page.fill("#crewDept", "Osvětlovači"); page.fill("#crewPos", "Gaffer"); page.click("#addCrew")
    expect(page.locator("#notice")).to_contain_text("Tomáš Novák: přidán/a.", timeout=10_000)
    expect(page.locator("#crew")).to_contain_text("Osvětlovači · Gaffer")  # typed text untouched
    page.click("role=tab[name='Dny']"); page.click("#newDay"); page.wait_for_selector("#general_crew_call", timeout=10_000)
    assert page.locator("label[for='general_crew_call'] .label").text_content().strip() == "Sraz štábu"
    assert page.locator("#publishState").inner_text().strip() == "Zatím nevydáno. Koncept je uložený v tomto telefonu."
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Sraz štábu je povinný")
    page.fill("#general_crew_call", "06:30"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Vydáno REV A", timeout=15_000)
    page.wait_for_selector("#shareLink", timeout=10_000)
    link = page.locator("#shareLink").get_attribute("href")
    # the toggle: English in the editor, and the sheet follows
    page.click("#langToggle")
    expect(page.locator("#publishState")).to_contain_text("REV A is live")
    v = ctx.new_page(); v.goto(link); v.wait_for_selector("#sheet.visible", timeout=15_000)
    assert "Day 1 of 1" in v.locator("#dayLabel").inner_text()
    v.close(); ctx.close()


def test_actual_times_after_wrap_stay_with_the_production(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-65: after the day the AD writes first shot and wrap; the days list shows the wrap; the crew's sheet does not change
    and stays on REV A; the CSV export carries the row."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E actuals {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Days']"); page.click("#newDay"); page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#actuals", timeout=10_000)
    page.fill("#actual_first_shot", "08:12"); page.fill("#actual_wrap", "19:40"); page.fill("#actual_note", "Rain from 15:00")
    page.click("#saveActuals")
    expect(page.locator("#notice")).to_contain_text("Actual times saved", timeout=10_000)
    assert page.locator("#publishState").inner_text().strip() == "REV A is live."  # no revision from actuals
    link = page.locator("#shareLink").get_attribute("href")

    page.reload(); page.wait_for_selector("#actuals", timeout=10_000)
    expect(page.locator("#actual_wrap")).to_have_value("19:40", timeout=10_000)
    page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']"); page.wait_for_selector("#days", timeout=10_000)
    expect(page.locator("#days li").first).to_contain_text("wrap 19:40")
    with page.expect_download() as dl:
        page.click("#exportActuals")
    csv = open(dl.value.path(), encoding="utf-8-sig").read()
    assert csv.splitlines()[0] == '"day";"date";"crew_call";"first_shot";"lunch_out";"lunch_in";"wrap";"note"'
    assert '"08:12";"";"";"19:40";"Rain from 15:00"' in csv

    v = page.context.new_page(); v.goto(link); v.wait_for_selector("#sheet.visible", timeout=15_000)
    assert "19:40" not in v.locator("#sheet").inner_text() and v.locator("#revBadgeWrap").inner_text().strip() == "REV A"
    v.close()


def test_crew_filter_narrows_the_list_and_the_print_view_has_everyone(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-60/FR-61: the filter narrows the list (and says 2 of 5) while imports, links and the print stay on the whole
    crew; a filter matching nobody offers a way out; the printed list groups by department with phones and no links."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E filter {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']"); page.wait_for_selector("#pasteCrew", timeout=10_000)
    page.click("#pasteCrew")
    page.fill("#pasteCrewText", "Camera:\nMarek Sýkora, DoP, 603 555 010, HoD\nPetra Králová, 1st AC, 602 111 222\nElectric:\nTomáš Novák, Gaffer, 601 234 567\nLukáš Malý, Best boy\nSound:\nJana Tichá, Mixer, 604 222 333")
    page.click("#importCrew")
    expect(page.locator("#crew li")).to_have_count(5, timeout=20_000)
    expect(page.locator("#crewCount")).to_have_text("5 people")

    page.fill("#crewFilter", "camera")
    expect(page.locator("#crew li")).to_have_count(2)
    expect(page.locator("#crewCount")).to_have_text("2 of 5")
    page.fill("#crewFilter", "601234")  # phone digits
    expect(page.locator("#crew li")).to_have_count(1)
    expect(page.locator("#crew li").first).to_contain_text("Tomáš Novák")
    page.fill("#crewFilter", "nikdo takový")
    expect(page.locator("#noCrewMatch")).to_be_visible()
    assert page.locator("#crew li").count() == 0
    page.click("#clearCrewFilter")
    expect(page.locator("#crew li")).to_have_count(5)

    # Copy all links works on the whole crew even while filtered.
    page.fill("#crewFilter", "camera")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.click("#copyAllLinks")
    expect(page.locator("#notice")).to_contain_text("5 links copied", timeout=5_000)

    # The print view: a new window with everyone, grouped, phones, nothing personal.
    with page.context.expect_page() as popup:
        page.click("#printCrew")
    printed = popup.value
    printed.wait_for_load_state("domcontentloaded")
    html = printed.content()
    for name in ("Marek Sýkora", "Petra Králová", "Tomáš Novák", "Lukáš Malý", "Jana Tichá"):
        assert name in html, name
    assert "603 555 010" in html and "<td>—</td>" in html  # Lukáš has no number
    assert "tok-" not in html and "sheet=" not in html
    assert html.index("Camera") < html.index("Marek Sýkora") < html.index("Petra Králová")
    printed.close()


def test_ad_moves_a_scene_to_the_next_day_and_the_crew_sees_where_it_went(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-203: one action from the day screen; a new revision on both days; the crew's sheet links to the other day."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E move {uuid.uuid4().hex[:6]}")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#shoot_date", "2031-03-10"); page.fill("#general_crew_call", "07:00")
    page.click("#addScene"); page.locator("#items input.scene").first.fill("42"); page.locator("#items input.set").first.fill("River")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.click("#startNextDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.locator("#items li").first.get_by_role("button", name="Remove").click()
    page.fill("#shoot_date", "2031-03-11"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)

    page.click("role=link[name='" + page.locator(".crumbs a").nth(1).inner_text() + "']")
    page.wait_for_selector("#days", timeout=10_000)
    page.locator("#days a.row").first.click()
    picker = page.get_by_label("Move to another day: 42")
    picker.wait_for(timeout=10_000)
    picker.select_option(index=1)
    page.click("#moveSceneGo")
    expect(page.locator("#notice")).to_contain_text("Scene 42 moved to Day 2", timeout=15_000)
    expect(page.locator("#publish")).to_contain_text("REV C", timeout=10_000)

    link = page.locator("#shareLink").get_attribute("href")
    v = page.context.new_page(); v.goto(link)
    moved = v.locator("#revChanges li[data-field='scene_moved_out']")
    expect(moved).to_contain_text("Day 2", timeout=15_000)
    v.locator("#revChanges li[data-field='scene_moved_out'] a").click()
    expect(v.locator("#revChanges li[data-field='scene_moved_in']")).to_contain_text("Day 1", timeout=15_000)
    v.close()


def test_a_day_with_unpublished_edits_cannot_be_moved(page: Page, frontend_url: str, api_url: str) -> None:
    """Failure case: replanning publishes the server's copy, so it must not run past edits that have not gone out."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E move dirty {uuid.uuid4().hex[:6]}")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "07:00"); page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    expect(page.locator("#moveDay")).to_be_enabled(timeout=10_000)
    page.fill("#general_crew_call", "06:00")
    expect(page.locator("#moveDay")).to_be_disabled()

