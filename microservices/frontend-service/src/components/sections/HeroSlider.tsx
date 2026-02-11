import { useRef, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface Slide {
  id: number
  image: string
  category: string
  title: string
  excerpt: string
}

const slides: Slide[] = [
  {
    id: 1,
    image: "https://picsum.photos/seed/hero1/900/500",
    category: "ULTIMA ORA",
    title: "Vertice Europeo, raggiunto l'accordo storico sulla difesa comune",
    excerpt: "I leader dei 27 approvano il piano strategico. Stanziati 150 miliardi in 5 anni.",
  },
  {
    id: 2,
    image: "https://picsum.photos/seed/hero2/900/500",
    category: "POLITICA",
    title: "Governo, tensioni sulla manovra: vertice a Palazzo Chigi",
    excerpt: "Il premier convoca i capigruppo per trovare un accordo sul decreto fiscale.",
  },
  {
    id: 3,
    image: "https://picsum.photos/seed/hero3/900/500",
    category: "SPORT",
    title: "Champions League, sorteggio quarti: Juventus-Real Madrid e Inter-PSG",
    excerpt: "Le italiane pescano avversari di altissimo livello. Andata il 2 aprile.",
  },
  {
    id: 4,
    image: "https://picsum.photos/seed/hero4/900/500",
    category: "ECONOMIA",
    title: "Borsa Milano a +1,8%, lo spread scende sotto i 115 punti",
    excerpt: "Trainati dai bancari, i mercati europei chiudono la settimana in positivo.",
  },
  {
    id: 5,
    image: "https://picsum.photos/seed/hero5/900/500",
    category: "CRONACA",
    title: "Maltempo al Centro-Sud, allerta rossa in cinque regioni",
    excerpt: "Piogge intense e venti forti previsti per le prossime 48 ore. Scuole chiuse.",
  },
]

export function HeroSlider() {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)

  const scrollTo = (index: number) => {
    const el = scrollRef.current
    if (!el) return
    const child = el.children[index] as HTMLElement
    if (child) {
      el.scrollTo({ left: child.offsetLeft, behavior: "smooth" })
      setActive(index)
    }
  }

  const prev = () => scrollTo(active === 0 ? slides.length - 1 : active - 1)
  const next = () => scrollTo(active === slides.length - 1 ? 0 : active + 1)

  return (
    <section className="relative">
      {/* Container scroll orizzontale */}
      <div
        ref={scrollRef}
        onScroll={() => {
          const el = scrollRef.current
          if (!el) return
          // snap detection
          const children = Array.from(el.children) as HTMLElement[]
          let closest = 0
          let minDist = Infinity
          children.forEach((child, i) => {
            const dist = Math.abs(child.offsetLeft - el.scrollLeft)
            if (dist < minDist) { minDist = dist; closest = i }
          })
          setActive(closest)
        }}
        className="scrollbar-hide flex snap-x snap-mandatory gap-2 overflow-x-auto"
      >
        {slides.map((slide) => (
          <a
            key={slide.id}
            href="#"
            className="group relative w-[85%] flex-shrink-0 snap-start overflow-hidden rounded-sm sm:w-[70%] lg:w-[65%]"
          >
            <img
              src={slide.image}
              alt={slide.title}
              className="aspect-[16/9] w-full object-cover"
            />
            {/* Overlay gradiente + testo */}
            <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/80 via-black/30 to-transparent p-4 md:p-5">
              <span className="mb-1 w-fit rounded-sm bg-libero-red px-1.5 py-0.5 text-[10px] font-extrabold uppercase text-txt-white">
                {slide.category}
              </span>
              <h2 className="text-base font-bold leading-tight text-white group-hover:underline md:text-xl lg:text-[22px]">
                {slide.title}
              </h2>
              <p className="mt-1 line-clamp-2 text-[12px] text-white/75 md:text-[13px]">
                {slide.excerpt}
              </p>
            </div>
          </a>
        ))}
      </div>

      {/* Frecce navigazione */}
      <button
        onClick={prev}
        className="absolute left-2 top-1/2 z-10 hidden -translate-y-1/2 rounded-sm bg-black/50 p-1.5 text-white transition-colors hover:bg-black/70 md:block"
      >
        <ChevronLeft className="size-5" />
      </button>
      <button
        onClick={next}
        className="absolute right-2 top-1/2 z-10 hidden -translate-y-1/2 rounded-sm bg-black/50 p-1.5 text-white transition-colors hover:bg-black/70 md:block"
      >
        <ChevronRight className="size-5" />
      </button>

      {/* Dots indicatore */}
      <div className="mt-2 flex justify-center gap-1.5">
        {slides.map((_, i) => (
          <button
            key={i}
            onClick={() => scrollTo(i)}
            className={`h-[3px] rounded-sm transition-all ${
              i === active ? "w-5 bg-libero-blue" : "w-3 bg-brd-medium"
            }`}
          />
        ))}
      </div>
    </section>
  )
}
