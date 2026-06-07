# Pushing this repo to GitHub

The repository is already initialised and committed locally on branch `main`
(the ~800 MB persona corpus is git-ignored; the generator reproduces it from
`--seed 2026`). Pick one option.

## Option A — one command (needs the GitHub CLI `gh`, authenticated)
```bash
cd /path/to/Infinite-Persona
gh repo create persona-engine --public --source=. --remote=origin --push
```

## Option B — create the empty repo on github.com, then push
1. Go to https://github.com/new → name it **persona-engine**, set **Public**,
   do NOT add a README/.gitignore/license (this repo already has them) → Create.
2. Then:
```bash
cd /path/to/Infinite-Persona
git remote add origin https://github.com/<your-username>/persona-engine.git
git push -u origin main
```

## Option C — clean clone from the bundle (no lock/cruft), then push
```bash
git clone infinite-persona.bundle persona-engine
cd persona-engine
git remote add origin https://github.com/<your-username>/persona-engine.git
git push -u origin main
```

A `infinite-persona.bundle` file (a complete, portable copy of the repo) sits in
the folder for Option C or for backup.
