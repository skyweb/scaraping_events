import { MapPin } from "lucide-react"
import type { CmsArticolo } from "@/lib/cms"

interface LocalSectionProps {
  city: string
  nav: { label: string; url: string }[]
  articles: CmsArticolo[]
}

export function LocalSection({ city, nav, articles }: LocalSectionProps) {
  if (articles.length === 0 && nav.length === 0) {
    return (
      <section className="overflow-hidden rounded-sm border border-brd-light bg-white p-4">
        <p className="text-center text-[12px] text-txt-meta">No data</p>
      </section>
    )
  }

  return (
    <section className="overflow-hidden rounded-sm border border-brd-light bg-white">
      {/* ── Header: Città + Nav ── */}
      <header className="border-b border-brd-light">
        {/* Riga 1: Nome città */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 pt-3 pb-2">
          <div className="flex items-center gap-1.5">
            <MapPin className="size-4 text-[#06c]" />
            <a
              href="#"
              className="text-[18px] font-semibold leading-tight text-[#191c22] hover:text-[#06c]"
              style={{ fontFamily: "Inter, Arial, sans-serif" }}
            >
              {city}
            </a>
          </div>
        </div>

        {/* Riga 2: Navigazione locale */}
        {nav.length > 0 && (
          <div className="scrollbar-hide flex gap-0 overflow-x-auto border-t border-brd-light">
            {nav.map((item, i) => (
              <a
                key={item.label}
                href={item.url}
                className={`flex-shrink-0 px-3 py-2 text-[12px] font-medium text-[#191c22] transition-colors hover:bg-[#f2f3fc] hover:text-[#06c] ${
                  i < nav.length - 1 ? "border-r border-brd-light" : ""
                }`}
              >
                {item.label}
              </a>
            ))}
          </div>
        )}
      </header>

      {/* ── Card notizie locali — scroll orizzontale ── */}
      {articles.length > 0 ? (
        <div className="scrollbar-hide flex gap-3 overflow-x-auto p-3">
          {articles.map((article, i) => (
            <article
              key={i}
              className="w-[210px] flex-shrink-0 overflow-hidden rounded-xl border border-[#e1e2eb] bg-white sm:w-auto sm:flex-1"
            >
              <a href={article.url} className="group block">
                <div className="overflow-hidden rounded-t-xl">
                  <img
                    src={article.immagine}
                    alt=""
                    className="aspect-[16/9] w-full object-cover transition-transform duration-300 group-hover:scale-105"
                    loading="lazy"
                  />
                </div>
                <div className="px-3 pt-2.5 pb-1.5">
                  <h2
                    className="line-clamp-3 text-[13px] font-semibold leading-snug text-[#191c22] group-hover:text-[#06c]"
                    style={{ fontFamily: "Inter, Arial, sans-serif" }}
                  >
                    {article.titolo}
                  </h2>
                </div>
              </a>
              <div className="px-3 pb-3">
                <span className="text-[10px] font-semibold uppercase tracking-wide text-[#4a6a01]">
                  {article.categoria}
                </span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="p-4 text-center text-[12px] text-txt-meta">No data</div>
      )}
    </section>
  )
}
