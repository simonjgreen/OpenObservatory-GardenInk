PYTHON ?= python3
.PHONY: help test preview verify cad-check
help:
	@printf '%s\n' 'make test         - all offline software tests' 'make preview      - no-clock sample PNG; no network, GPIO, or paid requests' 'make verify       - offline tests and sample preview' 'make cad-check    - mesh checks only (optional trimesh/numpy)' 'Use PYTHON=.venv/bin/python for a workstation virtual environment.'
test:
	$(PYTHON) tools/test_all.py
preview:
	mkdir -p local/previews local/preview-state
	GARDEN_INK_STATE_DIR="$(CURDIR)/local/preview-state" $(PYTHON) display/dashboard.py --demo --preview --output "$(CURDIR)/local/previews/no-clock.png"
verify: test preview
cad-check:
	$(PYTHON) tools/check_cad_meshes.py --output local/cad-mesh-check.json
