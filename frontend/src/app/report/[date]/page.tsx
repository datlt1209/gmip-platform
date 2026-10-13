"use client";
import { use } from "react";
import ReportPage from "@/components/ReportPage";

export default function ReportByDate({ params }: { params: Promise<{ date: string }> }) {
  const { date } = use(params);
  return <ReportPage date={date} />;
}
