import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "ExeGuard | Futuristic Discord Server Protection",
  description: "Secure your Discord server with state-of-the-art anti-nuke, anti-raid, and advanced automod configurations.",
  icons: {
    icon: "/favicon.ico",
  }
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="glow-spot-2"></div>
          {children}
        </Providers>
      </body>
    </html>
  );
}
