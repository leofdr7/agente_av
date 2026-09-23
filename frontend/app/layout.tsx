import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Fragment_Mono, Instrument_Sans } from "next/font/google";

import { RegisterServiceWorker } from "@/components/register-sw";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

const instrumentSans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const fragmentMono = Fragment_Mono({
  variable: "--font-fragment-mono",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: "Estimaciones | AgentA",
  description:
    "Órdenes de estimación de álgebra vectorial para AgentA.",
  applicationName: "AgentA",
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
  themeColor: "#234db5",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <ClerkProvider>
      <html
        lang="es"
        className={`${instrumentSans.variable} ${fragmentMono.variable} h-full antialiased`}
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
