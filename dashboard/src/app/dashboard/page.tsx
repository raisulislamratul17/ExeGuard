"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";

interface Guild {
  id: string;
  name: string;
  icon_url: string | null;
  bot_in: boolean;
  bot_api_error?: string;
  invite_url: string;
}

export default function Dashboard() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [guilds, setGuilds] = useState<Guild[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (status === "unauthenticated") router.push("/");
  }, [status, router]);

  useEffect(() => {
    if (status === "authenticated") {
      fetch("/api/guilds")
        .then((res) => {
          if (!res.ok) throw new Error("Failed to load your Discord servers");
          return res.json();
        })
        .then((data) => { setGuilds(data); setLoading(false); })
        .catch((err) => { setError(err.message); setLoading(false); });
    }
  }, [status]);

  if (status === "loading" || loading) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: "100vh" }}>
        <div className="flex items-center gap-sm">
          <div className="spinner" />
          <span style={{ color: "var(--body)" }}>Loading your console...</span>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <nav className="nav">
        <div className="flex items-center gap-sm">
          <Link href="/" className="flex items-center gap-sm" style={{ color: "var(--ink)" }}>
            <img src="/logo.jpg" alt="ExeGuard" style={{ width: "24px", height: "24px", borderRadius: "5px" }} />
            <span style={{ fontSize: "15px", fontWeight: 600, letterSpacing: "-0.3px" }}>ExeGuard</span>
          </Link>
        </div>

        <div className="flex items-center gap-sm">
          <div className="flex items-center gap-sm">
            {session?.user?.image && (
              <img src={session.user.image} alt="" style={{ width: "28px", height: "28px", borderRadius: "50%" }} />
            )}
            <span className="text-sm" style={{ fontWeight: 500 }}>{session?.user?.name}</span>
          </div>
          <button onClick={() => signOut()} className="btn btn-ghost btn-sm">Logout</button>
        </div>
      </nav>

      <div className="page-wrapper" style={{ flex: 1, paddingTop: "32px", paddingBottom: "48px" }}>
        <div className="flex items-center justify-between mb-lg">
          <div>
            <h2 style={{ marginBottom: "4px" }}>Select Server</h2>
            <p className="text-sm" style={{ color: "var(--body)" }}>Servers where you have Manage Server or Administrator permissions.</p>
          </div>
        </div>

        {error && (
          <div className="card mb-lg" style={{ borderLeft: "3px solid var(--error)", padding: "16px" }}>
            <strong style={{ color: "var(--error)" }}>Error:</strong> {error}
          </div>
        )}

        {guilds.length > 0 && guilds[0].bot_api_error && (
          <div className="card mb-lg" style={{ borderLeft: "3px solid var(--warning)", padding: "16px", background: "var(--warning-soft)" }}>
            <div className="flex items-center gap-sm mb-sm">
              <strong style={{ color: "var(--warning-deep)" }}>Bot Connection Issue</strong>
            </div>
            <p className="text-sm" style={{ color: "var(--body)" }}>
              The dashboard is having trouble reaching your Bot API. Servers may show as "Missing".
            </p>
            <code className="mono text-xs" style={{ display: "block", marginTop: "8px", padding: "8px", background: "rgba(0,0,0,0.04)", borderRadius: "4px", wordBreak: "break-all" }}>
              {guilds[0].bot_api_error}
            </code>
            <p className="text-xs mt-sm">
              Check your <strong>DISCORD_BOT_API_URL</strong> and <strong>DASHBOARD_API_KEY</strong> environment variables.
            </p>
          </div>
        )}

        {guilds.length === 0 ? (
          <div className="empty-state">
            <h3>No Servers Found</h3>
            <p>You must be an Owner, Administrator, or have the "Manage Server" permission to configure ExeGuard.</p>
          </div>
        ) : (
          <div className="grid-auto">
            {guilds.map((guild) => (
              <div key={guild.id} className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                <div className="flex items-center gap-md" style={{ marginBottom: "16px" }}>
                  {guild.icon_url ? (
                    <img src={guild.icon_url} alt="" style={{ width: "44px", height: "44px", borderRadius: "8px" }} />
                  ) : (
                    <div style={{ width: "44px", height: "44px", borderRadius: "8px", background: "var(--canvas-soft)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 600, fontSize: "18px" }}>
                      {guild.name.charAt(0)}
                    </div>
                  )}
                  <div style={{ overflow: "hidden" }}>
                    <div className="truncate" style={{ fontWeight: 500, marginBottom: "2px" }}>{guild.name}</div>
                    <span className={`badge ${guild.bot_in ? "badge-success" : "badge-danger"}`} style={{ fontSize: "11px" }}>
                      {guild.bot_in ? "Active" : "Missing"}
                    </span>
                  </div>
                </div>

                {guild.bot_in ? (
                  <Link href={`/dashboard/${guild.id}`} className="btn btn-primary btn-sm" style={{ width: "100%", justifyContent: "center" }}>
                    Manage Server
                  </Link>
                ) : (
                  <a href={guild.invite_url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm" style={{ width: "100%", justifyContent: "center" }}>
                    Setup ExeGuard
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <footer style={{ borderTop: "1px solid var(--hairline)", padding: "24px 0" }}>
        <div className="page-wrapper text-center">
          <p className="text-xs">ExeGuard Security Bot Panel</p>
        </div>
      </footer>
    </div>
  );
}
