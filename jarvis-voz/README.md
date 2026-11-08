# Jarvis — voz e Orb

Aplicativo independente para Windows. Esta versão tem somente a interface Orb e conversa por voz com Gemini Live.

## Iniciar

1. Instale Python 3.11 ou superior (marque **Add Python to PATH**).
2. Dê duplo clique em `INICIAR_JARVIS.bat`.
3. Na primeira abertura, informe sua chave da API Gemini.
4. Aguarde a conexão e converse normalmente.

O inicializador cria o ambiente virtual local e instala as dependências de `requirements.txt` automaticamente.

## Escopo desta versão

- Janela desktop com a Orb de partículas baseada no visual já existente no projeto.
- Microfone contínuo e resposta falada pelo Gemini Live.
- Interrupção de áudio quando o serviço sinaliza que o usuário interrompeu.
- Chave Gemini guardada no Gerenciador de Credenciais do Windows por meio do keyring.
- Nenhuma ferramenta, comando do sistema, automação ou integração com ChatGPT.

## Dependências

- Python 3.11+
- Microsoft Edge WebView2 Runtime (normalmente já presente no Windows 10 atualizado)
- Pacotes Python listados em `requirements.txt` (instalados pelo inicializador)

É necessária uma chave da API Gemini e conexão com a internet. O uso da API pode estar sujeito às cotas e condições da conta Google. O Gemini Live pode acelerar a cadência em respostas muito longas; por isso, o Jarvis está instruído a responder de forma mais concisa e conversacional.

## Observações

Este primeiro pacote é um lançador de desenvolvimento. A reprodução mantém uma fila de áudio com backpressure para não descartar blocos quando o dispositivo atrasa; a fila só é esvaziada quando o próprio Gemini sinaliza uma interrupção. O receptor permanece ativo entre turnos da mesma sessão. Depois de validar voz, microfone e interface no computador de destino, a etapa seguinte será empacotar a aplicação em um `.exe` independente.
