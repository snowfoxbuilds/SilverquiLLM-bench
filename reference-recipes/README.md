# Native reference images

These recipes build two explicit benchmark reference images containing real Claude and Codex CLIs.
The package versions and SHA-512 artifact pins in `lock.json` come from the authoritative native configuration recipes.
The Codex pin names its Linux amd64 package, not the small npm JavaScript launcher package.
The base is an independently selected immutable Python Debian image with benchmark tools; it is not a production workflow image.

```sh
python reference-recipes/build.py --out /tmp/native-references --cache /tmp/native-packages
SILVERQUILLM_NATIVE_REFERENCES=/tmp/native-references python -m pytest tests/test_native_references.py -m integration
```

Build with the pinned Karn dependency installed. The builder verifies the exact Karn bootstrap/initializer bytes and native archives before packaging.
The output contains explicit definitions, build logs and a source hash inventory.
The image IDs in checked-in references identify the actual built bytes. A later rebuild can yield different bytes because operating-system packages are resolved during the build; a new image must receive a newly generated definition and candidate identity.
No reverse descriptor label or build receipt is required to run an existing immutable image.

The normal adapter invokes the real CLI with the benchmark prompt on standard input; the agent writes the declared proposal file.
The explicit `--check` mode instead runs only `--version`, verifies declared inputs and writes an offline qualification proposal.
Tests select a separate no-network, no-credential definition for that check.
Offline qualification covers native startup, current-launch UID/GID bootstrap, file paths, exit handling and isolated gates; it does not claim model inference, login or production readiness.

Build outputs and authentication values do not belong in this directory.
