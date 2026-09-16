"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function StackCheck() {
  return (
    <Dialog>
      <DialogTrigger render={<Button />}>Comprobar stack</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Esqueleto listo</DialogTitle>
          <DialogDescription>
            El frontend con shadcn/ui compiló. El backend responde en{" "}
            <code className="font-mono text-foreground">/health</code> cuando
            uvicorn está en marcha.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  );
}
