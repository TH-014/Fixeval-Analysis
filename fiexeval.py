import os
import pandas as pd

# Path to the CSV the user uploaded
CSV_PATH = "./prompt_results/v011225/codes.csv"      # adjust if you put it elsewhere
OUT_DIR  = "generated_cases"          # where the .java files will go

# --------- load the data ----------
df = pd.read_csv(CSV_PATH)

# --- make sure the output folder exists
os.makedirs(OUT_DIR, exist_ok=True)

def sanitize(name: str) -> str:
    """
    Keep only alphanumerics, dash and underscore so the filename is safe
    on any OS. You can customise this rule as you like.
    """
    return "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_"))

# --------- write one .java file per row ----------
for i, row in df.iterrows():
    case_no   = str(row["case_no"]).strip()
    code_body = str(row["code_token"])

    filename = os.path.join(OUT_DIR, f"{sanitize(case_no)}.java")

    # If you might have duplicate case numbers, add a suffix like _1, _2, …
    # or use `i` in the filename.  Example:
    # filename = os.path.join(OUT_DIR, f"{sanitize(case_no)}_{i}.java")

    with open(filename, "w", encoding="utf-8") as f:
        # Ensure the file ends with a newline (optional but conventional)
        f.write(code_body if code_body.endswith("\n") else code_body + "\n")

print(f"Wrote {len(df)} Java files to {os.path.abspath(OUT_DIR)}")
