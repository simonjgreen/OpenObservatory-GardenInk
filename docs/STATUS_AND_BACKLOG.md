# Status and roadmap

## Current state

Garden Ink 2.1 provides an hourly, no-clock journal from a separate Open Observatory station. The project photograph shows this layout operating in a printed Counterframe enclosure. It establishes an assembled working device, not long-run service reliability or measured mechanical qualification.

| Area | Implemented | Remaining verification or limitation |
|---|---|---|
| Station client | Read-only bounded scan; today/hour aggregation; source/review filtering; partial totals | Recheck the API contract when upgrading the station |
| Display | HAT (E) driver, startup/manual pushed frames, on-the-hour scheduled reports, relevant-artwork redraws, persistent refresh guard, strong colour wash, controller sleep, portrait no-clock layout | Long-run reliability, live verification of artwork-triggered redraws and physical readability across lighting conditions |
| Services | Display and optional artwork units; unit validation before installation | Confirm unattended startup/recovery on the deployed Pi |
| Pi artwork worker | Disabled by default; up to two workers; durable request reservations and uncertainty handling | Paid operation and low-memory behaviour require a separately authorised device trial |
| Workstation studio | Serial generation, recovery, review, approval and export | Existing paid collection must be imported; parallel generation is not implemented |
| Artwork | Original robin reference; 47 bundled illustrations; 53-species studio catalogue | Consistent reviewed collection, anatomy checks and thumbnail quality |
| Enclosure | OpenSCAD source, four structural prints, four fit coupons and a release key | Record print settings, exact revision, cable fit, retention, temperature and latch life |

## Improvement priorities

1. **Content quality:** clearer summaries while preserving acoustic identification and coverage semantics.
2. **Refresh methodology:** verify on-the-hour scheduling on the deployed Pi, retaining persisted hardware cooldown, DST and midnight correctness.
3. **Readability:** direct monochrome DejaVu Sans and three daily cards selected in physical trials; continue checking longer live labels and varied lighting.
4. **Power consumption:** measure the complete device. Controller sleep does not suspend the Pi; no battery-life claim is established.
5. **Art style:** complete a consistent robin-reference collection, with human review of anatomy and species markings.

## Maintenance work

- Reconcile deployed source and existing artwork before replacing either; preserve uncertain paid attempts and approvals.
- Verify installed services and cooldown after upgrades.
- Improve studio export errors to distinguish missing, unapproved and uncertain images.
- Check Pillow forward compatibility without changing request fingerprints.
- If studio concurrency is added, use one coordinator/state writer with bounded requests and explicit uncertain-request recovery.
- Develop an explicit-file, state-preserving deployment helper before automating upgrades.

Offline tests cannot certify hardware operation, live-station compatibility, paid API access or physical fit.
