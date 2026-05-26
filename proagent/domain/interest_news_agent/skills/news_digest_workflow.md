# News Digest Workflow

## When to Use

Use this workflow for Chinese briefings that combine world, technology, AI,
finance, anime, convention, football, and World Cup items.

## Procedure

1. Call `memory_search` for saved preferences such as teams, leagues, anime titles, sources, language, time window, and digest length.
2. Call `news_source_catalog` to choose feeds and search queries for the requested categories.
3. Use `fetch_feed` for RSS/Atom sources and `web_news_search` for fresh web/news queries.
4. Deduplicate by URL first, then by very similar title.
5. Keep only items with a source URL.
6. Produce the digest with the required Chinese columns and original links.

## Quality Rules

- Prefer primary or reputable source pages over reposts.
- Do not include claims that only appear in search snippets unless the snippet is clearly attributable and linked.
- Label event dates explicitly for Shanghai convention and World Cup items.
- Use short summaries. The link is the handoff to the full article.
