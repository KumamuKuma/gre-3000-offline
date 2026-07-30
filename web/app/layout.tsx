import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const incoming = await headers();
  const host = incoming.get("x-forwarded-host") ?? incoming.get("host") ?? "localhost";
  const protocol = incoming.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const ogImage = `${protocol}://${host}/og.png`;
  return {
    title: "GRE 3000 Vocabulary Trainer · 原书词序",
    description: "支持 Windows、iPhone 与离线使用的 GRE 3000 词汇学习应用。",
    manifest: "/manifest.webmanifest",
    applicationName: "GRE 3000 Vocabulary Trainer",
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
      title: "GRE 3000 Vocabulary Trainer",
      description: "原书词序 · 多模式学习 · 离线可用",
      images: [{ url: ogImage, width: 1729, height: 910 }],
    },
    twitter: {
      card: "summary_large_image",
      title: "GRE 3000 Vocabulary Trainer",
      description: "原书词序 · 多模式学习 · 离线可用",
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
