import { ListSkeleton } from "@/components/list-skeleton";
import { PageHeader } from "@/components/page-header";

export default function Loading() {
  return (
    <>
      <PageHeader title="Proyectos" description="Cargando expedientes." />
      <ListSkeleton />
    </>
  );
}
