# Bat ecology and useful after-dark displays

## What should the main activity view show?

### Takeaway
Recommend a dusk-relative hourly activity profile, with tonight's completed bins against the median of recent comparable nights. This answers both “is this a busy evening?” and “when does this garden usually become active?”; it is a proposed display design, not a validated ecological indicator.

### Cited Findings
- A London acoustic study used one-minute intervals containing bat calls as “activity minutes”, partly to reduce inflation from one bat circling a detector. It defined its bat passes as individual classifier outputs up to five seconds, illustrating that a pass is an operational measurement rather than an individual animal. It also located peak activity using 15-minute bins after sunset and retained detector-level records to account for missing survey nights. — [Brook et al. (2025), methods 2.2 and 2.5](https://besjournals.onlinelibrary.wiley.com/doi/10.1002/2688-8319.70151)
- A study across 323 nights and 14 European sites found that time after sunset, night length and weather variables contributed differently for different species. Its findings argue against a universal nightly shape or simple weather explanation. — [Perks and Goodenough (2020), original research abstract](https://eprints.glos.ac.uk/8304/)
- BCT recommends consistent survey effort when monitoring change over time. Detector placement and detectability vary; some species cannot be conclusively identified from audio. — [BCT passive acoustic guidance](https://www.bats.org.uk/our-work/science-research/passive-acoustic-surveys/guidelines-for-passive-acoustic-surveys-of-bats-in-woodland)

### Inferences
- Proposed metric: unique one-minute intervals with at least one eligible bat acoustic record. Label it “minutes with bat sound” with a compact definition; never imply that it measures independent bats, continuous calling duration, visits or prey consumption. A single short record makes that interval active; several species in one minute must not inflate the all-bat total.
- This metric is defensible for comparisons only with known, comparable capture effort, configuration and eligibility filtering. Knowing that the API returned every record is separate from knowing that the microphone actually recorded throughout the period. Complete API pagination does not establish acoustic sampling effort.
- Align each night's bins to its own local sunset, not a fixed wall-clock hour. Use a labelled historical report cutoff and date spanning the night. Only draw elapsed, completed bins; leave future bins blank. A comparison made two hours after sunset should cover those same first two hours on prior nights.
- Use a recent-night median rather than one supposedly “normal” night. Show the number of eligible nights and avoid strong “unusual” claims from sparse history. Weather is context, not a proven explanation for tonight's difference.
- If capture effort is unavailable, a profile can still describe the records received, explicitly as “recorded activity”, but should not claim standardized rates, meaningful zero activity or ecological trends. This dependency belongs in implementation planning rather than overwhelming the small display.

### Gaps
- This research did not inspect the live station or establish whether its data include recording effort, continuous timestamped bat detections, suitable confidence/review fields or complete night history. The activity unit must follow the actual source schema.
- No evidence establishes that seven versus fourteen nights is optimal for this garden; this is a pragmatic design choice requiring local data.

## What are the strongest alternative screen ideas?

### Takeaway
Offer three choices: a nightly profile (recommended), seven-night comparison bars, or an illustrated bat field note. The last is particularly useful while data are sparse or the season is quiet.

### Cited Findings
- Common pipistrelles generally leave their roost around twenty minutes after sunset and often feed around gardens. They weigh roughly five grams; common and soprano pipistrelles were recognised as separate species in the 1990s, and their call frequencies are useful distinguishing characteristics. These are species-level facts, not observations made by this device. — [BCT common pipistrelle account](https://www.bats.org.uk/about-bats/what-are-bats/uk-bats/common-pipistrelle)
- BTO notes that similar calls complicate identification; its own published example groups Brandt's and whiskered bats because robust manual acoustic separation is unavailable. Changing file segmentation also changes recording counts, which is why BTO recommends standardised file length for comparisons. — [BTO, understanding Pipeline performance](https://www.bto.org/data/tools-products/acoustic-pipeline/support-hub/understanding-and-optimising)

### Inferences
- **Night profile:** tonight's hourly bars or dots with a simple recent-night reference line, plus first eligible sound recorded relative to sunset. Do not label the first garden recording “emergence”: that would imply observing departure from a roost.
- **Seven nights:** seven labelled bars show how recorded activity changes between evenings. Make a separate clearly incomplete tonight bar, or compare equal sunset-relative periods. Prior full nights versus tonight-to-date without distinction is misleading. Prefer this view for an immediately legible 480×800 design.
- **Bat field notes:** keep one bat illustration, one short sourced natural-history fact, and two local observations such as “acoustically identified on 4 of 7 monitored nights” and the latest historical record. Illustrations and facts can describe a species without asserting that a fresh unreviewed detection is confirmed.
- A “first recorded this season” or “heard again after 12 monitored nights” detail is interesting later, but requires a known monitoring denominator and stable review rules. Avoid “rare visitor” from classifier novelty alone.
- Do not infer flight height, hunting success, migration, roosting or feeding buzzes merely from an ordinary species detection. Acoustic identity and behaviour are different claims.

### Gaps
- No illustration or mockup was created. The user selects the direction first.
- The garden's actual species mix is unknown in this research, so common pipistrelle is an example, not a recommended assumed resident.

## How should quiet nights, winter and weather affect the content?

### Takeaway
Quiet nights should remain informative: show the last properly dated recording and a seasonal note, without turning missing data into ecological absence. Winter should naturally favour the field-note view.

### Cited Findings
- Bats spend much of winter hibernating; spring activity resumes gradually; females form maternity colonies and young become independent in summer; late summer and autumn include mating and building fat stores. This is broad UK seasonal context, not a rigid local schedule. — [BCT, a year in the life of a bat](https://www.bats.org.uk/about-bats/a-year-in-the-life-of-a-bat)
- Winter bats sometimes wake naturally to move roosts or feed in mild weather, so winter does not mean guaranteed silence. — [BCT, bats flying at unusual times](https://www.bats.org.uk/advice/im-concerned-about-bats/ive-seen-a-bat-flying-at-an-unusual-time)
- BCT's monitoring report describes lower expected activity in cold or wet weather and greater use of sheltered places in wind. It also explicitly adjusts national trends for detector and weather differences. — [NBMP annual report 2024, printed pages 18–19](https://cdn.bats.org.uk/uploads/pdf/Our%20Work/NBMP/NBMP-annual-report-2024.pdf)

### Inferences
- Example seasonal copy for autumn: “Bats are building fat reserves for winter.” Keep this separate from the local chart and avoid suggesting that this detector has observed fattening or mating.
- Distinguish “no eligible bat records in this report”, “recording unavailable”, and “data still incomplete”. Only known coverage supports “none recorded during monitored hours”.
- Include temperature or rain as a small historical annotation only if trustworthy observations exist. Say “a cooler evening” alongside a lower bar, not “cold weather kept the bats away”. Avoid a generic moon-phase activity prediction: reviewed research shows species-dependent associations.
- On winter evenings, a small recent-history strip plus one seasonal insight is likely more rewarding than a large empty graph. This is an editorial judgement, not a research finding.

### Gaps
- Quiet-night behaviour cannot distinguish hibernation, unmonitored time, detector limitations, weather effects or simple non-detection from the acoustic event feed alone.
