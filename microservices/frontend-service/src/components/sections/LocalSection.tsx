import { useEffect, useState } from "react"
import { CloudRain, CloudSun, Sun, Cloud, Snowflake, MapPin } from "lucide-react"
import { fetchLocalNews, type LocalNewsData } from "@/lib/local-news"

/* ── Mappa icone meteo ── */
const weatherIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  "cloud-rain": CloudRain,
  "cloud-sun": CloudSun,
  sun: Sun,
  cloud: Cloud,
  snowflake: Snowflake,
}

export function LocalSection() {
  const [data, setData] = useState<LocalNewsData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchLocalNews()
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  /* ── Stato di caricamento ── */
  if (error) {
    return (
      <section className="overflow-hidden rounded-sm border border-brd-light bg-white p-4">
        <p className="text-[12px] text-libero-red">{error}</p>
      </section>
    )
  }

  if (!data) {
    return (
      <section className="overflow-hidden rounded-sm border border-brd-light bg-white">
        {/* Skeleton header */}
        <header className="border-b border-brd-light">
          <div className="flex items-center gap-3 px-3 pt-3 pb-2">
            <div className="h-5 w-24 animate-pulse rounded bg-brd-light" />
            <div className="h-6 w-28 animate-pulse rounded-full bg-brd-light" />
            <div className="ml-auto h-8 w-24 animate-pulse rounded bg-brd-light" />
          </div>
          <div className="flex gap-0 border-t border-brd-light">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="h-8 w-20 animate-pulse border-r border-brd-light bg-brd-light/40" />
            ))}
          </div>
        </header>
        {/* Skeleton cards */}
        <div className="flex gap-3 p-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="w-[210px] flex-shrink-0 overflow-hidden rounded-xl border border-[#e1e2eb] bg-white sm:flex-1">
              <div className="aspect-[16/9] w-full animate-pulse bg-brd-light" />
              <div className="space-y-2 px-3 pt-2.5 pb-3">
                <div className="h-3 w-full animate-pulse rounded bg-brd-light" />
                <div className="h-3 w-3/4 animate-pulse rounded bg-brd-light" />
                <div className="h-2 w-16 animate-pulse rounded bg-brd-light" />
              </div>
            </div>
          ))}
        </div>
      </section>
    )
  }

  /* ── Icona meteo dinamica ── */
  const WeatherIcon = weatherIcons[data.weather.icon] ?? CloudRain

  return (
    <section className="overflow-hidden rounded-sm border border-brd-light bg-white">
      {/* ── Header: Città + Meteo + Nav ── */}
      <header className="border-b border-brd-light">
        {/* Riga 1: Nome città + Cambia città + Meteo */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 pt-3 pb-2">
          {/* Nome città */}
          <div className="flex items-center gap-1.5">
            <MapPin className="size-4 text-[#06c]" />
            <a
              href="#"
              className="text-[18px] font-semibold leading-tight text-[#191c22] hover:text-[#06c]"
              style={{ fontFamily: "Inter, Arial, sans-serif" }}
            >
              {data.city}
            </a>
          </div>

          {/* CTA Cambia città */}
          <a
            href="#"
            className="rounded-full bg-[#06c] px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#005bb5]"
          >
            Cambia città
          </a>

          {/* Widget Meteo */}
          <a
            href="#"
            className="ml-auto flex items-center gap-3 transition-colors hover:opacity-80"
            title={data.weather.condition}
          >
            <WeatherIcon className="size-8 text-[#06c]" />
            <div className="flex items-center gap-2.5">
              <div className="flex flex-col items-center">
                <span
                  className="text-[20px] font-bold leading-none text-[#191c22]"
                  style={{ lineHeight: 1.1 }}
                >
                  {data.weather.tempMin}°
                </span>
                <span className="text-[10px] uppercase text-[#666]">Min</span>
              </div>
              <div className="flex flex-col items-center">
                <span
                  className="text-[20px] font-bold leading-none text-[#191c22]"
                  style={{ lineHeight: 1.1 }}
                >
                  {data.weather.tempMax}°
                </span>
                <span className="text-[10px] uppercase text-[#666]">Max</span>
              </div>
            </div>
          </a>
        </div>

        {/* Riga 2: Navigazione locale */}
        <div className="scrollbar-hide flex gap-0 overflow-x-auto border-t border-brd-light">
          {data.nav.map((item, i) => (
            <a
              key={item.label}
              href={item.href}
              className={`flex-shrink-0 px-3 py-2 text-[12px] font-medium text-[#191c22] transition-colors hover:bg-[#f2f3fc] hover:text-[#06c] ${
                i < data.nav.length - 1 ? "border-r border-brd-light" : ""
              }`}
            >
              {item.label}
            </a>
          ))}
        </div>
      </header>

      {/* ── Card notizie locali — scroll orizzontale ── */}
      <div className="scrollbar-hide flex gap-3 overflow-x-auto p-3">
        {data.articles.map((article) => (
          <article
            key={article.id}
            className="w-[210px] flex-shrink-0 overflow-hidden rounded-xl border border-[#e1e2eb] bg-white sm:w-auto sm:flex-1"
          >
            <a href={article.url} className="group block">
              {/* Immagine 16:9 */}
              <div className="overflow-hidden rounded-t-xl">
                <img
                  src={article.image}
                  alt=""
                  className="aspect-[16/9] w-full object-cover transition-transform duration-300 group-hover:scale-105"
                  loading="lazy"
                />
              </div>

              {/* Titolo */}
              <div className="px-3 pt-2.5 pb-1.5">
                <h2
                  className="line-clamp-3 text-[13px] font-semibold leading-snug text-[#191c22] group-hover:text-[#06c]"
                  style={{ fontFamily: "Inter, Arial, sans-serif" }}
                >
                  {article.title}
                </h2>
              </div>
            </a>

            {/* Label categoria */}
            <div className="px-3 pb-3">
              <a
                href="#"
                className="text-[10px] font-semibold uppercase tracking-wide text-[#4a6a01] hover:underline"
              >
                {article.category}
              </a>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
