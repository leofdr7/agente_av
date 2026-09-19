import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { cn } from "cn";

export default function NotFound() {
  return (
    <>
      <PageHeader
        title="No está en el expediente"
        description="Ese proyecto o esa estimación no existe, o no te pertenece."
      />
      <Link href="/" className={cn(buttonVariants(), "h-9")}>
        Volver a proyectos
      </Link>
    </>
  );
}
