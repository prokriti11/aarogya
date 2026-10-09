import type { Metadata } from "next";
import { Bricolage_Grotesque, Public_Sans } from "next/font/google";
import Nav from "@/components/Nav";
import "./globals.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display", weight: ["500", "700"] });
const body = Public_Sans({ subsets: ["latin"], variable: "--font-body", weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "Aarogya: a health-insurance support bot, and the tests that keep it honest",
  description: "A RAG support bot over insurance policy documents, evaluated with rule checks, an LLM judge, and human review.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="min-h-screen">
        <Nav />
        <main className="mx-auto max-w-6xl px-5 pb-24 pt-8 sm:px-8">{children}</main>
      </body>
    </html>
  );
}
