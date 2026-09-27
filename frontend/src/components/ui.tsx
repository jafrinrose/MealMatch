import { useEffect, useState, type ReactNode } from "react";
import type { Tab } from "../types";

const navItems: { id: Tab; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "pantry", label: "Pantry" },
  { id: "recipes", label: "Recipes" },
  { id: "chat", label: "Assistant" },
  { id: "settings", label: "Settings" },
];

export function CountdownText({ readyAt, large = false }: { readyAt: string; large?: boolean }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const remaining = Math.max(0, new Date(readyAt).getTime() - now);
  const totalSeconds = Math.floor(remaining / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const value = `${hours > 0 ? `${hours}:` : ""}${String(minutes).padStart(hours > 0 ? 2 : 1, "0")}:${String(seconds).padStart(2, "0")}`;
  return <span className={large ? "countdown-large" : ""}>{remaining > 0 ? value : "Ready now"}</span>;
}

export function DesktopSidebar({ activeTab, onNavigate }: { activeTab: Tab; onNavigate: (tab: Tab) => void }) {
  return <aside className="desktop-sidebar"><BrandMark onClick={() => onNavigate("home")} /><nav aria-label="Primary navigation">{navItems.map((item) => <button className={activeTab === item.id ? "active" : ""} aria-current={activeTab === item.id ? "page" : undefined} key={item.id} onClick={() => onNavigate(item.id)}><Icon name={item.id} /><span>{item.label}</span></button>)}</nav><div className="sidebar-tip"><Icon name="sparkles" /><strong>Waste less this week</strong><span>Use 2 expiring items in your next meal.</span></div></aside>;
}

export function MobileNav({ activeTab, onNavigate }: { activeTab: Tab; onNavigate: (tab: Tab) => void }) {
  return <nav className="mobile-nav" aria-label="Primary navigation">{navItems.map((item) => <button className={activeTab === item.id ? "active" : ""} aria-current={activeTab === item.id ? "page" : undefined} key={item.id} onClick={() => onNavigate(item.id)}><Icon name={item.id} /><span>{item.label === "Assistant" ? "Chat" : item.label}</span></button>)}</nav>;
}

export function PageHeader({ eyebrow, title, subtitle, action }: { eyebrow?: string; title: string; subtitle?: string; action?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p>{eyebrow}</p>}<h1>{title}</h1>{subtitle && <span>{subtitle}</span>}</div>{action}</header>;
}

export function BrandMark({ compact = false, onClick }: { compact?: boolean; onClick?: () => void }) {
  const content = <><span><Icon name="chef" /></span>{!compact && <strong>MealMatch</strong>}</>;
  return onClick ? <button className={`brand-mark ${compact ? "compact" : ""}`} onClick={onClick} aria-label="Go to MealMatch home">{content}</button> : <div className={`brand-mark ${compact ? "compact" : ""}`}>{content}</div>;
}

export function EmptyState({ icon, title, text, action, onAction }: { icon: IconName; title: string; text: string; action?: string; onAction?: () => void }) {
  return <div className="empty-state"><span><Icon name={icon} /></span><h3>{title}</h3><p>{text}</p>{action && onAction && <button className="primary-button" onClick={onAction}>{action}</button>}</div>;
}

type IconName = Tab | "plus" | "arrow" | "sparkles" | "alert" | "chef" | "clock" | "search" | "edit" | "trash" | "check" | "back" | "send" | "sun" | "moon" | "close" | "receipt" | "camera" | "upload" | "bookmark" | "microphone" | "swap" | "play";

export function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    home: <><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/></>,
    pantry: <><path d="M4 9h16l-1.5 11h-13z"/><path d="m8 9 2-5M16 9l-2-5M3 9h18"/><path d="M9 13v3M15 13v3"/></>,
    recipes: <><path d="M6 11a6 6 0 0 1 12 0"/><path d="M4 12h16v3H4zM7 15v5h10v-5"/><path d="M12 5V3"/></>,
    chat: <path d="M20 11a8 8 0 0 1-8 8H6l-4 3 1.5-5A8 8 0 1 1 20 11Z"/>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    plus: <path d="M12 5v14M5 12h14"/>, arrow: <path d="M5 12h14m-5-5 5 5-5 5"/>, sparkles: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2z"/><path d="m6 14 .8 2.2L9 17l-2.2.8L6 20l-.8-2.2L3 17l2.2-.8zM19 3v4M17 5h4"/></>,
    alert: <><path d="M10.3 4 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></>,
    chef: <><path d="M7 11a4 4 0 1 1 1-7 5 5 0 0 1 8 0 4 4 0 1 1 1 7"/><path d="M7 10v9h10v-9M7 15h10"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>, search: <><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></>,
    edit: <><path d="m4 16-1 5 5-1L19 9l-4-4z"/><path d="m13 7 4 4"/></>, trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6"/></>,
    check: <path d="m5 12 4 4L19 6"/>, back: <path d="m15 18-6-6 6-6M9 12h11"/>, send: <path d="m3 3 18 9-18 9 4-9zm4 9h14"/>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></>, moon: <path d="M20 15.5A8 8 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z"/>, close: <path d="m6 6 12 12M18 6 6 18"/>,
    receipt: <><path d="M6 3h12v18l-2-1-2 1-2-1-2 1-2-1-2 1z"/><path d="M9 8h6M9 12h6M9 16h3"/></>, camera: <><path d="M4 7h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13" r="4"/></>, upload: <><path d="M12 16V4m-5 5 5-5 5 5"/><path d="M4 15v5h16v-5"/></>, bookmark: <path d="M6 3h12v18l-6-4-6 4z"/>,
    microphone: <><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/></>,
    swap: <><path d="M7 7h11l-3-3M18 7l-3 3"/><path d="M17 17H6l3 3M6 17l3-3"/></>,
    play: <path d="M8 5.5v13l10.5-6.5z"/>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
