# Spectra 6 implementation evidence

## What concrete community code exists for partial refresh?

### Takeaway
There is concrete source for spatial partial refresh, including an unmerged patch to Waveshare's exact `epd7in3e.py` module. That is promising evidence for reducing flashing area, but it is not proof that the installed Garden Ink panel revision supports it.

### Cited Findings
- GxEPD2 1.6.8 added GDEP073E01 partial update on 16 March 2026. The maintainer says his other six/seven-colour screens ignore command `0x83`; another user reports four unspecified Spectra6 revisions working. The latter is a community report, not universal compatibility proof. — [Maintainer discussion](https://github.com/ZinggJM/GxEPD2/discussions/161)
- Current GxEPD2 GDEP073E01 source sends `0x83` with coordinates before data transfer and refresh; partial refresh sets border floating with `0x50=0xFF` and uses the normal `0x12` refresh command. Native packed pixels are aligned to two-pixel boundaries; bitmap paths align to eight. `_setPartialRamArea` contains a controller-specific Y endpoint adjustment (`y+h`, commented “one more”). — [Source, methods around lines 312–410 and 443–498](https://github.com/ZinggJM/GxEPD2/blob/master/src/epd7c/GxEPD2_730c_GDEP073E01.cpp)
- Header explicitly sets `hasPartialUpdate=true`, `hasFastPartialUpdate=false`; full and partial refresh timing constants are both 15000ms. This implements a full waveform in a restricted area rather than a quick monochrome-style update. — [Header lines 19–30](https://github.com/ZinggJM/GxEPD2/blob/master/src/epd7c/GxEPD2_730c_GDEP073E01.h)
- Good Display calls its downloadable ESP32 example “Full update within a specified area”; its download page is dated 25 August 2025. — [Vendor sample](https://www.good-display.com/companyfile/1908.html)
- Waveshare PR #389, opened 6 May 2025 and still open when checked 27 September 2026, adds `displayPartial(image,x,y,w,h)` directly to `epd7in3e.py`. It uses `0x83`, sends the pixels, and calls its normal update function. Its code differs from GxEPD2: Y end is `y+h-1`, and it prefixes the pixel data with a `0x00` byte. These are implementation details needing review and hardware validation, not a copy/paste recipe. — [PR](https://github.com/waveshareteam/e-Paper/pull/389); [branch source lines 174–183](https://raw.githubusercontent.com/missionfloyd/e-Paper/spetra6-performance/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd7in3e.py)
- The examined GxEPD2 implementation uses window coordinates, not per-pixel no-change masking. It maps native colour code `0x7` with a “white” comment; it does not establish `0x7` as a retain-pixel code. — [Source end of file](https://github.com/ZinggJM/GxEPD2/blob/master/src/epd7c/GxEPD2_730c_GDEP073E01.cpp)

### Inferences
- Keeping an unchanged bird illustration outside the refresh rectangle could substantially improve perceived calm, even if changing text still flashes for the ordinary waveform duration. Multiple scattered changes, rotation, and panel window alignment will affect which area must flash.
- The supplied code is enough to justify considering an opt-in experiment, but not enough to enable partial refresh in production by default.

### Gaps
- Neither examined PR conversation specifies the exact tested HAT/panel revision or demonstrates the particular Garden Ink hardware.
- No measured maintenance interval for periodic full refreshes or long-term image-quality data was established from these code sources.
- No concrete per-pixel mask implementation was verified in this research strand.

## Is there a credible software route to shorter physical refresh?

### Takeaway
An exact Waveshare community patch reports roughly halving the 7.3-inch refresh by changing the panel clock register. The report is promising, but reverse-engineered, unmerged, temperature dependent, and missing rigorous colour-quality and lifetime validation.

### Cited Findings
- PR #387, opened 29 March 2025 and still open, reports 7.3-inch refresh measurements of 12.932 seconds at PLL `0x03`, 10.075 at `0x04`, 8.798 at `0x05`, 7.832 at `0x06`, and 6.746 at `0x07`. The author calls out temperature dependence and describes the command knowledge as reverse engineered. — [PR report](https://github.com/waveshareteam/e-Paper/pull/387)
- The same report discusses hardware AUTO sequencing of power-on, display refresh, and power-off; the Python port uses command `0x17` with `0xA5` and waits for BUSY. It also changes several other initialization values, so adopting the entire patch would do considerably more than change one clock byte. — [Python source, lines 86–145](https://raw.githubusercontent.com/missionfloyd/e-Paper/spetra6-performance/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd7in3e.py)
- PR #389's author says the patch applies #387 to Python, batches parameter writes, speeds buffer packing, and adds partial update. No hardware testing narrative or colour-quality comparison appears in the retrieved conversation, and no reviews are listed. — [PR #389](https://github.com/waveshareteam/e-Paper/pull/389)

### Inferences
- The PLL change addresses the panel's driving cadence rather than merely host image preparation. It could shorten the distracting flashing, but does not remove full-screen flashing on a full update.
- A bounded experiment should compare baseline against one change at a time, with the actual artwork and text, ordinary room temperatures, and side-by-side colour/ghosting inspection. Bulk-swapping the community driver would obscure the cause of any regression.

### Gaps
- PR #387 does not specify timing instrumentation or exact start/end boundaries. Describe its numbers as author-reported refresh timings, not verified DRF-only/BUSY intervals or a promise for our unit.
- No controlled quality, longevity, or warranty conclusions can be drawn. Do not assert proven damage from this change, nor claim the speed is free of trade-offs.

## How does this fit the current Garden Ink driver?

### Takeaway
Garden Ink presently uses the slower clock byte found in the community comparison, and has no partial-window path. We did not modify the driver or touch hardware.

### Cited Findings
- `INIT_SEQUENCE` has `0x30=0x03` and `0x50=0x3F`; the driver is expressly adapted from Waveshare's HAT(E) `epd7in3e`. — [Local driver lines 1 and 12–18](../../display/gardenink/hardware.py)
- `show()` writes the full 192000-byte buffer, triggers one `0x12` refresh, times through BUSY completion, and powers off; `close()` puts the panel into deep sleep. It does not issue a separate blank-screen refresh. — [Local driver lines 84–105](../../display/gardenink/hardware.py)
- The native packed image is derived by rotating the portrait render 90 or 270 degrees. Window coordinates would therefore need the same transformation. — [Local palette packing](../../display/gardenink/palette.py)
- GxEPD2 separately tracks initialization, hibernation, and panel power; hibernation forces reinitialization. Its partial feature writes controller memory before refreshing the selected area, so state and sleep behavior deserve explicit integration tests. — [Source, lines 467–535](https://github.com/ZinggJM/GxEPD2/blob/master/src/epd7c/GxEPD2_730c_GDEP073E01.cpp)

### Inferences
- Existing driver refresh-duration logging gives us a useful baseline without changing waveform behavior.
- Safe integration would preserve persisted cooldown, sleep/power-off, and BUSY handling; add a capability-gated optional partial path; preserve full refresh recovery after uncertain updates; and validate on this actual panel before production adoption.
- Do not simply keep panel high voltage enabled to retain state. Distinguish controller RAM retention, panel power-off, and deep sleep when assessing a future prototype.

### Gaps
- Exact installed panel revision remains unverified by this strand. Software similarity is not component identity.
- Controller RAM persistence across our reset/deep-sleep cycle was not established by these sources; no claim that previous image retention in RAM is required or sufficient is made here.
