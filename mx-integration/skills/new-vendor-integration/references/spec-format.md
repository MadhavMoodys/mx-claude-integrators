# `integration.yaml`

The scaffolder's input, and afterwards the repo's record of what it was told. The
`SessionStart` hook reads it, so keep it accurate as the integration grows.

```yaml
vendor: acme            # required
display_name: Acme      # optional, defaults to Vendor-capitalised
ticket: M3PDS-999       # required in practice
connector: false        # optional, defaults to false
```

## Fields

**`vendor`** — lowercase letters and digits, starting with a letter. It becomes a Java
package segment (`com.moodys.maxsight.acme`) and a Maven artifactId, so hyphens and
underscores are rejected rather than quietly mangled into something that compiles but
reads wrong. `dowjones`, not `dow-jones`.

**`display_name`** — the class-name prefix: `AcmeClient`, `AcmeConfig`,
`AcmeRateLimitException`. Must be a valid Java identifier prefix. Defaults to the
vendor with its first letter capitalised.

**`ticket`** — `PROJ-123`. Written into every generated TODO, and validated against
the same regex the commit hook uses, so a typo here fails at scaffold time rather than
at your first commit.

**`connector`** — `true` adds the orchestrator-facing module. `false` is the default
and the right choice for a vendor that only answers synchronous requests. See
`{{vendor}}-connector/PORTING.md` in the generated repo for what `true` actually
gives you.

## Parser limits

Deliberately a small subset of YAML, parsed by the stdlib so the plugin needs no
`pip install`. Supported: `key: value`, `key:` followed by `- item` lines, `#`
comments, blank lines. Quotes are stripped; `true`/`yes`/`false`/`no` become booleans.

Anything else — nesting, anchors, multi-line strings — is a hard error, not a silent
misread. If a future field genuinely needs structure, add a flat key rather than
teaching the parser to nest.

## Tokens

The scaffolder substitutes these in both file contents and path segments,
case-sensitively:

| Token | From | Example |
|---|---|---|
| `{{vendor}}` | `vendor` | `acme` |
| `{{Vendor}}` | `display_name` | `Acme` |
| `{{VENDOR}}` | `vendor`, uppercased | `ACME` |
| `TICKET-000` | `ticket` | `M3PDS-999` |

In YAML, `${{{VENDOR}}_BASE_URL}` expands to `${ACME_BASE_URL}` — the outer `${…}` is
the Spring placeholder, the inner `{{VENDOR}}` is the token.

Whole-line `{{#connector}}` … `{{/connector}}` markers keep or drop the lines between
them and are always removed. The markers must be alone on their line; an inline one is
left as literal text.
