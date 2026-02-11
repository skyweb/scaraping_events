import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Clock } from "lucide-react"
import { HeroSlider } from "./HeroSlider"
import { LocalSection } from "./LocalSection"
import { NewsCarousel } from "./NewsCarousel"
import type { NewsItem } from "./NewsCarousel"

/* ── Dati mock per carousel tematici ── */

const newsItems: NewsItem[] = [
  { id: 1, image: "https://picsum.photos/seed/n1/480/300", occhiello: "CRONACA", occhielloColor: "red", title: "Allerta meteo in diverse regioni: piogge intense previste per domani", time: "25 min fa" },
  { id: 2, image: "https://picsum.photos/seed/n2/480/300", occhiello: "POLITICA", occhielloColor: "blue", title: "Governo, tensioni nella maggioranza: vertice a Palazzo Chigi", time: "40 min fa" },
  { id: 3, image: "https://picsum.photos/seed/n3/480/300", occhiello: "ESTERI", occhielloColor: "red", title: "USA, la Fed lascia i tassi invariati: Wall Street reagisce positivamente", time: "1 ora fa" },
  { id: 4, image: "https://picsum.photos/seed/n4/480/300", occhiello: "ECONOMIA", occhielloColor: "blue", title: "Inflazione in calo: i dati Istat confermano il trend positivo", time: "1 ora fa" },
  { id: 5, image: "https://picsum.photos/seed/n5/480/300", occhiello: "CRONACA", occhielloColor: "red", title: "Terremoto in Emilia: scossa di magnitudo 3.2, nessun danno", time: "2 ore fa" },
  { id: 6, image: "https://picsum.photos/seed/n6/480/300", occhiello: "POLITICA", occhielloColor: "blue", title: "Riforma pensioni, le novità per il 2026: chi ci guadagna", time: "2 ore fa" },
]

const sportItems: NewsItem[] = [
  { id: 10, image: "https://picsum.photos/seed/s1/480/300", occhiello: "CALCIO", occhielloColor: "red", title: "Serie A, 25ª giornata: risultati, classifica e marcatori", time: "30 min fa" },
  { id: 11, image: "https://picsum.photos/seed/s2/480/300", occhiello: "CHAMPIONS", occhielloColor: "blue", title: "Juve-Real Madrid, Thiago Motta: \"Ce la giocheremo al massimo\"", time: "1 ora fa" },
  { id: 12, image: "https://picsum.photos/seed/s3/480/300", occhiello: "FORMULA 1", occhielloColor: "red", title: "Test Bahrain: Ferrari velocissima, Leclerc primo nel Day 2", time: "2 ore fa" },
  { id: 13, image: "https://picsum.photos/seed/s4/480/300", occhiello: "TENNIS", occhielloColor: "blue", title: "Sinner vince in due set e vola ai quarti del torneo di Dubai", time: "3 ore fa" },
  { id: 14, image: "https://picsum.photos/seed/s5/480/300", occhiello: "CALCIO", occhielloColor: "red", title: "Calciomercato: le trattative dell'ultimo giorno di sessione", time: "4 ore fa" },
  { id: 15, image: "https://picsum.photos/seed/s6/480/300", occhiello: "BASKET", occhielloColor: "blue", title: "Eurolega: Olimpia Milano batte il Barcellona in trasferta", time: "5 ore fa" },
]

const techItems: NewsItem[] = [
  { id: 20, image: "https://picsum.photos/seed/t1/480/300", occhiello: "AI", occhielloColor: "blue", title: "ChatGPT compie 3 anni: come ha cambiato il modo di lavorare", time: "1 ora fa" },
  { id: 21, image: "https://picsum.photos/seed/t2/480/300", occhiello: "SMARTPHONE", occhielloColor: "red", title: "Samsung Galaxy S26: prime immagini e specifiche trapelate", time: "2 ore fa" },
  { id: 22, image: "https://picsum.photos/seed/t3/480/300", occhiello: "AUTO", occhielloColor: "blue", title: "Auto elettriche 2026: i modelli più attesi sotto i 30mila euro", time: "3 ore fa" },
  { id: 23, image: "https://picsum.photos/seed/t4/480/300", occhiello: "CYBERSECURITY", occhielloColor: "red", title: "Attenzione alla nuova truffa via SMS: come riconoscerla", time: "4 ore fa" },
  { id: 24, image: "https://picsum.photos/seed/t5/480/300", occhiello: "GAMING", occhielloColor: "blue", title: "GTA 6: Rockstar conferma la data di uscita per ottobre 2026", time: "5 ore fa" },
  { id: 25, image: "https://picsum.photos/seed/t6/480/300", occhiello: "SPAZIO", occhielloColor: "red", title: "SpaceX: il razzo Starship completa con successo il sesto volo", time: "6 ore fa" },
]

const spettacoliItems: NewsItem[] = [
  { id: 30, image: "https://picsum.photos/seed/sp1/480/300", occhiello: "CINEMA", occhielloColor: "blue", title: "Oscar 2026: le previsioni sui favoriti e le sorprese attese", time: "1 ora fa" },
  { id: 31, image: "https://picsum.photos/seed/sp2/480/300", occhiello: "TV", occhielloColor: "red", title: "Ascolti TV ieri: chi ha vinto la prima serata di lunedì", time: "2 ore fa" },
  { id: 32, image: "https://picsum.photos/seed/sp3/480/300", occhiello: "MUSICA", occhielloColor: "blue", title: "Sanremo 2026: i nomi dei big in gara e le prime anticipazioni", time: "3 ore fa" },
  { id: 33, image: "https://picsum.photos/seed/sp4/480/300", occhiello: "GOSSIP", occhielloColor: "red", title: "La coppia dell'anno si è lasciata: l'annuncio sui social", time: "4 ore fa" },
  { id: 34, image: "https://picsum.photos/seed/sp5/480/300", occhiello: "SERIE TV", occhielloColor: "blue", title: "Le serie TV da vedere a febbraio: la guida completa", time: "5 ore fa" },
  { id: 35, image: "https://picsum.photos/seed/sp6/480/300", occhiello: "LIBRI", occhielloColor: "red", title: "I libri più venduti della settimana: la classifica aggiornata", time: "6 ore fa" },
]

/* ── Dati tabs ── */
const tabData: Record<string, { title: string; time: string }[]> = {
  ultimi: [
    { title: "Scossa di terremoto avvertita in Emilia: magnitudo 3.1", time: "8 min" },
    { title: "Sciopero treni 12 febbraio: orari e fasce garantite", time: "15 min" },
    { title: "Calcio, infortunio per il capitano della Nazionale", time: "22 min" },
    { title: "Previsioni meteo: sole nel weekend su tutta Italia", time: "30 min" },
    { title: "Prezzo benzina oggi: le quotazioni aggiornate", time: "45 min" },
    { title: "Pensioni febbraio 2026: cedolino e date di pagamento", time: "1 ora" },
  ],
  letti: [
    { title: "Pensioni, ecco gli importi: la tabella completa", time: "45k" },
    { title: "Bonus 2026: la lista aggiornata degli incentivi", time: "38k" },
    { title: "Bollette luce e gas: come risparmiare 400€ l'anno", time: "28k" },
    { title: "Classifica Serie A: la lotta scudetto aggiornata", time: "25k" },
    { title: "Oroscopo 11 febbraio: previsioni segno per segno", time: "21k" },
    { title: "Dieta: il trucco per perdere 3 kg in una settimana", time: "18k" },
  ],
}

export function MainFeed() {
  return (
    <div className="space-y-4">
      {/* ── HERO SLIDER con scroll orizzontale ── */}
      <HeroSlider />

      {/* ── Sezione locale Roma ── */}
      <LocalSection />

      {/* ── Ad leaderboard ── */}
      <div className="flex h-[60px] items-center justify-center border border-ad-border bg-ad-bg">
        <span className="text-[9px] font-bold uppercase tracking-widest text-ad-text">
          ADVERTISING — 728×60
        </span>
      </div>

      {/* ── Tabs: Ultima Ora / Più Letti ── */}
      <Card className="rounded-sm border-brd-light shadow-none">
        <Tabs defaultValue="ultimi">
          <TabsList className="h-auto w-full justify-start gap-0 rounded-none border-b border-brd-light bg-widget-header p-0">
            <TabsTrigger
              value="ultimi"
              className="rounded-none px-3 py-1.5 text-[11px] font-bold uppercase data-[state=active]:bg-card-bg data-[state=active]:text-libero-blue data-[state=active]:shadow-none"
            >
              ⚡ Ultima ora
            </TabsTrigger>
            <TabsTrigger
              value="letti"
              className="rounded-none px-3 py-1.5 text-[11px] font-bold uppercase data-[state=active]:bg-card-bg data-[state=active]:text-libero-blue data-[state=active]:shadow-none"
            >
              📊 Più letti
            </TabsTrigger>
          </TabsList>

          {Object.entries(tabData).map(([key, items]) => (
            <TabsContent key={key} value={key} className="mt-0">
              {items.map((item, i) => (
                <div key={i}>
                  <a href="#" className="flex items-start gap-2 px-3 py-[6px] transition-colors hover:bg-widget-bg">
                    <span className="mt-px flex size-[18px] flex-shrink-0 items-center justify-center rounded-sm bg-libero-blue text-[9px] font-bold text-txt-white">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] leading-snug text-txt-black hover:text-libero-blue">{item.title}</p>
                      <span className="text-[10px] text-txt-light">{item.time}</span>
                    </div>
                  </a>
                  {i < items.length - 1 && <Separator className="bg-brd-light" />}
                </div>
              ))}
            </TabsContent>
          ))}
        </Tabs>
      </Card>

      {/* ── CAROUSEL: Notizie ── */}
      <NewsCarousel sectionTitle="Notizie" sectionColor="bg-libero-blue" items={newsItems} />

      {/* ── CAROUSEL: Sport ── */}
      <NewsCarousel sectionTitle="Sport" sectionColor="bg-libero-green" items={sportItems} />

      {/* ── Ad mid-content ── */}
      <div className="flex h-[90px] items-center justify-center border border-ad-border bg-ad-bg">
        <span className="text-[9px] font-bold uppercase tracking-widest text-ad-text">
          ADVERTISING — 728×90
        </span>
      </div>

      {/* ── CAROUSEL: Tecnologia ── */}
      <NewsCarousel sectionTitle="Tecnologia" sectionColor="bg-libero-orange" items={techItems} />

      {/* ── CAROUSEL: Spettacoli ── */}
      <NewsCarousel sectionTitle="Spettacoli" sectionColor="bg-libero-red" items={spettacoliItems} />

      {/* ── Top news lista densa (sotto i carousel) ── */}
      <Card className="rounded-sm border-brd-light shadow-none">
        <div className="bg-bar-blue px-2.5 py-1.5">
          <span className="text-[11px] font-bold uppercase text-txt-white">Altre notizie</span>
        </div>
        <CardContent className="p-0">
          {[...newsItems, ...sportItems.slice(0, 2)].map((item, i) => (
            <div key={`list-${item.id}`}>
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
                  <span className="mt-0.5 flex items-center gap-0.5 text-[10px] text-txt-light">
                    <Clock className="size-2.5" /> {item.time}
                  </span>
                </div>
              </a>
              {i < 7 && <Separator className="bg-brd-light" />}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
