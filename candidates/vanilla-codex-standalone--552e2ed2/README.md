# vanilla-codex-standalone

Standalone Karn Construct Definition.

Image: `sha256:a8b10ff219d5d81870c1b17eae9dbe0eb7494db1c8bd08adcb174b927b569cd6`

Definition: `sha256:42093d3be2d5f373ed756298450d133ee71c28fe743e4251b45a32706bf60055`

The source copy reproduces the selected definition; it does not attest an image build.

This reference uses the pinned real codex CLI from [the reference recipe](../../reference-recipes/lock.json), without added knowledge or production workflow packages.

[Build and qualification](../../reference-recipes/README.md) describe the selected Python base, native artifact integrity and current-launch bootstrap. Offline qualification exercised actual CLI startup, declared files and isolated gates. No inference or subscription login was performed.

## Operator credential binding

Supply `OPENAI_API_KEY` in the benchmark process environment; the logical raw reference delivers it as `CODEX_API_KEY` only inside the selected run. This is the [native CLI API-key path](https://learn.chatgpt.com/docs/non-interactive-mode#use-api-key-auth). The reference uses a fresh native home and does not read or copy a subscription login file.

For Bash, read the value without putting it in shell history:

```sh
read -rs -p "API key: " OPENAI_API_KEY
export OPENAI_API_KEY
silverquillm run --candidate candidates/vanilla-codex-standalone--552e2ed2 --benchmark smoke --timeout 3600
unset OPENAI_API_KEY
```

A secret manager may instead populate the same environment variable before starting the benchmark or scheduler. Keep values outside definitions, candidate trees and results. Subscription-login lifecycle remains unsupported by this benchmark host.
