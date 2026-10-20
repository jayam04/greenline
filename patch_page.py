import re

with open("frontend/src/app/investments/transactions/page.tsx", "r") as f:
    content = f.read()

# 1. Import CorporateActionModal and Sparkles
content = content.replace(
    'import { TransactionModal, TransactionItem } from "@/components/TransactionModal";',
    'import { TransactionModal, TransactionItem } from "@/components/TransactionModal";\nimport { CorporateActionModal } from "@/components/CorporateActionModal";'
)

# Replace the lucide-react import if Sparkles is not imported
if "Sparkles" not in content.split('from "lucide-react";')[0]:
    content = content.replace(
        'RefreshCw\n} from "lucide-react";',
        'RefreshCw, Sparkles\n} from "lucide-react";'
    )

# 2. Add state for CorporateActionModal
content = content.replace(
    'const [isModalOpen, setIsModalOpen] = useState(false);',
    'const [isModalOpen, setIsModalOpen] = useState(false);\n  const [isCorpActionModalOpen, setIsCorpActionModalOpen] = useState(false);'
)

# 3. Add Corporate Action button
button_html = """
                <button
                  onClick={() => setIsCorpActionModalOpen(true)}
                  className="btn-pill-gray text-[11px]"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Corporate Action</span>
                </button>
                <button
"""
content = content.replace(
    """                <button
                  onClick={() => {
                    setEditingTransaction(null);
                    setIsModalOpen(true);
                  }}""",
    button_html + """                  onClick={() => {
                    setEditingTransaction(null);
                    setIsModalOpen(true);
                  }}"""
)

# 4. Render CorporateActionModal
modal_html = """
      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={loadTransactions}
        initialData={editingTransaction}
      />

      <CorporateActionModal
        isOpen={isCorpActionModalOpen}
        onClose={() => setIsCorpActionModalOpen(false)}
        onSuccess={loadTransactions}
      />
"""
content = content.replace(
    """      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={loadTransactions}
        initialData={editingTransaction}
      />""",
    modal_html
)

with open("frontend/src/app/investments/transactions/page.tsx", "w") as f:
    f.write(content)

