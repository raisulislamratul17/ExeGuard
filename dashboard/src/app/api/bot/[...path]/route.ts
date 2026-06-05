import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]/route";

const BOT_API_URL = process.env.DISCORD_BOT_API_URL || "http://localhost:8080";
const DASHBOARD_API_KEY = process.env.DASHBOARD_API_KEY || "";

// Helper to check user guild permissions via Discord API
async function hasGuildPermission(accessToken: string, guildId: string): Promise<boolean> {
  try {
    const res = await fetch("https://discord.com/api/users/@me/guilds", {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });
    
    if (!res.ok) return false;
    const guilds = await res.json();
    
    const targetGuild = guilds.find((g: any) => g.id === guildId);
    if (!targetGuild) return false;

    // Check MANAGE_GUILD (0x20) or ADMINISTRATOR (0x8) permission
    const permissions = parseInt(targetGuild.permissions);
    const hasManageGuild = (permissions & 0x20) === 0x20;
    const hasAdmin = (permissions & 0x8) === 0x8;
    
    return hasManageGuild || hasAdmin;
  } catch (error) {
    console.error("Failed to verify guild permission:", error);
    return false;
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const session = await getServerSession(authOptions) as any;
  if (!session || !session.accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const subPath = path.join("/");
  
  // Guild security check: if fetching guild settings/warnings, verify user permission
  if (path[0] === "guilds" && path[1]) {
    const guildId = path[1];
    const isAuthorized = await hasGuildPermission(session.accessToken, guildId);
    if (!isAuthorized) {
      return NextResponse.json({ error: "Forbidden: You do not have Manage Server permissions in this guild." }, { status: 403 });
    }
  }

  try {
    const targetUrl = `${BOT_API_URL}/api/${subPath}`;
    console.log(`Proxying GET request to Bot API: ${targetUrl}`);
    const response = await fetch(targetUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${DASHBOARD_API_KEY}`,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Bot API error (${response.status}): ${errorText}`);
      try {
        const errBody = JSON.parse(errorText);
        return NextResponse.json(errBody, { status: response.status });
      } catch {
        return NextResponse.json({ error: `Bot API returned ${response.status}: ${errorText}` }, { status: response.status });
      }
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (err: any) {
    console.error(`Bot API connection error: ${err.message}`);
    return NextResponse.json({ error: `Connection Refused: Could not reach Bot API at ${BOT_API_URL}. Ensure your bot is running and DISCORD_BOT_API_URL is correct.` }, { status: 500 });
  }
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const session = await getServerSession(authOptions) as any;
  if (!session || !session.accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const subPath = path.join("/");
  
  // Guild security check: if writing guild settings/actions, verify user permission
  if (path[0] === "guilds" && path[1]) {
    const guildId = path[1];
    const isAuthorized = await hasGuildPermission(session.accessToken, guildId);
    if (!isAuthorized) {
      return NextResponse.json({ error: "Forbidden: You do not have Manage Server permissions in this guild." }, { status: 403 });
    }
  }

  try {
    const body = await req.json().catch(() => ({}));
    const targetUrl = `${BOT_API_URL}/api/${subPath}`;
    const response = await fetch(targetUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${DASHBOARD_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      return NextResponse.json(errBody || { error: "Failed to execute on Bot API" }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Bot API Connection Refused" }, { status: 500 });
  }
}
