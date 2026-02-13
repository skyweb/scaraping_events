import { useEffect, useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Clock } from "lucide-react"
import { HeroSlider } from "./HeroSlider"
import { LocalSection } from "./LocalSection"
import { NewsCarousel } from "./NewsCarousel"
import type { NewsItem } from "./NewsCarousel"
import { homepageService } from "@/services/homepageService"
import type { CmsCitta, CmsArticolo } from "@/lib/cms"

/* ── Mappa colore CMS → classe Tailwind ── */
const COLORE_CSS: Record<string, string> = {
  blue: "bg-libero-blue",
  green: "bg-libero-green",
  red: "bg-libero-red",
  orange: "bg-libero-orange",
  yellow: "bg-libero-yellow",
  purple: "bg-purple-600",
}

function articoloToNewsItem(art: CmsArticolo, index: number): NewsItem {
  return {
    id: index,
    image: art.immagine,
    occhiello: art.categoria,
    occhielloColor: art.colore_categoria === "red" ? "red" : "blue",
    title: art.titolo,
    time: "",
  }
}

export function MainFeed() {
  const [cittaList, setCittaList] = useState<CmsCitta[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const list = await homepageService.getCittaList()
        const details = await Promise.all(
          list.map((c) => homepageService.getCitta(c.slug).catch(() => null))
        )
        if (!cancelled) {
          setCittaList(details.filter((c): c is CmsCitta => c !== null))
        }
      } catch {
        if (!cancelled) setCittaList([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-[300px] animate-pulse rounded-sm bg-brd-light" />
        <div className="h-[200px] animate-pulse rounded-sm bg-brd-light" />
        <div className="h-[180px] animate-pulse rounded-sm bg-brd-light" />
      </div>
    )
  }

  /* Prima sezione di ogni città → LocalSection, le restanti → carousel */
  const localBlocks = cittaList
    .filter((c) => c.sezioni.length > 0)
    .map((c) => ({
      slug: c.slug,
      nome: c.nome,
      nav: c.navigazione,
      articles: c.sezioni[0].articoli,
    }))

  const allCarousels = cittaList.flatMap((c) =>
    c.sezioni.slice(1).map((s) => ({ ...s, cittaSlug: c.slug }))
  )

  const altreNotizie = allCarousels
    .slice(0, 2)
    .flatMap((s) => s.articoli)
    .map(articoloToNewsItem)

  return (
    <div className="space-y-4">
      <HeroSlider />

      {cittaList.length === 0 && (
        <div className="rounded-sm border border-brd-light bg-white p-8 text-center text-[13px] text-txt-meta">
          No data
        </div>
      )}

      {/* ── Blocchi città (LocalSection) ── */}
      {localBlocks.map((block) => (
        <LocalSection
          key={block.slug}
          city={block.nome}
          nav={block.nav}
          articles={block.articles}
        />
      ))}

      {/* ── Carousel da tutte le città ── */}
      {allCarousels.map((sezione) => (
        <NewsCarousel
          key={`${sezione.cittaSlug}-${sezione.titolo}`}
          sectionTitle={sezione.titolo}
          sectionColor={COLORE_CSS[sezione.colore] ?? "bg-libero-blue"}
          items={sezione.articoli.map(articoloToNewsItem)}
          moreLink={sezione.link_vedi_tutti || "#"}
        />
      ))}

      {/* ── Altre notizie (lista densa) ── */}
      {altreNotizie.length > 0 && (
        <Card className="rounded-sm border-brd-light shadow-none">
          <div className="bg-bar-blue px-2.5 py-1.5">
            <span className="text-[11px] font-bold uppercase text-txt-white">Altre notizie</span>
          </div>
          <CardContent className="p-0">
            {altreNotizie.map((item, i) => (
              <div key={`list-${item.id}-${i}`}>
                <a href="#" className="group flex gap-2.5 px-2.5 py-2 transition-colors hover:bg-widget-bg">
                  <img src={item.image} alt="" className="size-[60px] flex-shrink-0 rounded-sm object-cover" />
                  <div className="min-w-0 flex-1">
                    <span className={`text-[9px] font-extrabold uppercase tracking-wide ${
                      item.occhielloColor === "red" ? "text-libero-red" : "text-libero-blue"
                    }`}>
                      {item.occhiello}
                    </span>
                    <h3 className="mt-px line-clamp-2 text-[12px] font-bold leading-tight text-txt-black group-hover:text-libero-blue">
                      {item.title}
                    </h3>
                    {item.time && (
                      <span className="mt-0.5 flex items-center gap-0.5 text-[10px] text-txt-light">
                        <Clock className="size-2.5" /> {item.time}
                      </span>
                    )}
                  </div>
                </a>
                {i < altreNotizie.length - 1 && <Separator className="bg-brd-light" />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
