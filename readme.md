# Ion

**Ion é um assistente local com cérebro de planejamento e agentes executores colaborativos.**

Esta versão preserva a aplicação completa Mark-LVI que já fornecia interface web/desktop, microfone, áudio, Gemini Live, memória, ferramentas, ações, plugins e painel remoto. A camada Ion é adicionada sem remover esses módulos de compatibilidade.

## Arquitetura

- **Ion:** decide arquitetura, tecnologias e tarefas, usando a enciclopédia técnica existente.
- **Microsoft Agent Framework:** runtime local do supervisor.
- **NVIDIA API:** executor prioritário para código.
- **Gemini API:** executor colaborativo que também programa e corrige.
- **Supervisor:** único responsável por distribuir tarefas, controlar concorrência, executar testes e solicitar correções. Os modelos executores não revisam nem aprovam.

## Estrutura principal

- `ion/` — cérebro, providers e orquestração do novo sistema.
- `actions/` — ações descobertas automaticamente pela aplicação.
- `core/` — áudio, voz, dispositivos, execução e runtime preservados.
- `memory/` — memória, continuidade e cognição existentes.
- `knowledge/` — enciclopédia e base técnica.
- `web/`, `web_ui.py`, `ui.py` — interfaces preservadas.
- `dashboard/` — painel de controle.

Os diretórios antigos `core/`, `actions/`, `memory/` e os adaptadores de UI permanecem temporariamente na raiz porque o código existente usa imports absolutos desses nomes. Eles não devem ser movidos até a bateria de testes no Windows passar.

## Instalação

Consulte [docs/ION_SETUP.md](docs/ION_SETUP.md). O comando principal para dependências novas é:

```powershell
python -m pip install -r requirements-ion.txt
```

O pacote MAF não inclui nem exige Ollama. O MAF roda localmente; as chamadas Gemini/NVIDIA usam a internet.

## Configuração

Copie `.env.example` para `.env` e configure as chaves. Nunca faça commit do arquivo `.env`.

## Limites importantes

A camada de supervisor é implementada no código, mas precisa ser instalada e exercitada no Windows com as chaves e dependências reais. Resultados de chamadas remotas ou arquivos no GitHub não comprovam que microfone, áudio ou execução local estejam funcionando na máquina.
