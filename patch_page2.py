import re

with open("frontend/src/app/investments/transactions/page.tsx", "r") as f:
    content = f.read()

# Add labels for split and bonus
content = content.replace(
    '{tx.transaction_type.toLowerCase() === "withdrawal" && `Withdrawal from ${tx.account_name || "account"}`}',
    '{tx.transaction_type.toLowerCase() === "withdrawal" && `Withdrawal from ${tx.account_name || "account"}`}\n                                  {tx.transaction_type.toLowerCase() === "split" && `Stock Split`}\n                                  {tx.transaction_type.toLowerCase() === "bonus" && `Bonus Shares`}\n                                  {tx.notes && <span className="ml-2 text-slate-500 italic">- {tx.notes}</span>}'
)

# Hide edit/delete for corporate actions
content = content.replace(
    '<div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">',
    '{tx.transaction_id >= 0 && (\n                              <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">'
)

content = content.replace(
    """                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>""",
    """                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>\n                            )}"""
)

with open("frontend/src/app/investments/transactions/page.tsx", "w") as f:
    f.write(content)
