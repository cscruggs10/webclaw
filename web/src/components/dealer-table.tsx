"use client";

import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { formatCell, visibleColumns, type DealerColumn, type Row } from "@/lib/dealer";

export function DealerTable({
  rows,
  columns,
  loading,
  error,
  emptyText,
  onRowClick,
}: {
  rows: Row[];
  columns: DealerColumn[];
  loading?: boolean;
  error?: Error | null;
  emptyText: string;
  onRowClick?: (row: Row) => void;
}) {
  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (error) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-destructive">
          Couldn&apos;t load this list: {error.message}
        </CardContent>
      </Card>
    );
  }
  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">{emptyText}</CardContent>
      </Card>
    );
  }
  const cols = visibleColumns(rows, columns);
  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              {cols.map((c) => (
                <TableHead key={c.key} className={c.align === "right" ? "text-right" : undefined}>
                  {c.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow
                key={String(row.id ?? i)}
                className={onRowClick ? "cursor-pointer" : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {cols.map((c) => (
                  <TableCell key={c.key} className={c.align === "right" ? "text-right tabular-nums" : undefined}>
                    {formatCell(row, c)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export function PageHeader({ title, count, children }: { title: string; count?: number; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">{title}</h1>
        {count != null && <span className="text-sm text-muted-foreground">{count} total</span>}
      </div>
      {children}
    </div>
  );
}
