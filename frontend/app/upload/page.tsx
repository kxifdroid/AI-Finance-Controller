"use client";

import { useState } from "react";
import { uploadFile, confirmMapping } from "@/lib/api";
import { 
  Upload, 
  FileText, 
  CheckCircle2, 
  AlertTriangle, 
  ChevronRight, 
  X, 
  Plus, 
  RotateCcw,
  Building2,
  CreditCard,
  Layers,
  ArrowRight,
  Sparkles,
  ShieldCheck
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

type UploadedFileState = {
  id: string;
  file: File;
  fileData: any | null;
  mapping: Record<string, string>;
  dataType: string;
  status: "pending" | "uploading" | "mapped" | "error";
  errorMsg: string;
};

const STEPPER_STEPS = [
  { id: 1, name: "Upload" },
  { id: 2, name: "Detect" },
  { id: 3, name: "Map Schema" },
  { id: 4, name: "Validate" },
  { id: 5, name: "Ingest" },
  { id: 6, name: "Ready" },
];

export default function UploadPage() {
  const [files, setFiles] = useState<UploadedFileState[]>([]);
  const [globalStatus, setGlobalStatus] = useState<"idle" | "mapping" | "confirming" | "success">("idle");
  const [globalError, setGlobalError] = useState("");
  const [datasetName, setDatasetName] = useState("");
  const [ingestionResult, setIngestionResult] = useState<any>(null);

  // Compute active stepper step
  const getActiveStep = () => {
    if (globalStatus === "success") return 6;
    if (globalStatus === "confirming") return 5;
    if (files.some(f => f.status === "uploading")) return 2;
    if (files.some(f => f.status === "mapped")) return 3;
    return 1;
  };

  const currentStep = getActiveStep();

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files).map((f) => ({
        id: Math.random().toString(36).substring(7),
        file: f,
        fileData: null,
        mapping: {},
        dataType: "BANK",
        status: "pending" as const,
        errorMsg: "",
      }));

      setFiles((prev) => [...prev, ...newFiles]);
      
      if (!datasetName && newFiles.length > 0) {
        setDatasetName(`Batch Ingestion ${new Date().toLocaleDateString()}`);
      }

      setGlobalStatus("mapping");
      
      for (const nf of newFiles) {
        updateFileState(nf.id, { status: "uploading" });
        try {
          const data = await uploadFile(nf.file);
          updateFileState(nf.id, {
            status: "mapped",
            fileData: data,
            mapping: data.suggested_mapping || {},
            dataType: data.detected_type || "UNKNOWN",
          });
        } catch (err: any) {
          updateFileState(nf.id, {
            status: "error",
            errorMsg: err.message || "Failed to parse file",
          });
        }
      }
    }
  };

  const updateFileState = (id: string, updates: Partial<UploadedFileState>) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...updates } : f)));
  };

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
    if (files.length === 1) {
      setGlobalStatus("idle");
    }
  };

  const handleConfirm = async () => {
    setGlobalStatus("confirming");
    setGlobalError("");
    
    const mappedFiles = files.filter(f => f.status === "mapped" && f.fileData);
    
    if (mappedFiles.length === 0) {
      setGlobalError("No valid files to confirm.");
      setGlobalStatus("mapping");
      return;
    }

    try {
      const payload = {
        dataset_name: datasetName,
        files: mappedFiles.map(f => ({
          file_id: f.fileData.file_id,
          filename: f.fileData.filename,
          file_type: f.fileData.file_type,
          data_type: f.dataType,
          mapping: f.mapping,
        }))
      };
      
      const result = await confirmMapping(payload);
      
      localStorage.setItem("latest_dataset_id", result.dataset_id);
      setIngestionResult(result);
      setGlobalStatus("success");
    } catch (err: any) {
      setGlobalError(err.message || "Failed to confirm mappings.");
      setGlobalStatus("mapping");
    }
  };

  const clearAllFiles = () => {
    setFiles([]);
    setGlobalStatus("idle");
    setGlobalError("");
    setIngestionResult(null);
  };

  const getTargetSchemaFields = (dataType: string) => {
    switch (dataType) {
      case "INVOICE":
        return [
          { key: "invoice_id", label: "Invoice ID", required: true, desc: "Unique ERP invoice number" },
          { key: "amount", label: "Invoice Amount (Gross)", required: true, desc: "Total invoiced amount" },
          { key: "invoice_date", label: "Invoice Date", required: true, desc: "Date invoice was issued" },
          { key: "order_id", label: "Order ID", required: false, desc: "Sales order or PO number" },
          { key: "invoice_reference", label: "Reference Code", required: false, desc: "Secondary invoice/PO reference" },
          { key: "customer_name", label: "Customer Name", required: false, desc: "Client or buyer company name" },
          { key: "customer_id", label: "Customer ID", required: false, desc: "Internal customer/account identifier" },
          { key: "tax_amount", label: "Tax / GST Amount", required: false, desc: "Billed tax component" },
          { key: "currency", label: "Currency", required: false, desc: "Currency code (default INR)" },
          { key: "due_date", label: "Due Date", required: false, desc: "Payment due date" },
        ];
      case "GATEWAY":
        return [
          { key: "gateway_txn_id", label: "Gateway Txn ID", required: true, desc: "Payment capture / charge ID" },
          { key: "gross_amount", label: "Gross Amount", required: true, desc: "Original captured payment amount" },
          { key: "transaction_date", label: "Transaction Date", required: true, desc: "Payment capture timestamp/date" },
          { key: "gateway_order_id", label: "Gateway Order ID", required: false, desc: "Razorpay/Stripe Order ID" },
          { key: "payment_reference", label: "Merchant Reference", required: false, desc: "Merchant order / reference ID" },
          { key: "net_amount", label: "Net Settlement Amount", required: false, desc: "Net payout after fees (or auto-computed)" },
          { key: "gateway_fee", label: "Gateway Processing Fee", required: false, desc: "Fee deducted by processor (MDR)" },
          { key: "tax_on_fee", label: "Tax on Fee (GST/VAT)", required: false, desc: "Tax levied on processing fees" },
          { key: "customer_name", label: "Customer / Payer", required: false, desc: "Payer name or cardholder name" },
          { key: "payment_method", label: "Payment Method", required: false, desc: "UPI, Card, Net Banking, Wallet" },
          { key: "currency", label: "Currency", required: false, desc: "Currency code (default INR)" },
        ];
      case "BANK":
        return [
          { key: "bank_txn_id", label: "Bank Transaction ID", required: true, desc: "UTR, reference, or line item ID" },
          { key: "amount", label: "Deposit / Credit Amount", required: true, desc: "Cleared funds deposited into bank" },
          { key: "transaction_date", label: "Statement Date", required: true, desc: "Bank value / clearing date" },
          { key: "utr", label: "UTR / Settlement Ref", required: false, desc: "Unique Transaction Reference number" },
          { key: "reference", label: "Narration / Reference", required: false, desc: "Bank memo, order reference, or UTR" },
          { key: "description", label: "Description / Narration", required: false, desc: "Detailed bank statement narration" },
          { key: "credit_amount", label: "Credit Column (if separate)", required: false, desc: "Deposit / credit amount column" },
          { key: "debit_amount", label: "Debit Column (if separate)", required: false, desc: "Withdrawal / debit amount column" },
          { key: "balance", label: "Closing Balance", required: false, desc: "Running account balance" },
          { key: "currency", label: "Currency", required: false, desc: "Currency code (default INR)" },
        ];
      default:
        return [];
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      
      {/* Header */}
      <div className="border-b border-border pb-5">
        <div className="flex items-center gap-2.5">
          <h1 className="text-2xl sm:text-[26px] font-bold tracking-tight text-content">
            Data Ingestion & Schema Mapping
          </h1>
          <span className="text-xs font-mono text-content-secondary bg-surface-secondary px-2.5 py-0.5 rounded-full border border-border">
            Multi-Source Ingestion
          </span>
        </div>
        <p className="mt-1 text-xs text-content-secondary">
          Upload Bank Statements, Payment Gateway logs, and ERP Invoices. Automatically detect columns, map to canonical schema, and ingest into the ledger.
        </p>
      </div>

      {/* 6-Step Progress Stepper */}
      <div className="rounded-xl border border-border bg-surface-secondary p-4 shadow-xs">
        <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1">
          {STEPPER_STEPS.map((step, idx) => {
            const isCompleted = step.id < currentStep;
            const isCurrent = step.id === currentStep;
            return (
              <div key={step.id} className="flex items-center gap-2 shrink-0">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "h-6 w-6 rounded-full flex items-center justify-center text-[11px] font-bold transition-all",
                      isCompleted
                        ? "bg-emerald-500 text-white"
                        : isCurrent
                        ? "bg-primary text-white ring-2 ring-primary/40"
                        : "bg-surface-elevated text-content-muted border border-border"
                    )}
                  >
                    {isCompleted ? "✓" : step.id}
                  </div>
                  <span
                    className={cn(
                      "text-xs font-medium whitespace-nowrap",
                      isCompleted ? "text-content-secondary" : isCurrent ? "text-content font-bold" : "text-content-muted"
                    )}
                  >
                    {step.name}
                  </span>
                </div>
                {idx < STEPPER_STEPS.length - 1 && (
                  <ChevronRight className="h-4 w-4 text-content-muted shrink-0 ml-1" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {globalStatus === "idle" && files.length === 0 ? (
        <div className="space-y-6">
          {/* Multi-Lane Dropzone */}
          <div className="border-2 border-dashed border-border hover:border-border-strong rounded-2xl p-10 text-center bg-surface-secondary transition-all">
            <Upload className="w-12 h-12 text-primary-light mx-auto mb-3" />
            <h2 className="text-lg font-bold text-content mb-1">
              Select or Drop Financial Dataset Files
            </h2>
            <p className="text-xs text-content-secondary mb-6 max-w-lg mx-auto">
              Upload multiple files simultaneously. Accepts CSV, XLSX, XLS, and PDF exports for Bank Statements, Payment Gateway captures, and ERP Invoices.
            </p>
            
            <label className="bg-primary hover:bg-primary-hover cursor-pointer text-white font-semibold py-2.5 px-6 rounded-xl transition-all inline-flex items-center gap-2 text-xs shadow-sm focus-ring">
              <Plus className="w-4 h-4" />
              Browse Financial Files
              <input 
                type="file" 
                multiple
                accept=".csv, .xls, .xlsx, .pdf"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
          </div>

          {/* 3 Source Lanes Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-xl border border-border bg-surface-secondary p-4 space-y-2 shadow-xs">
              <div className="flex items-center gap-2 text-sky-600 dark:text-sky-400 text-xs font-semibold uppercase tracking-wider">
                <Building2 className="h-4 w-4" /> Bank Statements
              </div>
              <p className="text-xs text-content-secondary">
                UTR numbers, clearing dates, credit/debit balances, and settlement narrations.
              </p>
            </div>

            <div className="rounded-xl border border-border bg-surface-secondary p-4 space-y-2 shadow-xs">
              <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 text-xs font-semibold uppercase tracking-wider">
                <CreditCard className="h-4 w-4" /> Gateway Logs
              </div>
              <p className="text-xs text-content-secondary">
                Gross capture, Razorpay/Stripe order IDs, MDR processing fees, GST, and net settlement.
              </p>
            </div>

            <div className="rounded-xl border border-border bg-surface-secondary p-4 space-y-2 shadow-xs">
              <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 text-xs font-semibold uppercase tracking-wider">
                <FileText className="h-4 w-4" /> ERP Invoices
              </div>
              <p className="text-xs text-content-secondary">
                Invoice numbers, client entities, billed tax, PO references, and receivable amounts.
              </p>
            </div>
          </div>
        </div>
      ) : globalStatus === "success" ? (
        /* Ingestion Success Completion State */
        <div className="bg-surface-secondary border border-emerald-500/30 rounded-2xl p-10 text-center space-y-6 shadow-xs">
          <div className="h-16 w-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-500 dark:text-emerald-400">
            <CheckCircle2 className="w-9 h-9" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-content">Dataset Ingestion Complete</h2>
            <p className="text-xs text-content-secondary mt-1 max-w-md mx-auto">
              Dataset <strong className="text-content font-mono">"{datasetName}"</strong> has been successfully canonicalized and ingested into the active reconciliation ledger.
            </p>
          </div>
          
          {ingestionResult?.files && (
            <div className="max-w-md mx-auto bg-surface border border-border rounded-xl p-4 text-left space-y-2.5 shadow-xs">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-content border-b border-border pb-2">
                Ingestion Summary
              </h3>
              {ingestionResult.files.map((f: any, idx: number) => (
                <div key={idx} className="flex justify-between items-center text-xs">
                  <span className="text-content font-mono font-medium">{f.file_type}</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold tabular-nums">
                    {f.rows_ingested} records ingested
                    {f.rows_skipped_as_duplicate > 0 && ` (${f.rows_skipped_as_duplicate} duplicates deduplicated)`}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={clearAllFiles}
              className="border border-border bg-surface hover:bg-surface-elevated text-content font-semibold py-2 px-5 rounded-xl inline-flex items-center gap-1.5 text-xs transition-colors focus-ring shadow-xs"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Upload Another File
            </button>
            <Link 
              href="/" 
              className="bg-primary hover:bg-primary-hover text-white font-bold py-2 px-6 rounded-xl inline-flex items-center gap-1.5 text-xs transition-all shadow-sm focus-ring"
            >
              Go to Financial Control Center <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      ) : (
        /* Active Mapping Configuration Workspace */
        <div className="space-y-6">
          
          {/* Dataset Configuration Bar */}
          <div className="bg-surface-secondary border border-border rounded-xl p-4 flex flex-col sm:flex-row justify-between sm:items-center gap-3 shadow-xs">
            <div>
              <h2 className="text-sm font-semibold text-content">Dataset Configuration</h2>
              <p className="text-xs text-content-secondary">All parsed files below will be unified under this dataset batch.</p>
            </div>
            <input 
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
              placeholder="e.g., March 2026 Monthly Close"
              className="bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-content w-full sm:w-64 focus-ring placeholder-content-muted"
            />
          </div>

          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white">Staged Files ({files.length})</h2>
            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={clearAllFiles}
                className="text-xs text-rose-600 dark:text-rose-300 hover:text-rose-700 dark:hover:text-rose-200 flex items-center gap-1 font-semibold px-2.5 py-1 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 transition-all focus-ring shadow-xs"
              >
                <RotateCcw className="w-3 h-3" /> Clear & Reset
              </button>
              <label className="cursor-pointer text-xs text-content hover:text-primary flex items-center gap-1 font-semibold px-2.5 py-1 rounded-lg bg-surface border border-border hover:bg-surface-elevated transition-colors shadow-xs">
                <Plus className="w-3 h-3" /> Add More Files
                <input 
                  type="file" 
                  multiple
                  accept=".csv, .xls, .xlsx, .pdf"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {files.map((f) => {
            const schemaFields = getTargetSchemaFields(f.dataType);
            const mappedCount = schemaFields.filter(field => Boolean(f.mapping[field.key])).length;
            const requiredMissing = schemaFields.filter(field => field.required && !f.mapping[field.key]);

            return (
              <div key={f.id} className="bg-surface-secondary border border-border rounded-xl p-5 relative space-y-4 shadow-xs">
                <button 
                  onClick={() => removeFile(f.id)}
                  className="absolute top-4 right-4 p-1 text-content-muted hover:text-rose-600 dark:hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition-colors focus-ring"
                  title="Remove file"
                >
                  <X className="w-4 h-4" />
                </button>
                
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pr-8">
                  <div>
                    <h3 className="text-sm font-bold text-content flex items-center gap-2">
                      <FileText className="w-4 h-4 text-primary-light" />
                      {f.file.name}
                    </h3>
                    {f.status === "uploading" && <span className="text-xs text-sky-600 dark:text-sky-400 animate-pulse font-medium">Analyzing columns & headers...</span>}
                    {f.status === "error" && <span className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1 font-medium"><AlertTriangle className="w-3.5 h-3.5" /> {f.errorMsg}</span>}
                    {f.status === "mapped" && (
                      <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Parsed ({f.fileData?.row_count} rows detected)
                      </span>
                    )}
                  </div>
                  
                  {f.status === "mapped" && (
                    <div className="flex items-center gap-2 bg-surface px-3 py-1.5 rounded-lg border border-border shadow-xs">
                      <span className="text-xs text-content-secondary font-medium">Data Type:</span>
                      <select 
                        value={f.dataType}
                        onChange={(e) => updateFileState(f.id, { dataType: e.target.value })}
                        className="bg-transparent text-content text-xs font-bold focus:outline-none"
                      >
                        <option value="BANK" className="bg-surface text-content">Bank Transactions</option>
                        <option value="GATEWAY" className="bg-surface text-content">Payment Gateway</option>
                        <option value="INVOICE" className="bg-surface text-content">ERP Invoices</option>
                      </select>
                    </div>
                  )}
                </div>

                {/* Auto-Mapping Validation Summary Bar */}
                {f.status === "mapped" && (
                  <div className={cn(
                    "flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-xs font-mono shadow-xs",
                    requiredMissing.length === 0
                      ? "bg-emerald-500/10 border border-emerald-500/25 text-emerald-700 dark:text-emerald-300"
                      : "bg-amber-500/10 border border-amber-500/25 text-amber-700 dark:text-amber-300"
                  )}>
                    <div className="flex items-center gap-1.5">
                      {requiredMissing.length === 0 ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                      ) : (
                        <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                      )}
                      <span>
                        Schema Validation: {mappedCount} of {schemaFields.length} columns mapped
                        {requiredMissing.length > 0 && ` · Missing required: ${requiredMissing.map(m => m.label).join(", ")}`}
                      </span>
                    </div>
                    <span className="text-[11px] font-bold">
                      {requiredMissing.length === 0 ? "✓ Ready to Ingest" : "Action Required"}
                    </span>
                  </div>
                )}

                {f.status === "mapped" && (
                  <div className="overflow-x-auto rounded-lg border border-border bg-surface shadow-xs">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-surface-secondary text-content-secondary uppercase text-[10px] border-b border-border">
                        <tr>
                          <th className="py-2.5 px-3 w-1/4">Canonical Target Field</th>
                          <th className="py-2.5 px-3 w-1/3">Source File Column</th>
                          <th className="py-2.5 px-3 w-5/12">Sample Data Preview</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {schemaFields.map((field) => {
                          const selectedCol = f.mapping[field.key] || "";
                          const sampleValues = selectedCol && f.fileData?.column_previews?.[selectedCol] 
                            ? f.fileData.column_previews[selectedCol] 
                            : [];
                          return (
                            <tr key={field.key} className="hover:bg-surface-secondary/40 transition-colors">
                              <td className="py-2.5 px-3">
                                <div className="font-mono text-xs font-bold text-content flex items-center gap-1.5">
                                  {field.label}
                                  {field.required && <span className="text-rose-500 font-bold">*</span>}
                                </div>
                                <div className="text-[11px] text-content-secondary">{field.desc}</div>
                              </td>
                              <td className="py-2.5 px-3">
                                <select 
                                  value={selectedCol}
                                  onChange={(e) => {
                                    const newMapping = { ...f.mapping, [field.key]: e.target.value };
                                    updateFileState(f.id, { mapping: newMapping });
                                  }}
                                  className="bg-surface-secondary border border-border rounded-lg px-2.5 py-1.5 text-xs font-mono w-full max-w-sm text-content focus-ring"
                                >
                                  <option value="">-- Unmapped / Optional --</option>
                                  {f.fileData?.headers.map((h: string) => (
                                    <option key={h} value={h}>{h}</option>
                                  ))}
                                </select>
                              </td>
                              <td className="py-2.5 px-3">
                                {sampleValues.length > 0 ? (
                                  <div className="flex flex-wrap gap-1.5">
                                    {sampleValues.map((val: string, vIdx: number) => (
                                      <span key={vIdx} className="inline-block bg-primary/10 border border-primary/25 text-primary rounded px-1.5 py-0.5 text-[11px] font-mono font-semibold">
                                        {val}
                                      </span>
                                    ))}
                                  </div>
                                ) : selectedCol ? (
                                  <span className="text-xs text-content-muted italic">No non-empty samples</span>
                                ) : (
                                  <span className="text-xs text-content-muted">—</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}

          {globalError && (
            <div className="p-3.5 bg-rose-500/10 border border-rose-500/40 rounded-xl text-rose-700 dark:text-rose-300 text-xs flex items-center justify-center gap-2 shadow-xs">
              <AlertTriangle className="w-4 h-4" />
              {globalError}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button 
              onClick={() => { setGlobalStatus("idle"); setFiles([]); setDatasetName(""); }}
              className="px-4 py-2 text-content-secondary hover:text-content transition-colors text-xs font-semibold rounded-lg"
            >
              Cancel
            </button>
            <button 
              onClick={handleConfirm}
              disabled={globalStatus === "confirming" || files.some(f => f.status === "uploading")}
              className="bg-primary hover:bg-primary-hover disabled:opacity-50 text-white font-bold py-2 px-6 rounded-xl transition-all shadow-sm flex items-center gap-2 text-xs focus-ring"
            >
              {globalStatus === "confirming" ? "Ingesting Dataset..." : "Confirm Mapping & Ingest All"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
