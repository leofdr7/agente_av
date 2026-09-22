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
          {/* #region agent log */}
          <script
            dangerouslySetInnerHTML={{
              __html: `(function(){var post=function(hypothesisId,message,data){fetch('http://127.0.0.1:7305/ingest/112c5700-fb95-409e-b8da-cac132656b93',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'fabb64'},body:JSON.stringify({sessionId:'fabb64',runId:'pre-fix',hypothesisId:hypothesisId,location:'app/layout.tsx:inline',message:message,data:data,timestamp:Date.now()})}).catch(function(){})};var shell=document.querySelector('div.min-h-dvh');var first=shell&&shell.firstElementChild;var controller=navigator.serviceWorker&&navigator.serviceWorker.controller;post('A','server-html-and-controller',{shellClass:shell?shell.className:null,firstTag:first?first.tagName:null,firstClass:first?first.className:null,hasSkip:!!(shell&&shell.querySelector('a[href="#main-content"]')),controller:controller?controller.scriptURL:null,controllerState:controller?controller.state:null});if(!('caches' in window)){post('E','no-cache-storage',{});return}caches.keys().then(function(keys){return Promise.all(keys.map(function(key){return caches.open(key).then(function(cache){return cache.keys().then(function(reqs){var next=reqs.filter(function(r){return r.url.indexOf('/_next/')!==-1}).map(function(r){return r.url});return{key:key,count:reqs.length,nextCount:next.length,nextSample:next.slice(0,4)}})})}))}).then(function(info){post('E','cache-storage',{caches:info})})}).catch(function(err){post('E','cache-error',{error:String(err)})})})();`,
            }}
          />
          {/* #endregion */}
          <Toaster />
          <RegisterServiceWorker />
        </body>
      </html>
    </ClerkProvider>
  );
}
