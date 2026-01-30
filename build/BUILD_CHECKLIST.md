# Build checklist (PyInstaller + Installer)

- Include new resource folders in `build/ssaa.spec` -> `datas`
- Access resources only through `app.paths.resource_path(...)`
- Add dynamic imports to `hiddenimports`
- Keep `app/version.py`, `version.json`, and `CHANGELOG.md` in sync
