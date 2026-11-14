"use client";

import { useRouter } from "next/navigation";
import { DealerTable, PageHeader } from "@/components/dealer-table";
import { useEntityList } from "@/lib/hooks";
import { DEAL_COLUMNS, rowsFrom } from "@/lib/dealer";
import { getEntityDetailUrl } from "@/lib/entity-routing";

export default function DealsPage() {
  const router = useRouter();
  const { data, isLoading, error } = useEntityList("automotiveclaw", "auto-list-deals", {
    limit: "200",
    offset: "0",
  });
  const rows = rowsFrom(data);
  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Deals" count={data ? Number(data.total_count ?? rows.length) : undefined} />
      <DealerTable
        rows={rows}
        columns={DEAL_COLUMNS}
        loading={isLoading}
        error={error as Error | null}
        emptyText="No deals yet. Sold units will show up here."
        onRowClick={(row) =>
          router.push(getEntityDetailUrl("automotiveclaw", "auto-list-deals", String(row.id)))
        }
      />
    </div>
  );
}
