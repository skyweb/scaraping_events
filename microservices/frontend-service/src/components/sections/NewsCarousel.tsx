import { useRef } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { ChevronLeft, ChevronRight } from "lucide-react"

export interface NewsItem {
  id: number
  image: string
  occhiello: string
  occhielloColor: "red" | "blue"
  title: string
  time?: string
}

interface NewsCarouselProps {
  sectionTitle: string
  sectionColor?: string          // colore header sezione
  items: NewsItem[]
  moreLink?: string
}

export function NewsCarousel({
  sectionTitle,
  sectionColor = "bg-libero-blue",
  items,
  moreLink = "#",
}: NewsCarouselProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  const scroll = (dir: "left" | "right") => {
    scrollRef.current?.scrollBy({
      left: dir === "left" ? -300 : 300,
      behavior: "smooth",
    })
  }

  return (
    <section>
      {/* Header sezione con titolo e frecce */}
      <div className="mb-1.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`h-4 w-1 rounded-sm ${sectionColor}`} />
          <h2 className="text-[13px] font-extrabold uppercase text-txt-black">{sectionTitle}</h2>
        </div>
        <div className="flex items-center gap-1">
          <a href={moreLink} className="mr-2 text-[11px] font-bold text-libero-blue hover:underline">
            Vedi tutti »
          </a>
          <button
            onClick={() => scroll("left")}
            className="rounded-sm border border-brd-light bg-card-bg p-0.5 text-txt-meta transition-colors hover:bg-widget-bg"
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            onClick={() => scroll("right")}
            className="rounded-sm border border-brd-light bg-card-bg p-0.5 text-txt-meta transition-colors hover:bg-widget-bg"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>

      {/* Carousel scroll orizzontale */}
      <div
        ref={scrollRef}
        className="scrollbar-hide -mx-1 flex gap-2 overflow-x-auto px-1 pb-1"
      >
        {items.map((item) => (
          <Card
            key={item.id}
            className="w-[200px] flex-shrink-0 overflow-hidden rounded-sm border-brd-light shadow-none sm:w-[220px] lg:w-[240px]"
          >
            <a href="#" className="group block">
              <div className="overflow-hidden">
                <img
                  src={item.image}
                  alt={item.title}
                  className="aspect-[16/10] w-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
              </div>
              <CardContent className="p-2">
                <span className={`text-[9px] font-extrabold uppercase tracking-wide ${
                  item.occhielloColor === "red" ? "text-libero-red" : "text-libero-blue"
                }`}>
                  {item.occhiello}
                </span>
                <h3 className="mt-0.5 line-clamp-3 text-[12px] font-bold leading-tight text-txt-black group-hover:text-libero-blue">
                  {item.title}
                </h3>
                {item.time && <span className="mt-1 block text-[10px] text-txt-light">{item.time}</span>}
              </CardContent>
            </a>
          </Card>
        ))}
      </div>
    </section>
  )
}
