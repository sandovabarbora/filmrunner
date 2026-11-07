# FilmRunner pro AD: prvních 30 minut a první natáčecí den

Pro asistenta režie nebo produkční, kdo píše dispozice. Názvy tlačítek jsou přesně tak, jak je vidíte v aplikaci v češtině (přepínač jazyka je vpravo nahoře: „English / Čeština“). Anglická verze je níže.

Stav k 22. 9. 2026. Co tu není slíbeno, to aplikace neumí. Co je „zatím neověřeno na telefonu“, je poctivě v `docs/research/pilot-readiness-2026-09.md`.

## Než začnete (10 minut, jednou za produkci)

1. Otevřete `https://sandovabarbora.github.io/filmrunner/editor.html`, zadejte e-mail, přijde vám kód. *(Přihlášení kódem čeká na nastavení odesílání e-mailů; do té doby vás přihlásí zakladatelka na schůzce.)*
2. **Produkce → „Založit“**: název produkce.
3. **Štáb**: máte tři cesty, vyberte jednu.
   - **„Vložit seznam…“** — zkopírujte lidi z tabulky nebo z WhatsAppu; řádek „Kamera:“ nastaví oddělení pro řádky pod ním, „HoD“ označí vedoucího.
   - **„…nebo importovat soubor (.xlsx, .csv)“** — Excel z produkce; aplikace pozná sloupce Jméno / Telefon / Oddělení / Pozice, když ne, vyberete je ručně.
   - **„…nebo starý call sheet v PDF“** — z minulé produkce; aplikace z textu vytáhne lidi, vy je zkontrolujete a potvrdíte „Přidat N lidí“.
   Kdo už ve FilmRunneru byl na jiné produkci, nabídne se při psaní jména — jeden člověk, jedno číslo, všude.
4. **Lokace**: název a adresu; adresa se sama převede na mapu, aby fungoval východ/západ slunce, počasí a nejbližší nemocnice. Poznámka k parkování se vytiskne na dispozice.
5. **Herci**: jméno, postava, obvyklé vyzvednutí. Časy na den nastavíte až u dne.
6. Prohlédněte si s lidmi stránku **Soukromí** (odkaz je u importů): co ukládáme, kde, kdo to vidí.

## Večer před prvním dnem (10 minut)

1. **Dny → „+ Nový den“** — nebo **„Importovat harmonogram… (.xlsx, .csv)“**, když máte harmonogram v Excelu či z Movie Magic: vzniknou **plánované dny**, štáb je nevidí, dokud je nevydáte.
2. Vyplňte **Sraz štábu** (povinné), **Začátek natáčení**. Východ, západ a počasí se doplní samy z první lokace, když je necháte prázdné.
3. **Osobní srazy**: jen pro lidi, kteří mají jiný čas než štáb — „Osobní sraz pro…“, vyberte člověka. Přenáší se do dalšího dne.
4. **Herci**: zaškrtněte, kdo pracuje, status (W/SW/WF/SWF/H/R), vyzvednutí, maska, na place.
5. **Harmonogram**: „+ Přidat scénu“ — obraz, INT/EXT, DEN/NOC, motiv, osminy stran, lokace.
6. **„Vydat“**. Odejde REV A.
7. Pošlete lidem jejich odkaz: **Štáb → u každého „WhatsApp“** (otevře chat s předepsanou zprávou), nebo **„Kopírovat všechny odkazy“** do tabulky. Každý odkaz je osobní, na celé natáčení — vždy otevře další natáčecí den toho člověka a jeho vlastní sraz. Neposílejte odkazy do skupiny; do skupiny pošlete **„Poslat den jako text“** ze stránky dne.

## Ráno a během dne

- Na stránce dne vidíte **„REV A otevřelo 12 z 40“** a jména těch, kdo ještě ne — u nich **„pošťouchnout“** otevře WhatsApp s připomínkou a jejich odkazem.
- Změna času nebo scény: upravte a **„Vydat REV B“**. Všichni s odkazem vidí novou verzi; kdo má zapnutá upozornění, dostane push; na dispozicích stojí „REV B nahrazuje A, vydáno 06:12“ a co se změnilo.
- Den se nekoná: **„Zrušit tento den…“** → potvrdit. Dispozice říkají ZRUŠENO, telefony s upozorněním dostanou zprávu. Obnovit jde „Obnovit den“ + vydání revize.
- Zítřek: **„Založit 2. den z tohoto“** zkopíruje sraz, štáb, osobní srazy i scény; změníte datum a scény.
- Po wrapu: **„Skutečné časy“** (první záběr, oběd, wrap, poznámka) → „Uložit skutečné časy“. Štáb to nevidí; v seznamu dnů je „wrap 19:40“ a **„Export skutečných časů (CSV)“** pro produkci.
- Papír: **„PDF“** na stránce dne otevře tiskovou verzi s QR kódem zpět na živé dispozice.

## Tři věci, které se pokazí první, a co s nimi aplikace dělá

1. **Na place není signál.** Dispozice, které si člověk jednou otevřel, zůstávají v telefonu a otevřou se i bez signálu — s poctivým řádkem „Offline · zobrazena kopie uložená …“. Nikdy tiše neukáže starou verzi jako živou. *(Ověřeno v testech; na reálném iPhonu čeká na kontrolu zakladatelky.)*
2. **Špatné číslo u člověka.** Opravíte ho ve **Štáb → Upravit**; propíše se hned na všechny dispozice i do jiných produkcí, kde ten člověk je. Když jste offline, změna se uloží v telefonu jako „neuloženo“ a odešle se, až budete online.
3. **Pozdní změna.** Vydáte REV B; kdo ji neotevřel, je vidět jménem a jde ho pošťouchnout přes WhatsApp. Push upozornění dostanou jen ti, kdo si je na svém odkazu zapnuli — počítejte s tím, že první den to bude menšina.

Kontakt: sandovabarb@gmail.com.

---

# FilmRunner for the AD: the first 30 minutes and the first shoot day

For the assistant director or coordinator who writes the call sheet. Button names are as they read in the Czech editor above; the English ones are the same words in English (language toggle top right).

## Before you start (10 minutes, once per production)

1. Open the editor, enter your e-mail, a code arrives. *(Code sign-in is waiting for the e-mail sending setup; until then the founder signs you in at the meeting.)*
2. **Productions → Create**: the production's name.
3. **Crew**: three ways, pick one — **Paste a list…** (from a spreadsheet or WhatsApp; a "Camera:" line sets the department, "HoD" marks a head), **…or import a file (.xlsx, .csv)** (columns detected, fixable by hand), **…or an old call sheet PDF** (contacts read from the text, you confirm). People already in FilmRunner from another production are offered as you type — one person, one number, everywhere.
4. **Locations**: name and address; the address becomes a map position for sunrise/sunset, weather and the nearest hospital. Parking notes print on the sheet.
5. **Cast**: name, character, usual pickup; times per day come later.
6. Show people the **Privacy** page (linked next to the imports).

## The evening before day 1 (10 minutes)

1. **Days → + New day**, or **Import schedule… (.xlsx, .csv)** from Excel or Movie Magic: planned days, invisible to the crew until published.
2. **Crew call** (required), **Shooting call**; sunrise, sunset and weather fill in from the first location when left blank.
3. **Personal calls** only for people whose call differs; they carry over to the next day.
4. **Cast**: tick who works, status, pickup, make-up, on set.
5. **Schedule**: + Add scene.
6. **Publish** → REV A.
7. Send everyone their link: **Crew → WhatsApp** per person, or **Copy all links**. Each link is personal and lasts the whole shoot. Never into the group; the group gets **Send day as text** from the day screen.

## Morning and during the day

- The day screen says **REV A opened by 12 of 40** and who has not; **nudge** opens WhatsApp with their link.
- A change: edit, **Publish REV B**; the sheet says "REV B replaces A, issued 06:12" and what changed; push to those who enabled it.
- Day off: **Cancel this day…**; **Restore the day** puts it back on and tells the crew.
- Tomorrow: **Start Day 2 from this one**.
- After wrap: **Actual times** → Save; **Export actual times (CSV)** on the days list.
- Paper: **PDF** on the day screen, with a QR code back to the live sheet.

## The three things that go wrong first

1. **No signal on set** — a sheet opened once stays on the phone and opens offline with an honest "Offline · showing the copy saved …" line; never a stale copy shown as live. *(Verified in tests; real-iPhone check pending with the founder.)*
2. **A wrong number** — fix it under Crew → Edit; it changes on every sheet and in other productions at once; offline edits queue as "not saved" and sync later.
3. **A late change** — publish REV B; those who have not opened it are listed by name and one tap away on WhatsApp. Push reaches only those who enabled it on their link — expect a minority on day one.

Contact: sandovabarb@gmail.com.
