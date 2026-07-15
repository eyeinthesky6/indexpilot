# AI discovery

IndexPilot's public documentation is available to search engines, coding agents, and AI assistants.
The deployed site publishes `robots.txt`, `sitemap.xml`, and `llms.txt` from the Next.js application.

## Explicit crawler access

`ui/app/robots.ts` explicitly allows:

| Agent | Purpose |
|---|---|
| `OAI-SearchBot` | Inclusion and citation in ChatGPT search results |
| `Claude-SearchBot` | Inclusion in Claude's search index |
| `Claude-User` | Pages fetched when a Claude user asks for them |

The wildcard rule also allows ordinary search crawlers and other readers. `GPTBot` and `ClaudeBot`
currently inherit that public access, but they are model-development crawlers and are **not required**
for search visibility. They can be denied separately in the future without blocking the three agents
above.

`llms.txt` is a short machine-readable project map. It helps an assistant find canonical pages, but it
does not replace `robots.txt`, the sitemap, semantic HTML, or normal links.

## Human and agent-readable pages

The public site uses text headings, descriptive links, image alternative text, semantic page regions,
and structured project metadata. These make the same content usable by people, screen readers, and
browser-based agents. The pages do not carry a `noindex` directive.

## Verification

After a Pages deployment, check:

```bash
curl -fsSL https://eyeinthesky6.github.io/indexpilot/robots.txt
curl -fsSL https://eyeinthesky6.github.io/indexpilot/sitemap.xml
curl -fsSL https://eyeinthesky6.github.io/indexpilot/llms.txt
```

Crawler access makes the project eligible to be discovered; it does not guarantee ranking or citation.
Useful public docs, inbound links, and accurate repository metadata still determine whether a result is
worth showing.

## Primary guidance

- [OpenAI: Publishers and developers FAQ](https://help.openai.com/en/articles/12627856-publishers-and-developers-faq)
- [Anthropic: web crawler controls](https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler)
- [Anthropic: blocking and removing content](https://support.anthropic.com/en/articles/10684638-blocking-and-removing-content-from-claude)
