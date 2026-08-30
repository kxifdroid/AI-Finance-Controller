import {
  MetricsSummary,
  MatchRecord,
  TransactionDetail,
  ExceptionRecord,
  CashForecastData,
  AIInvestigation,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function fetchMetrics(datasetId?: string): Promise<MetricsSummary> {
  const url = datasetId ? `${API_BASE}/api/metrics?dataset_id=${datasetId}` : `${API_BASE}/api/metrics`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function generateSyntheticData(count: number = 250): Promise<any> {
  const res = await fetch(`${API_BASE}/api/data/generate?count=${count}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("Failed to generate synthetic data");
  return res.json();
}

export async function triggerReconciliation(useAi: boolean = true, datasetId?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/reconciliation/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_ai: useAi, dataset_id: datasetId }),
  });
  if (!res.ok) throw new Error("Failed to run reconciliation pipeline");
  return res.json();
}

export async function resetReconciliation(datasetId?: string, clearAllData: boolean = true): Promise<any> {
  const res = await fetch(`${API_BASE}/api/reconciliation/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, clear_all_data: clearAllData }),
  });
  if (!res.ok) throw new Error("Failed to reset reconciliation analysis");
  return res.json();
}

export async function uploadFile(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  
  const res = await fetch(`${API_BASE}/api/upload/file`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload file");
  return res.json();
}

export async function confirmMapping(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/upload/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || `HTTP Error ${res.status}`);
  }
  return res.json();
}

export async function fetchTransactions(params: {
  status?: string;
  risk?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<{ total: number; page: number; pageSize: number; items: MatchRecord[] }> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.risk) q.set("risk", params.risk);
  if (params.search) q.set("search", params.search);
  if (params.page) q.set("page", params.page.toString());
  if (params.pageSize) q.set("page_size", params.pageSize.toString());

  const res = await fetch(`${API_BASE}/api/transactions?${q.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch transactions");
  return res.json();
}

export async function fetchTransactionDetail(id: string): Promise<TransactionDetail> {
  const res = await fetch(`${API_BASE}/api/transactions/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch transaction detail");
  return res.json();
}

export async function fetchExceptions(params: {
  status?: string;
  severity?: string;
  page?: number;
  pageSize?: number;
}): Promise<{ total: number; page: number; pageSize: number; items: ExceptionRecord[] }> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.severity) q.set("severity", params.severity);
  if (params.page) q.set("page", params.page.toString());
  if (params.pageSize) q.set("page_size", params.pageSize.toString());

  const res = await fetch(`${API_BASE}/api/exceptions?${q.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch exceptions");
  return res.json();
}

export async function updateExceptionStatus(
  id: string,
  status: string,
  notes?: string
): Promise<ExceptionRecord> {
  const res = await fetch(`${API_BASE}/api/exceptions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes }),
  });
  if (!res.ok) throw new Error("Failed to update exception status");
  return res.json();
}

export async function investigateException(id: string): Promise<AIInvestigation> {
  const res = await fetch(`${API_BASE}/api/exceptions/${id}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to investigate exception");
  }
  return res.json();
}

export async function approveException(id: string, notes?: string): Promise<ExceptionRecord> {
  const res = await fetch(`${API_BASE}/api/exceptions/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to approve exception");
  }
  return res.json();
}

export async function rejectException(id: string, reason: string): Promise<ExceptionRecord> {
  const res = await fetch(`${API_BASE}/api/exceptions/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to reject exception");
  }
  return res.json();
}

export async function fetchCashForecast(datasetId?: string): Promise<CashForecastData> {
  const url = datasetId ? `${API_BASE}/api/forecast?dataset_id=${datasetId}` : `${API_BASE}/api/forecast`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch cash forecast");
  return res.json();
}

export async function postFinanceChatMessage(message: string): Promise<{
  answer: string;
  thought_process: string[];
  tools_used: any[];
  referenced_exceptions: string[];
  referenced_transactions: string[];
}> {
  const res = await fetch(`${API_BASE}/api/finance/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error("Failed to communicate with Finance Q&A Agent");
  return res.json();
}
