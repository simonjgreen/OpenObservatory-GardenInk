# Partial-area refresh on 7.3-inch Spectra 6 panels

## Has partial-area refresh actually been demonstrated?

### Takeaway
Yes: vendor examples, community testing, and released GxEPD2 support establish a real option for the Good Display GDEP073E01. This corrects a blanket claim that Spectra 6 cannot update only an area, but does not establish compatibility with every branded panel. [GxEPD2 discussion](https://github.com/ZinggJM/GxEPD2/discussions/161)

### Cited Findings
- GxEPD2 maintainer Jean-Marc Zingg announced GDEP073E01 partial-update support in version 1.6.8 on March 16, 2026, reversing his earlier understanding. He distinguished GDEY073D46, where partial addressing exists but partial refresh is unusable, and said his other six/seven-colour displays ignore command 0x83. [Maintainer discussion](https://github.com/ZinggJM/GxEPD2/discussions/161)
- On January 23, 2026, tester `smarthomeagentur` reported Good Display's sample worked out of the box on four display revisions from different suppliers. The post does not identify those models, controller boards, or revision markings; it links a video. [Firsthand report and video link](https://github.com/ZinggJM/GxEPD2/discussions/161); [linked video, not inspected](https://photos.app.goo.gl/DWNDwvXDW4LGNNEd9)
- Good Display explicitly labels its ESP32 sample as a full update within a specified area, dated August 25, 2025. [Vendor download page](https://www.good-display.com/companyfile/1908.html)
- Good Display's store advertises refreshing modified regions to reduce visible flicker. Treat this as a vendor capability claim, not a durability test. [Vendor product page](https://www.buy-lcd.com/products/gdep073e01)

### Inferences
- A practical future experiment could target only the report region when artwork is unchanged; however, this is a compatibility hypothesis for Garden Ink, not a verified feature of its physical HAT (E).
- Do not equate the Spectra 6 marketing name, screen size, or identical resolution with verified waveform/controller compatibility.

### Gaps
- No firsthand report explicitly identifying successful partial-area refresh on the exact Waveshare 7.3-inch HAT (E) assembly was found in these searches.
- The successful four-revision report does not disclose the models. The video link was inaccessible to the web fetcher; no independent visual inspection was performed.

## Does it reduce the flashing area, duration, or both?

### Takeaway
The supported route runs a full colour update in a selected rectangle. It can reduce the affected area, but evidence does not show a corresponding reduction in waveform duration. [Good Display sample](https://www.good-display.com/companyfile/1908.html); [firsthand timing clarification](https://www.reddit.com/r/eink/comments/1r9aelk/partial_updates_on_spectra6_ee04/)

### Cited Findings
- GxEPD2's GDEP073E01 header has `hasPartialUpdate = true`, but `hasFastPartialUpdate = false`; both full and partial refresh time constants are 15,000 ms with the same approximately 12.468-second example in comments. These are source constants/comments, not measurements of Garden Ink. [Driver header](https://raw.githubusercontent.com/ZinggJM/GxEPD2/master/src/epd7c/GxEPD2_730c_GDEP073E01.h)
- In a firsthand clarification, `SnooEpiphanies7337` says Good Display's area-refresh samples worked across their Spectra 6 revisions but still take the full approximately 20 seconds for that area. They distinguish this from their separate quick-refresh technique, which interrupts a refresh with the reset pin. Combining those two was suggested, not demonstrated in that exchange. [Reddit developer exchange](https://www.reddit.com/r/eink/comments/1r9aelk/partial_updates_on_spectra6_ee04/)
- The GxEPD2 implementation accepts rectangular refresh coordinates and programs the partial RAM area before the display-refresh command. This supports the region distinction but is not independent physical evidence. [Driver source](https://raw.githubusercontent.com/ZinggJM/GxEPD2/master/src/epd7c/GxEPD2_730c_GDEP073E01.cpp)

### Inferences
- For the user's aesthetic concern, reducing flashing to a narrow report rectangle could be worthwhile even if elapsed refresh time remains long.
- The defensible correction to the previous answer is that community area-update support exists and merits compatibility investigation; it does not justify promising flicker-free updates or unchanged colour quality on this appliance.

### Gaps
- No measured relationship between rectangle size and duration was found.
- No direct comparison of the installed HAT (E)'s full and partial visual behaviour was available.

## What are the visible defects and long-term uncertainties?

### Takeaway
Compatibility has meaningful caveats: a directly documented Seeed EE04/Spectra 6 attempt produced severe colour drift. No controlled long-term cycle evidence was found for the exact target hardware. [Seeed firsthand thread](https://forum.seeedstudio.com/t/ee04-and-spectra-6-7-3-partial-refresh/295260)

### Cited Findings
- On April 1, 2026, `Acid` reported trying both Good Display and GxEPD2 examples on their EE04/Spectra 6 setup. White increasingly shifted toward blue, strongest toward the bottom. On April 14 they linked a video and said even one partial refresh was unusable. [Firsthand report and follow-up](https://forum.seeedstudio.com/t/ee04-and-spectra-6-7-3-partial-refresh/295260)
- Another participant's recommendation against production use was explicitly not based on long-term testing of that exact Seeed panel. Their claim concerned unspecified similar Waveshare colour panels. This is weak evidence for the installed HAT (E), not a demonstrated failure of it. [Qualification in same thread](https://forum.seeedstudio.com/t/ee04-and-spectra-6-7-3-partial-refresh/295260)

### Inferences
- Published examples establish possibility, while the EE04 result shows that transporting initialization/waveforms between apparently similar assemblies can fail visually. Which electrical, firmware, or panel difference caused the drift remains unknown.
- A future hardware experiment would need unchanged-artwork inspection and repeated-cycle checks; successful command completion alone cannot establish colour stability or panel longevity.

### Gaps
- No exact-controller explanation or validated fix for the EE04 blue drift was found.
- No specific safe number of partial updates between full refreshes can be justified from this evidence.
- No lifetime testing, measured wear impact, or validated recovery behaviour was found for partial updates on the installed HAT (E).
