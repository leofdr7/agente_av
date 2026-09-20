import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { RegisterServiceWorker } from "@/components/register-sw";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Estimaciones · TechChip",
  description:
    "Órdenes de estimación de álgebra vectorial para la planta TechChip Systems.",
  applicationName: "Estimaciones TechChip",
  appleWebApp: {
    capable: true,
    title: "Estimaciones",
    statusBarStyle: "default",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#1a2332",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <ClerkProvider>
      <html
        lang="es"
        className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}
      >
        <body className="flex min-h-full flex-col font-sans">
          {children}
          <Toaster />
          <RegisterServiceWorker />
        </body>
      </html>
    </ClerkProvider>
  );
}
