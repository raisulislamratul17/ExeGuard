"use client";

import { signIn, useSession } from "next-auth/react";
import Link from "next/link";
import React, { useEffect, useState } from "react";

export default function Home() {
  const { data: session, status } = useSession();
  const [stats, setStats] = useState({
    servers: "54",
    users: "38.2k",
    latency: "4.2ms"
  });

  useEffect(() => {
    if (status === "authenticated") {
      fetch("/api/bot/stats")
        .then((res) => res.json())
        .then((data) => {
          if (data && !data.error) {
            setStats({
              servers: String(data.guilds_count),
              users: `${(data.members_count / 1000).toFixed(1)}k`,
              latency: `${data.latency_ms}ms`
            });
          }
        })
        .catch(() => {});
    }
  }, [status]);

  return (
    <div style={{ minHeight: "100vh", position: "relative" }}>
      <div className="mesh-gradient" />

      <nav className="nav" style={{ background: "var(--canvas)", position: "relative", zIndex: 20 }}>
        <div className="flex items-center gap-sm">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span style={{ fontSize: "18px", fontWeight: 600, letterSpacing: "-0.5px" }}>ExeGuard</span>
        </div>

        <div className="flex items-center gap-sm">
          {status === "authenticated" ? (
            <Link href="/dashboard" className="btn btn-primary btn-sm">
              Console Dashboard
            </Link>
          ) : (
            <button onClick={() => signIn("discord")} className="btn btn-primary btn-sm">
              Sign In
            </button>
          )}
        </div>
      </nav>

      <div className="page-wrapper" style={{ paddingTop: "64px" }}>
        <section className="text-center" style={{ padding: "80px 0 48px" }}>
          <div className="badge badge-secondary mb-md" style={{ margin: "0 auto", width: "fit-content" }}>
            <span className="mono">v1.0.0</span> — Autonomous Discord Security
          </div>

          <h1 style={{ fontSize: "48px", lineHeight: "48px", letterSpacing: "-2.4px", marginBottom: "16px", maxWidth: "700px", margin: "0 auto 16px" }}>
            Secure your Discord server with millisecond precision.
          </h1>

          <p style={{ fontSize: "18px", lineHeight: "28px", maxWidth: "520px", margin: "0 auto 32px", color: "var(--body)" }}>
            ExeGuard is an autonomous defense bot protecting your servers from raids, nukes, token spams, and unauthorized external applications.
          </p>

          <div className="flex items-center justify-center gap-md" style={{ flexWrap: "wrap" }}>
            {status === "authenticated" ? (
              <Link href="/dashboard" className="btn btn-primary btn-lg">
                Access Dashboard Console
              </Link>
            ) : (
              <button onClick={() => signIn("discord")} className="btn btn-primary btn-lg">
                <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 2.855a.07.07 0 0 0-.076.03A20.036 20.036 0 0 0 .743 19.683a.07.07 0 0 0 .03.052 19.905 19.905 0 0 0 6.01 3.032.077.077 0 0 0 .084-.027c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.094 13.094 0 0 1-1.873-.894.077.077 0 0 1-.008-.128c.126-.093.252-.19.372-.287a.075.075 0 0 1 .077-.011c3.92 1.793 8.18 1.793 12.061 0a.073.073 0 0 1 .078.009c.12.099.246.195.373.289a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.01-3.03.077.077 0 0 0 .032-.054c3.001-5.89 2.13-11.45.738-16.79a.071.071 0 0 0-.075-.03Z" />
                </svg>
                Login via Discord
              </button>
            )}
            <a
              href={`https://discord.com/api/oauth2/authorize?client_id=${process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID || "123"}&permissions=8&scope=bot%20applications.commands`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary btn-lg"
            >
              Add Bot to Server
            </a>
          </div>
        </section>

        <section className="grid-3" style={{ marginBottom: "48px" }}>
          <div className="card">
            <div className="badge badge-secondary mb-sm mono">SERVERS</div>
            <div style={{ fontSize: "32px", fontWeight: 600, letterSpacing: "-1.28px", color: "var(--ink)" }}>{stats.servers}</div>
            <p className="text-sm mt-sm">Servers Secured</p>
          </div>
          <div className="card">
            <div className="badge badge-secondary mb-sm mono">USERS</div>
            <div style={{ fontSize: "32px", fontWeight: 600, letterSpacing: "-1.28px", color: "var(--ink)" }}>{stats.users}</div>
            <p className="text-sm mt-sm">Users Protected</p>
          </div>
          <div className="card">
            <div className="badge badge-secondary mb-sm mono">LATENCY</div>
            <div style={{ fontSize: "32px", fontWeight: 600, letterSpacing: "-1.28px", color: "var(--ink)" }}>{stats.latency}</div>
            <p className="text-sm mt-sm">API Response Time</p>
          </div>
        </section>

        <section className="grid-3" style={{ marginBottom: "80px" }}>
          <div className="card">
            <div style={{ width: "40px", height: "40px", borderRadius: "8px", background: "var(--canvas-soft)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "16px", fontSize: "20px" }}>
              <svg width="20" height="20" fill="none" stroke="var(--ink)" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 style={{ marginBottom: "8px", fontSize: "18px" }}>Anti-Nuke Protection</h3>
            <p className="text-sm">Real-time audit log scanner that detects and terminates mass role/channel deletions or webhook additions by rogue administrators.</p>
          </div>

          <div className="card">
            <div style={{ width: "40px", height: "40px", borderRadius: "8px", background: "var(--canvas-soft)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "16px" }}>
              <svg width="20" height="20" fill="none" stroke="var(--ink)" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <h3 style={{ marginBottom: "8px", fontSize: "18px" }}>Anti-Raid & Lockdowns</h3>
            <p className="text-sm">Monitors rapidly spike in joins. In the event of a bot wave, ExeGuard automatically locks down text/voice channels and kicks suspicious young accounts.</p>
          </div>

          <div className="card">
            <div style={{ width: "40px", height: "40px", borderRadius: "8px", background: "var(--canvas-soft)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "16px" }}>
              <svg width="20" height="20" fill="none" stroke="var(--ink)" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <h3 style={{ marginBottom: "8px", fontSize: "18px" }}>Secure Verification Gateways</h3>
            <p className="text-sm">Gate incoming members via CAPTCHA panels or button-click validation templates before granting full access to channel networks.</p>
          </div>
        </section>
      </div>

      <footer style={{ borderTop: "1px solid var(--hairline)", padding: "40px 0", marginTop: "0" }}>
        <div className="page-wrapper">
          <p className="text-xs text-center">
            ExeGuard Security Bot &copy; {new Date().getFullYear()} &mdash; Built for Discord communities that demand security.
          </p>
        </div>
      </footer>
    </div>
  );
}
