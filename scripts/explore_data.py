import pandas as pd

df = pd.read_excel("data/library_usage.xlsx")

print("Rows, columns:", df.shape)

print("\nColumn types:\n", df.dtypes)

print("\nMissing values per column:\n", df.isnull().sum())

print("\nUnique values per column:\n", df.nunique())

for col in df.columns:
    if df[col].nunique() < 50:
        print(f"\n--- {col} ---")
        print(df[col].value_counts(dropna=False))