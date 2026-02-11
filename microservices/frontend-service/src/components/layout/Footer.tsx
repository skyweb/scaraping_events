import { Separator } from "@/components/ui/separator"

const footerLinks = [
  "Chi siamo", "Contatti", "Pubblicità", "Disclaimer",
  "Privacy", "Cookie Policy", "Preferenze cookie",
]

const siteLinks = [
  "Notizie", "Sport", "Economia", "Tecnologia",
  "Spettacoli", "Motori", "Meteo", "Oroscopo",
]

export function Footer() {
  return (
    <footer className="border-t border-brd-medium bg-card-bg">
      <div className="mx-auto max-w-[980px] px-2 py-4">
        {/* Logo */}
        <div className="mb-3 flex items-center">
          <div className="flex h-6 items-center rounded-sm bg-libero-blue px-2">
            <span className="text-xs font-black text-txt-white">libero</span>
            <span className="text-xs font-black text-bar-yellow">.</span>
            <span className="ml-0.5 text-[9px] font-bold text-txt-white/70">it</span>
          </div>
        </div>

        {/* Mappa sito */}
        <div className="mb-3 flex flex-wrap gap-x-1 gap-y-0.5">
          {siteLinks.map((link, i) => (
            <span key={link} className="flex items-center">
              <a href="#" className="text-[11px] text-libero-blue hover:underline">{link}</a>
              {i < siteLinks.length - 1 && (
                <span className="ml-1 text-[11px] text-brd-medium">|</span>
              )}
            </span>
          ))}
        </div>

        <Separator className="mb-3 bg-brd-light" />

        {/* Link legali */}
        <div className="mb-2 flex flex-wrap gap-x-1 gap-y-0.5">
          {footerLinks.map((link, i) => (
            <span key={link} className="flex items-center">
              <a href="#" className="text-[10px] text-txt-meta hover:underline">{link}</a>
              {i < footerLinks.length - 1 && (
                <span className="ml-1 text-[10px] text-brd-medium">|</span>
              )}
            </span>
          ))}
        </div>

        <p className="text-[10px] leading-snug text-txt-light">
          &copy; {new Date().getFullYear()} Italiaonline S.p.A. — Sede legale: Via del Bosco Rinnovato 8/Building A, 20057 Assago (MI) —
          P.IVA 03970540963 — Tutti i diritti riservati.
        </p>
      </div>
    </footer>
  )
}
