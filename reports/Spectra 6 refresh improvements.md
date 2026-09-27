# Spectra 6 refresh improvements

Research checked on 27 September 2026.

**Yes: the community has found two promising approaches—shortening the refresh cycle and restricting it to a rectangle.** There is even a patch for Waveshare’s exact `epd7in3e.py` driver family. Community implementations demonstrate that partial-area refresh is possible on some Spectra 6 panels. Neither approach is physically validated on Garden Ink’s installed HAT (E), and neither establishes flicker-free operation. The strongest next step is a staged, opt-in hardware experiment, with the working driver retained as the baseline. ([Waveshare PR #389](https://github.com/waveshareteam/e-Paper/pull/389))

## A clock change reportedly nearly halves refresh

Waveshare community PR #387 reports **12.932 seconds at clock setting `0x03`, versus 6.746 seconds at `0x07`**, with intermediate settings yielding intermediate times. This changes the panel’s driving cadence, so it addresses the physical refresh rather than just image preparation. However, these are the author’s measurements: exact timing boundaries and instrumentation are unspecified, temperature matters, and the command knowledge is reverse engineered. The PR remained open when checked on 27 September 2026. ([PR #387](https://github.com/waveshareteam/e-Paper/pull/387))

PR #389 ports that work to Python and adds partial updates. It also changes other initialization values and power sequencing; adopting the whole patch would obscure which change caused an improvement or regression. Garden Ink already uses **`0x30=0x03`**, matching the reported slower baseline. That makes this relevant, but does not predict our unit’s result. ([Python patch](https://github.com/waveshareteam/e-Paper/pull/389); [our driver](../display/gardenink/hardware.py))

Independent evidence is mixed: one owner of the exact Waveshare HAT (E) family measured approximately 19–20 seconds from display-refresh command to BUSY completion despite trying “fast” initialization and monochrome images. Those trials do not establish that the PR’s particular clock change fails, but show why a promised six-second result would be premature. ([Owner’s measurements](https://forum.core-electronics.com.au/t/7-3-6-color-epd-refresh-rate-ws-27875/23398))

## Partial updates can leave the artwork undisturbed

GxEPD2 released partial-area support for the Good Display GDEP073E01 in version 1.6.8. Its maintainer explicitly distinguishes compatible and incompatible colour panels. Waveshare PR #389 implements the same general rectangular-window approach directly in `epd7in3e.py`, making this more than a speculative workaround. **Compatibility with our exact panel revision remains unverified.** ([Maintainer discussion](https://github.com/ZinggJM/GxEPD2/discussions/161); [Waveshare patch](https://github.com/waveshareteam/e-Paper/pull/389))

This is a **full colour waveform within a smaller area**, not a quick monochrome-style partial update. GxEPD2 marks fast partial refresh unsupported and gives full and partial refresh identical timing constants. The practical benefit would be keeping an unchanged illustration still while report text flashes. Those constants are code defaults, not measurements of our display. ([Good Display sample](https://www.good-display.com/companyfile/1908.html); [GxEPD2 driver header](https://github.com/ZinggJM/GxEPD2/blob/master/src/epd7c/GxEPD2_730c_GDEP073E01.h))

Colour quality needs close inspection. A Seeed EE04/Spectra 6 user reported severe blue drift after using both Good Display and GxEPD2 examples, including an unusable result after one partial update. That is adjacent hardware, not proof our HAT will behave similarly. **No controlled lifetime evidence for these modifications on our hardware was found.** ([Firsthand report](https://forum.seeedstudio.com/t/ee04-and-spectra-6-7-3-partial-refresh/295260))

## Test duration and flashing area separately

First identify the installed panel revision and measure preparation, upload, physical refresh and shutdown separately at ordinary room temperature. Then trial one clock setting change at a time, comparing colour, ghosting and settling against the baseline. Assess partial-area updates separately before combining the approaches; portrait rotation, window alignment and sleep behaviour need explicit verification.

Use the same existing artwork derived from the single original robin reference, with **no paid generation**. Preserve hourly scheduling, the persisted cooldown, BUSY handling, power-off and deep sleep. Do not bypass counters to accelerate trials. Retain full-refresh recovery and reject visible drift. The most useful improvement for the aesthetic could be a smaller flashing area even if its duration stays unchanged. This report is source and code review only; no application changes or physical validation were performed.

Supporting research: [implementation evidence](<../research_notes/Spectra 6 refresh improvements/implementation.md>), [partial-area refresh](<../research_notes/Spectra 6 refresh improvements/partial_refresh.md>), and [refresh timing](<../research_notes/Spectra 6 refresh improvements/faster_refresh.md>).
