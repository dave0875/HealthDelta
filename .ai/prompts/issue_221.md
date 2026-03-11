Issue: #221

Title: Fetch ORIN-generated insights into the iPhone app

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/221

Prompt
- Add the smallest end-to-end path that lets the iPhone app fetch generated insight cards from ORIN after an upload.
- Keep the existing local app-sandbox insight loading path as fallback.
- The first ORIN implementation may generate a narrow insight payload directly from the uploaded iOS dataset rather than introducing a full operator round-trip into the backend container.
- Cover success, empty-state, and failure behavior in tests.
