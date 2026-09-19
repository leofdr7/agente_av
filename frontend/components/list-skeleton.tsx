import { Skeleton } from "@/components/ui/skeleton";

export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="divide-y divide-ink/10 bg-sheet ring-1 ring-ink/10">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="space-y-2 px-4 py-3.5">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      ))}
    </div>
  );
}
