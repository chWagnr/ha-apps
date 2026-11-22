# Home Assistant app contributions

- Write commit subjects and bodies, pull request titles, and changelog entries in English, regardless of the language used in the conversation.
- Use "Home Assistant app" in user-facing text. Preserve compatibility identifiers such as `addon_config`, Supervisor API paths, and image names.
- Use a commit subject that describes the user-visible change. GitHub Actions copies commit subjects into the generated changelog, so review the wording before committing or squash merging.
- Let the changelog workflow generate release entries when an app version changes. Write any manually maintained release notes in English.
