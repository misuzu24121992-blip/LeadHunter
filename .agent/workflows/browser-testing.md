---
description: How to test web pages in the browser
---

## Browser Testing Rules

1. **Always reuse the user's existing Chrome browser** when testing any web page, especially pages that require login (Vercel, GitHub, Turso, etc.)
2. Use `ReusedSubagentId` from a previous browser subagent when continuing work on the same page
3. Never open a fresh browser session if the user already has a page open — their login sessions are already active
4. When the user has a browser page open (visible in metadata), prefer interacting with that existing page rather than creating new ones
