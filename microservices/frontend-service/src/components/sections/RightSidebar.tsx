import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { TrendingUp, TrendingDown } from "lucide-react"

/* ── Meteo ── */
const meteo = [
  { city: "Roma", temp: "18°", cond: "Sereno", icon: "☀️" },
  { city: "Milano", temp: "13°", cond: "Nuvoloso", icon: "☁️" },
  { city: "Napoli", temp: "19°", cond: "Sole", icon: "🌤️" },
  { city: "Torino", temp: "11°", cond: "Pioggia", icon: "🌧️" },
  { city: "Firenze", temp: "16°", cond: "Sereno", icon: "☀️" },
  { city: "Palermo", temp: "21°", cond: "Sole", icon: "☀️" },
]

/* ── Oroscopo ── */
const oroscopo = [
  { segno: "Ariete", simbolo: "♈", voto: "★★★★☆" },
  { segno: "Toro", simbolo: "♉", voto: "★★★★★" },
  { segno: "Gemelli", simbolo: "♊", voto: "★★★☆☆" },
  { segno: "Cancro", simbolo: "♋", voto: "★★★★☆" },
  { segno: "Leone", simbolo: "♌", voto: "★★★★★" },
  { segno: "Vergine", simbolo: "♍", voto: "★★★☆☆" },
]

/* ── Borsa ── */
const borsa = [
  { name: "FTSE MIB", val: "35.121,45", chg: "+1,24%", up: true },
  { name: "DAX", val: "18.892,10", chg: "+0,67%", up: true },
  { name: "EUR/USD", val: "1,0843", chg: "-0,12%", up: false },
  { name: "Spread", val: "118,4", chg: "-2,1", up: true },
  { name: "Petrolio", val: "82,45", chg: "+0,89%", up: true },
  { name: "Oro", val: "2.145,30", chg: "+0,34%", up: true },
]

/* ── Notizie flash sidebar ── */
const flash = [
  "Scuola: dal prossimo anno cambiano le prove Invalsi",
  "Auto: incentivi per l'elettrico prorogati fino a dicembre",
  "Superbonus: le ultime novità sulla cessione del credito",
  "Calcio: il calendario completo della Serie A",
  "Viaggi: le mete più economiche per Pasqua 2026",
]

export function RightSidebar() {
  return (
    <aside className="space-y-2">
      {/* ── Ad top sidebar ── */}
      <div className="flex h-[250px] items-center justify-center border border-ad-border bg-ad-bg">
        <div className="text-center">
          <p className="text-[9px] font-bold uppercase tracking-widest text-ad-text">ADVERTISING</p>
          <p className="text-[9px] text-ad-text">300×250</p>
        </div>
      </div>

      {/* ── Meteo widget ── */}
      <Card className="rounded-sm border-brd-light shadow-none">
        <div className="flex items-center justify-between bg-libero-blue px-2 py-1.5">
          <span className="text-[11px] font-bold uppercase text-txt-white">☁️ Meteo</span>
          <a href="#" className="text-[10px] text-bar-yellow hover:underline">tutte le città →</a>
        </div>
        <CardContent className="p-0">
          {meteo.map((m, i) => (
            <div key={m.city}>
              <div className="flex items-center justify-between px-2.5 py-[5px]">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm">{m.icon}</span>
                  <span className="text-[12px] font-bold text-txt-dark">{m.city}</span>
                </div>
                <div className="text-right">
                  <span className="text-[13px] font-bold text-txt-black">{m.temp}</span>
                  <span className="ml-1 text-[10px] text-txt-meta">{m.cond}</span>
                </div>
              </div>
              {i < meteo.length - 1 && <Separator className="bg-brd-light" />}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* ── Oroscopo widget ── */}
      <Card className="rounded-sm border-brd-light shadow-none">
        <div className="flex items-center justify-between bg-bar-yellow px-2 py-1.5">
          <span className="text-[11px] font-bold uppercase text-libero-blue">⭐ Oroscopo</span>
          <a href="#" className="text-[10px] font-bold text-libero-blue hover:underline">tutti i segni →</a>
        </div>
        <CardContent className="p-0">
          <div className="grid grid-cols-3">
            {oroscopo.map((o, i) => (
              <a
                key={o.segno}
                href="#"
                className={`flex flex-col items-center py-2 transition-colors hover:bg-widget-bg ${
                  i < 3 ? "border-b border-brd-light" : ""
                } ${i % 3 !== 2 ? "border-r border-brd-light" : ""}`}
              >
                <span className="text-lg leading-none">{o.simbolo}</span>
                <span className="mt-0.5 text-[10px] font-bold text-txt-dark">{o.segno}</span>
                <span className="text-[9px] leading-none text-libero-orange">{o.voto}</span>
              </a>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── Borsa widget ── */}
      <Card className="rounded-sm border-brd-light shadow-none">
        <div className="bg-libero-blue px-2 py-1.5">
          <span className="text-[11px] font-bold uppercase text-txt-white">📈 Borsa</span>
        </div>
        <CardContent className="p-0">
          {/* Header tabella */}
          <div className="flex items-center justify-between border-b border-brd-medium bg-widget-header px-2.5 py-1">
            <span className="text-[10px] font-bold text-txt-meta">Indice</span>
            <div className="flex gap-6">
              <span className="text-[10px] font-bold text-txt-meta">Valore</span>
              <span className="w-14 text-right text-[10px] font-bold text-txt-meta">Var%</span>
            </div>
          </div>
          {borsa.map((b, i) => (
            <div key={b.name}>
              <div className="flex items-center justify-between px-2.5 py-[4px]">
                <span className="text-[11px] font-bold text-txt-dark">{b.name}</span>
                <div className="flex items-center gap-4">
                  <span className="text-[11px] tabular-nums text-txt-dark">{b.val}</span>
                  <span className={`flex w-14 items-center justify-end gap-0.5 text-[11px] font-bold tabular-nums ${
                    b.up ? "text-libero-green" : "text-libero-red"
                  }`}>
                    {b.up ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
                    {b.chg}
                  </span>
                </div>
              </div>
              {i < borsa.length - 1 && <Separator className="bg-brd-light" />}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* ── Notizie flash ── */}
      <Card className="rounded-sm border-brd-light shadow-none">
        <div className="bg-libero-red px-2 py-1.5">
          <span className="text-[11px] font-bold uppercase text-txt-white">📌 Da non perdere</span>
        </div>
        <CardContent className="p-0">
          {flash.map((f, i) => (
            <div key={i}>
              <a
                href="#"
                className="block px-2.5 py-[5px] text-[11px] text-txt-dark transition-colors hover:bg-widget-bg hover:text-libero-blue"
              >
                » {f}
              </a>
              {i < flash.length - 1 && <Separator className="bg-brd-light" />}
            </div>
          ))}
        </CardContent>
      </Card>
    </aside>
  )
}
