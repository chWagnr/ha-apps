# Changelog

## [Unreleased]

## [0.5.1] - 2026-11-22

### Changes
- feat: Update repository URLs to point to "ha-apps" and improve documentation clarity ([73e656f](https://github.com/chWagnr/ha-apps/commit/73e656fdbcd9b0d6dc4718dc8a3a6fb4c5a245a0))
- feat: Update documentation to use "Home Assistant app" terminology and improve clarity ([2ce6f34](https://github.com/chWagnr/ha-apps/commit/2ce6f34f118929bc2f7abb45d11dbc2cea882f2b))
- feat: Bump version to 0.5.1 in Dockerfile, config.yaml, package.json, and package-lock.json ([d30611b](https://github.com/chWagnr/ha-apps/commit/d30611b3e1bbac5a5a4c45bda94c1ae1b40d7a7c))
- feat: Implement timestamping for upstream error logs ([b464b3d](https://github.com/chWagnr/ha-apps/commit/b464b3db4f1dc4803f6dc7e62f9f32dc019013c2))
- fix(deps): update dependency @modelcontextprotocol/sdk to v1.32.2 ([f97f6fd](https://github.com/chWagnr/ha-apps/commit/f97f6fd844c9aa2d4eb071d1c630f2daa6cdfc0a))
- chore(deps): update dependency node to v24.22.3 ([81a1cdf](https://github.com/chWagnr/ha-apps/commit/81a1cdf375266f15536b758b2e4d1d84b67d58cc))
- fix(deps): update dependency @modelcontextprotocol/sdk to v1.32.1 ([3f4915d](https://github.com/chWagnr/ha-apps/commit/3f4915d9a9a677cef814629328127288f361c48f))
- chore(deps): update dependency node to v24.22.0 ([33e7d69](https://github.com/chWagnr/ha-apps/commit/33e7d6912c13a060b7b24df2c4b23734f5936ec4))

## [0.5.0] - 2026-10-07

- Populate the MCP token and discovered Tandoor selection in app options on first start.
- Store MCP tokens only in app options; remove the unused pre-release token file.

## [0.4.1] - 2026-10-07

- Show login progress and success/error feedback directly below the sign-in form.
- Log login outcomes without credentials and respect hidden token fields.
- Add ISO 8601 UTC timestamps and severity to app log messages.

## [0.4.0] - 2026-10-07

- Generate a persistent MCP access token automatically on first start.
- Reveal the token on demand through the protected Ingress web UI.
- Keep manually configured MCP tokens as optional overrides.

## [0.3.0] - 2026-10-07

- Add one-time Tandoor login through a protected Home Assistant Ingress UI.
- Store only the returned token with owner-only permissions, bound to its origin.
- Keep manual API token configuration and activate MCP without a restart after login.

## [0.2.0] - 2026-10-07

- Discover installed Tandoor apps through Supervisor with the default role.
- Use the internal hostname and container port; keep manual URL support.
- Allow selecting a specific app and wait for Tandoor during startup.

## [0.1.0] - 2026-10-07

- Add authenticated Streamable HTTP access to Tandoor for amd64 and aarch64.
- Add read-only, recipe import and optional recipe editing modes.
- Isolate requests and limit bodies, origins and concurrent work.
