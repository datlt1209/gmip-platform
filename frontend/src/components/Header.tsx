"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/report", label: "Báo cáo hôm nay" },
  { href: "/archive", label: "Kho lưu trữ" },
];

export default function Header() {
  const path = usePathname();
  const active = (h: string) => (h === "/" ? path === "/" || path.startsWith("/indicators") : path.startsWith(h));
  return (
    <header className="header no-print">
      <div className="container header-in">
        <Link href="/" className="brand">GMIP <span>Global Macro Intelligence</span></Link>
        <nav>
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={active(n.href) ? "nav active" : "nav"}>{n.label}</Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
