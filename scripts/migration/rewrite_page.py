import os

with open("frontend/src/app/cashflow/transactions/page.tsx", "r") as f:
    content = f.read()

# Replace Account Filter with MultiSelect
content = content.replace(
    'const [selectedAccountId, setSelectedAccountId] = useState<string>("ALL");',
    'const [selectedAccountIds, setSelectedAccountIds] = useState<number[]>([]);'
)

# Also need imports for shadcn
imports = """import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Checkbox } from "@/components/ui/checkbox";
import { Check, ChevronsUpDown, Printer } from "lucide-react";
"""
content = content.replace('import { TransactionLedger, UnifiedRowItem } from "@/components/TransactionLedger";', 'import { TransactionLedger, UnifiedRowItem } from "@/components/TransactionLedger";\n' + imports)

# We need to rewrite the header section
header_start = content.find('{/* Header Bar */}')
main_card_start = content.find('{/* Main Card with Table */}')

header_replacement = """
"""
content = content[:header_start] + content[main_card_start:]

# Modify filteredRows logic for selectedAccountIds
old_account_filter = """      // Account filter
      if (selectedAccountId !== "ALL") {
        const aid = Number(selectedAccountId);
        if (!r.payments.some((p) => p.account_id === aid)) return false;
      }"""
new_account_filter = """      // Account filter
      if (selectedAccountIds.length > 0) {
        if (!r.payments.some((p) => selectedAccountIds.includes(p.account_id))) return false;
      }"""
content = content.replace(old_account_filter, new_account_filter)

# Modify selectedAccountInfo logic
old_acc_info = """  const selectedAccountInfo = useMemo(() => {
    if (selectedAccountId === "ALL") {
      return null;
    }
    const aid = Number(selectedAccountId);"""
new_acc_info = """  const selectedAccountInfo = useMemo(() => {
    if (selectedAccountIds.length !== 1) {
      return null;
    }
    const aid = selectedAccountIds[0];"""
content = content.replace(old_acc_info, new_acc_info)

# Find the Table Header Bar with Mode Selector & Filters
table_header_start = content.find('{/* Table Header Bar with Mode Selector & Filters */}')
ledger_start = content.find('{/* Ledger Table */}')

new_table_header = """{/* Table Header Bar with Mode Selector & Filters */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div>
              <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                Income & Spend Transactions ({filteredRows.length})
              </h2>
              <p className="text-[11px] font-medium text-slate-400">
                Historical statement ledger with continuous running net cash balance
              </p>
            </div>

            {selectedAccountInfo && (
              <div 
                data-testid="selected-account-balance"
                className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 dark:bg-blue-950/50 border border-blue-200/60 dark:border-blue-800/60 rounded-xl text-xs"
              >
                <Wallet className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                <span className="font-semibold text-slate-600 dark:text-slate-300">{selectedAccountInfo.name}:</span>
                <span className={`font-bold tabular-nums ${selectedAccountInfo.balance >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
                  {formatCurrency(selectedAccountInfo.balance, selectedAccountInfo.currency)}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => {
                setEditingTradeTx(null);
                setIsTradeModalOpen(true);
              }}
              className="px-3 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <Briefcase className="w-3.5 h-3.5 text-blue-500" />
              <span>+ Trade / SIP</span>
            </button>

            <button
              onClick={() => {
                setEditingCashflowTx(null);
                setIsCashflowModalOpen(true);
              }}
              className="px-3 py-1.5 text-xs font-bold bg-[#0F172A] hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-[#0F172A] rounded-lg transition-all shadow-sm flex items-center gap-1.5 cursor-pointer mr-2"
            >
              <Plus className="w-3.5 h-3.5 text-emerald-400" />
              <span>+ Cashflow</span>
            </button>
            
            <button
              onClick={() => setIsPrintModalOpen(true)}
              className="px-3 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer mr-2"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print</span>
            </button>

            {/* Search Input */}
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
              <input
                type="text"
                placeholder="Search merchant, account..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-[#F3F4F6] dark:bg-slate-800 text-xs font-semibold text-slate-800 dark:text-slate-100 placeholder-slate-400 pl-8 pr-3 py-1.5 rounded-lg border border-transparent focus:border-slate-300 dark:focus:border-slate-700 focus:bg-white dark:focus:bg-slate-900 focus:outline-none w-48"
              />
            </div>

            {/* Account Multi-Select Popover */}
            <Popover>
              <PopoverTrigger asChild>
                <button className="flex items-center justify-between bg-[#F1F5F9] dark:bg-slate-800 text-xs font-bold text-slate-700 dark:text-slate-200 px-3 py-1.5 rounded-lg w-40">
                  <span className="truncate">
                    {selectedAccountIds.length === 0 
                      ? "All Accounts" 
                      : selectedAccountIds.length === 1
                      ? accounts.find(a => a.account_id === selectedAccountIds[0])?.account_name
                      : `${selectedAccountIds.length} Accounts`}
                  </span>
                  <ChevronsUpDown className="ml-2 h-3.5 w-3.5 shrink-0 opacity-50" />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-56 p-0" align="end">
                <Command>
                  <CommandInput placeholder="Search accounts..." />
                  <CommandList>
                    <CommandEmpty>No account found.</CommandEmpty>
                    <CommandGroup>
                      {accounts.map((a) => (
                        <CommandItem
                          key={a.account_id}
                          onSelect={() => {
                            setSelectedAccountIds(prev => 
                              prev.includes(a.account_id) 
                                ? prev.filter(id => id !== a.account_id)
                                : [...prev, a.account_id]
                            )
                          }}
                        >
                          <Checkbox 
                            checked={selectedAccountIds.includes(a.account_id)}
                            className="mr-2"
                          />
                          {a.account_name} ({a.currency})
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>

            {/* Label Filter Select */}
            <Select value={selectedLabelFilter} onValueChange={setSelectedLabelFilter}>
              <SelectTrigger className="w-[140px] h-8 text-xs font-bold bg-[#F1F5F9] border-none">
                <SelectValue placeholder="All Labels" />
              </SelectTrigger>
              <SelectContent>
                {["ALL", "ESSENTIAL", "DISCRETIONARY", "LUXURY", "INVESTMENT"].map((lbl) => (
                  <SelectItem key={lbl} value={lbl} className="text-xs font-bold">
                    {lbl === "ALL" ? "All Labels" : lbl.charAt(0) + lbl.slice(1).toLowerCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
"""

content = content[:table_header_start] + new_table_header + "\n        " + content[ledger_start:]

content = content.replace("selectedAccountId={selectedAccountId}", "selectedAccountIds={selectedAccountIds}")

# Add print modal state
content = content.replace(
    'const [isTradeModalOpen, setIsTradeModalOpen] = useState(false);',
    'const [isTradeModalOpen, setIsTradeModalOpen] = useState(false);\n  const [isPrintModalOpen, setIsPrintModalOpen] = useState(false);'
)

# Add print modal to the bottom
print_modal_code = """
      <PrintTransactionsDialog
        isOpen={isPrintModalOpen}
        onClose={() => setIsPrintModalOpen(false)}
        accounts={accounts}
      />
"""
content = content.replace('    </div>\n  );\n}', print_modal_code + '\n    </div>\n  );\n}')

import_print = 'import { PrintTransactionsDialog } from "@/components/PrintTransactionsDialog";\n'
content = content.replace('import { TransactionLedger, UnifiedRowItem } from "@/components/TransactionLedger";', 'import { TransactionLedger, UnifiedRowItem } from "@/components/TransactionLedger";\n' + import_print)

with open("frontend/src/app/cashflow/transactions/page.tsx", "w") as f:
    f.write(content)

