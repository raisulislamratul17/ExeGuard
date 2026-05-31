"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";

interface Channel {
  id: string;
  name: string;
}

interface Role {
  id: string;
  name: string;
  color: string;
}

interface Settings {
  guild_id: number;
  antispam: number;
  antiraid: number;
  antinuke: number;
  verification: number;
  log_channel: number | null;
  mod_log_channel: number | null;
  join_log_channel: number | null;
  verified_role: number | null;
  raid_level: string;
  spam_threshold: number;
  spam_interval: number;
  timeout_duration: number;
  trust_all_bots: number;
  spam_emoji_limit: number;
  spam_mention_limit: number;
  spam_caps_ratio: number;
  spam_duplicate_threshold: number;
  spam_duplicate_interval: number;
  block_invites: number;
  block_links: number;
  bad_words: string;
  block_user_apps: number;
  bot_protection: number;
  
  // Custom properties added by API
  guild_name?: string;
  guild_icon?: string | null;
  channels?: Channel[];
  roles?: Role[];
}

interface Warning {
  id: number;
  user_id: string;
  username: string;
  mod_id: string;
  mod_name: string;
  reason: string;
  timestamp: string;
}

export default function GuildDashboard({ params }: { params: Promise<{ guildId: string }> }) {
  const { guildId } = React.use(params);
  const { data: session, status } = useSession();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<"overview" | "antinuke" | "antispam" | "logs" | "mod">("overview");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [panicLoading, setPanicLoading] = useState(false);

  // Moderation form state
  const [modTargetId, setModTargetId] = useState("");
  const [modAction, setModAction] = useState("timeout");
  const [modReason, setModReason] = useState("");
  const [modDuration, setModDuration] = useState("10");
  const [modMsg, setModMsg] = useState("");
  const [modError, setModError] = useState("");

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/");
    }
  }, [status, router]);

  const fetchData = async () => {
    if (status !== "authenticated") return;
    try {
      setLoading(true);
      // Fetch settings
      const settingsRes = await fetch(`/api/bot/guilds/${guildId}/settings`);
      if (!settingsRes.ok) {
        if (settingsRes.status === 404) {
          throw new Error("Bot is not in this server. Please invite ExeGuard first!");
        }
        throw new Error("Failed to load server settings.");
      }
      const settingsData = await settingsRes.json();
      setSettings(settingsData);

      // Fetch warnings
      const warningsRes = await fetch(`/api/bot/guilds/${guildId}/warnings`);
      if (warningsRes.ok) {
        const warningsData = await warningsRes.json();
        setWarnings(warningsData);
      }
      
      setLoading(false);
    } catch (err: any) {
      setError(err.message || "Failed to load data.");
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [status, guildId]);

  // Recalculate security score dynamically
  const calculateSecurityScore = () => {
    if (!settings) return 0;
    let score = 0;
    if (settings.antinuke === 1) score += 25;
    if (settings.antiraid === 1) score += 25;
    if (settings.antispam === 1) score += 20;
    if (settings.verification === 1) score += 15;
    if (settings.log_channel) score += 8;
    if (settings.mod_log_channel) score += 7;
    return score;
  };

  const handleSettingChange = (key: keyof Settings, value: any) => {
    if (!settings) return;
    setSettings({
      ...settings,
      [key]: value
    });
  };

  const saveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    try {
      setSuccessMsg("");
      setError("");
      
      const res = await fetch(`/api/bot/guilds/${guildId}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });

      if (!res.ok) throw new Error("Failed to save settings.");
      
      setSuccessMsg("System configurations updated successfully.");
      setTimeout(() => setSuccessMsg(""), 4000);
    } catch (err: any) {
      setError(err.message || "Failed to update configurations.");
    }
  };

  const togglePanicMode = async () => {
    if (!settings || panicLoading) return;
    try {
      setPanicLoading(true);
      setError("");
      
      // Determine new state (if either antiraid is on or if we just want to lock all channels)
      // We pass the "panic" action to the api action route
      const isPanicActive = settings.antiraid === 1 && settings.raid_level === "high"; 
      
      const res = await fetch(`/api/bot/guilds/${guildId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "panic",
          enabled: !isPanicActive,
          reason: "Dashboard Emergency Panic Triggered"
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Failed to toggle Panic Lockdown.");
      }

      const resData = await res.json();
      
      // Update local state temporarily to reflect
      if (!isPanicActive) {
        setSuccessMsg("EMERGENCY PANIC MODE ENABLED! All channels locked down.");
      } else {
        setSuccessMsg("Panic lockdown lifted. Normal server operations restored.");
      }
      
      // Refresh configurations
      await fetchData();
      setPanicLoading(false);
      setTimeout(() => setSuccessMsg(""), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to execute Panic command.");
      setPanicLoading(false);
    }
  };

  const executeModeration = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setModMsg("");
      setModError("");
      
      if (!modTargetId.trim()) {
        setModError("A valid Member User ID is required.");
        return;
      }

      const res = await fetch(`/api/bot/guilds/${guildId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: modAction,
          user_id: modTargetId.trim(),
          reason: modReason || "Administered from Web Dashboard Console",
          duration: parseInt(modDuration) || 10
        }),
      });

      const resData = await res.json();
      if (!res.ok) {
        throw new Error(resData.error || "Failed to execute moderation action.");
      }

      setModMsg(resData.message || "Action executed successfully.");
      setModTargetId("");
      setModReason("");
      
      // Reload warnings list
      const warningsRes = await fetch(`/api/bot/guilds/${guildId}/warnings`);
      if (warningsRes.ok) {
        setWarnings(await warningsRes.json());
      }
    } catch (err: any) {
      setModError(err.message || "Failed to run moderation command.");
    }
  };

  if (status === "loading" || loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
        <div style={{ border: "4px solid rgba(255, 255, 255, 0.05)", borderTop: "4px solid hsl(var(--primary))", borderRadius: "50%", width: "40px", height: "40px", animation: "spin-slow 1s linear infinite" }}></div>
        <p style={{ marginTop: "1rem", color: "hsl(var(--text-secondary))" }}>Loading server settings...</p>
      </div>
    );
  }

  if (error && !settings) {
    return (
      <div className="cyber-container" style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", minHeight: "100vh", textAlign: "center" }}>
        <div className="cyber-card" style={{ borderColor: "hsl(var(--danger))", padding: "2.5rem", maxWidth: "450px" }}>
          <h3 style={{ color: "hsl(var(--danger))", marginBottom: "1rem" }}>System Access Refused</h3>
          <p style={{ marginBottom: "1.5rem" }}>{error}</p>
          <Link href="/dashboard" className="cyber-btn">
            Return to Console
          </Link>
        </div>
      </div>
    );
  }

  const score = calculateSecurityScore();

  return (
    <main className="cyber-container" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Mini Breadcrumb Nav */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1.5rem 0", borderBottom: "1px solid rgba(255, 255, 255, 0.05)", marginBottom: "2rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <Link href="/dashboard" style={{ color: "hsl(var(--text-muted))", display: "flex", alignItems: "center", gap: "0.25rem" }}>
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Servers
          </Link>
          <span style={{ color: "rgba(255,255,255,0.15)" }}>/</span>
          <span style={{ fontWeight: "700", color: "#fff" }}>{settings?.guild_name}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span className="cyber-badge cyber-badge-info" style={{ fontSize: "0.75rem" }}>
            Bot Secured
          </span>
        </div>
      </header>

      {/* Main Grid: Info Bar & Tabs */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "2rem" }}>
        {/* Banner Section */}
        <div className="cyber-card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
            {settings?.guild_icon ? (
              <img src={settings.guild_icon} alt="Server Icon" style={{ width: "70px", height: "70px", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.1)" }} />
            ) : (
              <div style={{ width: "70px", height: "70px", borderRadius: "14px", backgroundColor: "rgba(255,255,255,0.05)", display: "flex", justifyContent: "center", alignItems: "center", fontSize: "1.75rem", fontWeight: "700", color: "hsl(var(--primary))" }}>
                {settings?.guild_name?.charAt(0)}
              </div>
            )}
            <div>
              <h2 style={{ fontSize: "1.6rem", color: "#fff", marginBottom: "0.25rem" }}>{settings?.guild_name}</h2>
              <p style={{ fontSize: "0.95rem" }}>Guild ID: {settings?.guild_id}</p>
            </div>
          </div>

          {/* Quick Info Alerts */}
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            {successMsg && (
              <div className="cyber-badge cyber-badge-success" style={{ padding: "0.6rem 1rem", animation: "pulse-slow 2s infinite" }}>
                {successMsg}
              </div>
            )}
            {error && (
              <div className="cyber-badge cyber-badge-danger" style={{ padding: "0.6rem 1rem" }}>
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Dynamic Sidebar + Tab Content Panels */}
        <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: "2rem" }}>
          {/* Sidebar Nav Tabs */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <button onClick={() => setActiveTab("overview")} className={activeTab === "overview" ? "cyber-btn" : "cyber-btn-secondary"} style={{ justifyContent: "flex-start", width: "100%", textShadow: "none" }}>
              📊 Control Hub
            </button>
            <button onClick={() => setActiveTab("antinuke")} className={activeTab === "antinuke" ? "cyber-btn" : "cyber-btn-secondary"} style={{ justifyContent: "flex-start", width: "100%", textShadow: "none" }}>
              🛡️ Anti-Nuke & Raid
            </button>
            <button onClick={() => setActiveTab("antispam")} className={activeTab === "antispam" ? "cyber-btn" : "cyber-btn-secondary"} style={{ justifyContent: "flex-start", width: "100%", textShadow: "none" }}>
              ⚡ Anti-Spam & Apps
            </button>
            <button onClick={() => setActiveTab("logs")} className={activeTab === "logs" ? "cyber-btn" : "cyber-btn-secondary"} style={{ justifyContent: "flex-start", width: "100%", textShadow: "none" }}>
              📝 Logs & Gateways
            </button>
            <button onClick={() => setActiveTab("mod")} className={activeTab === "mod" ? "cyber-btn" : "cyber-btn-secondary"} style={{ justifyContent: "flex-start", width: "100%", textShadow: "none" }}>
              🔨 Mod Center & Logs
            </button>
          </div>

          {/* Tab Content Panel */}
          <div className="cyber-card" style={{ padding: "2rem" }}>
            
            {/* TAB 1: OVERVIEW CONTROL HUB */}
            {activeTab === "overview" && settings && (
              <div>
                <h3 style={{ marginBottom: "1.5rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>Console Command Center</h3>
                
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "2rem" }}>
                  {/* Security Score Semicircular CSS Gauge */}
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
                    <div style={{ position: "relative", width: "160px", height: "100px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end" }}>
                      {/* Arc representation using SVG */}
                      <svg width="150" height="75" viewBox="0 0 100 50">
                        <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10" strokeLinecap="round" />
                        <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="url(#score-gradient)" strokeWidth="10" strokeLinecap="round" strokeDasharray="126" strokeDashoffset={126 - (126 * score) / 100} />
                        <defs>
                          <linearGradient id="score-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="hsl(var(--primary))" />
                            <stop offset="100%" stopColor="hsl(var(--secondary))" />
                          </linearGradient>
                        </defs>
                      </svg>
                      <div style={{ position: "absolute", bottom: "5px", textAlign: "center" }}>
                        <span style={{ fontSize: "2rem", fontWeight: "900", color: "#fff" }}>{score}%</span>
                      </div>
                    </div>
                    <span style={{ marginTop: "1rem", fontWeight: "700", textTransform: "uppercase", fontSize: "0.85rem", color: "hsl(var(--text-secondary))" }}>
                      Security Audit Score
                    </span>
                  </div>

                  {/* EMERGENCY PANIC TOGGLE CARD */}
                  <div className="cyber-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", borderColor: "rgba(255, 77, 77, 0.2)", background: "rgba(255, 77, 77, 0.02)" }}>
                    <div>
                      <h4 style={{ color: "hsl(var(--danger))", display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                        🚨 Emergency Panic Button
                      </h4>
                      <p style={{ fontSize: "0.88rem" }}>
                        Activating this immediately locks down all channels in the Discord server, preventing everyone from sending messages. Lift the lockdown to restore access.
                      </p>
                    </div>
                    
                    <button onClick={togglePanicMode} disabled={panicLoading} className="cyber-btn-danger" style={{ width: "100%", padding: "0.8rem", marginTop: "1rem", fontSize: "0.95rem" }}>
                      {panicLoading ? "Executing..." : "Trigger Emergency Lockdown"}
                    </button>
                  </div>
                </div>

                {/* Quick Status Switches */}
                <div style={{ marginTop: "3rem" }}>
                  <h4 style={{ marginBottom: "1.25rem" }}>Automated Protections Status</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
                    <div className="cyber-card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem" }}>
                      <span>Anti-Nuke Protection</span>
                      <span className={settings.antinuke === 1 ? "cyber-badge cyber-badge-success" : "cyber-badge cyber-badge-danger"}>
                        {settings.antinuke === 1 ? "ON" : "OFF"}
                      </span>
                    </div>
                    <div className="cyber-card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem" }}>
                      <span>Anti-Raid Monitoring</span>
                      <span className={settings.antiraid === 1 ? "cyber-badge cyber-badge-success" : "cyber-badge cyber-badge-danger"}>
                        {settings.antiraid === 1 ? "ON" : "OFF"}
                      </span>
                    </div>
                    <div className="cyber-card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem" }}>
                      <span>Anti-Spam Filter</span>
                      <span className={settings.antispam === 1 ? "cyber-badge cyber-badge-success" : "cyber-badge cyber-badge-danger"}>
                        {settings.antispam === 1 ? "ON" : "OFF"}
                      </span>
                    </div>
                    <div className="cyber-card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem" }}>
                      <span>User-App Shield</span>
                      <span className={settings.block_user_apps === 1 ? "cyber-badge cyber-badge-success" : "cyber-badge cyber-badge-danger"}>
                        {settings.block_user_apps === 1 ? "ON" : "OFF"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: ANTI-NUKE & ANTI-RAID */}
            {activeTab === "antinuke" && settings && (
              <form onSubmit={saveSettings}>
                <h3 style={{ marginBottom: "1.5rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>🛡️ Anti-Nuke & Anti-Raid Configurations</h3>
                
                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  {/* Anti Nuke Toggle */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <strong style={{ display: "block", marginBottom: "0.25rem" }}>Enable Anti-Nuke Engine</strong>
                      <span style={{ fontSize: "0.85rem", color: "hsl(var(--text-muted))" }}>Monitors channel deletions, role creations, and bans. rogue admins are automatically banned.</span>
                    </div>
                    <input type="checkbox" checked={settings.antinuke === 1} onChange={(e) => handleSettingChange("antinuke", e.target.checked ? 1 : 0)} style={{ width: "20px", height: "20px", accentColor: "hsl(var(--primary))", cursor: "pointer" }} />
                  </div>

                  <hr style={{ border: "0", borderTop: "1px solid rgba(255,255,255,0.05)" }} />

                  {/* Anti Raid Toggle */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <strong style={{ display: "block", marginBottom: "0.25rem" }}>Enable Anti-Raid Shield</strong>
                      <span style={{ fontSize: "0.85rem", color: "hsl(var(--text-muted))" }}>Triggers server-wide slowmode and locks down text channels in the event of an abnormal spike in joins.</span>
                    </div>
                    <input type="checkbox" checked={settings.antiraid === 1} onChange={(e) => handleSettingChange("antiraid", e.target.checked ? 1 : 0)} style={{ width: "20px", height: "20px", accentColor: "hsl(var(--primary))", cursor: "pointer" }} />
                  </div>

                  {/* Raid Threshold Level */}
                  <div>
                    <label style={{ display: "block", fontWeight: "600", marginBottom: "0.5rem" }}>Anti-Raid Severity Level</label>
                    <select value={settings.raid_level} onChange={(e) => handleSettingChange("raid_level", e.target.value)} className="cyber-input" style={{ background: "hsl(var(--bg-card))" }}>
                      <option value="low">Low (Locks Channels on Massive Joins only)</option>
                      <option value="medium">Medium (Locks + Kicks Suspicious Young Accounts)</option>
                      <option value="high">High (Maximum Lockdown + Auto-kick Young Accounts immediately)</option>
                    </select>
                  </div>

                  {/* Bot protection toggle */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <strong style={{ display: "block", marginBottom: "0.25rem" }}>Enable Bot Protection</strong>
                      <span style={{ fontSize: "0.85rem", color: "hsl(var(--text-muted))" }}>Prevents staff from accidentally kicking or banning invited bot integrations.</span>
                    </div>
                    <input type="checkbox" checked={settings.bot_protection === 1} onChange={(e) => handleSettingChange("bot_protection", e.target.checked ? 1 : 0)} style={{ width: "20px", height: "20px", accentColor: "hsl(var(--primary))", cursor: "pointer" }} />
                  </div>

                  <button type="submit" className="cyber-btn" style={{ alignSelf: "flex-start", marginTop: "1rem" }}>
                    Save Configurations
                  </button>
                </div>
              </form>
            )}

            {/* TAB 3: ANTI-SPAM & AUTOMOD */}
            {activeTab === "antispam" && settings && (
              <form onSubmit={saveSettings}>
                <h3 style={{ marginBottom: "1.5rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>⚡ Anti-Spam & Automod Filters</h3>
                
                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  {/* Anti Spam Toggle */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <strong style={{ display: "block", marginBottom: "0.25rem" }}>Enable Anti-Spam Engine</strong>
                      <span style={{ fontSize: "0.85rem", color: "hsl(var(--text-muted))" }}>Tracks rapidly repeated messages, caps spam, duplicate messages, and too many emojis.</span>
                    </div>
                    <input type="checkbox" checked={settings.antispam === 1} onChange={(e) => handleSettingChange("antispam", e.target.checked ? 1 : 0)} style={{ width: "20px", height: "20px", accentColor: "hsl(var(--primary))", cursor: "pointer" }} />
                  </div>

                  {/* External Apps Blocking */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <strong style={{ display: "block", marginBottom: "0.25rem" }}>Block External User-Installed Apps</strong>
                      <span style={{ fontSize: "0.85rem", color: "hsl(var(--text-muted))" }}>Blocks unauthorized bots or applications running from user accounts. Warns/timeouts offenders.</span>
                    </div>
                    <input type="checkbox" checked={settings.block_user_apps === 1} onChange={(e) => handleSettingChange("block_user_apps", e.target.checked ? 1 : 0)} style={{ width: "20px", height: "20px", accentColor: "hsl(var(--primary))", cursor: "pointer" }} />
                  </div>

                  <hr style={{ border: "0", borderTop: "1px solid rgba(255,255,255,0.05)" }} />

                  {/* Settings Grid */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1.5rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", marginBottom: "0.5rem" }}>Spam Messages Limit</label>
                      <input type="number" value={settings.spam_threshold} onChange={(e) => handleSettingChange("spam_threshold", parseInt(e.target.value))} className="cyber-input" />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", marginBottom: "0.5rem" }}>Emoji Limit per Message</label>
                      <input type="number" value={settings.spam_emoji_limit} onChange={(e) => handleSettingChange("spam_emoji_limit", parseInt(e.target.value))} className="cyber-input" />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", marginBottom: "0.5rem" }}>Caps Spam Ratio (0.0 - 1.0)</label>
                      <input type="number" step="0.1" value={settings.spam_caps_ratio} onChange={(e) => handleSettingChange("spam_caps_ratio", parseFloat(e.target.value))} className="cyber-input" />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", marginBottom: "0.5rem" }}>Timeout Duration (Seconds)</label>
                      <input type="number" value={settings.timeout_duration} onChange={(e) => handleSettingChange("timeout_duration", parseInt(e.target.value))} className="cyber-input" />
                    </div>
                  </div>

                  <hr style={{ border: "0", borderTop: "1px solid rgba(255,255,255,0.05)" }} />

                  {/* Links and Invite toggles */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <strong style={{ display: "block", fontSize: "0.95rem" }}>Block Invite Links</strong>
                        <span style={{ fontSize: "0.8rem", color: "hsl(var(--text-muted))" }}>Deletes discord invite codes</span>
                      </div>
                      <input type="checkbox" checked={settings.block_invites === 1} onChange={(e) => handleSettingChange("block_invites", e.target.checked ? 1 : 0)} style={{ width: "16px", height: "16px", accentColor: "hsl(var(--primary))" }} />
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <strong style={{ display: "block", fontSize: "0.95rem" }}>Block Web URLs</strong>
                        <span style={{ fontSize: "0.8rem", color: "hsl(var(--text-muted))" }}>Deletes standard HTTP/HTTPS links</span>
                      </div>
                      <input type="checkbox" checked={settings.block_links === 1} onChange={(e) => handleSettingChange("block_links", e.target.checked ? 1 : 0)} style={{ width: "16px", height: "16px", accentColor: "hsl(var(--primary))" }} />
                    </div>
                  </div>

                  {/* Word Blocklist */}
                  <div>
                    <label style={{ display: "block", fontWeight: "600", marginBottom: "0.5rem" }}>Blacklisted Words (Comma separated)</label>
                    <textarea value={settings.bad_words} onChange={(e) => handleSettingChange("bad_words", e.target.value)} rows={3} placeholder="spam, bot, hacker, free nitro" className="cyber-input" style={{ resize: "vertical" }} />
                  </div>

                  <button type="submit" className="cyber-btn" style={{ alignSelf: "flex-start", marginTop: "1rem" }}>
                    Save Configurations
                  </button>
                </div>
              </form>
            )}

            {/* TAB 4: LOGS & GATEWAYS */}
            {activeTab === "logs" && settings && (
              <form onSubmit={saveSettings}>
                <h3 style={{ marginBottom: "1.5rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>📝 Audit Logs & Verification Gateways</h3>
                
                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  {/* Channels selection dropdowns */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.5rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.95rem", fontWeight: "600", marginBottom: "0.5rem" }}>Security Logging Channel</label>
                      <select value={settings.log_channel || ""} onChange={(e) => handleSettingChange("log_channel", e.target.value ? parseInt(e.target.value) : null)} className="cyber-input" style={{ background: "hsl(var(--bg-card))" }}>
                        <option value="">No Logging Channel Set</option>
                        {settings.channels?.map((ch) => (
                          <option key={ch.id} value={ch.id}>#{ch.name}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "0.95rem", fontWeight: "600", marginBottom: "0.5rem" }}>Moderation Logging Channel</label>
                      <select value={settings.mod_log_channel || ""} onChange={(e) => handleSettingChange("mod_log_channel", e.target.value ? parseInt(e.target.value) : null)} className="cyber-input" style={{ background: "hsl(var(--bg-card))" }}>
                        <option value="">No Mod Channel Set</option>
                        {settings.channels?.map((ch) => (
                          <option key={ch.id} value={ch.id}>#{ch.name}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "0.95rem", fontWeight: "600", marginBottom: "0.5rem" }}>Member Joins Logging Channel</label>
                      <select value={settings.join_log_channel || ""} onChange={(e) => handleSettingChange("join_log_channel", e.target.value ? parseInt(e.target.value) : null)} className="cyber-input" style={{ background: "hsl(var(--bg-card))" }}>
                        <option value="">No Joins Channel Set</option>
                        {settings.channels?.map((ch) => (
                          <option key={ch.id} value={ch.id}>#{ch.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <hr style={{ border: "0", borderTop: "1px solid rgba(255,255,255,0.05)" }} />

                  {/* Verification Gates */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <strong style={{ display: "block", marginBottom: "0.25rem" }}>Require Member Verification Gate</strong>
                      <span style={{ fontSize: "0.85rem", color: "hsl(var(--text-muted))" }}>Locks new members out of standard channels until they complete a Captcha or Button verify check.</span>
                    </div>
                    <input type="checkbox" checked={settings.verification === 1} onChange={(e) => handleSettingChange("verification", e.target.checked ? 1 : 0)} style={{ width: "20px", height: "20px", accentColor: "hsl(var(--primary))", cursor: "pointer" }} />
                  </div>

                  {/* Verification Role */}
                  <div>
                    <label style={{ display: "block", fontSize: "0.95rem", fontWeight: "600", marginBottom: "0.5rem" }}>Assigned Verified Role</label>
                    <select value={settings.verified_role || ""} onChange={(e) => handleSettingChange("verified_role", e.target.value ? parseInt(e.target.value) : null)} className="cyber-input" style={{ background: "hsl(var(--bg-card))" }}>
                      <option value="">Select Verified Role</option>
                      {settings.roles?.map((role) => (
                        <option key={role.id} value={role.id}>{role.name}</option>
                      ))}
                    </select>
                  </div>

                  <button type="submit" className="cyber-btn" style={{ alignSelf: "flex-start", marginTop: "1rem" }}>
                    Save Configurations
                  </button>
                </div>
              </form>
            )}

            {/* TAB 5: MOD CENTER & LOGS */}
            {activeTab === "mod" && (
              <div>
                <h3 style={{ marginBottom: "1.5rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>🔨 Dashboard Moderation Hub</h3>
                
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "2rem" }}>
                  {/* Action Dispatcher Form */}
                  <form onSubmit={executeModeration} className="cyber-card" style={{ height: "fit-content" }}>
                    <h4 style={{ marginBottom: "1rem" }}>Execute Action</h4>
                    
                    {modMsg && (
                      <div className="cyber-badge cyber-badge-success" style={{ display: "block", padding: "0.5rem", marginBottom: "1rem", textAlign: "center" }}>
                        {modMsg}
                      </div>
                    )}
                    {modError && (
                      <div className="cyber-badge cyber-badge-danger" style={{ display: "block", padding: "0.5rem", marginBottom: "1rem", textAlign: "center" }}>
                        {modError}
                      </div>
                    )}

                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                      <div>
                        <label style={{ display: "block", fontSize: "0.85rem", fontWeight: "600", marginBottom: "0.35rem" }}>Member User ID</label>
                        <input type="text" placeholder="e.g. 718392182749102" value={modTargetId} onChange={(e) => setModTargetId(e.target.value)} className="cyber-input" />
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                        <div>
                          <label style={{ display: "block", fontSize: "0.85rem", fontWeight: "600", marginBottom: "0.35rem" }}>Command Action</label>
                          <select value={modAction} onChange={(e) => setModAction(e.target.value)} className="cyber-input" style={{ background: "hsl(var(--bg-card))" }}>
                            <option value="timeout">Timeout</option>
                            <option value="kick">Kick Member</option>
                            <option value="ban">Ban Member</option>
                          </select>
                        </div>

                        {modAction === "timeout" && (
                          <div>
                            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: "600", marginBottom: "0.35rem" }}>Duration (Minutes)</label>
                            <select value={modDuration} onChange={(e) => setModDuration(e.target.value)} className="cyber-input" style={{ background: "hsl(var(--bg-card))" }}>
                              <option value="5">5 minutes</option>
                              <option value="10">10 minutes</option>
                              <option value="60">1 hour</option>
                              <option value="1440">1 day</option>
                              <option value="10080">1 week</option>
                            </select>
                          </div>
                        )}
                      </div>

                      <div>
                        <label style={{ display: "block", fontSize: "0.85rem", fontWeight: "600", marginBottom: "0.35rem" }}>Infraction Reason</label>
                        <textarea placeholder="e.g. Excessive self-promotion or flooding chat channels" value={modReason} onChange={(e) => setModReason(e.target.value)} rows={2} className="cyber-input" style={{ resize: "vertical" }} />
                      </div>

                      <button type="submit" className="cyber-btn" style={{ width: "100%", marginTop: "0.5rem" }}>
                        Confirm Action
                      </button>
                    </div>
                  </form>

                  {/* Warnings Log History */}
                  <div style={{ display: "flex", flexDirection: "column" }}>
                    <h4 style={{ marginBottom: "1rem" }}>Recent Infractions Log</h4>
                    
                    {warnings.length === 0 ? (
                      <div className="cyber-card" style={{ textAlign: "center", padding: "2rem 1rem", flex: 1, display: "flex", justifyContent: "center", alignItems: "center" }}>
                        <p style={{ color: "hsl(var(--text-muted))" }}>No warnings logged. Server is clean!</p>
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", overflowY: "auto", maxHeight: "360px", paddingRight: "0.25rem" }}>
                        {warnings.map((warn) => (
                          <div key={warn.id} className="cyber-card" style={{ padding: "0.85rem 1.1rem", fontSize: "0.88rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                              <strong>{warn.username}</strong>
                              <span style={{ fontSize: "0.75rem", color: "hsl(var(--text-muted))" }}>{warn.timestamp.split(" ")[0]}</span>
                            </div>
                            <p style={{ fontSize: "0.85rem", color: "hsl(var(--text-secondary))", marginBottom: "0.35rem" }}>
                              <strong>Reason:</strong> {warn.reason}
                            </p>
                            <span style={{ fontSize: "0.75rem", color: "hsl(var(--text-muted))" }}>Warned by: {warn.mod_name}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Footer */}
      <footer style={{ marginTop: "5rem", textAlign: "center", padding: "2.5rem 0", borderTop: "1px solid rgba(255, 255, 255, 0.05)", fontSize: "0.85rem", color: "hsl(var(--text-muted))" }}>
        ExeGuard Control Console Panel
      </footer>
    </main>
  );
}
