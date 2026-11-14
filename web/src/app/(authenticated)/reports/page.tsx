"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/dealer-table";
import { useEntityList } from "@/lib/hooks";
import {
  balanceSheetSections,
  defaultPlRange,
  formatMoney,
  isoDate,
  profitAndLossSections,
  rowsFrom,
  trialBalanceLines,
  type Row,
  type StatementSection,
} from "@/lib/dealer";

const REPORTS = [
  { key: "balance-sheet", label: "Balance Sheet" },
  { key: "profit-and-loss", label: "Profit & Loss" },
  { key: "trial-balance", label: "Trial Balance" },
] as const;
type ReportKey = (typeof REPORTS)[number]["key"];

function useCompanyId(): string | undefined {
  const { data } = useEntityList("erpclaw", "list-companies", { limit: "5" });
  const first = rowsFrom(data)[0];
  return first ? String(first.id) : undefined;
}

function Status({ ok, text }: { ok: boolean; text: string }) {
  return (
    <div className={`flex items-center gap-2 text-sm ${ok ? "text-emerald-600" : "text-amber-600"}`}>
      {ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
      {text}
    </div>
  );
}

function Loading() {
  return (
    <div className="flex h-48 items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

function Failure({ error }: { error: unknown }) {
  return (
    <Card>
      <CardContent className="py-8 text-center text-sm text-destructive">
        Couldn&apos;t run this report: {(error as Error)?.message || "unknown error"}
      </CardContent>
    </Card>
  );
}

function SectionTable({ section }: { section: StatementSection }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{section.title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableBody>
            {section.lines.length === 0 ? (
              <TableRow>
                <TableCell className="text-muted-foreground">No activity</TableCell>
                <TableCell />
              </TableRow>
            ) : (
              section.lines.map((l, i) => (
                <TableRow key={`${l.account}-${i}`}>
                  <TableCell>{l.account}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatMoney(l.amount)}</TableCell>
                </TableRow>
              ))
            )}
            <TableRow className="font-semibold">
              <TableCell>Total {section.title.toLowerCase()}</TableCell>
              <TableCell className="text-right tabular-nums">{formatMoney(section.total)}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function BalanceSheet({ companyId }: { companyId?: string }) {
  const [asOf, setAsOf] = useState(isoDate(new Date()));
  const { data, isLoading, error } = useEntityList(
    "erpclaw", "balance-sheet", { company_id: companyId ?? "", as_of_date: asOf },
    { enabled: !!companyId },
  );
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="as-of">As of</Label>
          <Input id="as-of" type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} className="w-44" />
        </div>
      </div>
      {isLoading || !companyId ? <Loading /> : error ? <Failure error={error} /> : data ? (() => {
        const bs = balanceSheetSections(data as Row);
        return (
          <>
            <Status
              ok={bs.balanced}
              text={bs.balanced
                ? `Balanced: assets ${formatMoney(bs.totalAssets)} = liabilities + equity ${formatMoney(bs.totalLiabilitiesAndEquity)}`
                : `Out of balance: assets ${formatMoney(bs.totalAssets)} vs liabilities + equity ${formatMoney(bs.totalLiabilitiesAndEquity)}`}
            />
            <div className="grid gap-4 lg:grid-cols-3">
              {bs.sections.map((s) => <SectionTable key={s.title} section={s} />)}
            </div>
          </>
        );
      })() : null}
    </div>
  );
}

function ProfitAndLoss({ companyId }: { companyId?: string }) {
  const initial = defaultPlRange();
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const { data, isLoading, error } = useEntityList(
    "erpclaw", "profit-and-loss", { company_id: companyId ?? "", from_date: from, to_date: to },
    { enabled: !!companyId && !!from && !!to },
  );
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="pl-from">From</Label>
          <Input id="pl-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-44" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="pl-to">To</Label>
          <Input id="pl-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-44" />
        </div>
      </div>
      {isLoading || !companyId ? <Loading /> : error ? <Failure error={error} /> : data ? (() => {
        const pl = profitAndLossSections(data as Row);
        return (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              {pl.sections.map((s) => <SectionTable key={s.title} section={s} />)}
            </div>
            <Card>
              <CardContent className="flex items-center justify-between py-4 text-base font-semibold">
                <span>Net income</span>
                <span className="tabular-nums">{formatMoney(pl.netIncome)}</span>
              </CardContent>
            </Card>
          </>
        );
      })() : null}
    </div>
  );
}

function TrialBalance({ companyId }: { companyId?: string }) {
  const [asOf, setAsOf] = useState(isoDate(new Date()));
  const { data, isLoading, error } = useEntityList(
    "erpclaw", "trial-balance",
    { company_id: companyId ?? "", from_date: `${asOf.slice(0, 4)}-01-01`, to_date: asOf },
    { enabled: !!companyId && !!asOf },
  );
  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <Label htmlFor="tb-to">As of</Label>
        <Input id="tb-to" type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} className="w-44" />
      </div>
      {isLoading || !companyId ? <Loading /> : error ? <Failure error={error} /> : data ? (() => {
        const tb = trialBalanceLines(data as Row);
        return (
          <>
            <Status ok={tb.balanced} text={tb.balanced ? "Debits equal credits" : "Debits and credits do not match"} />
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Account</TableHead>
                      <TableHead className="text-right">Debit</TableHead>
                      <TableHead className="text-right">Credit</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tb.lines.length === 0 ? (
                      <TableRow><TableCell colSpan={3} className="text-muted-foreground">No balances yet</TableCell></TableRow>
                    ) : tb.lines.map((l) => (
                      <TableRow key={`${l.number}-${l.account}`}>
                        <TableCell>{l.number ? `${l.number} · ` : ""}{l.account}</TableCell>
                        <TableCell className="text-right tabular-nums">{l.debit ? formatMoney(l.debit) : ""}</TableCell>
                        <TableCell className="text-right tabular-nums">{l.credit ? formatMoney(l.credit) : ""}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow className="font-semibold">
                      <TableCell>Total</TableCell>
                      <TableCell className="text-right tabular-nums">{formatMoney(tb.totalDebit)}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatMoney(tb.totalCredit)}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </>
        );
      })() : null}
    </div>
  );
}

function ReportsInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requested = searchParams.get("report");
  const active: ReportKey = (REPORTS.find((r) => r.key === requested)?.key ?? "balance-sheet");
  const companyId = useCompanyId();
  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Reports" />
      <div className="flex gap-2 border-b">
        {REPORTS.map((r) => (
          <button
            key={r.key}
            onClick={() => router.replace(`/reports?report=${r.key}`)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              active === r.key ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>
      {active === "balance-sheet" && <BalanceSheet companyId={companyId} />}
      {active === "profit-and-loss" && <ProfitAndLoss companyId={companyId} />}
      {active === "trial-balance" && <TrialBalance companyId={companyId} />}
    </div>
  );
}

export default function ReportsPage() {
  return (
    <Suspense fallback={<Loading />}>
      <ReportsInner />
    </Suspense>
  );
}
