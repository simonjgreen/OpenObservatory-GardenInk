# Visual direction: an hourly field journal, not a clock

## Current hierarchy

1. Quiet `OPEN OBSERVATORY` identifier, large serif `The garden`, report date and botanical motif.
2. Restrained health note. A genuine pause/offline/non-live state must remain understandable, not masked as a quiet garden.
3. `HEARD IN THE LAST HOUR`, with a small historical report interval. Large illustration to the left, common/scientific names and explicitly labelled last-heard information to the right.
4. Other species heard during the report hour, text when space is limited.
5. `HEARD TODAY`: three other daily species, ordered by detection count, excluding the featured species from these cards only.
6. Two balanced footer groups, `TODAY` and `REPORT HOUR`, each showing species and acoustic detections (selected proposal B, 27 September 2026). Print the historical report interval once above the content, including date/zone qualification across midnight and DST; gallery mode labels this interval as applying to the report-hour totals. Preserve cached, paused and incomplete-count qualifications; missing station data shows unavailable totals, never zeros. Sample pages are labelled in the masthead so their count qualifications remain visible. The miniature footer vignette and “Small moments.” caption are removed; larger empty-state illustrations remain.

The screen is a **480 × 800** portrait composition sent to an **800 × 480** native device after rotation. Inspect output at actual resolution. The main art review footprint is 232 × 226 pixels; the small art review footprint is 102 × 100. Common names remain readable; long labels may wrap. Daytime scientific names use upright sans-serif type following the physical readability trials. Do not infer the sex, age or plumage of the actual caller from a decorative illustration.

## Selected typography target

On 27 September 2026, the user selected **E: DejaVu Sans Regular rendered directly in monochrome** as the clear winner of a physical comparison against thresholded DejaVu Sans and both rendering methods with Noto Sans. Use upright scientific names in this treatment. The trial used 18 px common names and 14 px supporting text; do not shrink essential labels to retain the previous four-column grid. Retain the editorial serif masthead as a separate title role. See [readability rules and trial evidence](READABILITY.md).

The user selected the three-card layout I. The daytime renderer uses 18 px daily common names and 14 px supporting text, wrapping instead of shrinking; exceptionally long labels receive two or one wider cards. The heading explicitly states how many species are shown, while aggregate totals retain every qualifying species.

## No clock, even one labelled snapshot

Use only the date and clearly historical phrases (`Report covers ...`, `Heard at ...`). They describe the report, not the current wall clock. During DST repetition or across midnight, qualify the interval enough to disambiguate it. Offline retained reports keep their original date/bounds.

## One illustration style

The authoritative reference is `art_studio/reference/robin.png`, identical to `display/assets/birds/erithacus_rubecula.png` and `display/autoart_reference/robin.png`. Use the source PNG, not a photograph of the e-paper screen and not an enlarged crop of a concept board.

Style: fine black feather hatching, natural proportions, restrained coloured wash on white, complete bird/feet/tail, modest branch or ground detail. Reject flat vector blocks, a common geometric body template repainted per species, cartoon rendering and unnecessary scene backgrounds. Do not give every bird a robin's orange breast. Anatomy and species markings require visual review after generation.

**The bundled 47 PNGs are preserved legacy inputs, not an approved consistent final collection.** Import existing paid replacement images with their approval state from the workstation.

## Palette and evidence

The renderer targets black, white, yellow, red, blue and green. Grey feather detail is deliberately rendered as black/white patterning rather than unconstrained coloured dithering. Physical pigment appearance, lighting and photography do not match RGB perfectly. Current PNG previews are real software output; AI concepts are design inspiration, not pixel-accurate test evidence.

The selected colour treatment is **strong wash** (27 September 2026). It preserves the existing black detail and spot colours, then fills approximately 70% of eligible white gaps within light, chromatic source regions using an ordered pattern. Neutral and dark source regions remain unchanged; `artwork_mode: ink` remains monochrome. This increases coloured area without regenerating artwork. The choice matches option C of the original-robin comparison at the runtime's 232 × 210 main and 102 × 100 thumbnail boxes. It was applied to the test installation with a private backup and the saved cooldown preserved; physical colour appearance still requires the user's assessment.

## Visual references

- `design/concepts/04-selected-editorial-target.png`: chosen composition; disregard its clock and any sightings/visits terminology.
- `design/previews/v2.1/no_clock.png`: current renderer baseline with labelled invented observations.
- `docs/images/garden-ink-device.jpg`: assembled device running the no-clock layout.

Source and actual rendered output take precedence over the concept image.
