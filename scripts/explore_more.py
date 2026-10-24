import pandas as pd

df = pd.read_excel("data/library_usage.xlsx")

# Fix the column names: keep only the first line and trim spaces
df.columns = [c.split("\n")[0].strip() for c in df.columns]
print("Clean column names:", list(df.columns))

# Which codes belong to each library name?
print("\nCodes per library:")
print(df.groupby("Home Library Definition")["Home Library Code"].unique())

# The 2 rows with no library code
print("\nRows missing a library code:")
print(df[df["Home Library Code"].isnull()])

# Are blank months the same rows as missing years?
blank_month = df["Circulation Active Month"].str.strip() == ""
print("\nBlank months:", blank_month.sum())
print("Same rows have missing year:", df.loc[blank_month, "Circulation Active Year"].isnull().all())
print("Checkouts for those rows:", df.loc[blank_month, "Total Checkouts"].describe())