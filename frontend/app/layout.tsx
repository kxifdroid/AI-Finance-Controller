import type { Metadata } from "next";
import { Navbar } from "@/components/navbar";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/lib/theme-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Finance Controller — Multi-source Reconciliation Agent",
  description: "Enterprise multi-source financial reconciliation pipeline with deterministic candidate scoring, AI-assisted verification, and ground-truth evaluation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-background text-content min-h-screen flex flex-col antialiased transition-colors duration-150">
        <ThemeProvider>
          <AuthProvider>
            <Navbar />
            <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
              {children}
            </main>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

