"use client";

import { useQuery } from "@tanstack/react-query";
import { ErrorBox, Loading } from "@/components/state";
import { Card } from "@/components/ui/card";
import { get, type DecisionRow } from "@/lib/api";
import { DecisionTable } from "./table";

export default function Decisions() {
  const q = useQuery({ queryKey: ["decisions", 500], queryFn: () => get<DecisionRow[]>("/decisions", { limit: "500" }) });
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Decisions</h1>
      <Card>{q.error ? <ErrorBox error={q.error} /> : q.data ? <DecisionTable rows={q.data} /> : <Loading />}</Card>
    </div>
  );
}
