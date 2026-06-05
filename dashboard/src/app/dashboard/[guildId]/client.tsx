"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";

interface Channel { id: string; name: string; }
interface Role { id: string; name: string; color: string; }

interface Settings {
  guild_id: number; guild_name?: string; guild_icon?: string | null;
  channels?: Channel[]; roles?: Role[];
  antispam: number; antiraid: number; antinuke: number; verification: number;
  log_channel: number | null; mod_log_channel: number | null; join_log_channel: number | null;
  verified_role: number | null; raid_level: string;
  spam_threshold: number; spam_interval: number; timeout_duration: number;
  trust_all_bots: number; spam_emoji_limit: number; spam_mention_limit: number;
  spam_caps_ratio: number; spam_duplicate_threshold: number; spam_duplicate_interval: number;
  block_invites: number; block_links: number; bad_words: string;
  block_user_apps: number; bot_protection: number;
}

interface Warning { id: number; user_id: string; username: string; mod_id: string; mod_name: string; reason: string; timestamp: string; }

type Tab = "overview" | "antinuke" | "antispam" | "logs" | "mod";

const ALLOWED_SETTINGS_KEYS = [
  "antispam", "antiraid", "antinuke", "verification",
  "log_channel", "mod_log_channel", "join_log_channel",
  "verified_role", "raid_level", "spam_threshold",
  "spam_interval", "timeout_duration", "trust_all_bots",
  "spam_emoji_limit", "spam_mention_limit", "spam_caps_ratio",
  "spam_duplicate_threshold", "spam_duplicate_interval",
  "block_invites", "block_links", "bad_words",
  "block_user_apps", "bot_protection",
] as const;

export default function GuildSettingsClient({ guildId }: { guildId: string }) {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [panicLoading, setPanicLoading] = useState(false);

  const [modTargetId, setModTargetId] = useState("");
  const [modAction, setModAction] = useState("timeout");
  const [modReason, setModReason] = useState("");
  const [modDuration, setModDuration] = useState("10");
  const [modMsg, setModMsg] = useState("");
  const [modError, setModError] = useState("");

  useEffect(() => {
    if (status === "unauthenticated") router.push("/");
  }, [status, router]);

  const fetchData = async () => {
    if (status !== "authenticated") return;
    try {
      setLoading(true);
      const settingsRes = await fetch(`/api/bot/guilds/${guildId}/settings`);
      if (!settingsRes.ok) {
        if (settingsRes.status === 404) throw new Error("Bot is not in this server. Please invite ExeGuard first!");
        throw new Error("Failed to load server settings.");
      }
      setSettings(await settingsRes.json());

      const warningsRes = await fetch(`/api/bot/guilds/${guildId}/warnings`);
      if (warningsRes.ok) setWarnings(await warningsRes.json());

      setLoading(false);
    } catch (err: any) {
      setError(err.message || "Failed to load data.");
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [status, guildId]);

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

  const handleSettingChange = (key: string, value: any) => {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
  };

  const saveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    try {
      setSuccessMsg(""); setError("");
      const payload: Record<string, any> = {};
      for (const key of ALLOWED_SETTINGS_KEYS) {
        if (key in settings) {
          payload[key] = (settings as any)[key];
        }
      }
      const res = await fetch(`/api/bot/guilds/${guildId}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const resData = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(resData.error || `API returned ${res.status}`);
      }
      setSuccessMsg("Settings saved successfully.");
      setTimeout(() => setSuccessMsg(""), 4000);
    } catch (err: any) {
      setError(err.message || "Failed to update settings.");
    }
  };

  const togglePanicMode = async () => {
    if (!settings || panicLoading) return;
    try {
      setPanicLoading(true); setError("");
      const isPanicActive = settings.antiraid === 1 && settings.raid_level === "high";
      const res = await fetch(`/api/bot/guilds/${guildId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "panic", enabled: !isPanicActive, reason: "Dashboard Emergency Panic" }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Failed to toggle Panic Lockdown.");
      }
      setSuccessMsg(isPanicActive ? "Panic lockdown lifted." : "EMERGENCY PANIC MODE ENABLED! All channels locked down.");
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
      setModMsg(""); setModError("");
      if (!modTargetId.trim()) { setModError("A valid Member User ID is required."); return; }
      const res = await fetch(`/api/bot/guilds/${guildId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: modAction, user_id: modTargetId.trim(),
          reason: modReason || "Administered from Web Dashboard Console",
          duration: parseInt(modDuration) || 10
        }),
      });
      const resData = await res.json();
      if (!res.ok) throw new Error(resData.error || "Failed to execute moderation action.");
      setModMsg(resData.message || "Action executed successfully.");
      setModTargetId(""); setModReason("");
      const wRes = await fetch(`/api/bot/guilds/${guildId}/warnings`);
      if (wRes.ok) setWarnings(await wRes.json());
    } catch (err: any) {
      setModError(err.message || "Failed to run moderation command.");
    }
  };

  if (status === "loading" || loading) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: "100vh" }}>
        <div className="flex items-center gap-sm">
          <div className="spinner" />
          <span style={{ color: "var(--body)" }}>Loading server settings...</span>
        </div>
      </div>
    );
  }

  if (error && !settings) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: "100vh" }}>
        <div className="card-lg" style={{ maxWidth: "400px", textAlign: "center" }}>
          <h3 style={{ color: "var(--error)", marginBottom: "12px" }}>Connection Error</h3>
          <p className="text-sm mb-lg">{error}</p>
          <Link href="/dashboard" className="btn btn-primary">Return to Console</Link>
        </div>
      </div>
    );
  }

  const score = calculateSecurityScore();

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <nav className="nav">
        <div className="flex items-center gap-sm">
          <Link href="/dashboard" className="btn btn-ghost btn-sm" style={{ padding: "4px 8px" }}>
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Servers
          </Link>
          <span style={{ color: "var(--hairline-strong)" }}>/</span>
          <span style={{ fontWeight: 500, fontSize: "14px" }}>{settings?.guild_name || "Loading..."}</span>
        </div>
        <div className="flex items-center gap-sm">
          {successMsg && <span className="badge badge-success">{successMsg}</span>}
          {error && <span className="badge badge-danger">{error}</span>}
        </div>
      </nav>

      <div className="page-wrapper" style={{ flex: 1, paddingTop: "24px", paddingBottom: "48px" }}>
        <div className="card-lg flex items-center justify-between" style={{ marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
          <div className="flex items-center gap-md">
            {settings?.guild_icon ? (
              <img src={settings.guild_icon} alt="" style={{ width: "56px", height: "56px", borderRadius: "10px" }} />
            ) : (
              <div style={{ width: "56px", height: "56px", borderRadius: "10px", background: "var(--canvas-soft)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "22px", fontWeight: 600 }}>
                {settings?.guild_name?.charAt(0)}
              </div>
            )}
            <div>
              <h2 style={{ marginBottom: "2px" }}>{settings?.guild_name}</h2>
              <p className="text-xs mono">ID: {settings?.guild_id}</p>
            </div>
          </div>
          <span className="badge badge-success">Bot Secured</span>
        </div>

        <div className="sidebar-layout">
          <div className="sidebar">
            <button onClick={() => setActiveTab("overview")} className={`sidebar-item ${activeTab === "overview" ? "active" : ""}`}>
              <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
              Control Hub
            </button>
            <button onClick={() => setActiveTab("antinuke")} className={`sidebar-item ${activeTab === "antinuke" ? "active" : ""}`}>
              <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
              Anti-Nuke & Raid
            </button>
            <button onClick={() => setActiveTab("antispam")} className={`sidebar-item ${activeTab === "antispam" ? "active" : ""}`}>
              <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg>
              Anti-Spam & Apps
            </button>
            <button onClick={() => setActiveTab("logs")} className={`sidebar-item ${activeTab === "logs" ? "active" : ""}`}>
              <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              Logs & Gateways
            </button>
            <button onClick={() => setActiveTab("mod")} className={`sidebar-item ${activeTab === "mod" ? "active" : ""}`}>
              <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
              Mod Center
            </button>
          </div>

          <div className="card-lg">
            {activeTab === "overview" && settings && (
              <div>
                <h3 className="mb-lg">Control Hub</h3>
                <div className="grid-2" style={{ marginBottom: "32px" }}>
                  <div className="card text-center" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "32px" }}>
                    <svg width="120" height="70" viewBox="0 0 120 60">
                      <path d="M 10 55 A 50 50 0 0 1 110 55" fill="none" stroke="var(--hairline)" strokeWidth="8" strokeLinecap="round" />
                      <path d="M 10 55 A 50 50 0 0 1 110 55" fill="none" stroke="var(--ink)" strokeWidth="8" strokeLinecap="round" strokeDasharray="157" strokeDashoffset={157 - (157 * score) / 100} />
                    </svg>
                    <div style={{ fontSize: "28px", fontWeight: 600, letterSpacing: "-1.28px", marginTop: "8px" }}>{score}%</div>
                    <p className="text-xs mono">Security Score</p>
                  </div>

                  <div className="card" style={{ borderLeft: "3px solid var(--error)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                    <div>
                      <h4 style={{ marginBottom: "8px", color: "var(--error)" }}>Emergency Panic</h4>
                      <p className="text-sm">Locks down all channels immediately. Lift to restore access.</p>
                    </div>
                    <button onClick={togglePanicMode} disabled={panicLoading} className="btn btn-danger btn-sm mt-md" style={{ width: "100%", justifyContent: "center" }}>
                      {panicLoading ? "Executing..." : "Trigger Emergency Lockdown"}
                    </button>
                  </div>
                </div>

                <h4 className="mb-md">Protection Status</h4>
                <div className="grid-2">
                  {[
                    { label: "Anti-Nuke Protection", key: "antinuke" as const },
                    { label: "Anti-Raid Monitoring", key: "antiraid" as const },
                    { label: "Anti-Spam Filter", key: "antispam" as const },
                    { label: "User-App Shield", key: "block_user_apps" as const },
                  ].map(({ label, key }) => (
                    <div key={key} className="card-soft flex items-center justify-between">
                      <span className="text-sm" style={{ fontWeight: 500 }}>{label}</span>
                      <span className={`badge ${settings[key] === 1 ? "badge-success" : "badge-danger"}`}>
                        {settings[key] === 1 ? "ON" : "OFF"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "antinuke" && settings && (
              <form onSubmit={saveSettings}>
                <h3 className="mb-lg">Anti-Nuke & Anti-Raid</h3>
                <div className="flex flex-col" style={{ gap: "20px" }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <strong style={{ display: "block", marginBottom: "4px" }}>Anti-Nuke Engine</strong>
                      <p className="text-sm" style={{ color: "var(--body)" }}>Monitors channel deletions, role creations, and bans. Rogue admins are automatically banned.</p>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={settings.antinuke === 1} onChange={(e) => handleSettingChange("antinuke", e.target.checked ? 1 : 0)} />
                      <span className="toggle-slider" />
                    </label>
                  </div>

                  <hr className="divider" />

                  <div className="flex items-center justify-between">
                    <div>
                      <strong style={{ display: "block", marginBottom: "4px" }}>Anti-Raid Shield</strong>
                      <p className="text-sm" style={{ color: "var(--body)" }}>Triggers server-wide slowmode and locks down text channels during join spikes.</p>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={settings.antiraid === 1} onChange={(e) => handleSettingChange("antiraid", e.target.checked ? 1 : 0)} />
                      <span className="toggle-slider" />
                    </label>
                  </div>

                  <div>
                    <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Raid Severity Level</label>
                    <select value={settings.raid_level} onChange={(e) => handleSettingChange("raid_level", e.target.value)} className="input">
                      <option value="low">Low — Lock channels on massive joins only</option>
                      <option value="medium">Medium — Lock + kick suspicious young accounts</option>
                      <option value="high">High — Maximum lockdown + auto-kick young accounts immediately</option>
                    </select>
                  </div>

                  <hr className="divider" />

                  <div className="flex items-center justify-between">
                    <div>
                      <strong style={{ display: "block", marginBottom: "4px" }}>Bot Protection</strong>
                      <p className="text-sm" style={{ color: "var(--body)" }}>Prevents staff from accidentally kicking or banning invited bot integrations.</p>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={settings.bot_protection === 1} onChange={(e) => handleSettingChange("bot_protection", e.target.checked ? 1 : 0)} />
                      <span className="toggle-slider" />
                    </label>
                  </div>

                  <button type="submit" className="btn btn-primary btn-sm" style={{ alignSelf: "flex-start" }}>Save</button>
                </div>
              </form>
            )}

            {activeTab === "antispam" && settings && (
              <form onSubmit={saveSettings}>
                <h3 className="mb-lg">Anti-Spam & Automod</h3>
                <div className="flex flex-col" style={{ gap: "20px" }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <strong style={{ display: "block", marginBottom: "4px" }}>Anti-Spam Engine</strong>
                      <p className="text-sm" style={{ color: "var(--body)" }}>Tracks rapid messages, caps spam, duplicates, and emoji abuse.</p>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={settings.antispam === 1} onChange={(e) => handleSettingChange("antispam", e.target.checked ? 1 : 0)} />
                      <span className="toggle-slider" />
                    </label>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <strong style={{ display: "block", marginBottom: "4px" }}>Block External User-Installed Apps</strong>
                      <p className="text-sm" style={{ color: "var(--body)" }}>Blocks unauthorized bots or applications from user accounts.</p>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={settings.block_user_apps === 1} onChange={(e) => handleSettingChange("block_user_apps", e.target.checked ? 1 : 0)} />
                      <span className="toggle-slider" />
                    </label>
                  </div>

                  <hr className="divider" />

                  <div className="grid-2">
                    <div>
                      <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Spam Message Limit</label>
                      <input type="number" value={settings.spam_threshold} onChange={(e) => handleSettingChange("spam_threshold", parseInt(e.target.value))} className="input" />
                    </div>
                    <div>
                      <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Emoji Limit per Message</label>
                      <input type="number" value={settings.spam_emoji_limit} onChange={(e) => handleSettingChange("spam_emoji_limit", parseInt(e.target.value))} className="input" />
                    </div>
                    <div>
                      <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Caps Ratio (0.0 - 1.0)</label>
                      <input type="number" step="0.1" value={settings.spam_caps_ratio} onChange={(e) => handleSettingChange("spam_caps_ratio", parseFloat(e.target.value))} className="input" />
                    </div>
                    <div>
                      <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Timeout Duration (seconds)</label>
                      <input type="number" value={settings.timeout_duration} onChange={(e) => handleSettingChange("timeout_duration", parseInt(e.target.value))} className="input" />
                    </div>
                  </div>

                  <hr className="divider" />

                  <div className="grid-2">
                    <div className="flex items-center justify-between card-soft">
                      <span className="text-sm" style={{ fontWeight: 500 }}>Block Invite Links</span>
                      <label className="toggle">
                        <input type="checkbox" checked={settings.block_invites === 1} onChange={(e) => handleSettingChange("block_invites", e.target.checked ? 1 : 0)} />
                        <span className="toggle-slider" />
                      </label>
                    </div>
                    <div className="flex items-center justify-between card-soft">
                      <span className="text-sm" style={{ fontWeight: 500 }}>Block Web URLs</span>
                      <label className="toggle">
                        <input type="checkbox" checked={settings.block_links === 1} onChange={(e) => handleSettingChange("block_links", e.target.checked ? 1 : 0)} />
                        <span className="toggle-slider" />
                      </label>
                    </div>
                  </div>

                  <div>
                    <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Blacklisted Words (comma separated)</label>
                    <textarea value={settings.bad_words} onChange={(e) => handleSettingChange("bad_words", e.target.value)} rows={2} placeholder="spam, bot, hacker, free nitro" className="input" />
                  </div>

                  <button type="submit" className="btn btn-primary btn-sm" style={{ alignSelf: "flex-start" }}>Save</button>
                </div>
              </form>
            )}

            {activeTab === "logs" && settings && (
              <form onSubmit={saveSettings}>
                <h3 className="mb-lg">Logs & Verification</h3>
                <div className="flex flex-col" style={{ gap: "20px" }}>
                  <div className="grid-2">
                    <div>
                      <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Security Log Channel</label>
                      <select value={settings.log_channel ? String(settings.log_channel) : ""} onChange={(e) => handleSettingChange("log_channel", e.target.value ? parseInt(e.target.value) : null)} className="input">
                        <option value="">No channel set</option>
                        {settings.channels?.map((ch) => (<option key={ch.id} value={ch.id}>#{ch.name}</option>))}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Moderation Log Channel</label>
                      <select value={settings.mod_log_channel ? String(settings.mod_log_channel) : ""} onChange={(e) => handleSettingChange("mod_log_channel", e.target.value ? parseInt(e.target.value) : null)} className="input">
                        <option value="">No channel set</option>
                        {settings.channels?.map((ch) => (<option key={ch.id} value={ch.id}>#{ch.name}</option>))}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Join Log Channel</label>
                      <select value={settings.join_log_channel ? String(settings.join_log_channel) : ""} onChange={(e) => handleSettingChange("join_log_channel", e.target.value ? parseInt(e.target.value) : null)} className="input">
                        <option value="">No channel set</option>
                        {settings.channels?.map((ch) => (<option key={ch.id} value={ch.id}>#{ch.name}</option>))}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm" style={{ display: "block", fontWeight: 500, marginBottom: "6px" }}>Verified Role</label>
                      <select value={settings.verified_role ? String(settings.verified_role) : ""} onChange={(e) => handleSettingChange("verified_role", e.target.value ? parseInt(e.target.value) : null)} className="input">
                        <option value="">No role set</option>
                        {settings.roles?.map((role) => (<option key={role.id} value={role.id}>{role.name}</option>))}
                      </select>
                    </div>
                  </div>

                  <hr className="divider" />

                  <div className="flex items-center justify-between">
                    <div>
                      <strong style={{ display: "block", marginBottom: "4px" }}>Require Member Verification</strong>
                      <p className="text-sm" style={{ color: "var(--body)" }}>New members must complete CAPTCHA or button verification before accessing channels.</p>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={settings.verification === 1} onChange={(e) => handleSettingChange("verification", e.target.checked ? 1 : 0)} />
                      <span className="toggle-slider" />
                    </label>
                  </div>

                  <button type="submit" className="btn btn-primary btn-sm" style={{ alignSelf: "flex-start" }}>Save</button>
                </div>
              </form>
            )}

            {activeTab === "mod" && (
              <div>
                <h3 className="mb-lg">Moderation Center</h3>
                <div className="grid-2">
                  <form onSubmit={executeModeration} className="card" style={{ height: "fit-content" }}>
                    <h4 className="mb-md">Execute Action</h4>
                    <p className="text-xs mb-md" style={{ color: "var(--body)", fontStyle: "italic" }}>
                      Only members with moderation permissions (Kick Members, Ban Members, Administrator) can be targeted. Regular members are protected.
                    </p>

                    {modMsg && <div className="badge badge-success mb-md" style={{ display: "block", textAlign: "center", padding: "8px" }}>{modMsg}</div>}
                    {modError && <div className="badge badge-danger mb-md" style={{ display: "block", textAlign: "center", padding: "8px" }}>{modError}</div>}

                    <div className="flex flex-col" style={{ gap: "12px" }}>
                      <div>
                        <label className="text-xs" style={{ display: "block", fontWeight: 500, marginBottom: "4px" }}>Member User ID</label>
                        <input type="text" placeholder="e.g. 718392182749102" value={modTargetId} onChange={(e) => setModTargetId(e.target.value)} className="input input-sm" />
                      </div>
                      <div className="grid-2">
                        <div>
                          <label className="text-xs" style={{ display: "block", fontWeight: 500, marginBottom: "4px" }}>Action</label>
                          <select value={modAction} onChange={(e) => setModAction(e.target.value)} className="input input-sm">
                            <option value="timeout">Timeout</option>
                            <option value="kick">Kick</option>
                            <option value="ban">Ban</option>
                          </select>
                        </div>
                        {modAction === "timeout" && (
                          <div>
                            <label className="text-xs" style={{ display: "block", fontWeight: 500, marginBottom: "4px" }}>Duration</label>
                            <select value={modDuration} onChange={(e) => setModDuration(e.target.value)} className="input input-sm">
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
                        <label className="text-xs" style={{ display: "block", fontWeight: 500, marginBottom: "4px" }}>Reason</label>
                        <textarea placeholder="e.g. Excessive self-promotion" value={modReason} onChange={(e) => setModReason(e.target.value)} rows={2} className="input" />
                      </div>
                      <button type="submit" className="btn btn-primary btn-sm" style={{ width: "100%", justifyContent: "center" }}>Confirm Action</button>
                    </div>
                  </form>

                  <div>
                    <h4 className="mb-md">Recent Infractions</h4>
                    {warnings.length === 0 ? (
                      <div className="empty-state">
                        <p className="text-sm">No warnings logged. Server is clean!</p>
                      </div>
                    ) : (
                      <div className="flex flex-col" style={{ gap: "8px", maxHeight: "400px", overflowY: "auto" }}>
                        {warnings.map((warn) => (
                          <div key={warn.id} className="card-soft">
                            <div className="flex items-center justify-between mb-sm">
                              <strong className="text-sm">{warn.username}</strong>
                              <span className="text-xs">{warn.timestamp?.split(" ")[0]}</span>
                            </div>
                            <p className="text-xs mb-sm"><strong>Reason:</strong> {warn.reason}</p>
                            <span className="text-xs mono">by {warn.mod_name}</span>
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

      <footer style={{ borderTop: "1px solid var(--hairline)", padding: "24px 0" }}>
        <div className="page-wrapper text-center">
          <p className="text-xs">ExeGuard Control Console</p>
        </div>
      </footer>
    </div>
  );
}
