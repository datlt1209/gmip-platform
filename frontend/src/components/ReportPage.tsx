"use client";
import { useEffect } from "react";
import { useAsync } from "@/lib/useAsync";
import { getLatestReport, getReportByDate } from "@/services/api";
import { ErrorState, Loading } from "./States";
import ReportView from "./ReportView";

export default function ReportPage({ date }: { date?: string }) {
  const { data, loading, error, reload } = useAsync(() => (date ? getReportByDate(date) : getLatestReport()), [date]);
  useEffect(() => {
    if (data && sessionStorage.getItem("gmip-print")) {
      sessionStorage.removeItem("gmip-print");
      setTimeout(() => window.print(), 300);
    }
  }, [data]);
  return (
    <main className="container">
      {loading && <Loading label="Đang tải báo cáo…" />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && <ReportView report={data} />}
    </main>
  );
}
