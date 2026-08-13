# Homebrew

Install TermProof from the repository tap:

```bash
brew tap md-mt/termproof https://github.com/md-mt/termproof
brew install termproof
termproof --help
```

If Homebrew asks for tap trust:

```bash
brew trust --formula md-mt/termproof/termproof
brew install termproof
```

The formula installs `agg`, `ffmpeg`, and `python@3.13`, so video evidence works without a separate Rust toolchain.
