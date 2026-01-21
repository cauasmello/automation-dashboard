## Telegram -> Google Sheets

### Setup
1. Crie um virtualenv e instale dependências
   - python -m venv .venv
   - .\.venv\Scripts\Activate.ps1
   - python -m pip install -r requirements.txt

2. Google Sheets (Service Account)
   - Coloque o arquivo em: credentials/service_account.json
   - Compartilhe a planilha com o e-mail da service account (Editor)

3. Telegram (Telethon)
   - Rode o script e faça login com seu telefone quando pedir
   - O arquivo de sessão (*.session) será criado localmente (não vai pro Git)

### Rodar
- python .\src\telegram_to_sheets.py