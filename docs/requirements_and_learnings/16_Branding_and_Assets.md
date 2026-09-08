<!-- VIVENTIUM START
Purpose: Document Viventium branding requirements and how favicon/logo assets are applied.
Details: Keep this updated when branding assets or metadata change.
VIVENTIUM END -->

# Viventium Branding and Assets

## Requirements
- Use the assets in `docs/assets/favicon_viv/` as the **single source of truth** for logos, favicons, and app icons.
- LibreChat and the modern agent playground must **only** show Viventium branding (no upstream names).
- Social share metadata must use Viventium title/description and link to `https://viventium.ai`.
- Help/marketing links in the modern playground must point to `https://viventium.ai`.

## Everyday interface

Use short, human wording and existing components. Show the useful state and primary action first;
put account mechanics, experimental integrations, exclusivity and diagnostics in details. A stored
account means saved, not verified access. Keep explicit API-key, sign-in and removal paths available.
The Connected Accounts shortcut opens those rows first. On narrow screens, the active settings tab
must remain visible, rows must fit, and controls must work by keyboard in light and dark themes.
Activity details stay separate from the answer, and show original events without duplicate summaries.
Main's landing view needs no technical role description. Keep that choice in the managed agent
source, with model-menu metadata derived by the existing compiler. Key dialogs use provider display
names and associate their retention description with the dialog for assistive technology.

A temporary server outage must not be presented as a rejected sign-in. Authentication owns refresh
and redirects: a confirmed rejected session or successful refresh without a token goes to sign-in;
transport, rate-limit and server failures preserve the requested route. Reuse the request library's
bounded recovery and offer one Retry action if the initial session cannot be checked. Do not infer
rejection from elapsed time, clear a known session on a transient user lookup failure, or claim an
unverified session is authenticated. Preserve query, hash and subdirectory destinations.
Explicit Log out opens the local sign-in page on either server success or failure. Its trusted
local destination is separate from post-login redirect validation; identity-provider logout keeps
its existing server-authored redirect.

## Specifications
### Asset sources
- Favicon + app icons: `docs/assets/favicon_viv/`
- Manifest template: `docs/assets/favicon_viv/site.webmanifest`

### LibreChat (`viventium_v0_4/LibreChat`)
- **HTML metadata + icons**: `client/index.html`
  - Title: `Viventium`
  - Description: `Viventium — Augmented Human Intelligence`
  - Social metadata: `og:*` + `twitter:*`
  - Manifest link: `assets/site.webmanifest`
- **PWA manifest config**: `client/vite.config.ts`
  - `manifest.name/short_name`: `Viventium`
  - Icons: `assets/web-app-manifest-192x192.png`, `assets/web-app-manifest-512x512.png`
- **Runtime defaults**:
  - `api/server/routes/config.js`: default `appTitle` + `helpAndFaqURL` to Viventium.
  - `client/src/routes/Layouts/Startup.tsx`: fallback document title.
  - `client/src/components/Auth/AuthLayout.tsx`: fallback logo alt text.
  - `client/src/hooks/Endpoint/Icons.tsx`, `client/src/utils/agents.tsx`, and
    `client/src/components/Endpoints/*Icon.tsx`: agent/model fallback surfaces use
    `/assets/logo.svg` so missing built-in or user agent avatars show the Viventium mark instead
    of LibreChat's generic feather icon.
  - `client/src/components/Chat/Menus/Endpoints/components/SpecIcon.tsx`: model-spec icon URLs
    that are local asset paths, such as `/assets/logo.svg`, are rendered as images instead of being
    treated as built-in icon keys.
  - `client/src/components/Endpoints/viventiumLogoTheme.ts`,
    `client/src/components/Endpoints/ViventiumLogoIcon.tsx`, and
    `client/src/components/Endpoints/URLIcon.tsx`: the Viventium logo SVG receives the active app
    light/dark `color-scheme` when the user explicitly chooses light or dark mode; `system` mode
    keeps the SVG's native `prefers-color-scheme` behavior.
- **Footer branding**:
  - `client/src/components/Chat/Footer.tsx`: uses `Viventium ${Constants.VERSION}` link + `com_ui_latest_footer`.
  - `client/src/locales/**/translation.json`: `com_ui_latest_footer` set to `Viventium — Augmented Human Intelligence`.
- **UI links**:
  - `client/src/components/ui/AdminSettingsDialog.tsx`: "More info" link points to `https://viventium.ai`.
  - `client/src/components/SidePanel/Agents/Code/ApiKeyDialog.tsx`: code API link points to `https://viventium.ai`.
- **Copied assets** (post-build): `client/public/assets/*`
  - `site.webmanifest` icon paths are `/assets/...` because `post-build` copies `public/assets` → `dist/assets`.

### Browser stylesheet compatibility

LibreChat's standard `client/.browserslistrc` gives PostCSS the same Baseline Widely Available
2025-05-01 floor already shipped by Vite 7: Chrome/Edge 107, Firefox 104, and Safari 16, including
compatible mobile/downstream browsers. Keep it aligned when changing the JavaScript target.
`postcss-preset-env` owns required CSS fallbacks and its built-in Autoprefixer; do not add a second
prefixing pass. Native dark, group, and focus selectors must retain their meaning, and Safari's
required prefixes must remain. Do not suppress warnings or raise the browser floor merely to
make builds quiet.

The existing LibreChat release-contract suite processes real CSS and checks that its target list
includes the installed Vite defaults. Supporting dev/build measurements are separate from real
browser responsiveness, theme, keyboard, and mobile QA in `BRAND-001`.

Sources: [Vite 7 target change](https://v7.vite.dev/guide/migration.html),
[PostCSS Preset Env target/prefix ownership](https://github.com/csstools/postcss-plugins/blob/main/plugin-packs/postcss-preset-env/README.md),
[Browserslist dated Baseline queries](https://github.com/browserslist/browserslist#full-list).

### Modern agent playground (`viventium_v0_4/agent-starter-react`)
- **App metadata + icons**: `app/layout.tsx`
  - Uses `pageTitle`, `pageDescription`, `siteUrl` (from `app-config.ts`)
  - Adds `og:*` + `twitter:*` tags and favicon/app icon links
- **Header links**: `app/(app)/layout.tsx` (Viventium.AI)
- **Open Graph image**: `app/(app)/opengraph-image.tsx`
  - Uses Viventium logo from `public/viventium-logo.svg`
  - Fallbacks use local Viventium assets (no upstream wordmarks)
- **Asset locations**:
  - `public/`: `favicon.svg`, `favicon.ico`, `favicon-96x96.png`, `apple-touch-icon.png`,
    `web-app-manifest-*.png`, `site.webmanifest`, `viventium-logo.svg`
  - `app/`: `favicon.ico`, `icon.png`, `apple-touch-icon.png` (Next.js metadata discovery)

## Use Cases
- Browser tab + installable app show Viventium icon and name.
- Shared links render Viventium title/description and Viventium-hosted OG image.
- Playground footer/help links point to `https://viventium.ai`.

## Edge Cases
- Missing `APP_TITLE` or playground config → fallback to Viventium.
- LibreChat assets must live in `client/public/assets` so `post-build` copies them.
- Open Graph image generation expects local assets under `public/` for dev and Vercel for prod.

## Integration Points
- `docs/assets/favicon_viv/` is the authoritative asset source.
- `LibreChat/client/scripts/post-build.cjs` controls static asset copying.
- `agent-starter-react/app-config.ts` controls `pageTitle`, `pageDescription`, `siteUrl`, and logo paths.

## Learnings
- Keep Vite PWA manifest icons aligned with the asset folder that is copied in `post-build`.
- Next.js prefers icon files under `app/` for automatic metadata inclusion.

### ModelSpec iconURL for Agent Avatars
- **Problem**: ModelSpecs have an `iconURL` field, but setting it to an endpoint name (e.g., `agents`) shows the generic feather icon, not the agent's custom avatar.
- **Solution**: Use the **full URL** to the agent's avatar image stored in MongoDB.
- **Agent avatar storage**: Avatars are stored in MongoDB (`agents` collection) with a filepath like:
  ```
  /images/<user_id>/agent-<agent_id>-avatar-<timestamp>.png
  ```
- **Full URL format**: Prepend the domain to get the accessible URL:
  ```
  https://chat.viventium.ai/images/<user_id>/agent-<agent_id>-avatar-<timestamp>.png
  ```
- **Lookup command**: To find an agent's avatar URL from MongoDB:
  ```bash
  mongosh "<MONGO_URI>" --eval "db.agents.findOne({id: '<agent_id>'}).avatar"
  ```
- **iconURL options in modelSpecs**:
  - Full URL (`https://...`) → displays the image (use this for custom agent avatars)
  - Endpoint name (`agents`, `openAI`, etc.) → displays the endpoint's default icon
  - Relative Viventium asset path (`/assets/logo.svg`) → displays the local Viventium logo image
    and follows explicit app light/dark theme through `color-scheme`.
- **Note**: If the agent's avatar is updated via the Agent Builder, the `iconURL` in `librechat.yaml` must be manually updated to match.
- **Note**: LibreChat does not accept client-sent `iconURL` for conversations; `iconURL` is derived server-side from the selected model spec (`spec`). See `22_Gateway_Conversation_Metadata_Parity.md`.

### Local ModelSpec Logo Resolution (2026-05-18)
- **Observed issue**: Viventium model specs already used `iconURL: /assets/logo.svg`, but the model
  selector treated non-HTTP values as built-in icon keys. Because `/assets/logo.svg` was not a key in
  the endpoint icon map, agent model rows fell through to LibreChat's generic feather icon.
- **Rule**: Local asset paths, image extensions, HTTP(S) URLs, and `data:image/*` URLs are image
  sources unless they exactly match a known built-in icon key.
- **Theme rule**: The canonical `logo.svg` contains light and dark variants. When the app theme is
  explicitly `light` or `dark`, Viventium logo image elements must set the matching CSS
  `color-scheme`; when the app theme is `system`, the SVG's own `prefers-color-scheme` media query
  remains authoritative.
- **Regression case**: `qa/branding-assets/cases.md` `BRAND-004`.

### Local Avatar Resolution for Exported Conversation Data (2026-03-05)
- **Observed issue**: Imported/exported conversation/message docs can contain stale remote `iconURL` values (`https://chat.viventium.ai/...`) that fail locally and fall back to generic icons.
- **Reliable source**: Agent Builder avatar in `agents.avatar.filepath` (local `/images/...`) is the source of truth for current agent icon.
- **Additional root cause (older conversations)**:
  - Message avatar hooks attempted to resolve agents/assistants via `message.model` first.
  - For many historical messages, `message.model` is a base model name (e.g., `grok-4-1-fast-non-reasoning`), not an entity id.
  - This prevented fallback to `conversation.agent_id` / `conversation.assistant_id`, so stale remote `iconURL` paths were used.
- **UI rule implemented (updated 2026-03-05)**:
  - Preserve stored conversation/message `iconURL` first so historical chats keep their original icon.
  - If that URL fails to load (stale/404), fall back to live `assistantAvatar` / `agentAvatar`.
  - If both fail, fall back to endpoint/default icon.
- **Files updated**:
  - `client/src/hooks/Messages/useMessageActions.tsx`
  - `client/src/hooks/Messages/useMessageHelpers.tsx`
  - `client/src/hooks/Messages/__tests__/useMessageActions.spec.tsx`
  - `client/src/components/Endpoints/EndpointIcon.tsx`
  - `client/src/components/Endpoints/ConvoIconURL.tsx`
  - `client/src/components/Endpoints/URLIcon.tsx`
  - `client/src/components/Endpoints/__tests__/URLIcon.spec.tsx`

<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:START -->
## Stable requirement declarations

Each line is the canonical public owner declaration for one stable requirement ID. Detailed sections supply implementation context; they must not narrow or contradict these declared outcomes.

CORE-017: Every user-facing Viventium surface uses the Viventium name and canonical V mark. Upstream LibreChat names, wordmarks, and generic feather fallbacks must not appear as product identity.
<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:END -->
