# Preparação do Ion no Windows

A aplicação preservada continua usando `requirements.txt`. A nova camada adiciona o Microsoft Agent Framework.

## 1. Ambiente

No terminal PowerShell, na raiz do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-ion.txt
```

Se a política do PowerShell bloquear a ativação, use `\.venv\Scripts\python.exe -m pip ...` sem ativar o ambiente.

## 2. Chaves

Copie `.env.example` para `.env` e preencha `GEMINI_API_KEY` e `NVIDIA_API_KEY`. O arquivo `.env` é ignorado pelo Git. O código também reconhece a chave Gemini guardada em `config/api_keys.json`.

## 3. Inicialização preservada

A inicialização antiga continua em `python main.py`. A interface web continua sendo servida pelo backend existente. A ação de desenvolvimento `ion_develop_project` será carregada automaticamente quando o framework estiver instalado.

## 4. Verificações locais obrigatórias

```powershell
python -m compileall -q ion actions/ion_development.py
python -m pytest -q
python main.py
```

Depois, valide no próprio computador:
- microfone e saída de voz;
- Gemini Live / sessão de conversação;
- painel de tarefas;
- conexão de cada API;
- um projeto pequeno enviado pelo Ion e os comandos de teste desse projeto.

A integração remota não substitui a validação com os dispositivos e chaves reais da máquina.
