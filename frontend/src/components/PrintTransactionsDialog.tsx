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

  const [datePreset, setDatePreset] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const handleDatePreset = (preset: string) => {
    setDatePreset(preset);
    const today = new Date();
    let start = "";
    let end = "";

    if (preset === "thisMonth") {
      start = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
      end = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];
    } else if (preset === "lastMonth") {
      start = new Date(today.getFullYear(), today.getMonth() - 1, 1).toISOString().split('T')[0];
      end = new Date(today.getFullYear(), today.getMonth(), 0).toISOString().split('T')[0];
    } else if (preset === "thisYear") {
      start = new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0];
      end = new Date(today.getFullYear(), 11, 31).toISOString().split('T')[0];
    }

    setStartDate(start);
    setEndDate(end);
  };

  const handlePrint = () => {
    // Open print view in new tab or route
    const query = new URLSearchParams();
    if (selectedAccounts.length > 0) query.set("accounts", selectedAccounts.join(","));
    query.set("types", Object.keys(types).filter(k => (types as any)[k]).join(","));
    if (startDate) query.set("startDate", startDate);
    if (endDate) query.set("endDate", endDate);
    
    window.open(`/cashflow/transactions/print?${query.toString()}`, "_blank");
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
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
          <div className="space-y-3">
            <h4 className="font-semibold text-sm">Date Range</h4>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant={datePreset === "all" ? "default" : "outline"} size="sm" onClick={() => handleDatePreset("all")}>All Time</Button>
              <Button type="button" variant={datePreset === "thisMonth" ? "default" : "outline"} size="sm" onClick={() => handleDatePreset("thisMonth")}>This Month</Button>
              <Button type="button" variant={datePreset === "lastMonth" ? "default" : "outline"} size="sm" onClick={() => handleDatePreset("lastMonth")}>Last Month</Button>
              <Button type="button" variant={datePreset === "thisYear" ? "default" : "outline"} size="sm" onClick={() => handleDatePreset("thisYear")}>This Year</Button>
              <Button type="button" variant={datePreset === "custom" ? "default" : "outline"} size="sm" onClick={() => handleDatePreset("custom")}>Custom</Button>
            </div>
            {datePreset === "custom" && (
              <div className="flex gap-4 items-center mt-2">
                <input 
                  type="date" 
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50" 
                  value={startDate} 
                  onChange={e => setStartDate(e.target.value)}
                />
                <span className="text-sm text-gray-500">to</span>
                <input 
                  type="date" 
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50" 
                  value={endDate} 
                  onChange={e => setEndDate(e.target.value)}
                />
              </div>
            )}
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
