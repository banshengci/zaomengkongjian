import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "造梦空间 DreamSpace",
  description: "建立在造梦人物智能之上的故事剧场",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="topbar">
          <a href="/" className="brand">
            造梦空间
          </a>
          <nav>
            <a href="/">书卷</a>
            <a href="/chapters">章节</a>
            <a href="/crossover">群英会</a>
            <a href="/settings">模型</a>
            <a href="/bridge">桥接</a>
          </nav>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
