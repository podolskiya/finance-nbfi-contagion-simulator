import sys

path = sys.argv[1]
with open(path, "r", encoding="latin-1") as f:
    header = f.readline().strip()

columns = header.split("\t")
print(f"Total columns: {len(columns)}")
print(f"First 10 columns: {columns[:10]}")

for keyword in ["RSSD", "J454", "NAME"]:
    matches = [c for c in columns if keyword in c.upper()]
    print(f"\nColumns containing '{keyword}' ({len(matches)}):")
    for m in matches[:15]:
        print(f"  {m}")