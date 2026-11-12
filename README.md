# Rusticide

A GitHub Action that watches your repo's own first-party security
advisories, and once they pile up past a threshold, rewrites your entire
codebase in Rust and force-pushes it straight to `main`. No pull request.
No review. No undo. It happens once, ever, per repo.

This is a joke taken seriously enough to actually work. It is not a safety
feature, a security tool, or something you should put in front of a repo you
care about. Read [Why this is dangerous](#why-this-is-dangerous) before you
install it.

## What it actually does

1. **Daily, it checks your advisories.** You tell it your package's
   ecosystem and name (e.g. `npm` / `left-pad`). It queries GitHub's global
   Security Advisories API for that ecosystem+package — this is the only way
   to see advisories filed by *other people* against your package; there is
   no "advisories against my repo" endpoint, only "advisories against this
   package name," so you have to say what that name is.
2. **It sums the damage.** All advisories published in the trailing 6 months
   (configurable) are summed by CVSS score (or just counted — your choice).
   Advisories without a numeric CVSS score fall back to a severity-based
   estimate (low=2.5, medium=5.0, high=7.5, critical=9.5).
3. **If you're over the threshold, it rewrites everything.** One single
   Claude Code session, with your Anthropic API key, with no supervision,
   given full write access to the checkout and told to rewrite the whole
   repo in Rust (or Erlang, if you're already in Rust — if you were already
   memory-safe, the joke escalates). It tries to build and test its own
   output, retrying within that same session, but it is not allowed to stop
   and ask you anything.
4. **It pushes to `main` regardless of whether it worked.** Passing build
   and tests only affects whether the thing that lands on `main` happens to
   function. It does not affect whether it lands.
5. **It only ever does this once.** A marker file is committed in the same
   push as the rewrite. Once it exists, every future run is a no-op, forever,
   even if your advisories keep piling up.

## Setup

### Required inputs

| Input | Description |
|---|---|
| `ecosystem` | GHSA/OSV ecosystem your package is published under (`npm`, `pip`, `cargo`, `maven`, `gem`, `composer`, `nuget`, `go`, ...) |
| `package` | Exact published package name in that ecosystem |
| `anthropic-api-key` | Your own Anthropic API key, used for the one-shot rewrite session |
| `push-token` | A PAT or GitHub App token with `contents: write`, and bypass on `main`'s branch protection (see below) — the default `GITHUB_TOKEN` cannot force-push to a protected branch, and this Action does not try to change your branch protection settings for you |

### Optional inputs

| Input | Default | Description |
|---|---|---|
| `threshold-mode` | `cvss-sum` | `cvss-sum` or `count` |
| `threshold-value` | `30` | Numeric threshold in whichever mode you picked |
| `window-months` | `6` | Trailing window size for aggregating advisories |
| `marker-path` | `.rusticide-done` | Path to the file that permanently disables future rewrites once one has happened |

### Branch protection — read this

If `main` is protected (as most repos that would actually have tracked
CVSS scores probably are), a normal token cannot force-push to it. You must
do one of:

- Disable branch protection on `main`, or
- Add your `push-token`'s identity (a PAT's user, or your GitHub App) to the
  protected branch's bypass list for force-pushes.

This Action will not do this for you. If you haven't set this up, the push
step will simply fail and nothing will happen to your repo — which, depending
on your feelings about this whole idea, might be the safer outcome anyway.

### Example workflow

See [`.github/workflows/example-consumer.yml`](.github/workflows/example-consumer.yml).

```yaml
on:
  schedule:
    - cron: '0 7 * * *'

jobs:
  rusticide:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: antitree/rusticide@main
        with:
          ecosystem: npm
          package: your-package-name
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          push-token: ${{ secrets.RUSTICIDE_PUSH_TOKEN }}
```

## Why this is dangerous

This is listed as a fact, not a warning you can configure away:

- There is no human gate anywhere in this pipeline, by design.
- The trigger is third-party-filed security advisories — anyone who can get
  a plausible GHSA logged against your package's ecosystem+name can
  eventually push your CVSS sum over the threshold, on a timeline you don't
  control.
- The rewrite is unreviewed and the push happens whether or not the result
  builds, compiles, or does anything close to what your original code did.
- This is architecturally equivalent to an unreviewed force-push to `main`
  triggered by external, adversarially-influenceable input. That is the
  entire point: it's a demonstration of how bad an idea "automate security
  remediation with zero review" is, built well enough that the demonstration
  actually lands.

Do not run this against a repo whose `main` branch matters to you, your
users, or anyone downstream of you.

## Known gaps (v1)

- **Whole-repo rewrite only.** No monorepo/component scoping. If any part of
  your repo trips the threshold, the Action rewrites all of it.
- **Build success is the only pass/fail signal**, and it doesn't gate the
  push anyway. Test suites coupled to the original language (e.g. Jest
  against JS) will not run against Rust/Erlang output unless they're
  black-box/CLI/HTTP-level.
- **No protection against concurrent runs.** If two runs somehow race, the
  last force-push wins and the marker file alone does not prevent that.
- **Single LLM provider.** Claude only, via your own Anthropic API key. No
  other provider is supported in v1.
