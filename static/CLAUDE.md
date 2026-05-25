# static/

## Purpose
All files served directly to the browser. No Python executes here.
The static handler in `handlers/static_handler.py` serves these files after
path traversal validation.

Nothing in this directory should ever contain secrets, API keys, or internal
path information. Assume all files here are publicly readable.

## File index

### `index.html`
The single HTML page for the application. Responsibilities:
- Loads Tailwind CSS from CDN
- Loads D3.js from CDN
- Loads `js/app.js` (deferred, so DOM is ready before JS runs)
- Defines the page structure: player dropdowns, stat selector, GW slider, chart containers
- Contains no inline JavaScript beyond what is unavoidable
- Contains no inline styles (use Tailwind classes only)

**Security note**: all dynamic content rendered into the DOM by D3.js must use
`.textContent` or D3's `.text()` — never `.innerHTML` on user-supplied or
API-supplied strings. See `js/CLAUDE.md`.

### `js/app.js`
All client-side JavaScript. See `js/CLAUDE.md`.

### `css/styles.css`
Custom CSS only for things Tailwind cannot handle (e.g. SVG-specific rules for D3 charts).
Tailwind utility classes in HTML cover everything else. Keep this file minimal.

## CDN dependencies

| Library | Version | Loaded from |
|---|---|---|
| Tailwind CSS | 3.x (play CDN) | cdn.tailwindcss.com |
| D3.js | 7.x | cdn.jsdelivr.net/npm/d3@7 |

**Why CDN and not local copies?**
For development, CDN is fine. For production, pin the CDN URL to a specific version
and add a `crossorigin="anonymous"` attribute plus a `integrity` (SRI hash) attribute
so the browser verifies the file hasn't been tampered with.

Example of production-safe script tag:
```html
<script
  src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"
  integrity="sha384-<hash>"
  crossorigin="anonymous">
</script>
```

## Security rules

1. **No secrets here**: API keys, tokens, or credentials must never appear in static files.
   The FPL API requires no key, so this is not a current risk — but it is a standing rule.

2. **SRI hashes on CDN scripts**: before going to production, every CDN `<script>` and
   `<link>` tag must include `integrity` and `crossorigin="anonymous"` attributes.
   This prevents a compromised CDN from executing arbitrary code in users' browsers.

3. **No inline event handlers**: no `onclick="..."` or `onerror="..."` in HTML.
   All event listeners are attached in `app.js`.

4. **Content-Security-Policy**: the server will send a `Content-Security-Policy` header
   restricting script sources to the CDN origins above. This is set in `base_handler.py`,
   not in HTML meta tags (HTTP headers take precedence and cannot be overridden by the page).
