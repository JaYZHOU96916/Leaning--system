"use client";

import {
  CalendarDays,
  CircleHelp,
  Gauge,
  GraduationCap,
  LayoutGrid,
  Library,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { API_DOCS_URL } from "@/lib/api";

const navigation = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/library", label: "Library", icon: Library },
  { href: "/progress", label: "Progress", icon: Gauge },
];

const pageNames: Record<string, string> = {
  "/": "Semester overview",
  "/calendar": "Calendar",
  "/library": "Library",
  "/progress": "Progress",
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const pageName = pageNames[pathname] ?? "Academic OS";

  return (
    <main className="app-shell">
      <aside className="side-rail">
        <Link className="brand-mark" href="/" aria-label="Academic OS 首页">
          <GraduationCap size={22} />
        </Link>
        <nav className="rail-nav" aria-label="主导航">
          {navigation.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                className={`rail-button rail-link ${active ? "rail-button-active" : ""}`}
                href={href}
                key={href}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={19} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>
        <a className="rail-button rail-link rail-help" href={API_DOCS_URL} target="_blank" rel="noreferrer" title="API 文档">
          <CircleHelp size={19} />
          <span>Help</span>
        </a>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="mobile-brand"><GraduationCap size={20} /> Academic OS</div>
          <div className="crumb"><span>ACADEMIC OS</span><span className="crumb-separator">/</span><strong>{pageName}</strong></div>
          <div className="topbar-actions">
            <span className="sync-pill"><span className="sync-dot" /> Canvas workspace</span>
            <span className="avatar" aria-label="个人资料">JZ</span>
          </div>
        </header>
        <nav className="mobile-route-nav" aria-label="移动端主导航">
          {navigation.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return <Link className={active ? "mobile-route-active" : ""} href={href} key={href}><Icon size={16} /><span>{label}</span></Link>;
          })}
        </nav>
        {children}
      </section>
    </main>
  );
}
