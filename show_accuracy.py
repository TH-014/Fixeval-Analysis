import pandas as pd

# Load CSV
df = pd.read_csv("result.csv")

# List of all unique verdicts
verdicts = ['Accepted', 'Compile Error', 'Memory Limit Exceeded', 'Runtime Error', 'Time Limit Exceeded']

# Initialize result dictionary
result_table = []

for verdict in verdicts:
    # True Positives: predicted == actual == verdict
    tp = ((df['actual_verdict'] == verdict) & (df['predicted_verdict'] == verdict)).sum()
    
    # False Positives: actual != verdict & predicted == verdict
    fp = ((df['actual_verdict'] != verdict) & (df['predicted_verdict'] == verdict)).sum()
    
    # False Negatives: actual == verdict & predicted != verdict
    fn = ((df['actual_verdict'] == verdict) & (df['predicted_verdict'] != verdict)).sum()
    
    # Total actual for this verdict
    total = (df['actual_verdict'] == verdict).sum()

    # Accuracy: tp / total_actual as percentage
    accuracy = (tp / total * 100) if total > 0 else 0.0

    result_table.append({
        'verdict': verdict,
        'accuracy': f"{accuracy:.2f}%",
        'false positives': fp,
        'false negatives': fn,
        'total': total
    })

# Convert to DataFrame for pretty display
result_df = pd.DataFrame(result_table)

# Print the result table
print(result_df.to_markdown(index=False))
