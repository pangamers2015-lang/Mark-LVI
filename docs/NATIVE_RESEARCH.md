# Jarvis native research

The default `web_search` action now runs inside Jarvis. It does not delegate web
research to FCC, Qwen, or another assistant.

## Required API keys

Set both keys in the process environment:

- `NVIDIA_API_KEY`: NVIDIA NIM inference.
- `TAVILY_API_KEY`: the single configured web-search provider.

Alternatively, add these fields to the existing local `config/api_keys.json`
(the file is not meant to be committed):

```json
{
  "nvidia_api_key": "nvapi-...",
  "tavily_api_key": "tvly-..."
}
```

Environment variables take precedence. Never commit real keys.

## Runtime

Install the project's requirements with:

```powershell
python -m pip install -r requirements.txt
```

The research workflow uses:

- LangGraph for intent/depth routing and bounded workflow execution.
- Tavily as the only web-search provider.
- NVIDIA Nemotron 3 Ultra through the OpenAI-compatible NVIDIA NIM endpoint.
- HTTP page extraction for source evidence and URL-based citations.

The model defaults to `nvidia/nemotron-3-ultra-550b-a55b`. Override it with
`JARVIS_RESEARCH_MODEL` if needed. Model inference is hosted by NVIDIA; the
550B model is not downloaded or run on the local PC.

## Modes

- `search`: bounded fast search and cited synthesis.
- `research`: multi-query deep research, parallel source collection, page
  extraction, and a structured report with citations.
- `news`, `price`, `compare`: specialized prompts through the same research
  pipeline and same Tavily provider.
- `weather`: separate Open-Meteo public weather API; it is not a web-search
  provider.

If either key is missing, Jarvis returns a clear configuration error instead
of silently falling back to another search engine or external agent.
