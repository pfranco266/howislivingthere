# CLAUDE.md — How Is Living There?

## ⚠️ Security & Secrets — READ FIRST

This section is non-negotiable. Follow every rule, every time.

### Never expose secrets

- **NEVER** print, log, echo, display, or include the contents of any environment variable in any output — not in terminal output, not in code comments, not in error messages, not in `console.log` statements, not in commit messages.
- When referencing API keys in conversation, code comments, or documentation, **ALWAYS** use placeholder text: `sk-ant-***REDACTED***`, `pk.***REDACTED***`, etc.
- **NEVER** write code that logs or prints the value of `process.env.*`, `import.meta.env.*`, or `os.getenv(*)`. If you need to verify a key exists, check for truthiness only:
  ```python
  if not os.getenv("ANTHROPIC_API_KEY"):
      print("ERROR: ANTHROPIC_API_KEY not set")  # never print the actual value
  ```
- If a script fails due to a missing or invalid key, the error message should say `"ANTHROPIC_API_KEY is missing or invalid"` — **NEVER** `"ANTHROPIC_API_KEY value 'sk-ant-abc123...' is invalid"`.

### `.env` file rules

- `.env` is gitignored. Verify this before every commit.
- The `.env` file contains sensitive credentials. Never read its full contents into output. When you need to check what vars exist, use: `grep -oP '^[A-Z_]+' .env` (prints only variable names, not values).
- If you need to add or modify a `.env` variable, tell the developer what to add (with placeholder values) and let them do it manually. **Do NOT write the `.env` file directly if it contains real credentials.**

### Git safety

- Before any `git add` or `git commit`, always verify `.env` is in `.gitignore`.
- Never commit files in `data/raw/` — these may contain API responses with metadata.
- If you suspect a secret was accidentally committed, alert the developer immediately and recommend rotating the key.

### Mapbox token

The Mapbox public token (`VITE_MAPBOX_TOKEN`) is less sensitive since it ships in the frontend bundle. However, for production deployment, recommend the developer restrict it to their domain in the Mapbox dashboard.

---

## Project Overview

"How Is Living There?" is a web application that visualizes real-world living experience data from the Reddit subreddit r/howislivingthere. Users posted questions like "How is living in Lisbon, Portugal?" and commenters who live or have lived there share honest reviews. This app pulls that data, parses locations, and displays them on an interactive Mapbox globe where users can click any marker to read the top-voted comments about what it's actually like to live there.

Think of it as **YelpCamp but for cities, powered by Reddit reviews instead of user-generated content.**

## Architecture

**Static site with a separate data pipeline. No backend server needed.**

```
[Python Scraper] → Reddit public JSON → Claude API (parse titles) → Geocode → locations.json
[React App]      → reads locations.json → renders Mapbox GL map + UI
```

### Frontend: React + Vite
- **Map:** Mapbox GL JS via `react-map-gl` with `globe` projection
- **Styling:** Plain CSS with CSS variables (no Tailwind, no CSS-in-JS)
- **Data:** Static JSON file imported at build time from `src/data/locations.json`
- **Deployment target:** Vercel or Netlify (static)

### Data Pipeline: Python
- Located in `/scraper/` directory
- Runs independently from the React app
- Outputs to `src/data/locations.json` which the React app imports
- Uses Reddit's public JSON endpoints (no OAuth required)
- Uses Claude API (claude-sonnet-4-20250514) to parse location names from Reddit post titles
- Uses Nominatim (via geopy) for geocoding — FREE, no API key needed, but rate-limit to 1 req/sec

## Data Model

```typescript
// src/data/locations.json schema
interface Location {
  id: string;                    // Unique hash of city+country
  city: string;                  // "Lisbon"
  country: string;               // "Portugal"
  region?: string;               // "Europe" (for filtering)
  lat: number;                   // 38.7223
  lng: number;                   // -9.1393
  precision: "city" | "region" | "country";  // How specific the location is
  posts: Post[];                 // All Reddit posts about this location (merged)
}

interface Post {
  redditId: string;              // Reddit post ID for linking back
  title: string;                 // Original post title
  upvotes: number;               // Post score
  url: string;                   // Link back to Reddit thread
  comments: Comment[];           // Top 20 comments by score
}

interface Comment {
  text: string;                  // Comment body
  score: number;                 // Upvote count
  author: string;                // Reddit username
  redditId: string;              // Comment ID for linking
}
```

**Merging rule:** If multiple posts refer to the same city+country, merge them into one Location with multiple Posts. Sort posts by upvotes descending.

## Design System

The visual identity is dark, editorial, and clean. NOT generic SaaS — think "National Geographic meets Reddit."

### Colors (CSS variables)
```css
--bg-deep: #0f0f23;
--bg-mid: #1a1a2e;
--bg-panel: #141428;
--accent: #FF6B35;           /* Reddit-orange inspired */
--accent-dim: rgba(255,107,53,0.15);
--text: #ffffff;
--text-muted: rgba(255,255,255,0.5);
--text-dim: rgba(255,255,255,0.3);
--border: rgba(255,255,255,0.07);
```

### Typography
```css
/* Import from Google Fonts */
--font-display: 'DM Serif Display', Georgia, serif;   /* Headings, city names */
--font-body: 'DM Sans', -apple-system, sans-serif;    /* Body text */
--font-mono: 'DM Mono', monospace;                     /* Metadata, labels */
```

### Mapbox Configuration
```javascript
{
  style: 'mapbox://styles/mapbox/dark-v11',
  projection: 'globe',
  fog: {
    color: 'rgb(15, 15, 35)',
    'high-color': 'rgb(20, 20, 50)',
    'horizon-blend': 0.08,
    'space-color': 'rgb(10, 10, 25)',
    'star-intensity': 0.6,
  }
}
```

### Marker Styling
- Unclustered markers: orange (#FF6B35) circles with glow effect
- Clusters: larger orange circles with count, click to zoom in
- On hover: scale up, increase glow
- On click: fly to location, open detail popup/panel

### Map Behavior
- Globe slowly auto-rotates when idle and zoom < 4
- Auto-rotation stops on user interaction, resumes after idle
- Clicking a cluster zooms to expand it
- Clicking an individual marker opens a popup with city name, country, upvote count, and top comments
- Popup includes link back to original Reddit thread

## Component Structure

```
App.jsx
├── Header                    # "How Is Living There?" title + r/howislivingthere badge
├── MapView                   # Mapbox GL map (main content, full viewport)
│   ├── Source + Layers        # GeoJSON source with clustering
│   └── Popup                  # Appears on marker click
│       ├── LocationHeader     # City, country, upvote count
│       └── CommentCard[]      # Top comments with score + author
└── HintBar                   # Bottom bar: "scroll to zoom · click to explore"
```

### Popup Content
When a marker is clicked, show a Mapbox popup (not a separate panel) containing:
1. City name (DM Serif Display, large)
2. Country (DM Mono, small, dim)
3. Upvote badge (orange background, "▲ 847")
4. Subreddit attribution ("r/howislivingthere")
5. Divider
6. "Top Comments" label + "showing X of Y comments" count
7. Comment cards (scrollable):
   - Comment text in quotes
   - Author ("u/username") and score ("▲ 612")
   - First comment gets orange left border, rest get dim border
8. "View on Reddit →" link at bottom

## Scraper Pipeline

Uses Reddit's public JSON endpoints — no OAuth or API registration required.

### Step 1: scrape_reddit.py
- Hit `https://www.reddit.com/r/howislivingthere/top.json?t=all&limit=100`
- Set User-Agent header: `"HowIsLivingThere/1.0 (data visualization project)"`
- Paginate with `after` parameter until `after` is null
- For each post, fetch comments from `https://www.reddit.com/r/howislivingthere/comments/POST_ID.json?sort=top&limit=200`
- Keep top 50 qualifying comments per post (min 80 chars, score 5+, no bots, no stickied)
- Save raw data to `data/raw/posts.json`
- Rate limit: 1 request every 2 seconds

### Step 2: parse_locations.py
- Read raw posts
- Batch titles (15 per API call) and send to Claude API (claude-sonnet-4-20250514) to extract:
  ```json
  { "city": "Lisbon", "country": "Portugal", "precision": "city" }
  ```
- Handle edge cases:
  - `"How is living in the Bay Area?"` → `{ city: "San Francisco Bay Area", country: "United States", precision: "region" }`
  - `"How is life in rural Japan?"` → `{ city: "Rural Japan", country: "Japan", precision: "region" }`
  - Image-only posts with no location in title → `{ city: null, country: null, precision: null }` (skip these)
- Save to `data/raw/parsed_locations.json`

### Step 3: geocode.py
- For each parsed location, use Nominatim to get lat/lng
- Rate limit: max 1 request per 1.5 seconds (Nominatim policy)
- Cache results in `data/raw/geocode_cache.json` so re-runs are fast
- Save to `data/raw/geocoded.json`

### Step 4: merge_output.py
- Merge posts about the same location (same city+country after normalization)
- Sort comments by score descending, keep top 20 per post
- Output final `src/data/locations.json`

### Running the full pipeline:
```bash
cd scraper
python run_all.py
# Or skip re-scraping:
python run_all.py --skip-scrape
```

## Environment Variables

Stored in `.env` (gitignored). **Never display actual values — see Security section above.**

Required variables:
```
VITE_MAPBOX_TOKEN=pk.***REDACTED***
ANTHROPIC_API_KEY=sk-ant-***REDACTED***
```

The React app accesses the Mapbox token via `import.meta.env.VITE_MAPBOX_TOKEN` (Vite requires the `VITE_` prefix for client-exposed vars).

## Key Technical Decisions

1. **No backend** — static JSON consumed at build time. Add a backend later if needed.
2. **Mapbox GL JS** — globe projection with smooth zoom, dark style, clustering built-in.
3. **Popups over side panels** — keep UX simple for V1, user stays oriented on the map.
4. **Claude for title parsing** — regex is too fragile for the variety of post titles.
5. **Nominatim over Google Geocoding** — free, no API key, good enough for city-level precision.
6. **Python scraper separate from React** — different runtime, different concerns, run independently.
7. **Public Reddit JSON** — no OAuth registration needed, sufficient rate limits for batch scraping.

## Testing

- `npm run dev` — starts Vite dev server on localhost:5173
- `npm run build` — production build to dist/
- Scraper scripts are run manually from `/scraper/` directory

## Don't

- **Don't** print, log, or expose any API keys or secrets (see Security section)
- **Don't** write to `.env` directly if it contains real credentials — instruct the developer to update it manually
- Don't use Tailwind CSS — use plain CSS with variables
- Don't add a database — JSON file is the data store for V1
- Don't build auth or user accounts — this is a read-only data visualization
- Don't over-engineer the scraper — it runs manually, not as a service
- Don't use Create React App — we use Vite
- Don't add TypeScript for V1 — keep it simple, add types in V2
- Don't install UI component libraries (MUI, Chakra, etc.) — custom CSS only
- Don't use localStorage or sessionStorage in the React app
