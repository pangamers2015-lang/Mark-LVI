# Arquitetura do Ion

## Papéis

- **Ion (cérebro):** interpreta o pedido, consulta a enciclopédia, decide tecnologias e frameworks, especifica contratos, divide o trabalho e define critérios de aceite.
- **Microsoft Agent Framework (MAF):** runtime local do workflow supervisor. O supervisor controla agenda, concorrência, estado das tarefas, execução de testes e conclusão.
- **NVIDIA API:** agente executor de programação preferencial, sem exclusividade.
- **Gemini API:** agente executor colaborativo; também programa, implementa e corrige.
- **Supervisor:** único responsável por verificar os arquivos entregues, executar os testes declarados/automáticos e solicitar correções. NVIDIA e Gemini não fazem revisão nem aprovação.

## Ciclo

1. Ion gera plano estruturado com tecnologias, tarefas, arquivos permitidos, dependências e comandos de validação.
2. O supervisor valida a estrutura e impede dependências circulares.
3. Tarefas independentes e sem colisão de arquivos podem executar em paralelo. NVIDIA recebe prioridade inicial; o balanceador também atribui trabalho ao Gemini.
4. Cada executor devolve os arquivos completos em JSON.
5. O supervisor restringe gravações ao workspace e à lista de arquivos permitidos.
6. O supervisor executa os comandos de teste permitidos. Em falha, retorna a saída ao executor responsável e repete a validação, respeitando o limite de tentativas.
7. A tarefa só é marcada concluída quando os testes aplicáveis passam. Dependência ausente bloqueia, não é confundida com sucesso.

## NVIDIA: limite compartilhado

Todas as chamadas NVIDIA feitas pelo processo Ion passam por um único limitador deslizante de até 40 chamadas em 60 segundos. Chamadas excedentes aguardam; não há bypass no módulo de provider.

## MAF e execução local

O MAF roda como biblioteca Python dentro do processo local. Não é um modelo de IA e não exige Ollama. Gemini e NVIDIA são APIs remotas; o código de orquestração, a fila, o workspace e os testes rodam no Windows.

## Integração com a aplicação preservada

A ação `ion_develop_project` é descoberta automaticamente por `core/action_loader.py`. Ela é executada em segundo plano pela infraestrutura já existente, preservando o ciclo de voz e a interface de tarefas. A interface anterior, captura de microfone, backend, memória, ações e ferramentas permanecem na raiz como camada de compatibilidade. Não mover módulos com imports absolutos até validar no Windows.
