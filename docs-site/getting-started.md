# Getting Started

TermProof verifies terminal and TUI behavior by running JSON recipes against a real process and saving evidence for review.

## Install

Until the first PyPI release is published, install from GitHub:

```bash
pip install git+https://github.com/md-mt/termproof.git
```

From a source checkout:

```bash
git clone https://github.com/md-mt/termproof.git
cd termproof
uv run termproof --help
```

## Create A Recipe Pack

```bash
termproof init .termproof/recipes --name my-tui --command "my-tui"
```

## Run Verification

```bash
termproof run .termproof/recipes --video --out .termproof/runs
```

For larger suites:

```bash
termproof run .termproof/recipes --parallel 8 --skip-unchanged --out .termproof/runs
```

Upload `.termproof/runs` as a CI artifact so reviewers can inspect the cast, screenshots, text snapshots, video, JSON result, and Markdown report.
