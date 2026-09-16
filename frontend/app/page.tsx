import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StackCheck } from "@/components/stack-check";

const surfaces = [
  { name: "Backend FastAPI", port: ":8000", path: "/health" },
  { name: "Frontend Next.js", port: ":3000", path: "/" },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col bg-[#dfe6ee] bg-[linear-gradient(to_right,rgb(26_35_50/0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgb(26_35_50/0.08)_1px,transparent_1px)] bg-[size:24px_24px]">
      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-8 px-4 py-12">
        <header className="border-l-4 border-[#c45c26] pl-4">
          <p className="font-mono text-sm text-[#1a2332]/70">Fase 0 · monorepo</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-[#1a2332]">
            Álgebra vectorial
          </h1>
          <p className="mt-2 max-w-md text-[#1a2332]/80">
            Estimaciones a partir de presupuestos. Este esqueleto confirma que
            FastAPI y Next.js levantan sin lógica de negocio.
          </p>
        </header>

        <Card className="bg-white/90">
          <CardHeader>
            <CardTitle>Superficies locales</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <Input
              readOnly
              defaultValue="uvicorn · npm run dev"
              aria-label="Comandos de desarrollo"
            />
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>App</TableHead>
                  <TableHead>Puerto</TableHead>
                  <TableHead>Ruta</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {surfaces.map((surface) => (
                  <TableRow key={surface.name}>
                    <TableCell className="font-medium">{surface.name}</TableCell>
                    <TableCell className="font-mono">{surface.port}</TableCell>
                    <TableCell className="font-mono">{surface.path}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <StackCheck />
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
