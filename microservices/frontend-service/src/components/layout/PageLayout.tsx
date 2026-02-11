import type { ReactNode } from "react"
import { Header } from "./Header"
import { Footer } from "./Footer"

export function PageLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-svh bg-page-bg">
      <Header />
      <div className="mx-auto max-w-[980px] px-2 py-3">
        {children}
      </div>
      <Footer />
    </div>
  )
}
