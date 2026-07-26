# Bootstrap / Mirroring procedure

## Human gate — initial creation of md-mt/termproof-plugin-template

GitHub requires an initial default-branch commit to create a repository. No PR-only policy violation is intended here — this human gate is recorded explicitly:

1. Maintainer creates empty repo md-mt/termproof-plugin-template via GitHub UI with no files.
2. From md-mt/termproof main after reviewed PR merges containing plugin-template/:

   ```bash
   ./plugin-template/scripts/bootstrap.sh md-mt/termproof-plugin-template
   cd ../termproof-plugin-template
   git init
   git add .
   git commit -m "Initial commit: TermProof plugin template"
   git branch -M main
   git push -u origin main
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
git commit -am "Sync template from termproof@SHA"
git push
```

If template repo main is protected, open PR there as well.
