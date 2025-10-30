import sys
import pandas as pd

# usage: python scripts/inspect_parquet.py <parquet_file>
if len(sys.argv) < 2:
    print('usage: python scripts/inspect_parquet.py <parquet_file>')
    sys.exit(1)

file = sys.argv[1]
df = pd.read_parquet(file)
print(df.head(10)) 