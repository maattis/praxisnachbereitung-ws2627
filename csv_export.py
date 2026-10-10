from pathlib import Path
import pandas as pd

csv_path = Path("excel/Gesamt.CSV")

df = pd.read_csv(csv_path, sep=";", encoding="latin-1")
df.columns = [str(c).strip() for c in df.columns]

print("Import erfolgreich:")
print(f"Zeilen: {len(df)}, Spalten: {len(df.columns)}")
print(df.head())
