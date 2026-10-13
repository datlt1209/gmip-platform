import type { Metadata } from "next";
import Header from "@/components/Header";
import "./globals.css";

export const metadata: Metadata = {
  title: "GMIP – Theo dõi chỉ số kinh tế thế giới",
  description: "Dashboard vĩ mô toàn cầu và báo cáo kinh tế hàng ngày bằng tiếng Việt.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <Header />
        {children}
      </body>
    </html>
  );
}
