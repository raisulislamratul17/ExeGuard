"use client";

import { signIn, useSession } from "next-auth/react";
import Link from "next/link";
import React, { useEffect, useState } from "react";

export default function Home() {
  const { data: session, status } = useSession();
  const [stats, setStats] = useState({
    servers: "54",
    users: "38.2k",
    actions: "1,842",
    latency: "4.2ms"
  });

  // Try to load real global stats from bot backend proxy if session exists
  useEffect(() => {
    if (status === "authenticated") {
      fetch("/api/bot/stats")
        .then((res) => res.json())
        .then((data) => {
          if (data && !data.error) {
            setStats({
              servers: String(data.guilds_count),
              users: `${(data.members_count / 1000).toFixed(1)}k`,
              actions: "Dynamic Logs Active",
              latency: `${data.latency_ms}ms`
            });
          }
        })
        .catch((err) => console.log("Failed to fetch live stats:", err));
    }
  }, [status]);

  return (
    <main className="cyber-container" style={{ minHeight: "100vh", display: "flex", flexDirection: "column", justifyContent: "center", position: "relative" }}>
      {/* Top Header */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1.5rem 0", borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: "hsl(var(--primary))", filter: "drop-shadow(0 0 8px hsla(var(--primary), 0.6))" }}>
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span style={{ fontSize: "1.5rem", fontWeight: "800", letterSpacing: "0.05em", background: "linear-gradient(90deg, #fff, hsl(var(--secondary)))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            EXEGUARD
          </span>
        </div>
        <div>
          {status === "authenticated" ? (
            <Link href="/dashboard" className="cyber-btn" style={{ textShadow: "none" }}>
              Console Dashboard
            </Link>
          ) : (
            <button onClick={() => signIn("discord")} className="cyber-btn-secondary">
              Login to Control Panel
            </button>
          )}
        </div>
      </header>

      {/* Hero Section */}
      <section style={{ textAlign: "center", padding: "5rem 0 3rem 0", zIndex: 10 }}>
        <div className="cyber-badge cyber-badge-info" style={{ marginBottom: "1.5rem" }}>
          <span className="pulse" style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "hsl(var(--secondary))", display: "inline-block", marginRight: "0.25rem" }}></span>
          V1.0.0 Cybernetic System Active
        </div>
        <h1 style={{ fontSize: "3.5rem", fontWeight: "900", marginBottom: "1.5rem", lineHeight: "1.1", letterSpacing: "-0.03em" }}>
          Next-Gen Security for <br />
          <span style={{ background: "linear-gradient(90deg, hsl(var(--primary)), hsl(var(--secondary)))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", textShadow: "0 0 30px hsla(var(--primary), 0.2)" }}>
            Discord Communities
          </span>
        </h1>
        <p style={{ maxWidth: "600px", margin: "0 auto 2.5rem auto", fontSize: "1.15rem", color: "hsl(var(--text-secondary))" }}>
          ExeGuard is an autonomous defense bot protecting your servers from raids, nukes, token spams, and unauthorized external applications with millisecond precision.
        </p>

        <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap" }}>
          {status === "authenticated" ? (
            <Link href="/dashboard" className="cyber-btn" style={{ fontSize: "1.1rem", padding: "0.9rem 2.2rem" }}>
              Access Dashboard Console
            </Link>
          ) : (
            <button onClick={() => signIn("discord")} className="cyber-btn" style={{ fontSize: "1.1rem", padding: "0.9rem 2.2rem" }}>
              <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24" style={{ marginRight: "0.5rem" }}>
                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 2.855a.07.07 0 0 0-.076.03A20.036 20.036 0 0 0 .743 19.683a.07.07 0 0 0 .03.052 19.905 19.905 0 0 0 6.01 3.032.077.077 0 0 0 .084-.027c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.094 13.094 0 0 1-1.873-.894.077.077 0 0 1-.008-.128c.126-.093.252-.19.372-.287a.075.075 0 0 1 .077-.011c3.92 1.793 8.18 1.793 12.061 0a.073.073 0 0 1 .078.009c.12.099.246.195.373.289a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.01-3.03.077.077 0 0 0 .032-.054c3.001-5.89 2.13-11.45.738-16.79a.071.071 0 0 0-.075-.03Z" />
              </svg>
              Login via Discord
            </button>
          )}
          <a href={`https://discord.com/api/oauth2/authorize?client_id=${process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID || "123"}&permissions=8&scope=bot%20applications.commands`} target="_blank" rel="noopener noreferrer" className="cyber-btn-secondary" style={{ fontSize: "1.1rem", padding: "0.9rem 2.2rem" }}>
            Add Bot to Server
          </a>
        </div>
      </section>

      {/* Stats Counter Section */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1.5rem", margin: "3rem 0" }}>
        <div className="cyber-card" style={{ textAlign: "center" }}>
          <h3 style={{ fontSize: "2rem", color: "hsl(var(--primary))", marginBottom: "0.25rem", textShadow: "0 0 10px hsla(var(--primary), 0.4)" }}>
            {stats.servers}
          </h3>
          <p style={{ fontSize: "0.9rem", color: "hsl(var(--text-secondary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>Servers Secured</p>
        </div>
        <div className="cyber-card" style={{ textAlign: "center" }}>
          <h3 style={{ fontSize: "2rem", color: "hsl(var(--secondary))", marginBottom: "0.25rem", textShadow: "0 0 10px hsla(var(--secondary), 0.4)" }}>
            {stats.users}
          </h3>
          <p style={{ fontSize: "0.9rem", color: "hsl(var(--text-secondary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>Users Protected</p>
        </div>
        <div className="cyber-card" style={{ textAlign: "center" }}>
          <h3 style={{ fontSize: "2rem", color: "hsl(var(--success))", marginBottom: "0.25rem", textShadow: "0 0 10px hsla(var(--success), 0.4)" }}>
            {stats.latency}
          </h3>
          <p style={{ fontSize: "0.9rem", color: "hsl(var(--text-secondary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>API Uptime Latency</p>
        </div>
        <div className="cyber-card" style={{ textAlign: "center" }}>
          <h3 style={{ fontSize: "2rem", color: "hsl(var(--warning))", marginBottom: "0.25rem", textShadow: "0 0 10px hsla(var(--warning), 0.4)" }}>
            100%
          </h3>
          <p style={{ fontSize: "0.9rem", color: "hsl(var(--text-secondary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>Raid Defeated Rate</p>
        </div>
      </section>

      {/* Modular Feature Cards */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "2rem", padding: "2rem 0 5rem 0" }}>
        
        {/* Anti-Nuke */}
        <div className="cyber-card">
          <div style={{ display: "inline-flex", padding: "0.75rem", borderRadius: "8px", background: "rgba(108, 92, 231, 0.1)", color: "hsl(var(--primary))", marginBottom: "1.25rem" }}>
            <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3 style={{ marginBottom: "0.5rem" }}>Anti-Nuke Protection</h3>
          <p style={{ fontSize: "0.95rem" }}>
            Real-time audit log scanner that detects and terminates mass role/channel deletions or webhook additions by rogue administrators. Rogue admins are instantly stripped of roles and banned.
          </p>
        </div>

        {/* Anti-Raid */}
        <div className="cyber-card">
          <div style={{ display: "inline-flex", padding: "0.75rem", borderRadius: "8px", background: "rgba(0, 212, 255, 0.1)", color: "hsl(var(--secondary))", marginBottom: "1.25rem" }}>
            <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <h3 style={{ marginBottom: "0.5rem" }}>Anti-Raid & Lockdowns</h3>
          <p style={{ fontSize: "0.95rem" }}>
            Monitors rapidly spike in joins. In the event of a bot wave, ExeGuard automatically locks down text/voice channels, sets slowmode delays, and kicks suspicious young accounts.
          </p>
        </div>

        {/* Custom Gateways */}
        <div className="cyber-card">
          <div style={{ display: "inline-flex", padding: "0.75rem", borderRadius: "8px", background: "rgba(46, 204, 113, 0.1)", color: "hsl(var(--success))", marginBottom: "1.25rem" }}>
            <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h3 style={{ marginBottom: "0.5rem" }}>Secure Verification Gateways</h3>
          <p style={{ fontSize: "0.95rem" }}>
            Gate incoming members via highly interactive, automated CAPTCHA panels or button-click validation templates before granting full access to channel networks.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ textAlign: "center", padding: "2.5rem 0", borderTop: "1px solid rgba(255, 255, 255, 0.05)", fontSize: "0.9rem", color: "hsl(var(--text-muted))" }}>
        ExeGuard Security Bot © {new Date().getFullYear()} — Made with 💜 for advanced Discord operations.
      </footer>
    </main>
  );
}
