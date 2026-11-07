# Ion — instruções para agentes executores

Este repositório contém a aplicação de voz e interface preservada e a nova camada Ion.
A autoridade arquitetural é Ion; o supervisor baseado no Microsoft Agent Framework
coordena NVIDIA e Gemini e é o único responsável por executar testes e aprovar tarefas.

## Papéis
- Ion decide arquitetura, stack, contratos, arquivos e critérios de aceite.
- NVIDIA e Gemini são executores colaborativos. Ambos podem escrever, implementar e corrigir.
- NVIDIA tem preferência inicial para programação; o supervisor também distribui tarefas reais ao Gemini.
- Os executores nunca revisam nem aprovam o trabalho uns dos outros. Não criem etapas de revisão.
- O supervisor executa os comandos de teste definidos no plano, devolve falhas ao executor e aprova quando passar.

## Escopo de cada tarefa
- Altere somente os arquivos explicitamente listados na tarefa.
- Não escolha outra linguagem, framework, arquitetura ou biblioteca por conta própria.
- Não sobrescreva arquivos fora do workspace informado.
- Não acesse nem altere .env, config/api_keys.json, .git, bancos pessoais, credenciais ou tokens.
- Não instale dependências, não execute comandos de instalação e não faça commits.
- Se uma dependência ou requisito for impossível, informe o bloqueio ao supervisor em vez de improvisar.
- Preserve os contratos e imports existentes. Faça mudanças incrementais.

## Aplicação existente — preservar
- `main.py` contém a sessão de voz e integra a interface com o runtime Gemini Live existente.
- `ui.py` e `web/index.html` são interfaces existentes; microfone, Orb, áudio e layout devem ser preservados.
- `web_ui.py` é a ponte HTTP/eventos da interface web.
- `core/`, `actions/`, `memory/`, `providers/`, `plugins/` e `dashboard/` são módulos já usados.
- Há imports absolutos como `from core...` e `from actions...`; não mova essas pastas sem uma tarefa explícita que inclua a migração de todos os imports e testes.
- Novas capacidades do Ion ficam preferencialmente em `ion/`; ferramentas auto-descobertas ficam em `actions/`.

## Ambiente e execução
- O ambiente-alvo primário é Windows 10/11 com Python 3.12.
- Ferramentas de áudio e Qt precisam continuar isoladas do thread da UI.
- Ações são descobertas automaticamente por `core/action_loader.py` através de um dicionário `TOOL`.
- A ação deve retornar resultados estruturados e não alegar sucesso sem evidência.
- O workspace de projetos gerados fica em `Desktop/IonProjects`, salvo caminho especificado pelo usuário.
- O supervisor limita testes a comandos permitidos e executa-os dentro do workspace.

## Formato de entrega
O executor retorna JSON contendo:
- `summary`: resumo objetivo;
- `files`: lista de objetos `{path, content}` com o conteúdo integral de cada arquivo autorizado.

Não inclua revisão, aprovação ou relatório de testes inventado. Os resultados dos testes são produzidos pelo supervisor.
