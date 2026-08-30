"use client";

import { useState } from "react";
import { uploadFile, confirmMapping } from "@/lib/api";
import { Upload, FileText, CheckCircle, AlertTriangle, ChevronRight, X, Plus, RotateCcw } from "lucide-react";
import Link from "next/link";

type UploadedFileState = {
  id: string;
  file: File;
  fileData: any | null;
  mapping: Record<string, string>;
  dataType: string;
  status: "pending" | "uploading" | "mapped" | "error";
  errorMsg: string;
};

export default function UploadPage() {
  const [files, setFiles] = useState<UploadedFileState[]>([]);
  const [globalStatus, setGlobalStatus] = useState<"idle" | "mapping" | "confirming" | "success">("idle");
  const [globalError, setGlobalError] = useState("");
  const [datasetName, setDatasetName] = useState("");

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
        // Auto-set dataset name based on the first file or current date
        setDatasetName(`Batch Upload ${new Date().toLocaleDateString()}`);
      }

      setGlobalStatus("mapping");
      
      // Upload them sequentially or parallel to get mappings
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

  const [ingestionResult, setIngestionResult] = useState<any>(null);

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
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Upload Center</h1>
        <p className="text-gray-400">Upload your financial files for automatic schema detection and ingestion.</p>
      </div>
      
      {globalStatus === "idle" && files.length === 0 ? (
        <div className="border-2 border-dashed border-border rounded-xl p-12 text-center bg-card">
          <Upload className="w-16 h-16 text-gray-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">Drag and drop your financial files here</h2>
          <p className="text-gray-400 mb-8 max-w-md mx-auto">
            Upload multiple files at once. You can mix CSV, XLSX, XLS, and PDF files containing Bank Statements, Gateway captures, or Invoices.
          </p>
          
          <label className="bg-primary hover:bg-primary-dark cursor-pointer text-white font-medium py-3 px-8 rounded-xl transition-colors inline-flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Select Files
            <input 
              type="file" 
              multiple
              accept=".csv, .xls, .xlsx, .pdf"
              onChange={handleFileChange}
              className="hidden"
            />
          </label>
        </div>
      ) : globalStatus === "success" ? (
        <div className="bg-card border border-border rounded-xl p-12 text-center">
          <CheckCircle className="w-20 h-20 text-emerald-500 mx-auto mb-6" />
          <h2 className="text-3xl font-bold text-white mb-2">Upload Successful!</h2>
          <p className="text-gray-400 mb-6 text-lg">Dataset "{datasetName}" is ready for reconciliation.</p>
          
          {ingestionResult?.files && (
            <div className="max-w-lg mx-auto bg-background border border-border rounded-xl p-6 mb-8 text-left space-y-4">
              <h3 className="font-semibold text-white border-b border-border pb-2">Ingestion Summary</h3>
              {ingestionResult.files.map((f: any, idx: number) => (
                <div key={idx} className="flex justify-between items-center text-sm">
                  <span className="text-gray-400 font-mono">{f.file_type}</span>
                  <span className="text-emerald-400">
                    {f.rows_ingested} ingested
                    {f.rows_skipped_as_duplicate > 0 && ` (${f.rows_skipped_as_duplicate} duplicate rows skipped)`}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-center gap-4">
            <button
              onClick={clearAllFiles}
              className="border border-border bg-gray-800 hover:bg-gray-700 text-gray-200 font-medium py-3 px-6 rounded-xl inline-flex items-center gap-2 text-lg transition-colors"
            >
              <RotateCcw className="w-5 h-5" /> Upload Another Batch
            </button>
            <Link href="/" className="bg-primary hover:bg-primary-dark text-white font-medium py-3 px-8 rounded-xl inline-flex items-center gap-2 text-lg transition-colors">
              Go to Dashboard <ChevronRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          
          <div className="bg-card border border-border rounded-xl p-6 flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-white">Dataset Configuration</h2>
              <p className="text-sm text-gray-400">All files below will be grouped into this dataset.</p>
            </div>
            <input 
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
              placeholder="E.g., Q3 Financials"
              className="bg-background border border-border rounded-lg px-4 py-2 text-sm w-64 focus:border-primary focus:outline-none"
            />
          </div>

          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white">Files ({files.length})</h2>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={clearAllFiles}
                className="text-sm text-rose-400 hover:text-rose-300 flex items-center gap-1.5 font-medium px-3 py-1.5 rounded-lg border border-rose-500/20 bg-rose-950/20 hover:bg-rose-900/30 transition-all"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Clear & Start Over
              </button>
              <label className="cursor-pointer text-sm text-primary hover:text-primary-light flex items-center gap-1 font-medium">
                <Plus className="w-4 h-4" /> Add More Files
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

          {files.map((f) => (
            <div key={f.id} className="bg-card border border-border rounded-xl p-6 relative">
              <button 
                onClick={() => removeFile(f.id)}
                className="absolute top-4 right-4 p-1 text-gray-500 hover:text-red-400 rounded-full hover:bg-red-500/10 transition-colors"
                title="Remove file"
              >
                <X className="w-5 h-5" />
              </button>
              
              <div className="flex justify-between items-start mb-6 pr-8">
                <div>
                  <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                    <FileText className="w-5 h-5 text-primary" />
                    {f.file.name}
                  </h3>
                  {f.status === "uploading" && <span className="text-sm text-blue-400 animate-pulse">Analyzing file...</span>}
                  {f.status === "error" && <span className="text-sm text-red-400 flex items-center gap-1"><AlertTriangle className="w-4 h-4" /> {f.errorMsg}</span>}
                  {f.status === "mapped" && <span className="text-sm text-emerald-400 flex items-center gap-1"><CheckCircle className="w-4 h-4" /> Parsed ({f.fileData?.row_count} rows)</span>}
                </div>
                
                {f.status === "mapped" && (
                  <div className="flex items-center gap-3 bg-background px-3 py-1.5 rounded-lg border border-border">
                    <span className="text-sm text-gray-400">Data Type:</span>
                    <select 
                      value={f.dataType}
                      onChange={(e) => updateFileState(f.id, { dataType: e.target.value })}
                      className="bg-transparent text-white text-sm font-medium focus:outline-none"
                    >
                      <option value="BANK">Bank Transactions</option>
                      <option value="GATEWAY">Gateway Payments</option>
                      <option value="INVOICE">Invoices</option>
                    </select>
                  </div>
                )}
              </div>

              {f.status === "mapped" && (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-border text-gray-400 text-xs uppercase tracking-wider">
                        <th className="py-2.5 px-3 w-1/4">Target Field</th>
                        <th className="py-2.5 px-3 w-1/3">Mapped Source Column</th>
                        <th className="py-2.5 px-3 w-5/12">3 Real Sample Values from File</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                      {getTargetSchemaFields(f.dataType).map((field) => {
                        const selectedCol = f.mapping[field.key] || "";
                        const sampleValues = selectedCol && f.fileData?.column_previews?.[selectedCol] 
                          ? f.fileData.column_previews[selectedCol] 
                          : [];
                        return (
                          <tr key={field.key} className="hover:bg-card/40 transition-colors">
                            <td className="py-3 px-3">
                              <div className="font-mono text-sm font-semibold text-white flex items-center gap-1.5">
                                {field.label}
                                {field.required && <span className="text-rose-400 font-bold">*</span>}
                              </div>
                              <div className="text-xs text-gray-400">{field.desc}</div>
                            </td>
                            <td className="py-3 px-3">
                              <select 
                                value={selectedCol}
                                onChange={(e) => {
                                  const newMapping = { ...f.mapping, [field.key]: e.target.value };
                                  updateFileState(f.id, { mapping: newMapping });
                                }}
                                className="bg-background border border-border rounded-lg px-3 py-2 text-xs font-mono w-full max-w-sm focus:border-primary focus:outline-none"
                              >
                                <option value="">-- Unmapped / Optional --</option>
                                {f.fileData?.headers.map((h: string) => (
                                  <option key={h} value={h}>{h}</option>
                                ))}
                              </select>
                            </td>
                            <td className="py-3 px-3">
                              {sampleValues.length > 0 ? (
                                <div className="flex flex-wrap gap-1.5">
                                  {sampleValues.map((val: string, vIdx: number) => (
                                    <span key={vIdx} className="inline-block bg-primary/10 border border-primary/30 text-primary-light rounded px-2 py-0.5 text-xs font-mono">
                                      {val}
                                    </span>
                                  ))}
                                </div>
                              ) : selectedCol ? (
                                <span className="text-xs text-gray-500 italic">No non-empty samples</span>
                              ) : (
                                <span className="text-xs text-gray-600">—</span>
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
          ))}

          {globalError && (
            <div className="p-4 bg-red-900/20 border border-red-500/50 rounded-lg text-red-400 flex items-center justify-center gap-2">
              <AlertTriangle className="w-5 h-5" />
              {globalError}
            </div>
          )}

          <div className="flex justify-end gap-4 mt-8">
            <button 
              onClick={() => { setGlobalStatus("idle"); setFiles([]); setDatasetName(""); }}
              className="px-6 py-2.5 text-gray-400 hover:text-white transition-colors font-medium rounded-lg"
            >
              Cancel Everything
            </button>
            <button 
              onClick={handleConfirm}
              disabled={globalStatus === "confirming" || files.some(f => f.status === "uploading")}
              className="bg-primary hover:bg-primary-dark disabled:opacity-50 text-white font-bold py-2.5 px-8 rounded-xl shadow-lg glow-primary transition-all flex items-center gap-2"
            >
              {globalStatus === "confirming" ? "Ingesting Data..." : "Confirm & Ingest All"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
