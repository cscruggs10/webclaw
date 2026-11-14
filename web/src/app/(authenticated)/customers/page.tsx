"use client";

import { useRouter } from "next/navigation";
import { DealerTable, PageHeader } from "@/components/dealer-table";
import { useEntityList } from "@/lib/hooks";
import { CUSTOMER_COLUMNS, rowsFrom } from "@/lib/dealer";
import { getEntityDetailUrl } from "@/lib/entity-routing";

export default function CustomersPage() {
  const router = useRouter();
  // ERPClaw's customer master holds every buyer; AutomotiveClaw only extends some of them.
  const { data, isLoading, error } = useEntityList("erpclaw", "list-customers", {
    limit: "200",
    offset: "0",
  });
  const rows = rowsFrom(data);
  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Customers" count={data ? Number(data.total_count ?? rows.length) : undefined} />
      <DealerTable
        rows={rows}
        columns={CUSTOMER_COLUMNS}
        loading={isLoading}
        error={error as Error | null}
        emptyText="No customers yet."
        onRowClick={(row) => router.push(getEntityDetailUrl("erpclaw", "customers", String(row.id)))}
      />
    </div>
  );
}
