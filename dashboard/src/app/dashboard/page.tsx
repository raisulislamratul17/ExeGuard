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
    if (status === "unauthenticated") {
      router.push("/");
    }
  }, [status, router]);

  useEffect(() => {
    if (status === "authenticated") {
      fetch("/api/guilds")
        .then((res) => {
          if (!res.ok) throw new Error("Failed to load your Discord servers");
          return res.json();
        })
        .then((data) => {
          setGuilds(data);
          setLoading(false);
        })
        .catch((err) => {
          setError(err.message);
          setLoading(false);
        });
    }
  }, [status]);

  if (status === "loading" || loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
        <div style={{ border: "4px solid rgba(255, 255, 255, 0.05)", borderTop: "4px solid hsl(var(--primary))", borderRadius: "50%", width: "40px", height: "40px", animation: "spin-slow 1s linear infinite" }}></div>
        <p style={{ marginTop: "1rem", color: "hsl(var(--text-secondary))" }}>Loading your Control Console...</p>
      </div>
    );
  }

  return (
    <main className="cyber-container" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Dashboard Nav Bar */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1.5rem 0", borderBottom: "1px solid rgba(255, 255, 255, 0.05)", marginBottom: "3rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ color: "hsl(var(--primary))", filter: "drop-shadow(0 0 5px hsla(var(--primary), 0.5))" }}>
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span style={{ fontSize: "1.25rem", fontWeight: "800", letterSpacing: "0.05em", color: "#fff" }}>
            EXEGUARD CONSOLE
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            {session?.user?.image && (
              <img src={session.user.image} alt="User Avatar" style={{ width: "32px", height: "32px", borderRadius: "50%", border: "1px solid hsl(var(--secondary))" }} />
            )}
            <span style={{ fontSize: "0.95rem", fontWeight: "600" }}>{session?.user?.name}</span>
          </div>
          <button onClick={() => signOut()} className="cyber-btn-secondary" style={{ padding: "0.5rem 1rem", fontSize: "0.85rem" }}>
            Logout
          </button>
        </div>
      </header>

      {/* Main Section */}
      <section style={{ flex: 1 }}>
        <h2 style={{ marginBottom: "0.5rem", fontWeight: "800" }}>Select Server to Manage</h2>
        <p style={{ color: "hsl(var(--text-muted))", marginBottom: "2rem" }}>
          Showing all Discord servers where you have Manage Server / Administrator permissions.
        </p>

        {error && (
          <div className="cyber-card" style={{ borderColor: "hsl(var(--danger))", color: "hsl(var(--danger))", padding: "1rem", marginBottom: "2rem" }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {guilds.length > 0 && guilds[0].bot_api_error && (
          <div className="cyber-card" style={{ borderColor: "hsl(var(--warning))", background: "rgba(255, 165, 0, 0.05)", padding: "1rem", marginBottom: "2rem", fontSize: "0.9rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "hsl(var(--warning))", marginBottom: "0.5rem" }}>
              <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <strong>Bot Connection Issue</strong>
            </div>
            <p style={{ color: "hsl(var(--text-secondary))" }}>
              The dashboard is having trouble reaching your Bot API. This is why servers might appear as "Missing".
            </p>
            <code style={{ display: "block", marginTop: "0.5rem", padding: "0.5rem", background: "rgba(0,0,0,0.3)", borderRadius: "4px", fontSize: "0.8rem", wordBreak: "break-all" }}>
              {guilds[0].bot_api_error}
            </code>
            <p style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}>
              Check your <strong>DISCORD_BOT_API_URL</strong> and <strong>DASHBOARD_API_KEY</strong> environment variables in Vercel.
            </p>
          </div>
        )}

        {guilds.length === 0 ? (
          <div className="cyber-card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
            <h3 style={{ marginBottom: "0.5rem" }}>No Servers Found</h3>
            <p>You must be an Owner, Administrator, or possess the "Manage Server" permission to configure ExeGuard.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1.5rem" }}>
            {guilds.map((guild) => (
              <div key={guild.id} className="cyber-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", height: "180px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  {guild.icon_url ? (
                    <img src={guild.icon_url} alt={`${guild.name} icon`} style={{ width: "50px", height: "50px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }} />
                  ) : (
                    <div style={{ width: "50px", height: "50px", borderRadius: "10px", backgroundColor: "rgba(255,255,255,0.05)", display: "flex", justifyContent: "center", alignItems: "center", fontSize: "1.25rem", fontWeight: "700", color: "hsl(var(--primary))" }}>
                      {guild.name.charAt(0)}
                    </div>
                  )}
                  <div style={{ overflow: "hidden" }}>
                    <h3 style={{ fontSize: "1.1rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginBottom: "0.25rem" }}>
                      {guild.name}
                    </h3>
                    <div style={{ display: "flex", alignItems: "center" }}>
                      {guild.bot_in ? (
                        <span className="cyber-badge cyber-badge-success" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}>
                          Active
                        </span>
                      ) : (
                        <span className="cyber-badge cyber-badge-danger" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}>
                          Missing
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: "1rem" }}>
                  {guild.bot_in ? (
                    <Link href={`/dashboard/${guild.id}`} className="cyber-btn" style={{ width: "100%", textShadow: "none" }}>
                      Manage Server
                    </Link>
                  ) : (
                    <a href={guild.invite_url} target="_blank" rel="noopener noreferrer" className="cyber-btn-secondary" style={{ width: "100%" }}>
                      <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" style={{ marginRight: "0.4rem" }}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                      </svg>
                      Setup ExeGuard
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer style={{ marginTop: "5rem", textAlign: "center", padding: "2rem 0", borderTop: "1px solid rgba(255, 255, 255, 0.05)", fontSize: "0.85rem", color: "hsl(var(--text-muted))" }}>
        ExeGuard Security Bot Panel
      </footer>
    </main>
  );
}
