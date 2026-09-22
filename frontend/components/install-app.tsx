"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "cn";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

function isStandaloneDisplay(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.matchMedia("(display-mode: fullscreen)").matches ||
    Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
  );
}

function isIosDevice(): boolean {
  const ua = window.navigator.userAgent;
  const classic = /iphone|ipad|ipod/i.test(ua);
  const iPadOs = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
  return classic || iPadOs;
}

function subscribeDisplayMode(onChange: () => void) {
  const queries = ["(display-mode: standalone)", "(display-mode: fullscreen)"]
    .map((query) => window.matchMedia(query));
  queries.forEach((query) => query.addEventListener("change", onChange));
  window.addEventListener("appinstalled", onChange);
  return () => {
    queries.forEach((query) => query.removeEventListener("change", onChange));
    window.removeEventListener("appinstalled", onChange);
  };
}

const subscribeDevice = () => () => {};
const serverStandalone = () => true;
const serverIos = () => false;

export function InstallAppButton({ className }: { className?: string }) {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const standalone = useSyncExternalStore(subscribeDisplayMode, isStandaloneDisplay, serverStandalone);
  const ios = useSyncExternalStore(subscribeDevice, isIosDevice, serverIos);
  const [hintOpen, setHintOpen] = useState(false);

  useEffect(() => {
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  if (standalone) return null;

  const install = async () => {
    if (!deferred) return;
    await deferred.prompt();
    const choice = await deferred.userChoice;
    if (choice.outcome === "accepted") {
      setDeferred(null);
    }
  };

  if (deferred) {
    return (
      <Button
        type="button"
        variant="outline"
        size="xs"
        className={cn("h-7 border-ink/15 bg-sheet text-[11px] text-ink", className)}
        onClick={() => void install()}
      >
        Instalar app
      </Button>
    );
  }

  if (!ios) return null;

  return (
    <div className={cn("relative", className)}>
      <Button
        type="button"
        variant="outline"
        size="xs"
        className="h-7 border-ink/15 bg-sheet text-[11px] text-ink"
        aria-expanded={hintOpen}
        onClick={() => setHintOpen((open) => !open)}
      >
        Instalar app
      </Button>
      {hintOpen ? (
        <p
          role="status"
          className="absolute right-0 top-[calc(100%+0.5rem)] z-40 w-56 border-l-[3px] border-copper bg-sheet px-3 py-2 text-xs text-ink shadow-sm"
        >
          En Safari: toca Compartir y luego Añadir a pantalla de inicio.
        </p>
      ) : null}
    </div>
  );
}
