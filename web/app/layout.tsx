import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const incoming = await headers();
  const host = incoming.get("x-forwarded-host") ?? incoming.get("host") ?? "localhost";
  const protocol = incoming.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const ogImage = `${protocol}://${host}/og.png`;
  return {
    title: "GRE 3000 · 原书词序离线学习",
    description: "可安装到 iPhone 主屏幕的 GRE 3000 词离线学习应用。",
    manifest: "/manifest.webmanifest",
    applicationName: "GRE 3000",
    appleWebApp: {
      capable: true,
      statusBarStyle: "black-translucent",
      title: "GRE 3000",
    },
    icons: {
      icon: "/icon.svg",
      apple: "/apple-touch-icon.png",
    },
    openGraph: {
      type: "website",
      title: "GRE 3000",
      description: "原书词序 · 离线学习",
      images: [{ url: ogImage, width: 1734, height: 907 }],
    },
    twitter: {
      card: "summary_large_image",
      title: "GRE 3000",
      description: "原书词序 · 离线学习",
      images: [ogImage],
    },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#17223b",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
