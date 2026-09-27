# Readability rules and physical comparison

The selected daytime design is **E typography with I’s three-card layout**, confirmed by the user on the physical 480 × 800 Garden Ink panel. The dated notes below retain the trial history. The two user-supplied photographs on 27 September 2026 are visual evidence, not instructions or a substitute for a controlled comparison.

## What the photographs and renderer show

The large title and featured common name have a clear hierarchy. Small italic scientific names have broken-looking strokes in the photographs, and the four-column row makes the common names, scientific names and times compete in narrow spaces. Photography, lighting and the panel can all contribute; the photos alone cannot identify the cause.

The actual renderer uses 13 px serif daily names, 10 px italic scientific names, 10 px times and 9–10 px footer qualifications. Its generic text fitting can shrink content to 10 px. The first photo's paired totals give a clearer association between numbers and their reporting period than the older footer in the second photo. Preserve that grouping.

## Rules to design against

1. Render type at native resolution, in solid black on white. Keep text out of illustration dithering and do not resize a finished page. Judge the PNG at 100% and then on physical pigment.
2. Use a small, explicit set of semantic styles. The user selected **E: DejaVu Sans Regular with direct monochrome rendering** on 27 September 2026, from a physical four-way comparison. Use this for common/scientific names, dates, observations, counts and explanations in the layout trials. Retain the existing editorial serif masthead as a separate title treatment. Use real bold faces sparingly for section labels or warnings.
3. Trial 14 px as the minimum for meaningful supporting text, 18 px for daily common names, 24–28 px for the featured name, 32–39 px for the title, and 28–32 px for totals. These are panel-pixel hypotheses, not print-point accessibility standards or proven reading-distance guarantees.
4. Never shrink essential information to fit. Wrap at word boundaries; if it still will not fit, allocate another line or simplify the composition. Keep common names, health warnings, report bounds and incomplete/cached qualifications intact. Shorten a secondary species list by showing fewer names and an explicit “+N more”.
5. Keep body text in sentence case. Use short section headings and ordinary spacing; reserve spaced capitals for the optional small brand identifier. Avoid decorative italic captions that consume space needed for observations.
6. Scientific names use upright DejaVu Sans in the selected E treatment. This deliberately departs from the previous italic convention to prioritise the user's physical readability assessment. Never reduce scientific names to preserve a four-column grid.
7. Left-align names and explanations. Use stable baselines/row steps, at least 4 px between wrapped text lines, and 8–12 px between different information groups. Separate groups with whitespace and restrained 1 px rules, not a line around every object.
8. Keep numbers next to their labels and group them by Today / Report hour. Preserve thousands separators, “+” partial totals, unavailable values and clear historical time wording. Do not abbreviate away date or timezone information at midnight or DST boundaries.
9. Status must use text as well as colour. Keep the explanation “Acoustic IDs, not individual birds” readable; detections are not visits, songs or individual animals. A sample page must visibly say SAMPLE.
10. Spend space on information before decoration. For the next full-layout trial, retain the principal bird illustration and paired totals, remove redundant decorative captions, and compare two wider daily-species cards with the current four narrow cards. Fewer visible cards must not change aggregate counts or imply there were fewer species.
11. Evaluate the font and rasterization together at the intended native size before tuning the final size scale. Inspect repeated straight stems, curves, counters, digits and punctuation. Do not assume thresholding smoothed type produces the same glyphs as direct monochrome drawing. More uniform strokes may be thinner and less legible at a distance; require physical feedback before choosing a method.

The general principles of clear fonts, left alignment, restrained bold and avoiding small italic/all-capital blocks are supported by the [Home Office typography guidance](https://design.homeoffice.gov.uk/accessibility/page-structure/layout-typography) and [GOV.UK accessible-document guidance](https://www.gov.uk/guidance/publishing-accessible-documents). Their web reflow and print-point requirements do not directly specify pixels for this fixed-resolution panel. Physical comparison decides the project choices.

## Trial 1: text treatment

Render with `.venv/bin/python tools/readability_trial.py`. The output is a native 480 × 800 black/white specimen using the production text rasterizer and its threshold. No station, GPIO or artwork generation is involved in rendering.

| Choice | Common names | Scientific names | Supporting text |
|---|---|---|---|
| A | Serif, 13 px | Serif italic, 10 px | Sans, 10 px |
| B | Serif, 18 px | Serif italic, 14 px | Sans, 14 px |
| C | Sans bold, 18 px | Sans upright, 14 px | Sans, 14 px |

All blocks contain identical words, have the same width and row positions, and appear on one physical refresh. A reproduces the current small-card type sizes, not the entire existing layout. B and C are overall treatments: this is not an experiment that isolates font family from weight or size. Their supporting text is deliberately identical.

Stand at the usual viewing distance in ordinary lighting. Read the names, scientific-name line, observation time and incomplete-scan note. Report the easiest block, the hardest line, approximate distance and whether any line needs leaning closer. Preference alone is insufficient: check that the small text can actually be read. If B and C are close, repeat with positions reversed and compare just the differing names.

## Trial 2: the complete composition

After feedback, use the chosen text treatment in two real report layouts with identical frozen observations and existing artwork. Compare two wider daily cards against three narrower cards, showing the alternatives sequentially with the persisted panel guard. The originally proposed four-column comparison is superseded: a 102 px column cannot fit even some single-word common names at the selected 18 px size, so retaining it would require changing the size or breaking names mid-word. Keep totals and coverage semantics identical. Do not declare a winner before physical feedback.

Inspect normal, long-name, missing-art, quiet/empty, unavailable/cached, paused, partial, midnight and DST renders. Include any additional locally installed layouts before applying a shared typography change. Check bounds, text collisions and all qualifications at 480 × 800. Mocked checks do not certify physical readability.

## Live trial discipline

The user explicitly requested a live comparison. Verify the deployed source matches the inspected guard/driver, back up display metadata and the previous frame privately, stop only the display service cleanly, and acquire its existing hardware lock. Use its saved 180-second push guard and persist the new attempt before GPIO access. Do not reset counters, alter the driver, read credentials, contact paid-generation APIs or touch the artwork ledger. Keep the cached observation snapshot and night-edition state intact.

Arrange a transient automatic service restart before pausing the display, so a disconnected session cannot leave reporting stopped indefinitely. Keep the comparison on screen for roughly 20 minutes, then let the ordinary service generate a fresh report using the same saved guard. Record hardware completion separately from the user's still-pending readability judgement.

## Feedback and controlled follow-up — 27 September 2026

The user found both B and C legible, with C more legible, but noticed uneven stroke thickness. Their close and distant photographs show the actual comparison. The supporting lines in B and C are pixel-identical in the source PNG: that preference does not establish that C's supporting-text font differs from B's. Their common/scientific name treatments do differ.

Investigation reproduced an uneven-stem example before the panel: DejaVu Sans Regular at 14 px, rendered to an antialiased mask and thresholded at 112 as in `Page.text`, gives capital H a two-pixel left stem and a one-pixel right stem. Drawing the same text with Pillow `ImageDraw.fontmode = '1'` gives one-pixel stems on both sides. This establishes a software contribution; it does not quantify any further effects from pigment or photography. Serif faces also have intentional stroke contrast.

[Pillow's ImageDraw documentation](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html#PIL.ImageDraw.ImageDraw.fontmode) specifies `1` for drawing without antialiasing and `L` with antialiasing. This follow-up uses direct monochrome drawing, not a different threshold on the same smoothed mask.

Render the follow-up with `.venv/bin/python tools/readability_font_trial.py`. It is a native 480 × 800, black/white, offline specimen. It uses locally installed DejaVu Sans and Noto Sans; the pre-rendered PNG requires no new fonts on the Pi.

| Choice | Font | Rendering |
|---|---|---|
| D | DejaVu Sans Regular | Current grayscale mask, threshold 112 |
| E | DejaVu Sans Regular | Direct monochrome |
| F | Noto Sans Regular | Current grayscale mask, threshold 112 |
| G | Noto Sans Regular | Direct monochrome |

Every block has identical words, regular weight, upright scientific names, 18 px common names and 14 px supporting text. Compare D/E or F/G to isolate rendering; D/F or E/G to compare families under the same rendering method. Equal nominal size does not guarantee equal apparent size or x-height across fonts. Labels outside the specimen retain existing production styling.

Choose the easiest block at the normal viewing distance, then inspect `HHH nnn mmm`, `Il1` and `0O` up close. The monosized stem example alone is not a reason to choose thinner text if it becomes harder to read. This test isolated the rendering choice before the full-composition trial.

The user subsequently selected **E as the clear winner**, with a photograph of the physical result. This settles the font/rendering choice for the following layout trials; it does not yet approve a final layout or certify every size, face or night-page arrangement. The trial tools are offline comparisons and do not change production settings.

## Full-layout specimens H and I

Render using `.venv/bin/python tools/readability_layout_trial.py`. Both pages use the same frozen, explicitly labelled sample snapshot for 27 September 2026, report interval 11.01am–12.01pm BST. No live station data or paid artwork is requested. The normal report snapshot is left intact on the Pi.

- **H:** two wider daily-species cards, 204 px of content per card.
- **I:** three narrower daily-species cards, 132 px of content per card.

Both use direct monochrome DejaVu Sans Regular for data, 18 px daily common names and 14 px supporting information. The featured name is 24 px; the retained serif masthead is 34 px. Bold is restricted to section headings. Both have the same main Blackbird illustration, hourly other-species list and paired Today / Report hour totals. Their daily subset headings say how many other frequent species are illustrated; aggregate species/detection counts remain identical. Scientific names are upright; the report interval is stated once above the main illustration instead of repeated in the footer. This releases room for 14 px count labels and the acoustic-identification qualification.

The tool checks all text runs for overlap and page bounds without shrinking or truncating. Both native renders were visually inspected. The fixture is intentionally a complete, normal daytime sample: this tool refuses unsupported geometry rather than pretending to be a replacement for the production renderer. It is not a substitute for production regression coverage of long names, partial/offline states and DST/midnight.

The live sequence shows H first, then I after the installed 180-second start-to-start guard. The feedback question is whether I's third species remains as comfortable to read as H's two wider cards. If neither works at the normal viewing distance, adjust spacing and hierarchy before reducing type sizes.

## Selected production design

The user chose the layout with three cards after replaying H and I. The production daytime renderer now follows I: direct monochrome DejaVu Sans, 18 px daily names, 14 px supporting text, upright scientific names and paired totals. Long names wrap and reclaim illustration space. For exceptionally long accepted source labels, the row falls back to two or one wider cards; the heading states how many species are shown. Artwork-refresh tracking uses the same selection. Aggregate counts are never reduced to match the illustrated subset.

The report interval appears once above the content. In gallery mode the day starts at local midnight and the displayed trailing-hour bounds explicitly qualify the report-hour totals. Cached, paused and incomplete qualifications retain two readable footer lines. Unknown totals remain unavailable; no clock or paid-generation changes are introduced.

Validation of the complete local installation included 329 offline tests and 74 native renders. The standalone readability commit passed all 256 offline tests against the published repository. Regression coverage includes consistent stems, three-card artwork tracking, historical-time qualifications, unavailable/partial totals and long-station-name overflow. The selected layout completed a successful physical panel update. Private deployment logs and backups are intentionally kept outside Git.

## All-page review — 27 September 2026

This follow-up applies the selected E typography to the gallery and all three after-dark editions. It is prepared on `codex/readability-all-pages` in an isolated worktree. The night implementation was initially snapshotted from existing local work, then the readability change was rebased onto the published night feature. The user approved all 24 previews and authorised commit, GitHub push and device deployment on 27 September 2026.

- Supporting labels, dates, chart axes, legends and operational messages use at least 14 px direct monochrome DejaVu Sans. Common names use 18 px, featured names 24 px, and the serif masthead remains 34 px. Scientific names are upright. Chart values and totals use regular sans; bold is reserved for short headings and warnings.
- The gallery normally shows six species in two columns. Long accepted names receive taller or wider cards, with the displayed subset stated explicitly. Sparse galleries use the available space. The artwork watcher uses exactly the same selection; aggregate counts remain unchanged.
- Night pages reserve room for independent unavailable, cached, paused and incomplete qualifications. Report bounds retain dates and timezones when required. Every sample identifies itself in the masthead, including samples of failure states.
- Rhythm charts thin numeric/axis annotations for long nights without removing bins. Unknown bins always retain a marker and medians never bridge unknown comparison intervals. Owl markers have their own row; the caption and legend occupy separate lines. Larger axis numbers reserve their actual width.
- History has a separate count column; unsupported nights remain gaps. Owl panels wrap both common and scientific names. Long metadata takes space from the upper composition instead of crossing the footer or shrinking type.
- The owl journal retains bat and owl illustrations, larger observation text, and a readable compact chart. The no-owl variant uses the bat illustration and explicitly identifies the owl artwork as a field guide.

Run `python tools/readability_pages.py` with the workstation virtual environment to create 24 deterministic 480 × 800 samples under `local/previews/readability-all-pages/`. The twelve paired sheets paste the native frames without resampling. `manifest.json` lists every page, and `checks.json` records minimum sizes, fitting, margins and text collisions. The samples cover normal journal/gallery/night editions, no owl, quiet/empty, missing art, unavailable/cached/paused/partial, midnight, DST, long nights and long names. Tests additionally exercise large bat totals and simultaneous maximum-length common/scientific labels. This is offline rendering verification, not physical-panel approval.
