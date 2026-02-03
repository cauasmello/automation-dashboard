## Telegram -> Google Sheets -> Parquet

### Setup
1. Exportar mensagens enviadas no telegram e preencher planilha;
2. Exportar planilha e transformar em arquivo .parquet;
3. Criar Dashboard em cima do .parquet.

### Rodar
- python .\src\telegram_to_sheets.py
- python .\src\export_to_parquet.py
- python .dashboard.py