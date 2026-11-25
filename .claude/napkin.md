# Napkin Runbook

## Curation Rules
- Re-prioritize on every read.
- Keep recurring, high-value notes only; max 10 items per category.
- Each item includes a date and an explicit "Do instead" action.

## Execution & Validation
1. **[2026-11-25] Book outputs are grouped by execution timestamp.**
   Do instead: keep generated CBZ/PDF files inside a unique `saida/YYYY-MM-DD_HH-MM-SS/` folder.
2. **[2026-11-25] Manga input is already extracted into numbered chapter folders.**
   Do instead: point book-generation scripts at the extracted collection folder; do not assume the adjacent `.7z` is expanded.
