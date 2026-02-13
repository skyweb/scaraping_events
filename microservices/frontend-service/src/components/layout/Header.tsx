import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Search, Menu, X } from "lucide-react"
import { useState } from "react"

const navItems = [
  "HOME", "NEWS", "SPORT", "ECONOMIA", "SCIENZE",
  "TECNOLOGIA", "SPETTACOLI", "MOTORI", "VIDEO", "FOTO",
]

const serviceItems = [
  { label: "MAIL", highlight: true },
  { label: "COMMUNITY" },
  { label: "METEO" },
  { label: "OROSCOPO" },
  { label: "SPORT" },
  { label: "VIDEO" },
]

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <header className="w-full">
      {/* ── Header principale: logo + search ── */}
      <div className="border-b border-brd-light bg-card-bg">
        <div className="mx-auto flex h-14 max-w-[980px] items-center justify-between px-2">
          {/* Logo placeholder */}
          <a href="/" className="flex items-center">
            <div className="flex h-9 items-center rounded-sm bg-libero-blue px-4">
              <span className="text-lg font-black tracking-tight text-txt-white">libero</span>
              <span className="ml-0.5 text-lg font-black text-bar-yellow">.</span>
              <span className="ml-1 text-[10px] font-bold text-txt-white/70">it</span>
            </div>
          </a>

          {/* Search bar */}
          <div className="relative hidden sm:block">
            <Input
              placeholder="Cerca su Libero"
              className="h-8 w-56 rounded-sm border-brd-medium bg-card-bg pl-3 pr-8 text-xs placeholder:text-txt-light"
            />
            <button className="absolute right-0 top-0 flex h-8 w-8 items-center justify-center rounded-r-sm bg-libero-blue text-txt-white">
              <Search className="size-3.5" />
            </button>
          </div>

          {/* Hamburger mobile */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="rounded-sm p-1 text-txt-dark lg:hidden"
          >
            {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {/* ── Navbar navigazione ── */}
      <div className="bg-bar-blue">
        <div className="mx-auto max-w-[980px] px-2">
          {/* Desktop */}
          <nav className="hidden h-8 items-center lg:flex">
            {navItems.map((item, i) => (
              <a
                key={item}
                href="#"
                className={`flex h-full items-center border-r border-white/20 px-3 text-[11px] font-bold tracking-wide text-txt-white transition-colors first:border-l hover:bg-white/15 ${
                  i === 0 ? "bg-white/15" : ""
                }`}
              >
                {item}
              </a>
            ))}
          </nav>

          {/* Mobile */}
          {mobileOpen && (
            <nav className="py-1 lg:hidden">
              {navItems.map((item) => (
                <a
                  key={item}
                  href="#"
                  className="block border-b border-white/10 px-3 py-2 text-[11px] font-bold text-txt-white hover:bg-white/10"
                >
                  {item}
                </a>
              ))}
            </nav>
          )}
        </div>
      </div>
    </header>
  )
}
