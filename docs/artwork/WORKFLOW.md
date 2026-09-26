# Artwork workflow

Use `art_studio/reference/robin.png` as the single original style reference. The studio has 53 species; the bundled display collection has 47 images with mixed styles. Import existing paid images and state through [local recovery](../operations/LOCAL_RECOVERY.md) before generating replacements.

## Workstation tool

Commands below run from `art_studio/`, with Pillow installed. When using the root virtualenv, prefix commands with `PYTHON=../.venv/bin/python`.

```bash
bash art.sh list
bash art.sh generate --set all --plan
bash art.sh recover --species "Motacilla cinerea"
bash art.sh generate --set all --retry-uncertain --timeout 1200 --plan
# Only after inspecting the plan and explicitly authorising paid requests:
bash art.sh generate --set all --retry-uncertain --timeout 1200
bash art.sh review
bash art.sh approve --set all
bash art.sh export
```

Recovery uses a same-attempt saved `output/raw/motacilla_cinerea.png`, when one exists. It cannot recover a remote response that never arrived locally. A timeout may follow server processing/charging, so `--retry-uncertain` is an explicit decision, not a free retry. No automatic POST retry was implemented.

The timeout setting does not alter image request fingerprints. Changing the shared style brief/model/quality/reference does, so do not change those while completing the collection. `--regenerate` is for a deliberately named species only.

`approve --set all` validates the entire selected set before writing approvals. Missing or uncertain images can block approval of that set. Inspect individual states before interpreting an export readiness error.

## Canada goose correction

For an image with extra limbs, use a species-specific correction. The example note targets `Branta canadensis`; it asks for exactly two anatomically connected legs and two webbed feet, one goose in a clear side view on flat ground, with no ground stroke/reflection resembling an extra limb. The exact note is in `GOOSE_REGENERATION_NOTE.txt`.

Import the workstation species.json before editing: the note may already be present. Do not append it twice or change every species' shared style fingerprint. The targeted command is:

```bash
bash art.sh generate --species "Branta canadensis" --regenerate --timeout 1200
```

This is a new paid request. Inspect the result at both full art and thumbnail size; explicit anatomy words do not guarantee correctness. Approve the replacement only after inspection. The tool archives the previous attempt.

## Manual generation remains serial

The studio holds `output/.studio.lock` and coordinates a single JSON state.json. Parallel generation is not implemented. Do not bypass the lock or open four terminals against the same output directory. A proper pool must preserve one state owner, per-species raw files, request caps, pending/uncertain status, safe interruption and explicit retries. Concurrency must not change the request fields/reference and accidentally invalidate the collection.

The Pi missing-art worker is a separate tool and already permits up to two requests, with SQLite reservations and globally spaced starts. That does not mean the manual studio has become parallel.

## API settings and privacy

Both workflows preserve the original `gpt-image-2-2026-04-21`, high quality, 1536×1024, reference-guided image-edit call. Newer model names in provider docs are not permission to silently change an in-progress collection. Input fidelity is omitted for this model. Provider rates/access can change; verify official documentation/account limits before production changes.

Manual studio key = hidden input / optional OPENAI_API_KEY, not saved by the studio. Pi auto-art key = explicitly saved in .secrets/openai-api-key for unattended use. Never confuse that key with the optional local-station bearer token.

No audio, coordinates or detected-record data belong in image prompts. Species identity, standard art instructions and the reference are sufficient. Images are decorative, not evidence of a camera sighting or a classifier's correctness.

## Anatomy, approval and publication

A valid PNG is not a valid bird. Review legs/feet, beak shape, wing/tail continuity, markings, crop and style. The full library export requires all selected images to be present and approved, unless an explicitly partial proof pack is requested. The on-Pi worker can auto-publish or require review; automatic publication is labelled as such in its ledger and is not a human approval.

Keep raw outputs and archived rejects after deployment. Custom art wins over auto-generated cache, which wins over bundled fallbacks. Alias files/manifests matter (e.g. Corvus monedula / Coloeus monedula); use the provided exporter/importer rather than copying just one filename without metadata.
