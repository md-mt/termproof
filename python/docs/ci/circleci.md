# CircleCI Orb

TermProof provides a CircleCI orb source at [`.circleci/orb.yml`](../../.circleci/orb.yml). The orb installs TermProof, runs a recipe pack, stores `.termproof/runs` as build artifacts, and publishes JUnit XML through CircleCI test results.

After the orb is published to the CircleCI registry, projects can use:

```yaml
version: 2.1

orbs:
  termproof: md-mt/termproof@1.0.0

workflows:
  verify:
    jobs:
      - termproof/verify:
          recipe-path: .termproof/recipes
```

The reusable command can also run inside an existing job:

```yaml
version: 2.1

orbs:
  termproof: md-mt/termproof@1.0.0

jobs:
  test:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - termproof/verify:
          recipe-path: examples/generic
          output-dir: .termproof/circleci
```

## Parameters

| Parameter | Default | Purpose |
| --- | --- | --- |
| `recipe-path` | required | Recipe file or recipe pack directory to run. |
| `output-dir` | `.termproof/runs` | Evidence output directory. |
| `termproof-source` | `git+https://github.com/md-mt/termproof.git` | Package source passed to `uvx --from`. Use `termproof` after PyPI publishing. |
| `video` | `true` | Render MP4 evidence. |
| `fps` | `60` | Video frames per second. |
| `extra-args` | empty | Extra arguments appended to `termproof run`. |

## Evidence

The orb stores the output directory as `termproof-evidence`. TermProof verification failures still upload evidence before the job exits non-zero; use workflow reruns or SSH debugging to inspect partial output when dependency installation fails before TermProof starts.

The orb also writes JUnit XML at `latest-report.xml` and publishes it with `store_test_results`, so failures appear in CircleCI's Tests tab.

## Publishing

Validate the orb source before publishing:

```bash
circleci orb validate .circleci/orb.yml
```

Publish from a CI context that has a CircleCI token and access to the `md-mt` namespace:

```bash
circleci orb publish .circleci/orb.yml md-mt/termproof@1.0.0
```
