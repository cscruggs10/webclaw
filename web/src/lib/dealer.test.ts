import { describe, it, expect } from "vitest";
import {
  INVENTORY_COLUMNS,
  visibleColumns,
  formatCell,
  formatYear,
  formatMoney,
  formatMiles,
  rowsFrom,
  defaultPlRange,
  balanceSheetSections,
  profitAndLossSections,
  trialBalanceLines,
} from "./dealer";

const forester = {
  id: "5f3f", naming_series: "AVEH-2026-00001", stock_number: "585388", vin: "JF2SKAXC4LH585388",
  year: 2020, make: "Subaru", model: "Forester", trim: "Touring", color_exterior: "Silver",
  color_interior: null, mileage: "113794", invoice_price: "11375.00", msrp: null,
  vehicle_status: "available",
};

describe("inventory columns", () => {
  it("labels cost as Cost and formats year, miles and money", () => {
    const labels = INVENTORY_COLUMNS.map((c) => c.label);
    expect(labels).toEqual(["Stock #", "Year", "Make", "Model", "Trim", "Color", "Miles", "Cost", "Status"]);
    expect(labels).not.toContain("Invoice Price");
    const byKey = Object.fromEntries(INVENTORY_COLUMNS.map((c) => [c.key, formatCell(forester, c)]));
    expect(byKey.year).toBe("2020");
    expect(byKey.mileage).toBe("113,794");
    expect(byKey.invoice_price).toBe("$11,375.00");
    expect(byKey.vehicle_status).toBe("Available");
  });

  it("hides columns that are empty for every row", () => {
    const noTrim = { ...forester, trim: "" };
    const cols = visibleColumns([noTrim], INVENTORY_COLUMNS).map((c) => c.key);
    expect(cols).not.toContain("trim");
    expect(cols).toContain("stock_number");
    expect(visibleColumns([], INVENTORY_COLUMNS)).toHaveLength(INVENTORY_COLUMNS.length);
  });

  it("formats edge values", () => {
    expect(formatYear("2,020")).toBe("2020");
    expect(formatMoney(null)).toBe("");
    expect(formatMiles("abc")).toBe("abc");
  });

  it("reads the first array in a list response", () => {
    expect(rowsFrom({ rows: [forester], total_count: 1 })).toHaveLength(1);
    expect(rowsFrom({ customers: [], tags: ["x"] })).toEqual([]);
    expect(rowsFrom(undefined)).toEqual([]);
  });
});

describe("reports", () => {
  it("defaults the P&L to Jan 1 through today", () => {
    expect(defaultPlRange(new Date(2026, 10, 14))).toEqual({ from: "2026-01-01", to: "2026-11-14" });
  });

  it("builds a balanced balance sheet", () => {
    const bs = balanceSheetSections({
      assets: [
        { account: "Operating Checking Account", amount: "-11375.00" },
        { account: "Vehicle Inventory", amount: "11375.00" },
      ],
      total_assets: "0.00", liabilities: [], total_liabilities: "0.00",
      equity: [], total_equity: "0.00", net_income_ytd: "0.00",
    });
    expect(bs.sections.map((s) => s.title)).toEqual(["Assets", "Liabilities", "Equity"]);
    expect(bs.sections[0].lines).toHaveLength(2);
    expect(bs.balanced).toBe(true);
  });

  it("adds year-to-date net income to equity", () => {
    const bs = balanceSheetSections({
      assets: [{ account: "Cash", amount: "500" }], total_assets: "500",
      liabilities: [], total_liabilities: "0", equity: [], total_equity: "0", net_income_ytd: "500",
    });
    expect(bs.sections[2].lines).toEqual([{ account: "Net income this year", amount: "500" }]);
    expect(bs.balanced).toBe(true);
  });

  it("reads P&L sections and net income", () => {
    const pl = profitAndLossSections({
      income: [{ account: "Sales Revenue", amount: "15000.00" }], income_total: "15000.00",
      expenses: [], expense_total: "0.00", net_income: "15000.00",
    });
    expect(pl.sections[0].lines[0].account).toBe("Sales Revenue");
    expect(pl.netIncome).toBe("15000.00");
  });

  it("keeps only trial balance accounts with a balance", () => {
    const tb = trialBalanceLines({
      accounts: [
        { account_name: "Operating Checking Account", account_number: "1112", closing_debit: "0.00", closing_credit: "11375.00" },
        { account_name: "Vehicle Inventory", account_number: "", closing_debit: "11375.00", closing_credit: "0.00" },
        { account_name: "Petty Cash", account_number: "1111", closing_debit: "0.00", closing_credit: "0.00" },
      ],
    });
    expect(tb.lines.map((l) => l.account)).toEqual(["Operating Checking Account", "Vehicle Inventory"]);
    expect(tb.totalDebit).toBe(11375);
    expect(tb.balanced).toBe(true);
  });
});
