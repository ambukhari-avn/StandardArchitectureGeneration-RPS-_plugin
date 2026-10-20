# Open questions

Each item has a default so work can continue. "Owner" is who can answer. Update the status when answered and move the answer into `decisions.md`.

## Waiting on the client

| # | Question | Why it matters | Default until answered | Owner | Status |
|---|---|---|---|---|---|
| Q1 | Instruction file (do and don't rules) | Holds rules we must not invent: when a BOQ category is drawn or skipped, allowed connections, naming. | Provisional file in `skills/arch/instructions.md`. | Client | A short style sheet (cable colours and four drawing rules) arrived 2026-10-20; the do and don't rules did not |
| Q2 | Cable colour standard | Legend and cables read from the cable table. | **Answered** (D22). Still open: dash style (none given, so solid) and the legend wording (we use the client's connection-type names). | Client | Mostly answered |
| Q29 | **ANSWERED 2026-10-20 (D24): the prompt says whether there is a DMZ and what is in it.** Earlier text: DMZ (Level 3.5) rules. *Partly answered by the WAVE example:* it shows a firewall between the enterprise layer and the DMZ, an OT firewall between the DMZ and Level 3, and inside the DMZ switches, a firewall manager, a redundant cybersecurity management server, network-attached storage, SIEM, Nozomi Guardian and Nozomi CMC, plus a text box of services (Active Directory, patch management, and so on). Still open: The instructions say "represented with boxes when needed" and mention an attached example architecture for L3.5. That example was not in the document or the folder. When is a DMZ needed? What boxes does it hold? Which connections must cross it? | Purdue validation and the DMZ layout. | Draw no DMZ unless the prompt or BOQ asks for one. | Client |
| Q30 | **ANSWERED 2026-10-20 (D25): the server's BOQ line says it is a VM.** Earlier text: VM contents. *Shown by the WAVE example:* a dashed "Virtual Environment" box with a note number ("Note 1") around the servers, and the note's contents as boxes in a side panel. Still open: "Whenever there is a VM, what is inside it is mentioned in a text box or on the side, as in the example." How does the BOQ say a server is a VM and what is inside it? | Needs the example architecture. | Not drawn until the example arrives. | Client |
| Q32 | **Example architecture (Project WAVE, SEWA) received 2026-10-20.** It answers part of Q29 and Q30 (see below) but its legend does not follow the colour standard: Ethernet is black, a *redundant* Ethernet cable is red, Hardwired is black. The standard says Ethernet blue and Fibre red. Which is right? Is "redundant Ethernet" a cable type of its own? | Cable table and legend. | The standard (D22). | Client |
| Q33 | **Mirrored sites.** The example draws a primary site (MCC) and a secondary site (DRC) side by side, each with the same layers, linked by "By SEWA" arrows. Is mirroring a layout feature the plugin must support, and how does a prompt or BOQ ask for it? | Layout engine needs a "repeat this set of groups" primitive. | Not supported until confirmed. | Client |
| Q34 | **Scope colouring and footer variant.** The example shades Avanceon scope grey and Client's scope pink (legend boxes), and its footer has "Client:", "Drawing No.", Prepared / Approved / Checked (that order) and a blank "Size", with no Contractor. Our footer has End User, Contractor, Prepared / Checked / Approved and Size A3. Which footer is standard, and is scope colouring required? | Footer form and legend. | Our footer (all files get the footer, D5); no scope colouring. | Client |
| Q35 | **Pictures versus boxes at Level 1.** In the example even a new RTU is a box ("New RTU", "Existing Schneider M340", "Existing Trango logger"), while servers, workstations, the laptop, firewalls, switches and gateways are pictures. The dataset has PLC and RTU pictures. Which rule decides? | D8 and D23. | Dataset picture where one exists, except field devices (D23). | Client |
| Q36 | **A3 legibility, again.** The example page is 35.2 x 20.3 in with 10 to 12 pt text. Fitted to A3 width (x0.47) that text becomes 3.8 to 5.6 pt, below the 6 pt floor. | Same conflict as Q6. | Q6 default. | Client |
| Q31 | **Rules removed from the first version.** An earlier draft told us to show DIN-rail or rack-mount switches, a patch panel in the networking layer, generic gateways, servers, firewalls, SCADA switches, and had an unclear "PLT" process item. The second version drops them. Are they gone, or just not restated? | Decides switch and gateway handling. | Draw whatever the BOQ and dataset give; unmatched items become boxes (D18). | Client |

## Decisions we need

| # | Question | Why it matters | Default until answered | Owner |
|---|---|---|---|---|
| Q3 | Dataset layer name to Purdue level mapping. The dataset has 11 layer labels: Network, SCADA / L2, HMI, PLC / L1, Field device, Sensor / L0, Field device / L0, Analyzer / L0, Sensor, Detector, Power. Only some carry L0, L1 or L2. | Bands come from this. Levels 3, 3.5 and 4 appear nowhere in the dataset. | Drafted in `data/purdue_map.json`. Five labels carry their own tag (L0, L1, L2). Sensor, Field device, Detector and Power are *proposed* as level 0; HMI and Network *inherit* the level of the group they are placed in. No dataset layer maps to levels 3, 3.5 or 4. | Client or user |
| Q4 | A BOQ item has no dataset entry. | Decides whether the run stops or draws something. | Now drawn as a rectangle with the BOQ wording, flagged in the Notes (decision D18, provisional). Reason: only 1 of Korangi's 17 BOQ headings matches a dataset component, so stopping on each would not work. Confirm, and confirm the text comes from the BOQ. | User |
| Q5 | Draw every Purdue level, or only the levels in use? | Changes the look of small diagrams. | Only levels in use. | User |
| Q6 | True A3 legibility versus showing everything. The approved KSU drawing is 41.9 x 16.4 in and the Murtiba pages are about 19 x 15 in, both labelled "A3". | A3 and "draw all 50 buildings" cannot both hold at 6 pt. | A3, one page, no collapsing. If it does not fit, fail with a report naming what did not fit. | Client |
| Q7 | Is collapsing identical items ("OWS-01 to OWS-06", "Building x50") allowed? | The overflow ladder's fourth step. | Off. | Client |
| Q8 | Which wins when the BOQ and an approved drawing disagree? KSU: drawing shows 4 switches and 4 FO panels, BOQ has 2 and 2; note says 47 buildings, BOQ and drawing show 50. | Decides what the validator enforces. | BOQ wins; differences are reported in the Notes. | Client |
| Q9 | A BOQ disagrees with itself: K20 D header says RIO panels 1-4, six are listed as priced items. | Same. | Draw the priced lines, warn in the Notes. | Client |
| Q10 | Typos inside BOQ names ("Utiltiy Warehouse", "Portable water pumping station", "GPW Server"). Copy as written or correct? | Spelling is a core requirement. | Copy as written and flag. | User |

## Information the BOQs do not carry

| # | Question | Default |
|---|---|---|
| Q11 | Network topology and which device connects to which. No BOQ states it. | Ask in the question flow; any assumed connection is marked in the Notes. |
| Q12 | Redundancy: how it is shown (KSU: two FO links per building, pairs of switches). | Ask in the question flow. |
| Q13 | Room and area grouping (control room versus server room). Engineering knowledge, not BOQ content. | Ask, or take it from the instruction file. |
| Q14 | KSU building names and IDs. The BOQ says "list attached in Appendix". | Needs the appendix as an input. |
| Q15 | Murtiba has four pages (Rockwell and Honeywell, SIL-2 and SIL-3). Is a run one variant on one page? | One variant per run. |
| Q27 | **Label wording.** Dataset titles are generic ("Compact PLC", "Safety PLC", "HMI panel"; several brands share one title). Engineers' drawings often print the model ("Rockwell L81E", "S7-1200 G2 CPU 1214C"). Should the label be the title only, or title plus part number? | Decides how a picture and its label read. | Title only. | Client |
| Q28 | **Labels that contain a note.** "Rack server (use 2 stacked for redundant pair)" is used verbatim as a label. Is the bracket part of the label or an instruction? | Spelling and appearance. | Verbatim. | Client |
| Q16 | Which footer variants must be supported besides the Avanceon one (Khobar uses the client's own title block)? | Avanceon footer on every page (client decision). |

## Housekeeping

| # | Item | Owner |
|---|---|---|
| Q17 | **Visio check outstanding.** None of our `.vsdx` files has been opened in real Visio yet: footer demo, KSU spike output, repaired ChatGPT file. Until one opens cleanly, D2 is unproven. | User |
| Q18 | The FADI DAYA BOQ has no matching diagram, and the SARAYA `.vsdx` has no BOQ. Are the counterparts available? | User |
| Q19 | The dataset's Read me says pictures came from Google image results. Is internal use inside Avanceon diagrams confirmed? | Client |
| Q20 | Held-out set for evaluation: Murtiba. KSU was studied in detail during the spike, so it is no longer a clean hold-out. Rules must not be written from Murtiba. | Me |

## Platform: ChatGPT (changed 2026-10-20)

| # | Question | Why it matters | Default until answered | Owner |
|---|---|---|---|---|
| Q40 | **Which ChatGPT form is "the plugin"?** Options seen in third-party sources (OpenAI's own help pages returned 403 to me, so none of this is verified): (a) a custom GPT with Code Interpreter, a short instruction text and uploaded knowledge files, running our scripts in its sandbox; (b) an app built with the Apps SDK, which needs an MCP server hosted over HTTPS and a review before public use. | Decides packaging, how files reach the user, what limits apply, and whether anything must be hosted. | Keep the Python core unchanged; build nothing ChatGPT-specific until this is answered. | User |
| Q41 | **Limits to confirm before packaging a custom GPT** (secondhand figures only): about 20 knowledge files per GPT; instructions about 4,000 tokens; whether Code Interpreter can unzip an uploaded bundle and run Python from it; whether it can hand a generated .vsdx back as a download. Our repo is many files, so it would ship as one zip. | Whether the design fits at all. | Ship scripts, data and icons as a single zip. | Me, once Q40 is answered |
| Q42 | **Which model writes the spec?** The "Claude produces the spec" step becomes "ChatGPT produces the spec". The spec schema, validator and instruction file must be written for it, and its output checked by the validator before anything is drawn. | Phase 4 design. | Model-neutral spec; the validator is the gate. | Me |
| Q43 | **Instruction text.** `skills/arch/instructions.md` and the footer-form wording refer to Claude and slash commands. They need rewriting for a GPT's instruction field (short, so the long rules must live in a knowledge file). | Phase 6. | Provisional text stays until Q40. | Me |

## Claude plugin format (checked 2026-10-19; superseded by the move to ChatGPT, kept for reference)

| # | Item | Default |
|---|---|---|
| Q21 | **Command name.** A plugin skill is invoked as `/<plugin>:<skill>`, so ours is `/arch:arch`. The docs do not say how to get a bare `/arch` from a plugin. | Keep `/arch:arch`. Choose the final plugin name before release. |
| Q22 | **Team install layout.** The docs show a marketplace pointing at `./plugins/<name>`; a single-plugin repo with the plugin at the repo root is not shown. | Test with `--plugin-dir` now; decide the layout in task 6.5. |
| Q23 | **Asking questions.** The official docs do not document `AskUserQuestion` for plugin skills, and community reports say it can return empty answers. | One chat form per round (as built for the footer), then one script call. |
| Q24 | **Manifest author.** `claude plugin validate` warns that no author is set. | Left unset until you choose a name. |
| Q25 | **Python on Windows.** The docs do not say whether to call `python` or `python3`. | `python` (works on this machine); test again on the target machine. |
| Q26 | **Version pinning.** If `version` is set in `plugin.json`, teammates only get updates when it is bumped. | Bump on every release. |

## Seen in the dataset review (no action unless it causes a problem)
- Row 37 is labelled "Industrial switch, CISCO" but its picture is a limit switch with a roller arm (visible in the catalogue page). Rows 31 and 33 look doubtful.
- 23 distinct components have a picture. 20 rows name an image file that is not embedded and are drawn as boxes. (An earlier count of 22 pictured rows and 34 such rows was wrong; the importer's report is the reference.)
- Row 35's picture is anchored on row 34 but sits in row 35; stacked pictures under rows 2, 16 and 18 are not used (D17).
- Components in the supplied BOQs with no dataset entry (sounder, beacon, manual call point, open-path detector, GPS clock, SmartX AS-P, Modicon Edge I/O NTS; no Rockwell or Honeywell parts). Under D8 these become rectangles, or Q4 applies.
- The dataset has no ids, aliases or label positions. Ids are generated by the importer; aliases are added only after confirmation (D21).
- Match coverage on the real BOQs (`scripts/match_report.py`): Kemari 55 distinct items and Korangi 64, none matched at line level; at heading level Korangi matches 1 of 17 ("Flame Detectors"). The dataset holds generic types; the BOQ lines are model-specific commercial items.

## Seen while building Phase 3 (no action unless it causes a problem)
- The Korangi workbook is a copy of Kemari: its BOQ heading still reads "PRL - Kemari".
- Murtiba quantities such as 8.66667 (18 lines in `BOQ Rockwell SIL2`) cannot be real counts; they are rounded up and noted when drawn.
- Murtiba sheets carry a lot of zero-quantity lines (66 in `BOQ Rockwell SIL2`, 186 in `BOQ Rockwell SIL3 ALTERNATE`): options not taken. They are listed in the BOQ report, not drawn.
- The KSU zone ("New Buildings") is lost from the parents of `All Instruments` and similar sections that follow it; the heading outline still holds the full order, so nothing is lost for a reader of the outline.
- Which Murtiba sheet is "the BOQ" depends on the variant (Rockwell or Honeywell, SIL-2 or SIL-3); the run must say which, and `boq_report.py --list` shows the candidates.

