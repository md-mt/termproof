# Homebrew

TermProof ships a tap-compatible Homebrew formula at `Formula/termproof.rb`.

## Install

```bash
brew tap md-mt/termproof https://github.com/md-mt/termproof
brew install termproof
termproof --help
```

If Homebrew asks you to trust the tap before installing, trust only this formula:

```bash
brew trust --formula md-mt/termproof/termproof
brew install termproof
```

The formula installs Homebrew `agg`, `ffmpeg`, and `python@3.13`, so `termproof run --video` works without a separate Rust toolchain.

## Upgrade

```bash
brew update
brew upgrade termproof
```

## Smoke Test

```bash
termproof init .termproof/recipes --name homebrew-smoke --command "printf ready"
termproof run .termproof/recipes --out .termproof/runs
```
