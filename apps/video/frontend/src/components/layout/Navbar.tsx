"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useStore } from "@/store/useStore";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/discover", label: "Discover" },
  { href: "/discover?category=documentary", label: "Documentary" },
  { href: "/discover?category=romance", label: "Romance" },
  { href: "/discover?category=crime", label: "Crime" },
  { href: "/discover?category=horror", label: "Horror" },
  { href: "/discover?category=new_releases", label: "New" },
];

export function Navbar() {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, wallet, role, logout, fetchWallet } = useStore();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (isAuthenticated) fetchWallet();
  }, [isAuthenticated]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/discover?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery("");
    }
  };

  const creditBalance = wallet?.credit_balance ?? 0;
  const creditColor =
    !wallet ? "text-[#A0A8C0]"
    : creditBalance < 100 ? "text-[#E05252]"
    : creditBalance < 300 ? "text-[#F5C842]"
    : "text-[#3DCC7E]";

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? "bg-[#0A0C14]/95 backdrop-blur-md shadow-lg" : "bg-gradient-to-b from-black/80 to-transparent"
      }`}
    >
      <div className="max-w-[1440px] mx-auto px-4 md:px-8 h-16 flex items-center gap-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 flex-shrink-0">
          <span className="text-2xl font-black tracking-tight text-white">
            BAZZY<span className="text-[#4F8EF7]">VIDEO</span>
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden lg:flex items-center gap-1 ml-4">
          {NAV_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                pathname === l.href
                  ? "text-white bg-white/10"
                  : "text-[#A0A8C0] hover:text-white hover:bg-white/5"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Search */}
        <form onSubmit={handleSearch} className="hidden md:flex items-center">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search or describe a mood…"
              className="bg-white/8 border border-white/10 rounded-full px-4 py-1.5 text-sm text-white placeholder-[#5A607A]
                         w-56 focus:w-80 focus:outline-none focus:border-[#4F8EF7] transition-all duration-300"
            />
            <button type="submit" className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5A607A] hover:text-white">
              🔍
            </button>
          </div>
        </form>

        {/* Auth / credits */}
        {isAuthenticated ? (
          <div className="flex items-center gap-3">
            {/* Credit balance */}
            <Link href="/wallet" className={`hidden md:flex items-center gap-1.5 text-sm font-mono ${creditColor}`}>
              <span>◈</span>
              <span>{wallet ? creditBalance.toLocaleString() : "…"}</span>
            </Link>

            {/* Filmmaker / Admin links */}
            {(role === "filmmaker" || role === "admin") && (
              <Link
                href={role === "admin" ? "/admin" : "/filmmaker"}
                className="hidden md:block text-xs px-2.5 py-1 rounded border border-[#4F8EF7]/40 text-[#4F8EF7] hover:bg-[#4F8EF7]/10 transition-colors"
              >
                {role === "admin" ? "Admin" : "Dashboard"}
              </Link>
            )}

            {/* Add credits */}
            <Link
              href="/wallet"
              className="text-xs px-3 py-1.5 rounded-full bg-[#4F8EF7] text-white font-semibold hover:bg-[#6AA0FF] transition-colors"
            >
              + Credits
            </Link>

            {/* Logout */}
            <button
              onClick={logout}
              className="text-[#5A607A] hover:text-white text-sm transition-colors"
              title="Sign out"
            >
              ⎋
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Link href="/auth/login" className="text-sm text-[#A0A8C0] hover:text-white transition-colors px-3 py-1.5">
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="text-sm px-4 py-1.5 rounded-full bg-[#4F8EF7] text-white font-semibold hover:bg-[#6AA0FF] transition-colors"
            >
              Join
            </Link>
          </div>
        )}

        {/* Mobile menu toggle */}
        <button
          className="lg:hidden text-white p-1 ml-1"
          onClick={() => setMenuOpen(!menuOpen)}
        >
          {menuOpen ? "✕" : "☰"}
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="lg:hidden bg-[#0A0C14]/98 border-t border-white/5 px-4 pb-4">
          <form onSubmit={handleSearch} className="pt-4 pb-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search or describe a mood…"
              className="w-full bg-white/8 border border-white/10 rounded-lg px-4 py-2 text-sm text-white placeholder-[#5A607A] focus:outline-none focus:border-[#4F8EF7]"
            />
          </form>
          {NAV_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setMenuOpen(false)}
              className="block py-2.5 text-sm text-[#A0A8C0] hover:text-white border-b border-white/5"
            >
              {l.label}
            </Link>
          ))}
          {isAuthenticated && wallet && (
            <div className={`pt-3 text-sm font-mono ${creditColor}`}>
              ◈ {creditBalance.toLocaleString()} credits
            </div>
          )}
        </div>
      )}
    </header>
  );
}
