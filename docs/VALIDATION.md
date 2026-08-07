# Validation

Run the complete repository validation contract locally:

```bash
bash validate-local.sh
```

It performs the same checks as `.github/workflows/validate.yml`:

- compiles every Python entry point and package module;
- validates all shipped JSON configuration files;
- validates the merged default runtime mapping configuration;
- runs the complete unittest suite under an explicit target-Wayland test environment;
- separately verifies that active color-temperature control fails without Wayland state;
- checks event-log rotation, full/actions/off modes, permissions and path safety;
- checks the systemd service, installer and udev safety contract;
- verifies the structured `--json-status` service and retention contract;
- checks shell syntax;
- parses every SVG asset.

Successful completion prints:

```text
MIDILIN_VALIDATION_OK
```

## GitHub Actions

The `Validate` workflow runs for `main`, `agent/**` branches, pull requests to
`main`, and manual `workflow_dispatch` runs. It calls `validate-local.sh`, so
local and hosted validation use one implementation rather than duplicated
commands.

The latest validated observable-runtime branch passed the Linux workflow before
physical hardware acceptance. A future pull request is not repository-validated
until its own head commit has a successful `Validate` run, even when GitHub's
mergeability calculation succeeds.

Manual rerun:

1. Open **Actions → Validate**.
2. Select **Run workflow**.
3. Choose the branch under review.
4. Confirm that the run is associated with the expected head commit.

## Physical acceptance

Hosted CI cannot prove USB permissions, X1/F1 packet behavior, LED output,
Sway/gamma-control availability, laptop backlight control, or DDC/CI support on
the target monitors. Keep the PR draft until those checks pass on the Garuda
workstation and retain the resulting `--json-status`, event-tail and service-log
evidence.
