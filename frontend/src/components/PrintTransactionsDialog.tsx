import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";

export function PrintTransactionsDialog({
  isOpen,
  onClose,
  accounts
}: {
  isOpen: boolean;
  onClose: () => void;
  accounts: any[];
}) {
  const [selectedAccounts, setSelectedAccounts] = useState<number[]>([]);
  const [types, setTypes] = useState({
    income: true,
    expense: true,
    transfer: true,
    investment: true,
  });

  const handlePrint = () => {
    // Open print view in new tab or route
    const query = new URLSearchParams();
    if (selectedAccounts.length > 0) query.set("accounts", selectedAccounts.join(","));
    query.set("types", Object.keys(types).filter(k => (types as any)[k]).join(","));
    
    window.open(`/cashflow/transactions/print?${query.toString()}`, "_blank");
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Print Transactions Ledger</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="space-y-2">
            <h4 className="font-semibold text-sm">Select Accounts (leave empty for all)</h4>
            <div className="max-h-[150px] overflow-y-auto space-y-2 border rounded-md p-2">
              {accounts.map(acc => (
                <div key={acc.account_id} className="flex items-center space-x-2">
                  <Checkbox 
                    id={`acc-${acc.account_id}`} 
                    checked={selectedAccounts.includes(acc.account_id)}
                    onCheckedChange={(checked) => {
                      if (checked) setSelectedAccounts([...selectedAccounts, acc.account_id]);
                      else setSelectedAccounts(selectedAccounts.filter(id => id !== acc.account_id));
                    }}
                  />
                  <label htmlFor={`acc-${acc.account_id}`} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                    {acc.account_name} ({acc.currency})
                  </label>
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <h4 className="font-semibold text-sm">Transaction Types</h4>
            <div className="grid grid-cols-2 gap-2">
              {["income", "expense", "transfer", "investment"].map(type => (
                <div key={type} className="flex items-center space-x-2">
                  <Checkbox 
                    id={`type-${type}`} 
                    checked={(types as any)[type]}
                    onCheckedChange={(checked) => setTypes({ ...types, [type]: checked })}
                  />
                  <label htmlFor={`type-${type}`} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 capitalize">
                    {type}
                  </label>
                </div>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handlePrint}>Generate Print</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
