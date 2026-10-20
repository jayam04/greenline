import os

with open("frontend/src/components/TransactionLedger.tsx", "r") as f:
    content = f.read()

# Instead of writing python script to parse, I'll just rewrite the file fully using write_to_file tool.
