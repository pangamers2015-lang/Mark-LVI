# Jarvis — integração do cérebro ChatGPT com a voz existente

## Decisão arquitetural

O ChatGPT será o cérebro central do Jarvis: interpreta a intenção, raciocina, planeja, escolhe ferramentas, decide quando delegar trabalho e revisa os resultados. O Jarvis continua sendo a camada local de execução, interface, permissões, memória operacional e integração com o computador.

A camada de voz existente deve ser preservada. Gemini e NVIDIA permanecem como provedores auxiliares/delegados, não como o cérebro principal. Qwen não faz parte desta arquitetura.

## O que a auditoria encontrou

- A interface web atual envia texto para `/api/texto`; o backend encaminha a mensagem por `_on_text_command`.
- A captura de microfone e o fluxo de áudio em tempo real estão no ciclo Gemini Live de `main.py`.
- O Gemini Live atual usa uma única sessão para áudio de entrada, transcrição, raciocínio, chamadas de ferramentas e áudio de saída.
- O projeto já contém `PipelineEngine`, que separa STT → LLM → TTS e conserva o contrato de eventos consumido pelo restante do aplicativo.
- Porém, selecionar o pipeline diretamente não preserva a voz atual: os provedores STT/TTS do pipeline são componentes diferentes do Gemini Live. Portanto, não se deve simplesmente trocar o modo padrão para `pipeline` e declarar a voz preservada.
- A aplicação já tem memória cognitiva local, registro de ações/ferramentas, confirmação de operações e ponte para Obsidian. Essas peças devem continuar locais e fornecer contexto ao cérebro por recuperação seletiva; não se deve presumir que o ChatGPT tenha acesso direto ao banco local.

## Fluxo-alvo

1. A interface atual continua sendo a única interface do Jarvis.
2. O componente de voz atual continua responsável por microfone, detecção de fala/pausas, transcrição, reprodução, voz e interrupção.
3. A transcrição ou texto digitado é entregue ao adaptador do cérebro ChatGPT.
4. O Jarvis recupera do SQLite/Obsidian somente as memórias e conhecimentos relevantes e os inclui no contexto da solicitação.
5. O ChatGPT retorna resposta e/ou plano de ação estruturado.
6. O orquestrador local valida o plano, aplica permissões e confirma operações sensíveis antes de executar.
7. Gemini e NVIDIA podem receber tarefas auxiliares quando o ChatGPT decidir delegar; seus resultados voltam ao ChatGPT para revisão.
8. A resposta final do ChatGPT é entregue à camada de voz existente para ser falada e exibida na interface.

## Autenticação ChatGPT

Preferir o fluxo oficial **Sign in with ChatGPT — token sharing para clientes open source/local-hosted**, com registro dinâmico do agente no primeiro login. Solicitar explicitamente o escopo `chatgpt.tokens.use.direct` junto dos escopos necessários, validar os escopos efetivamente concedidos e não inferir autorização a partir de um login de identidade.

- Não usar nem solicitar uma chave da API Platform como substituto silencioso do plano ChatGPT.
- Não persistir tokens em texto puro, no repositório, em logs ou no estado enviado à interface.
- Guardar credenciais com criptografia protegida pelo sistema operacional (DPAPI no Windows; armazenamento seguro equivalente nas demais plataformas).
- Implementar renovação, revogação, cancelamento, limites de uso e mensagens claras quando o compartilhamento da cota não for autorizado.
- A integração usa a Responses API com o token delegado. A compatibilidade de chamadas de ferramentas precisa ser validada no adaptador antes de habilitar execução autônoma.

## Implementação em etapas

1. Criar um adaptador de cérebro ChatGPT com autenticação oficial, armazenamento seguro, renovação e estado de conexão.
2. Separar a interface de voz do raciocínio sem substituir o modelo/voz atual. O adaptador de voz deve emitir transcrições para o cérebro e receber texto para fala.
3. Encaminhar texto digitado e transcrições para o mesmo cérebro, mantendo o contrato de eventos e a interface atuais.
4. Conectar o cérebro ao catálogo local de ferramentas com execução validada, permissões e confirmação para ações sensíveis.
5. Adicionar delegação explícita para Gemini e NVIDIA e retorno dos resultados ao ChatGPT.
6. Integrar recuperação de memória persistente SQLite e conhecimento visual Obsidian.
7. Validar primeiro o caminho de texto; depois voz, interrupção, ferramentas, delegação e retomada de sessão.

## Restrições de migração

- Não substituir a interface atual nem criar uma segunda interface.
- Não remover nem reescrever a captura de áudio, o detector de interrupção, a reprodução ou a voz antes de comprovar a compatibilidade do adaptador.
- Não tornar Whisper/Piper/SAPI a voz padrão: são alternativas do pipeline, não equivalentes automáticos à voz Gemini Live atual.
- Não executar ferramentas diretamente a partir de texto livre do modelo; usar chamadas estruturadas, validação de esquema, política e confirmação.
- Não armazenar memória indiscriminadamente: persistir decisões/preferências explícitas e conhecimento validado, recuperando apenas o contexto relevante.
- Não introduzir Qwen.

## Estado desta auditoria

Esta decisão documenta o desenho e os pontos de integração identificados. Ela não declara que o login ChatGPT, a ponte de voz ou a delegação já estejam implementados. A próxima alteração funcional deve começar pelo adaptador de autenticação/cérebro e pela separação segura do fluxo Gemini Live, sem trocar a voz.
