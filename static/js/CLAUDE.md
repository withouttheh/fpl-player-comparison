# static/js/

## Purpose
All client-side JavaScript. Communicates with the Python server via `fetch()`,
transforms the JSON responses, and renders D3.js visualisations into the DOM.

## File index

### `app.js`
The single JS file for the application. Organised into clear sections:

```
1. Config          — API base URL, stat labels, colour palette
2. State           — selected players, selected stat, GW range (plain JS object)
3. API calls       — fetch wrappers for /api/players, /api/player/<id>/history, /api/player/<id>/fixtures
4. Chart renderers — D3.js bar chart, line chart, radar chart (each a standalone function)
5. UI controls     — dropdowns, stat selector, GW slider event listeners
6. Init            — called once on DOMContentLoaded; populates dropdowns, renders default state
```

## D3.js patterns used

**Bar chart** (`renderBarChart(data, stat, players)`)
Grouped bar chart comparing two players per gameweek on a single stat.
Uses `d3.scaleBand` for x-axis, `d3.scaleLinear` for y-axis.

**Line chart** (`renderLineChart(data, stat, players)`)
Cumulative line chart over the selected gameweek range.
Uses `d3.line`, `d3.scaleLinear` for both axes, `d3.axisBottom/Left`.

**Radar chart** (`renderRadarChart(data, player)`)
Per-player radar across attacking/defensive metrics.
Uses `d3.scaleLinear` mapped to polar coordinates — built manually, not a D3 plugin.

## Security rules

### XSS — the primary client-side risk

All data displayed in the DOM comes from the FPL API via the Python server.
Even though we control the server, treat all API data as untrusted.
Player names, team names, and any string value could contain HTML or script characters
if the FPL API were ever compromised or if data is malformed.

**Rule: never use `.innerHTML` on data from the API.**

Safe:
```js
element.textContent = player.full_name;        // safe — browser does not parse as HTML
d3.select("p").text(player.full_name);          // safe — D3 .text() sets textContent
```

Unsafe:
```js
element.innerHTML = player.full_name;           // NEVER — parses as HTML
container.innerHTML = `<p>${player.full_name}</p>`;  // NEVER
```

For SVG text labels in D3, use `.text()` — never `.html()`.

### fetch() — validating API responses

Never assume the server returns the expected shape.
Always check before accessing nested properties:

```js
async function fetchHistory(playerId) {
    const res = await fetch(`/api/player/${encodeURIComponent(playerId)}/history`);
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data)) throw new Error("Unexpected response format");
    return data;
}
```

`encodeURIComponent` on any value interpolated into a URL — even if it came from
a dropdown that was populated from the API, it must still be encoded.

### No dynamic code evaluation

Never use `eval()`, `new Function()`, or `setTimeout("string")`.
D3 and the patterns above do not require these.

### Error display

Errors (failed fetches, unexpected data shapes) are displayed to the user as a
plain text message in a dedicated error container in the DOM.
Never write error objects or stack traces into the DOM — they leak internal structure.
