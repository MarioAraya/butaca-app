# Test Normandie scraping feature

Verify that the Normandie scraper works end-to-end: backend scrapes the site, data lands in the DB, and the frontend shows the movies. Take 3 screenshots and save them for review.

## Steps

### 0. Pre-flight checks

- Confirm `frontend/src/App.jsx` has `'normandie'` in `TARGET_PATTERNS`. If missing, add it:
  ```js
  const TARGET_PATTERNS = ['imperio', 'estaci', 'normandie']
  ```
  Then note in the summary that you added it.

- Confirm `.env` exists in the project root with `API_ADMIN_KEY`. If missing, use the default `change-me-in-production` and note it.

### 1. Start the backend

```bash
uvicorn src.main:app --reload --port 8000
```

Run in background. Wait 3 seconds, then verify it's up:

```bash
curl -s http://localhost:8000/api/v1/health || curl -s http://localhost:8000/
```

### 2. Start the frontend

From the `frontend/` directory:

```bash
npm run dev
```

Run in background. Frontend will be available at `http://localhost:5175`. Wait 3 seconds.

### 3. Trigger Normandie scrape

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/scrape \
  -H "X-API-Key: ${API_ADMIN_KEY:-change-me-in-production}" \
  | python3 -m json.tool
```

Wait for it to finish (the endpoint is synchronous — it returns when done). Log the result.

### 4. Verify data in the API

```bash
curl -s "http://localhost:8000/api/v1/movies" \
  | python3 -c "
import sys, json
movies = json.load(sys.stdin)
norm = [m for m in movies if m.get('slug','').startswith('normandie-')]
print(f'Total movies: {len(movies)}')
print(f'Normandie movies: {len(norm)}')
for m in norm[:5]:
    print(f'  - {m[\"title\"]} ({m[\"slug\"]})')
"
```

If 0 Normandie movies found, stop and report the error — do not continue to screenshots.

### 5. Take 3 screenshots

Use the browser devtools MCP (or Puppeteer/Playwright if available) to open and screenshot:

**Screenshot 1 — Movie list with Normandie entries visible**
- URL: `http://localhost:5175`
- Wait for the movie cards to render
- Save to: `screenshots/normandie-test/01-movie-list.png`

**Screenshot 2 — A Normandie movie card in detail**
- On the same page, click on any movie card that has `Normandie` shown as the cinema
- Wait for the modal to open
- Save to: `screenshots/normandie-test/02-movie-modal.png`

**Screenshot 3 — Raw API response in browser**
- URL: `http://localhost:8000/api/v1/movies`
- Scroll so Normandie slugs are visible (use browser find or scroll down)
- Save to: `screenshots/normandie-test/03-api-response.png`

Create the output directory first:
```bash
mkdir -p screenshots/normandie-test
```

### 6. Summary report

Print a summary:
- Did the scrape succeed?
- How many Normandie movies were found?
- Were screenshots taken successfully?
- Was `TARGET_PATTERNS` modified? (if so, remind the user to commit that change)
- Path to screenshots folder

## Notes

- Screenshots folder is gitignored — add `screenshots/` to `.gitignore` if not present.
- The scrape hits the real normandie.cl site — needs internet access.
- If the backend is already running on port 8000, skip step 1.
- If the frontend is already running on port 5175, skip step 2.
