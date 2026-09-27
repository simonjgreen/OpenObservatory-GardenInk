# Faster pigment refresh on 7.3-inch Spectra 6 / Waveshare HAT E

## Do fast initialization or image simplification reliably shorten the flash?

### Takeaway
There is conflicting community evidence, so an assurance that software cannot shorten the flash would be too strong. One exact-model owner found no benefit from fast initialization or black-and-white content; separate Waveshare PRs report a much shorter refresh and need evaluation with clearly separated timing phases.

### Cited Findings
- In October 2025, a Waveshare WS-27875 / 7.3 HAT E owner reported trying Waveshare and Good Display examples, including an initialization sequence marked fast. They measured approximately 19–20 seconds from the final display-refresh command (DRF) to BUSY becoming idle, regardless of color or initialization code; uploading the picture added roughly another second. This is a useful first-person hardware report with a defined measurement boundary, not a controlled multi-unit study. — [Core Electronics thread](https://forum.core-electronics.com.au/t/7-3-6-color-epd-refresh-rate-ws-27875/23398)
- Other replies suggested simpler images or black-and-white output, but supplied no measurements for this panel. The original tester's measurements did not support that suggestion. The tester's speculation about a theoretical minimum or changing factory waveform must not be presented as established fact. — [Same first-person discussion](https://forum.core-electronics.com.au/t/7-3-6-color-epd-refresh-rate-ws-27875/23398)
- Waveshare PRs report 12.932 → 6.746 seconds, relevant counterevidence that merits consideration. The [implementation notes](implementation.md) cover the changes and limitations of the timing evidence. — [PR 387](https://github.com/waveshareteam/e-Paper/pull/387), [PR 389](https://github.com/waveshareteam/e-Paper/pull/389)
- Official Python epd7in3e driver sends image data first, then POWER_ON, DISPLAY_REFRESH, waits on BUSY, and POWER_OFF. Its BUSY polling interval is only 5 milliseconds. Speeding image transfer or reducing post-refresh sleep can reduce end-to-end execution without necessarily reducing flashing. — [Waveshare Python source](https://raw.githubusercontent.com/waveshareteam/e-Paper/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd7in3e.py)

### Inferences
- Measure preparation, SPI upload, and DRF-to-BUSY separately before judging any speed patch. This avoids attributing a faster upload to faster pigment movement.
- A normal black-and-white image sent through the unchanged six-colour update path is not a demonstrated flash-reduction workaround.

### Gaps
- No controlled repeatable benchmark across HAT E production revisions was found.
- No reviewed evidence here establishes a universal 6.7-second result, preserved color quality, or long-term safety of the PR changes; consult companion implementation notes.

## Why do credible sources report 12, 19, 25, or 28 seconds?

### Takeaway
Different panel revisions and timing boundaries explain at least some variation. Twelve seconds is not simply imaginary: the GxEPD2 author recorded that scale of pigment timing, but it is not a guarantee for later units.

### Cited Findings
- Current GxEPD2 GDEP073E01 header records an example full-refresh measurement of 12,468,000 microseconds, with both full and partial fallback time constants set to 15,000 milliseconds and fast-partial capability false. These constants are not a claim that every panel refreshes in exactly 15 seconds. — [GxEPD2 header](https://raw.githubusercontent.com/ZinggJM/GxEPD2/master/src/epd7c/GxEPD2_730c_GDEP073E01.h)
- Good Display currently lists 15–22 seconds full refresh for its GDEP073E01 panel. — [Manufacturer product page](https://www.good-display.com/product/533.html)
- Pimoroni currently lists its 7.3-inch Spectra 6 Inky Impression at 28 seconds core refresh. Its revision history says units made from April 2026 use a new AC-waveform panel with a slower core update in return for better color and less ghosting. The page gives 20–35 seconds as a realistic complete cycle across sizes/revisions and notes that cooler temperatures lengthen refresh. The 12-second footnote refers to manufacturer core timing at 25–50°C. This is adjacent hardware, not proof that the user's Waveshare contains that revision. — [Pimoroni current product and revision history](https://shop.pimoroni.com/products/inky-impression)

### Inferences
- Panel label/revision and ambient temperature belong alongside timing data when comparing results.
- Buying another nominally identical 7.3-inch Spectra 6 panel does not guarantee a faster update; newer can be slower for improved image quality.

### Gaps
- The user's exact panel revision and pigment-only elapsed time are not established in this research.
- I found no demonstrated, reproducible temperature-spoofing workaround specifically validated on the 7.3 HAT E. Temperature dependence is not a recommendation to heat the artwork display or spoof its sensor.

## Are there dramatic waveform hacks elsewhere that could transfer?

### Takeaway
Yes, adjacent Spectra 6 experimentation exists, but the striking subsecond example sacrifices the intended full-colour image. It is not a suitable drop-in improvement for Garden Ink artwork.

### Cited Findings
- FreeInk's native driver for M5Stack PaperColor (4-inch, 400×600 Spectra 6, ED2208) interrupts the normal approximately 15-second waveform at about 340 milliseconds to obtain a monochrome reading mode. Its authors say proper white and full color require a complete waveform; interrupted operation can visibly darken the display over hours as charge accumulates, so periodic complete waveforms are necessary. This is author-reported behavior for a different panel and device. — [FreeInk PaperColor behavior](https://github.com/Free-Ink/freeink-sdk#M5Stack-PaperColor-refresh-behavior)
- Glider's technical overview distinguishes Spectra 6 Plus as capable of faster operation with driver circuit changes; it is not presented as a software switch for a regular Waveshare HAT E. — [Glider technical overview](https://github.com/Modos-Labs/Glider)

### Inferences
- The adjacent 340ms hack should not be offered as a way to preserve the existing robin artwork while making its update subtle.
- A waveform trial on the actual HAT E should be judged on color, ghosting, and unchanged-region artifacts as well as elapsed seconds.

### Gaps
- No evidence found that FreeInk's interrupted-refresh method has been validated on the user's HAT E.
- Region-limited refresh is covered in the [partial-refresh notes](partial_refresh.md); this speed note should not be read as saying that partial refresh is impossible.
