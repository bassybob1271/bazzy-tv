import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Navbar } from "@/components/layout/Navbar";

export const viewport: Viewport = { themeColor: "#0A0C14" };

export const metadata: Metadata = {
  title: "Bazzy TV — Cinema for the Community",
  description:
    "Stream documentaries, romance, crime, horror, and new releases. $10 = 1,000 credits. 80% goes to filmmakers.",
  openGraph: {
    title: "Bazzy TV",
    description: "Cinema for the Community. Powered by co-op credits.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0A0C14] text-white antialiased">
        <Navbar />
        <main className="pt-16">{children}</main>
        <footer className="mt-20 border-t border-white/5 px-6 py-10 text-center text-xs text-[#5A607A]">
          <p className="mb-2">
            <span className="text-white font-semibold">BAZZY TV</span> — a co-op platform where 80% of every credit goes to the filmmaker.
          </p>
          <p>© {new Date().getFullYear()} Bazzy Live LLC. All rights reserved.</p>
          <div className="flex items-center justify-center gap-6 mt-4">
            <a href="/terms" className="hover:text-[#A0A8C0] transition-colors">Terms</a>
            <a href="/privacy" className="hover:text-[#A0A8C0] transition-colors">Privacy</a>
            <a href="/filmmaker" className="hover:text-[#4F8EF7] transition-colors">Filmmakers</a>
            <a href="/admin" className="hover:text-[#4F8EF7] transition-colors">Admin</a>
          </div>
        </footer>
      </body>
    </html>
  );
}
