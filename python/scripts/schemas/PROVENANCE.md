# Vendored SchemaStore schemas

`scripts/validate_community_health.py` validates community-health YAML against
pinned copies of the SchemaStore schemas so the harness is hermetic on a fresh
checkout (no network, no `/tmp` preseed required).

| File | Source | SHA-256 |
| --- | --- | --- |
| `github-issue-config.json` | https://www.schemastore.org/schemas/json/github-issue-config.json | `899e718f4b8c965413b07ec63d8f089792a10c42409270db560b9a7ec0224a5a` |
| `github-funding.json` | https://www.schemastore.org/schemas/json/github-funding.json | `90d83f41c25a0029653a7ba64080aa6f3973527eed533f18f5b932a425bc802b` |

Retrieved 2026-08-01. To re-pin against the live SchemaStore copies:

```sh
curl -fsSL https://www.schemastore.org/schemas/json/github-issue-config.json \
  -o scripts/schemas/github-issue-config.json
curl -fsSL https://www.schemastore.org/schemas/json/github-funding.json \
  -o scripts/schemas/github-funding.json
shasum -a 256 scripts/schemas/*.json
```

Update the table above when re-pinning. To validate against the live schema
without re-vendoring, pass `--issue-config-schema <url-or-path>` /
`--funding-schema <url-or-path>` to the harness.
