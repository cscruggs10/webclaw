/**
 * Dealer-style home: column definitions and formatting for the Inventory,
 * Deals, Customers and Reports tabs. Pure functions so they can be tested.
 */

export type Row = Record<string, unknown>;

export interface DealerColumn {
  key: string;
  label: string;
  format?: "money" | "year" | "miles" | "status" | "date" | "text";
  align?: "left" | "right";
  /** Read the value from the first of these keys that is present. */
  keys?: string[];
}

export function isEmptyValue(v: unknown): boolean {
  return v === null || v === undefined || (typeof v === "string" && v.trim() === "");
}

export function cellValue(row: Row, col: DealerColumn): unknown {
  for (const k of col.keys ?? [col.key]) {
    if (!isEmptyValue(row[k])) return row[k];
  }
  return null;
}

/** Drop columns that are empty in every row. With no rows, keep them all. */
export function visibleColumns(rows: Row[], cols: DealerColumn[]): DealerColumn[] {
  if (rows.length === 0) return cols;
  return cols.filter((c) => rows.some((r) => !isEmptyValue(cellValue(r, c))));
}

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatMoney(v: unknown): string {
  if (isEmptyValue(v)) return "";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return money.format(n);
}

export function formatMiles(v: unknown): string {
  if (isEmptyValue(v)) return "";
  const n = Number(String(v).replace(/,/g, ""));
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("en-US");
}

/** Years are labels, not quantities: 2020, never 2,020. */
export function formatYear(v: unknown): string {
  if (isEmptyValue(v)) return "";
  return String(v).replace(/[,\s]/g, "");
}

export function formatStatus(v: unknown): string {
  if (isEmptyValue(v)) return "";
  const s = String(v).replace(/[_-]+/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatDate(v: unknown): string {
  if (isEmptyValue(v)) return "";
  const s = String(v);
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[2]}/${m[3]}/${m[1]}` : s;
}

export function formatCell(row: Row, col: DealerColumn): string {
  const v = cellValue(row, col);
  switch (col.format) {
    case "money": return formatMoney(v);
    case "year": return formatYear(v);
    case "miles": return formatMiles(v);
    case "status": return formatStatus(v);
    case "date": return formatDate(v);
    default: return isEmptyValue(v) ? "" : String(v);
  }
}

export const INVENTORY_COLUMNS: DealerColumn[] = [
  { key: "stock_number", label: "Stock #" },
  { key: "year", label: "Year", format: "year" },
  { key: "make", label: "Make" },
  { key: "model", label: "Model" },
  { key: "trim", label: "Trim" },
  { key: "color_exterior", label: "Color" },
  { key: "mileage", label: "Miles", format: "miles", align: "right" },
  // AutomotiveClaw has no cost column; the unit's cost basis is kept in invoice_price.
  { key: "invoice_price", label: "Cost", format: "money", align: "right" },
  { key: "vehicle_status", label: "Status", format: "status" },
];

export const DEAL_COLUMNS: DealerColumn[] = [
  { key: "naming_series", label: "Deal #" },
  { key: "deal_type", label: "Type", format: "status" },
  { key: "salesperson", label: "Salesperson" },
  { key: "selling_price", label: "Sale Price", format: "money", align: "right" },
  { key: "total_gross", label: "Gross", format: "money", align: "right" },
  { key: "deal_status", label: "Status", format: "status" },
  { key: "delivered_date", label: "Delivered", format: "date" },
];

export const CUSTOMER_COLUMNS: DealerColumn[] = [
  { key: "name", label: "Name" },
  { key: "customer_type", label: "Type", format: "status" },
  { key: "customer_group", label: "Group" },
  { key: "territory", label: "Territory" },
  { key: "credit_limit", label: "Credit Limit", format: "money", align: "right" },
  { key: "status", label: "Status", format: "status" },
];

/** First array-valued key in a list response ("rows", "customers", ...). */
export function rowsFrom(data: Row | undefined | null): Row[] {
  if (!data) return [];
  for (const [k, v] of Object.entries(data)) {
    if (Array.isArray(v) && k !== "tags" && k !== "requires") return v as Row[];
  }
  return [];
}

// ── Reports ────────────────────────────────────────────────────────────────

export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Profit & Loss defaults to January 1 of this year through today. */
export function defaultPlRange(today: Date = new Date()): { from: string; to: string } {
  return { from: `${today.getFullYear()}-01-01`, to: isoDate(today) };
}

export interface StatementLine { account: string; amount: string }
export interface StatementSection { title: string; lines: StatementLine[]; total: string }

function lines(v: unknown): StatementLine[] {
  if (!Array.isArray(v)) return [];
  return v.map((r) => ({
    account: String((r as Row).account ?? (r as Row).account_name ?? ""),
    amount: String((r as Row).amount ?? "0"),
  }));
}

export function balanceSheetSections(data: Row): {
  sections: StatementSection[];
  totalAssets: number;
  totalLiabilitiesAndEquity: number;
  balanced: boolean;
  netIncome: string;
} {
  const netIncome = String(data.net_income_ytd ?? "0");
  const equityLines = lines(data.equity);
  if (Number(netIncome) !== 0) {
    equityLines.push({ account: "Net income this year", amount: netIncome });
  }
  const totalEquity = Number(data.total_equity ?? 0) + Number(netIncome);
  const sections: StatementSection[] = [
    { title: "Assets", lines: lines(data.assets), total: String(data.total_assets ?? "0") },
    { title: "Liabilities", lines: lines(data.liabilities), total: String(data.total_liabilities ?? "0") },
    { title: "Equity", lines: equityLines, total: totalEquity.toFixed(2) },
  ];
  const totalAssets = Number(data.total_assets ?? 0);
  const totalLiabilitiesAndEquity = Number(data.total_liabilities ?? 0) + totalEquity;
  return {
    sections,
    totalAssets,
    totalLiabilitiesAndEquity,
    balanced: Math.abs(totalAssets - totalLiabilitiesAndEquity) < 0.005,
    netIncome,
  };
}

export function profitAndLossSections(data: Row): { sections: StatementSection[]; netIncome: string } {
  return {
    sections: [
      { title: "Income", lines: lines(data.income), total: String(data.income_total ?? "0") },
      { title: "Expenses", lines: lines(data.expenses), total: String(data.expense_total ?? "0") },
    ],
    netIncome: String(data.net_income ?? "0"),
  };
}

export interface TrialBalanceLine { account: string; number: string; debit: number; credit: number }

/** Accounts with a closing balance, plus debit and credit totals. */
export function trialBalanceLines(data: Row): {
  lines: TrialBalanceLine[]; totalDebit: number; totalCredit: number; balanced: boolean;
} {
  const accounts = Array.isArray(data.accounts) ? (data.accounts as Row[]) : [];
  const out: TrialBalanceLine[] = [];
  for (const a of accounts) {
    const debit = Number(a.closing_debit ?? 0);
    const credit = Number(a.closing_credit ?? 0);
    if (debit === 0 && credit === 0) continue;
    out.push({
      account: String(a.account_name ?? a.account ?? ""),
      number: String(a.account_number ?? ""),
      debit,
      credit,
    });
  }
  const totalDebit = out.reduce((s, l) => s + l.debit, 0);
  const totalCredit = out.reduce((s, l) => s + l.credit, 0);
  return { lines: out, totalDebit, totalCredit, balanced: Math.abs(totalDebit - totalCredit) < 0.005 };
}
