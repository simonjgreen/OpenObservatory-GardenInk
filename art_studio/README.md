# Workstation art studio

Generate, review and export a consistent bird illustration collection using the original robin reference. Preserve existing paid output, approvals, catalogue, style brief and reference before making new requests: [local recovery](../docs/operations/LOCAL_RECOVERY.md).

From this folder with the root virtual environment:

```bash
PYTHON=../.venv/bin/python bash art.sh list
PYTHON=../.venv/bin/python bash art.sh generate --set all --plan
PYTHON=../.venv/bin/python bash art.sh review
```

List, plan, review, approval and export make no API calls. Generation is paid and requires explicit confirmation. The studio is serial, with one `output/.studio.lock` and JSON state file. See the [artwork workflow](../docs/artwork/WORKFLOW.md) for recovery, approval and export.
