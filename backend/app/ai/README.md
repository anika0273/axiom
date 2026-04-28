# ai

Claude (Anthropic SDK) integration.

| File | Purpose |
|---|---|
| `client.py` | Initialises the `anthropic.AsyncAnthropic` client (singleton) |
| `prompts.py` | All prompt templates as named string constants — never inline elsewhere |
| `summariser.py` | Generates natural-language experiment summaries from stats results |
| `advisor.py` | Recommends next actions (stop/continue/iterate) given experiment state |

Guidelines:
- Use `cache_control` on long system prompts to reduce latency and cost
- Default model: `claude-sonnet-4-6`
- Return structured data via tool use / structured output where possible
- Log token usage in debug mode
