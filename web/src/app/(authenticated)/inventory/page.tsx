"use client";

import { useRouter } from "next/navigation";
import { DealerTable, PageHeader } from "@/components/dealer-table";
import { useEntityList } from "@/lib/hooks";
import { INVENTORY_COLUMNS, rowsFrom } from "@/lib/dealer";
import { getEntityDetailUrl } from "@/lib/entity-routing";

export default function InventoryPage() {
  const router = useRouter();
  const { data, isLoading, error } = useEntityList("automotiveclaw", "auto-list-vehicles", {
    limit: "200",
    offset: "0",
  });
  const rows = rowsFrom(data);
  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Inventory" count={data ? Number(data.total_count ?? rows.length) : undefined} />
      <DealerTable
        rows={rows}
        columns={INVENTORY_COLUMNS}
        loading={isLoading}
        error={error as Error | null}
        emptyText="No vehicles in inventory yet."
        onRowClick={(row) =>
          router.push(getEntityDetailUrl("automotiveclaw", "auto-list-vehicles", String(row.id)))
        }
      />
    </div>
  );
}
