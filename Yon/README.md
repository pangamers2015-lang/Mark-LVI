# Yon — agente pessoal autônomo

Este diretório é a raiz isolada do novo projeto Yon. O cérebro autônomo ainda será construído em etapas posteriores; esta primeira entrega estabelece a interface e a camada de interação.

## Primeira versão: interface e conversação

- Orb holográfica de pontos, baseada na animação visual do projeto de origem, com fundo escuro e paleta clara/neutra.
- Chat lateral funcional; **T** abre o chat e **Esc** fecha.
- Engrenagem para configurar a chave da API Gemini.
- Entrada de texto, envio com Enter e leitura de anexos de texto comuns.
- Transcrição de entrada e saída exibida dentro do chat, sem texto sobreposto à Orb.
- Sessão Gemini Live conectada ao iniciar. O microfone é aberto durante a fala do Yon apenas para análise local de possível interrupção; esses blocos não são enviados ao Gemini enquanto não houver voz do usuário confirmada. Fora desse momento, o microfone só transmite enquanto Espaço está pressionado. Soltar envia `audio_stream_end` para concluir a fala. No celular, toque e segure a Orb.
- Interrupção por voz: durante a resposta, `EchoGuard` compara o áudio captado com o áudio reproduzido e `BargeInDetector` exige fala sustentada antes de cortar a resposta. A fala confirmada é então encaminhada ao Gemini; uma pausa curta encerra a captura. Espaço continua disponível como interrupção manual imediata.
- Reconexão automática da sessão de voz após uma queda.

## Referência e créditos

Esta interface foi desenvolvida como uma implementação independente inspirada e adaptada a partir do projeto **MARK LVI / JARVIS**, de FatihMakes: https://github.com/FatihMakes/Mark-LVI. O repositório de origem é a referência para os componentes de voz e interação examinados; o Yon mantém código, interface e arquitetura próprios. Consulte o repositório original e sua licença (CC BY-NC 4.0) para os termos aplicáveis ao material reutilizado ou adaptado.

## Componentes de voz extraídos/adaptados

A implementação de origem foi inspecionada em `main.py`, `core/echo.py`, `core/barge_in.py`, `providers/audio.py` e `web/index.html`.

- Modelo de voz/conversa em tempo real identificado no código de origem: `models/gemini-3.1-flash-live-preview`.
- Modelo textual de reserva: `gemini-2.5-flash`.
- Adaptados para este projeto: fluxo PCM 16 kHz de entrada / 24 kHz de saída, transcrições de entrada/saída, reprodução em blocos e interrupção imediata ao pressionar Espaço durante a resposta.
- A interface não reaproveita os pop-ups antigos nem as legendas sobre a Orb.

A nova implementação é isolada: não importa o antigo `main.py`, o sistema de ferramentas, a memória ou a arquitetura cognitiva do projeto de origem.

## Instalação e execução no Windows

Requer Python 3.11 ou superior.

```powershell
cd Yon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Na primeira execução, abra a engrenagem e salve uma chave válida da API Gemini. A chave é gravada localmente em `config/api_key.json`, ignorada pelo Git. A interface abre em `http://127.0.0.1:8765`. Para iniciar com duplo clique, use `INICIAR.bat`.

## Dependências

- `numpy`
- `sounddevice`
- `google-genai`

A interface usa HTML/CSS/JavaScript sem framework adicional. O servidor local usa apenas a biblioteca padrão do Python. Não é necessário instalar Node.js, PyQt ou Docker para esta etapa.

## Limitações que ainda precisam de validação no computador

- O fluxo de áudio e a detecção de interrupção foram integrados ao código, mas precisam ser testados com o microfone e os alto-falantes reais. O cancelamento adaptativo de eco reduz falsos cortes; o resultado depende do ambiente acústico e do dispositivo. Fones de ouvido são úteis no primeiro teste.
- A detecção automática de interrupção deve ser calibrada em hardware real; se o ambiente não permitir distinguir voz e eco com confiança, o sistema deve evitar interromper e o usuário ainda pode usar Espaço.
- O reconhecimento/transcrição e a fala em tempo real dependem da disponibilidade e das cotas do modelo Gemini Live.
- Anexos nesta primeira versão aceitam arquivos de texto (TXT, MD, CSV, JSON e código); PDF e documentos Office ainda não foram adicionados.
- Feedbacks verbais curtos enquanto o usuário ainda está elaborando uma ideia, raciocínio incremental durante a fala e execução paralela de tarefas serão evoluções posteriores do motor de conversação e do cérebro.

## Próximas etapas

1. Executar `INICIAR.bat` ou `python app.py` e testar Espaço pressionado/solto, microfone, áudio de saída, transcrição, chat e reconexão.
2. Ajustar a sensibilidade do áudio conforme os testes reais.
3. Refinar as configurações da API e os anexos.
4. Construir o cérebro central, memória, enciclopédia técnica, catálogo de ferramentas e sistema de aprendizagem/autoevolução.

## Princípios

- Não reutilizar a arquitetura antiga do agente; reaproveitamento limitado aos componentes de interface e interação listados acima.
- Não presumir que uma integração funciona sem teste.
- Manter o projeto nesta pasta/branch isolada até validação e autorização explícita para qualquer substituição da estrutura principal.
