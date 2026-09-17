import sys

file_path = "/home/jayampatel/swe/greenline/frontend/src/components/TransactionLedger.tsx"
with open(file_path, "r") as f:
    content = f.read()

target = """                  {/* Primary Row */}
                  <div 
                    className={`flex items-center justify-between p-4 cursor-pointer select-none`}
                    onClick={() => hasSplits && toggleRow(tx.key)}
                  >
                    {/* Left: Icon & Details */}
                    <div className="flex items-center gap-3.5 flex-1 min-w-0">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${iconBg}`}>
                        <Icon className="w-4.5 h-4.5" />
                      </div>
                      <div className="flex flex-col min-w-0 pr-4">
                        <div className="font-bold text-[#0F172A] truncate text-sm">
                          {tx.title}
                        </div>
                        <div className="text-xs text-slate-500 truncate flex items-center gap-1.5 mt-0.5">
                          <span>{tx.items[0]?.category_name || "Uncategorized"}</span>
                          {paymentDisplay && (
                            <>
                              <span className="w-1 h-1 bg-slate-300 rounded-full" />
                              <span className="flex items-center gap-1">
                                <CreditCard className="w-3 h-3" />
                                {paymentDisplay}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Right: Amount & Badges */}
                    <div className="flex flex-col items-end shrink-0 gap-1 pl-2">
                      <div className={`font-bold tabular-nums text-sm ${tx.isTransfer ? "text-[#0F172A]" : tx.isIncome ? "text-emerald-600" : "text-rose-600"}`}>
                        {tx.isIncome ? "+" : "-"}{formatCurrency(tx.totalAmount, tx.currency)}
                      </div>
                      
                      <div className="flex items-center gap-1.5">
                        {showRunningBalance && runningBalanceDisplay ? (
                          <div className="text-[10px] font-semibold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                            Bal: {runningBalanceDisplay}
                          </div>
                        ) : !showRunningBalance && labelBadges.length > 0 ? (
                          <div className="flex gap-1">
                            {labelBadges.map((lbl, i) => (
                              <span key={i} className="text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                                {lbl}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        
                        {hasSplits && (
                          <div className="text-slate-400 ml-1">
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Desktop Actions (Hover) - Hidden on mobile, shown on hover on desktop */}
                    <div className="hidden md:flex opacity-0 hover:opacity-100 items-center justify-end gap-1 ml-4" onClick={(e) => e.stopPropagation()}>
                      {tx.source === "cashflow" && tx.rawCashflow && (
                        <>
                          <button onClick={() => onEditCashflow?.(tx.rawCashflow!)} className="p-1.5 text-slate-400 hover:text-blue-600 rounded-lg" title="Edit">
                            <Edit className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => onDeleteCashflow?.(tx.rawCashflow!.cashflow_id)} className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg" title="Delete">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                      {tx.source === "investment" && tx.rawTrade && (
                        <>
                          <button onClick={() => onEditTrade?.(tx.rawTrade!)} className="p-1.5 text-slate-400 hover:text-blue-600 rounded-lg" title="Edit">
                            <Edit className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => onDeleteTrade?.(tx.rawTrade!.transaction_id)} className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg" title="Delete">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Mobile Actions (Always visible below row on small screens) */}
                  <div className="md:hidden flex items-center justify-end gap-3 px-4 pb-3" onClick={(e) => e.stopPropagation()}>
                     {tx.source === "cashflow" && tx.rawCashflow && (
                        <>
                          <button onClick={() => onEditCashflow?.(tx.rawCashflow!)} className="text-[11px] font-bold text-slate-500 flex items-center gap-1 uppercase">
                            <Edit className="w-3 h-3" /> Edit
                          </button>
                          <button onClick={() => onDeleteCashflow?.(tx.rawCashflow!.cashflow_id)} className="text-[11px] font-bold text-rose-500 flex items-center gap-1 uppercase">
                            <Trash2 className="w-3 h-3" /> Delete
                          </button>
                        </>
                      )}
                      {tx.source === "investment" && tx.rawTrade && (
                        <>
                          <button onClick={() => onEditTrade?.(tx.rawTrade!)} className="text-[11px] font-bold text-slate-500 flex items-center gap-1 uppercase">
                            <Edit className="w-3 h-3" /> Edit
                          </button>
                          <button onClick={() => onDeleteTrade?.(tx.rawTrade!.transaction_id)} className="text-[11px] font-bold text-rose-500 flex items-center gap-1 uppercase">
                            <Trash2 className="w-3 h-3" /> Delete
                          </button>
                        </>
                      )}
                  </div>"""

replacement = """                  {/* Primary Row (Responsive Grid) */}
                  <div 
                    className="grid grid-cols-12 items-center p-4 cursor-pointer select-none group"
                    onClick={() => hasSplits && toggleRow(tx.key)}
                  >
                    {/* Col 1: Icon & Title (Spans 8 cols on mobile, 4 on desktop) */}
                    <div className="col-span-8 md:col-span-4 flex items-center gap-3.5 min-w-0 pr-4">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${iconBg}`}>
                        <Icon className="w-4.5 h-4.5" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <div className="font-bold text-[#0F172A] truncate text-sm">
                          {tx.title}
                        </div>
                        {/* Mobile shows category/account below title, Desktop hides it */}
                        <div className="md:hidden text-xs text-slate-500 truncate flex items-center gap-1.5 mt-0.5">
                          <span>{tx.items[0]?.category_name || "Uncategorized"}</span>
                          {paymentDisplay && (
                            <>
                              <span className="w-1 h-1 bg-slate-300 rounded-full" />
                              <span className="flex items-center gap-1">
                                <CreditCard className="w-3 h-3" />
                                <span className="truncate">{paymentDisplay}</span>
                              </span>
                            </>
                          )}
                        </div>
                        {/* Desktop shows notes (if any) below title */}
                        <div className="hidden md:block text-xs text-slate-500 truncate mt-0.5">
                          {tx.notes ? tx.notes : <span className="text-transparent select-none">No notes</span>}
                        </div>
                      </div>
                    </div>

                    {/* Col 2: Category & Labels (Spans 3 cols, hidden on mobile) */}
                    <div className="hidden md:flex col-span-3 flex-col items-start pr-4 min-w-0">
                      <div className="text-sm text-slate-700 truncate w-full">
                        {tx.items[0]?.category_name || "Uncategorized"}
                      </div>
                      <div className="flex gap-1 mt-0.5">
                        {labelBadges.map((lbl, i) => (
                          <span key={i} className="text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                            {lbl}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Col 3: Payment Account (Spans 2 cols, hidden on mobile) */}
                    <div className="hidden md:flex col-span-2 flex-col items-start pr-4 min-w-0">
                      <div className="flex items-center gap-1.5 text-sm text-slate-700 truncate w-full">
                        <CreditCard className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{paymentDisplay}</span>
                      </div>
                      {hasSplits && (
                        <div className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                          <span className="w-3 h-3 flex items-center justify-center bg-slate-200 rounded-sm text-[8px] font-bold">S</span> Split
                        </div>
                      )}
                    </div>

                    {/* Col 4: Actions & Amount (Spans 4 cols on mobile, 3 on desktop) */}
                    <div className="col-span-4 md:col-span-3 flex items-center justify-end gap-3 min-w-0">
                      
                      {/* Desktop Actions (visible on row hover) - Positioned BEFORE Amount */}
                      <div className="hidden md:flex opacity-0 group-hover:opacity-100 transition-opacity items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        {tx.source === "cashflow" && tx.rawCashflow && (
                          <>
                            <button onClick={() => onEditCashflow?.(tx.rawCashflow!)} className="p-1 text-slate-400 hover:text-blue-600 rounded-lg" title="Edit">
                              <Edit className="w-4 h-4" />
                            </button>
                            <button onClick={() => onDeleteCashflow?.(tx.rawCashflow!.cashflow_id)} className="p-1 text-slate-400 hover:text-rose-600 rounded-lg" title="Delete">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                        {tx.source === "investment" && tx.rawTrade && (
                          <>
                            <button onClick={() => onEditTrade?.(tx.rawTrade!)} className="p-1 text-slate-400 hover:text-blue-600 rounded-lg" title="Edit">
                              <Edit className="w-4 h-4" />
                            </button>
                            <button onClick={() => onDeleteTrade?.(tx.rawTrade!.transaction_id)} className="p-1 text-slate-400 hover:text-rose-600 rounded-lg" title="Delete">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>

                      {/* Amount & Balance */}
                      <div className="flex flex-col items-end shrink-0 pl-2">
                        <div className={`font-bold tabular-nums text-sm ${tx.isTransfer ? "text-[#0F172A]" : tx.isIncome ? "text-emerald-600" : "text-rose-600"}`}>
                          {tx.isIncome ? "+" : "-"}{formatCurrency(tx.totalAmount, tx.currency)}
                        </div>
                        
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {showRunningBalance && runningBalanceDisplay && (
                            <div className="text-[10px] font-semibold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                              Bal: {runningBalanceDisplay}
                            </div>
                          )}
                          
                          {hasSplits && (
                            <div className="text-slate-400 ml-1">
                              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Mobile Actions (Always visible below row on small screens) */}
                  <div className="md:hidden flex items-center justify-end gap-3 px-4 pb-3" onClick={(e) => e.stopPropagation()}>
                     {tx.source === "cashflow" && tx.rawCashflow && (
                        <>
                          <button onClick={() => onEditCashflow?.(tx.rawCashflow!)} className="text-[11px] font-bold text-slate-500 flex items-center gap-1 uppercase">
                            <Edit className="w-3 h-3" /> Edit
                          </button>
                          <button onClick={() => onDeleteCashflow?.(tx.rawCashflow!.cashflow_id)} className="text-[11px] font-bold text-rose-500 flex items-center gap-1 uppercase">
                            <Trash2 className="w-3 h-3" /> Delete
                          </button>
                        </>
                      )}
                      {tx.source === "investment" && tx.rawTrade && (
                        <>
                          <button onClick={() => onEditTrade?.(tx.rawTrade!)} className="text-[11px] font-bold text-slate-500 flex items-center gap-1 uppercase">
                            <Edit className="w-3 h-3" /> Edit
                          </button>
                          <button onClick={() => onDeleteTrade?.(tx.rawTrade!.transaction_id)} className="text-[11px] font-bold text-rose-500 flex items-center gap-1 uppercase">
                            <Trash2 className="w-3 h-3" /> Delete
                          </button>
                        </>
                      )}
                  </div>"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w") as f:
        f.write(content)
    print("Successfully replaced.")
else:
    print("Target not found.")

