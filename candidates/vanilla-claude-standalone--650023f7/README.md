# vanilla-claude-standalone

Standalone Karn Construct Definition.

Image: `sha256:e31d6ef6dace56ef1536450ab0344cdebe24835bca480deaf92f7d9da8ec0377`

Definition: `sha256:86ec567db389c43fa7533c4980621ff98cb5c439a585ceb54e488d4f9c10e600`

The source copy reproduces the selected definition; it does not attest an image build.

This reference uses the pinned real claude CLI from [the reference recipe](../../reference-recipes/lock.json), without added knowledge or production workflow packages.

[Build and qualification](../../reference-recipes/README.md) describe the selected Python base, native artifact integrity and current-launch bootstrap. Offline qualification exercised actual CLI startup, declared files and isolated gates. No inference or subscription login was performed.

## Operator credential binding

Supply `ANTHROPIC_API_KEY` in the benchmark process environment; the logical raw reference delivers it as `ANTHROPIC_API_KEY` only inside the selected run. This is the [native CLI API-key path](https://code.claude.com/docs/en/authentication#authentication-precedence). The reference uses a fresh native home and does not read or copy a subscription login file.

For Bash, read the value without putting it in shell history:

```sh
read -rs -p "API key: " ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY
silverquillm run --candidate candidates/vanilla-claude-standalone--650023f7 --benchmark smoke --timeout 3600
unset ANTHROPIC_API_KEY
```

A secret manager may instead populate the same environment variable before starting the benchmark or scheduler. Keep values outside definitions, candidate trees and results. Subscription-login lifecycle remains unsupported by this benchmark host.
