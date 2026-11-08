# Pesquisa web nativa do Jarvis

O Jarvis executa pesquisa e síntese internamente: LangGraph coordena o fluxo,
Siftdog fornece pesquisa e extração web auto-hospedadas, e NVIDIA Nemotron
planeja e sintetiza as evidências. A pesquisa não depende de provedores
comerciais de busca nem delega a FCC, Qwen ou outros agentes.

## Custos e chaves

- **Siftdog:** software open source sob licença MIT, executado localmente.
- **SearXNG:** metabusca open source usada pelo Siftdog para consultar mecanismos públicos.
- **Pesquisa:** sem chave de API paga e sem cobrança por consulta do Siftdog.
- **NVIDIA_API_KEY:** continua necessária para inferência hospedada do Nemotron.

Opcionalmente, configure `SIFTDOG_URL` (padrão
`http://127.0.0.1:8000`) e `SIFTDOG_API_KEY` se a autenticação for ativada
no serviço. Também podem ser definidas as chaves `siftdog_url` e
`siftdog_api_key` no arquivo local `config/api_keys.json`. A chave do
serviço é dispensável na configuração local padrão.

## Instalação e inicialização no Windows

A pesquisa web usa dois contêineres: Siftdog e SearXNG. É necessário instalar
e iniciar Docker Desktop com Docker Compose v2. O download das imagens é feito
na primeira inicialização.

Na raiz do repositório, execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\\scripts\\start_siftdog.ps1
```

O script cria um arquivo local `.env` com segredo aleatório para o SearXNG,
baixa as imagens, inicia os serviços e aguarda a API responder em
`http://127.0.0.1:8000/health`.

Para encerrar os contêineres e liberar a memória:

```powershell
powershell -ExecutionPolicy Bypass -File .\\scripts\\stop_siftdog.ps1
```

Os dados e configurações do serviço permanecem no repositório; o script de
parada não remove imagens baixadas. O Jarvis não instala Docker nem inicia o
serviço silenciosamente: a instalação e a primeira inicialização serão feitas
separadamente, após a preparação do ambiente.

## Arquitetura

- LangGraph: roteamento automático e orquestração de pesquisa rápida/profunda.
- Siftdog: API local de pesquisa, extração, rastreamento e mapas de sites.
- SearXNG: agrega mecanismos públicos sem chave de pesquisa paga.
- NVIDIA Nemotron 3 Ultra: planejamento de consultas e síntese com citações.
- Open-Meteo: API independente de clima, preservada.
- Playwright/browser control: automação de navegador, separada da pesquisa web.

O Siftdog usa ranking BM25. Mecanismos públicos podem aplicar CAPTCHA ou
limitação temporária; se todos os mecanismos ativos bloquearem a instância,
a pesquisa pode retornar erro 502. O modo avançado busca e extrai conteúdo
das páginas, mas páginas que dependem de JavaScript podem não ser totalmente
renderizadas.

O modelo padrão é `nvidia/nemotron-3-ultra-550b-a55b`. Pode ser alterado por
`JARVIS_RESEARCH_MODEL`. A inferência ocorre na infraestrutura da NVIDIA;
o modelo 550B não é baixado nem executado no PC local.

## Modos

- `search`: pesquisa rápida com fontes e síntese citada.
- `research`: pesquisa profunda com múltiplas consultas, coleta paralela,
  extração de páginas e relatório estruturado.
- `news`, `price`, `compare`: prompts especializados no mesmo pipeline.
- `weather`: API Open-Meteo, separada do mecanismo de pesquisa.

Se o serviço Siftdog estiver desligado, o Jarvis retorna um erro explícito com
orientação para iniciar o serviço; não troca silenciosamente para outro
provedor ou agente.
