# Jarvis — projeto independente

Esta pasta é a raiz de desenvolvimento do novo Jarvis. O projeto será construído de forma independente; não importar a arquitetura antiga do Yon/Mark-LVI.

## Objetivo inicial

Construir um agente pessoal completo, começando por uma camada de interação funcional e evoluindo para o cérebro autônomo.

## Reaproveitamento seletivo da interface e interação existentes

Extrair e adaptar somente os componentes necessários do projeto de origem:

- Orb holográfica: aparência, cores, fundo e animações atuais.
- Chat: estrutura e comportamento atuais; a tecla **T** abre o chat.
- Engrenagem: menu e controles de API existentes (confirmar o comportamento exato antes de alterar).
- Entrada de texto: receber, ler e compreender mensagens.
- Arquivos: receber e interpretar arquivos enviados pelo chat.
- Áudio: captura do microfone, reconhecimento de fala, conversação, resposta falada e transcrição exibida no chat.
- Camada atual de modelo/API para compreensão e conversação, após identificar no repositório a implementação e suas dependências.

## Ajustes obrigatórios na interface

- Remover as legendas/letras sobrepostas à Orb durante a fala, que apresentam falhas.
- Remover os pop-ups atuais.
- Manter a Orb, o fundo, as cores, o chat, o atalho **T** e a engrenagem.
- É permitido adotar outro framework de interface se houver vantagem técnica, preservando a identidade visual e o comportamento acordado.

## Conversação natural em tempo real

A camada de áudio deverá evoluir para permitir:

- baixa latência e escuta contínua;
- interrupção da fala do Jarvis pelo usuário;
- feedbacks curtos e naturais de acompanhamento;
- compreensão incremental enquanto o usuário ainda explica;
- planejamento e execução de tarefas em segundo plano durante a conversa;
- continuidade de contexto entre voz, chat, raciocínio e execução.

## Arquitetura nova a construir

1. Cérebro central e orquestrador.
2. Memória de curto e longo prazo.
3. Enciclopédia técnica e grafo de conhecimento.
4. Motor de identificação de lacunas, pesquisa, aprendizagem, testes e validação.
5. Catálogo operacional de ferramentas, integrações e comandos.
6. Descoberta de capacidades instaladas no computador e uso seguro de ferramentas.
7. Sistema multiagente e execução paralela.
8. Planejamento, execução, observabilidade e verificação de resultados.
9. Autoevolução com versões experimental, estável e recuperação.
10. Interface integrada à camada de interação reaproveitada.

## Princípios de desenvolvimento

- O novo Jarvis é um projeto do zero; reaproveitamento limitado aos componentes explicitamente listados acima.
- Não presumir capacidades: inspecionar, documentar e testar cada integração.
- Ferramentas externas devem ser descobertas, avaliadas e validadas antes do uso.
- Execução no computador deve respeitar permissões e políticas explícitas.
- O trabalho será desenvolvido nesta pasta/branch isolada; a substituição da estrutura principal do repositório só ocorrerá depois da validação e autorização do usuário.

## Estado

Fundação documental criada. Próxima atividade: inventariar a implementação de voz, chat, Orb, engrenagem e API no código de origem para extrair apenas os componentes aprovados.
