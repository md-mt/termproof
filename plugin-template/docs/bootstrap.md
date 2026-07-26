# Bootstrap / Mirroring procedure

## Human gate — initial creation of md-mt/termproof-plugin-template

GitHub requires an initial default-branch commit to create a repository. No PR-only policy violation is intended here — this human gate is recorded explicitly:

1. Maintainer creates empty repo md-mt/termproof-plugin-template via GitHub UI with no files.
2. From md-mt/termproof main after reviewed PR merges containing plugin-template/:

   ```bash
   # From termproof checkout main — copy source out of monorepo first
   cp -R plugin-template ../termproof-plugin-template
   cd ../termproof-plugin-template
   git init
   git remote add origin https://github.com/md-mt/termproof-plugin-template.git
   git add .
   git commit -m "Initial commit: TermProof plugin template"
   git branch -M main
   git push -u origin main
   ```

   Or use the bootstrap script (recommended):

   ```bash
   ./plugin-template/scripts/bootstrap.sh md-mt/termproof-plugin-template
   ```

3. Enable Template repository setting in GitHub repo settings.
4. Add branch protection requiring PRs.

## Ongoing sync

Template source lives in md-mt/termproof/plugin-template/. All changes to the template arrive by PR there.

Sync to separate repo:

```bash
./plugin-template/scripts/sync.sh ../termproof-plugin-template
cd ../termproof-plugin-template
git status
git add -A
git diff --cached   # review what will be committed
git commit -m "Sync template from termproof@SHA"
git push
```

If template repo main is protected, open PR there as well.
