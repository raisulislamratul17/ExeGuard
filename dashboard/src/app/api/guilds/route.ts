import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]/route";

const BOT_API_URL = (process.env.DISCORD_BOT_API_URL || "http://localhost:8080").replace(/\/+$/, "");
const DASHBOARD_API_KEY = process.env.DASHBOARD_API_KEY || "";

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions) as any;
  if (!session || !session.accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // 1. Fetch user's guilds from Discord
    const userGuildsRes = await fetch("https://discord.com/api/users/@me/guilds", {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });

    if (!userGuildsRes.ok) {
      return NextResponse.json({ error: "Failed to fetch user guilds from Discord" }, { status: userGuildsRes.status });
    }

    const userGuilds = await userGuildsRes.json();

    // Filter user guilds where they have MANAGE_GUILD (0x20) or ADMINISTRATOR (0x8) permissions
    const managedGuilds = userGuilds.filter((g: any) => {
      const perms = parseInt(g.permissions);
      return (perms & 0x20) === 0x20 || (perms & 0x8) === 0x8;
    });

    // 2. Fetch bot's guilds from Render Bot API
    let botGuilds: any[] = [];
    let botApiError = "";
    try {
      console.log(`Fetching bot guilds from: ${BOT_API_URL}/api/guilds`);
      const botGuildsRes = await fetch(`${BOT_API_URL}/api/guilds`, {
        headers: {
          Authorization: `Bearer ${DASHBOARD_API_KEY}`,
        },
        cache: 'no-store'
      });
      
      if (botGuildsRes.ok) {
        botGuilds = await botGuildsRes.json();
        console.log(`Successfully fetched ${botGuilds.length} guilds from bot API`);
      } else {
        const errorText = await botGuildsRes.text();
        botApiError = `Bot API returned ${botGuildsRes.status}: ${errorText}`;
        console.error(botApiError);
      }
    } catch (err: any) {
      botApiError = `Failed to connect to Bot API at ${BOT_API_URL}: ${err.message}`;
      console.error(botApiError);
    }

    // 3. Map user guilds and cross-reference bot presence
    const mappedGuilds = managedGuilds.map((ug: any) => {
      const botInGuild = botGuilds.some((bg: any) => bg.id === ug.id);
      const iconUrl = ug.icon 
        ? `https://cdn.discordapp.com/icons/${ug.id}/${ug.icon}.png` 
        : null;

      return {
        id: ug.id,
        name: ug.name,
        icon_url: iconUrl,
        bot_in: botInGuild,
        bot_api_error: botApiError, // Pass error to frontend for debugging
        invite_url: `https://discord.com/api/oauth2/authorize?client_id=${process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID}&permissions=8&scope=bot%20applications.commands&guild_id=${ug.id}&disable_guild_select=true`
      };
    });

    return NextResponse.json(mappedGuilds);
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Internal Server Error" }, { status: 500 });
  }
}
