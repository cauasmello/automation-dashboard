from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

from config import SHEET_ID, WORKSHEET_NAME

BASE_DIR = Path(__file__).resolve().parents[1]
CREDENTIALS_FILE = BASE_DIR / "credentials" / "service_account.json"
PARQUET_FILE = BASE_DIR / "data" / "events.parquet"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def connect_worksheet():
    creds = Credentials.from_service_account_file(str(CREDENTIALS_FILE), scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)
    return ws


def main():
    print("Conectando à planilha...")
    ws = connect_worksheet()

    # Lê todos os valores da aba
    values = ws.get_all_values()  # lista de listas

    if not values or len(values) <= 1:
        print("Planilha vazia ou só com cabeçalho. Nada para exportar.")
        return

    # Primeira linha = cabeçalho
    header = values[0]
    rows = values[1:]

    # Garante que o cabeçalho tem exatamente as colunas desejadas
    # (ajuste aqui se seus nomes forem outros)
    expected = ["Saída", "Entrada", "Data"]
    if header[:3] != expected:
        print("Aviso: cabeçalho diferente do esperado:", header[:3])
        print("Usando assim mesmo.")

    # Monta DataFrame
    df = pd.DataFrame(rows, columns=header)

    # Adiciona coluna de Data/Hora da Exportação
    exported_at = pd.Timestamp.now(tz="America/Sao_Paulo")
    df["Data/Hora da Exportação"] = exported_at

    # Salva sobrescrevendo SEMPRE
    PARQUET_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PARQUET_FILE, index=False)
    print(f"Exportação concluída. Arquivo salvo em: {PARQUET_FILE}")


if __name__ == "__main__":
    main()