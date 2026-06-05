import GuildSettingsClient from "./client";

export default async function GuildSettingsPage({
  params,
}: {
  params: Promise<{ guildId: string }>;
}) {
  const { guildId } = await params;
  return <GuildSettingsClient guildId={guildId} />;
}
