# Validation

Run the complete repository validation contract locally:

```bash
bash validate-local.sh
```

It performs the same checks as `.github/workflows/validate.yml`:

- compiles every Python entry point and package module;
- validates all shipped JSON configuration files;
- validates the merged default runtime mapping configuration;
- runs the complete unittest suite;
- verifies the structured `--json-status` contract;
- checks shell syntax;
- parses every SVG asset.

Successful completion prints:

```text
MIDILIN_VALIDATION_OK
```

## GitHub Actions

Repository Actions must be enabled before merging a pull request. In GitHub:

1. Open **Settings → Actions → General**.
2. Under **Actions permissions**, allow the repository's validation workflow
   and the pinned marketplace actions it uses.
3. Save the setting.
4. Open **Actions → Validate** and run **Run workflow**, or push a branch commit.

A pull request without an executed `Validate` workflow is not considered
repository-validated even when its mergeability calculation succeeds.
