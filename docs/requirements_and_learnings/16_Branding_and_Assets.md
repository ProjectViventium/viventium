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
  - `client/src/hooks/Endpoint/Icons.tsx` and `client/src/utils/agents.tsx`: agent-avatar
    fallbacks use `assets/logo.svg` so missing built-in or user agent avatars show the Viventium
    mark instead of LibreChat's generic feather icon.
- **Footer branding**:
  - `client/src/components/Chat/Footer.tsx`: uses `Viventium ${Constants.VERSION}` link + `com_ui_latest_footer`.
  - `client/src/locales/**/translation.json`: `com_ui_latest_footer` set to `Viventium — Augmented Human Intelligence`.
- **UI links**:
  - `client/src/components/ui/AdminSettingsDialog.tsx`: "More info" link points to `https://viventium.ai`.
  - `client/src/components/SidePanel/Agents/Code/ApiKeyDialog.tsx`: code API link points to `https://viventium.ai`.
- **Copied assets** (post-build): `client/public/assets/*`
  - `site.webmanifest` icon paths are `/assets/...` because `post-build` copies `public/assets` → `dist/assets`.

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
  - Relative path (`/assets/...`) → may not resolve correctly
- **Note**: If the agent's avatar is updated via the Agent Builder, the `iconURL` in `librechat.yaml` must be manually updated to match.
- **Note**: LibreChat does not accept client-sent `iconURL` for conversations; `iconURL` is derived server-side from the selected model spec (`spec`). See `22_Gateway_Conversation_Metadata_Parity.md`.

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
