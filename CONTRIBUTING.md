# Contributing

Garden Ink is an alternative e-ink interface for [Open Observatory](https://github.com/simonjgreen/OpenObservatory). Keep changes small and preserve compatibility with the existing appliance and artwork collection.

Read [architecture](docs/ARCHITECTURE.md), [status](docs/STATUS_AND_BACKLOG.md) and the relevant [documentation](docs/INDEX.md). Agent contributors should also read [AGENTS.md](AGENTS.md).

Run `make test` and `make preview` with the root virtual environment, as described in the [development workflow](docs/development/WORKFLOW.md). For layout changes, inspect the actual 480 × 800 output. Validate changed systemd units with `systemd-analyze verify`. Explain the change and its validation in the pull request, distinguishing mocked checks from physical testing.

Preserve detection/review semantics, local-day/DST boundaries and persisted hardware cooldown. Paid generation and live deployment require explicit authorisation. Keep private station details, credentials, observations and paid-generation state out of issues, screenshots and commits.
