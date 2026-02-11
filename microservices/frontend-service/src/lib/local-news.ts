export interface LocalArticle {
  id: number
  image: string
  title: string
  category: string
  url: string
}

export interface LocalNewsData {
  city: string
  weather: {
    icon: string
    condition: string
    tempMin: number
    tempMax: number
  }
  nav: { label: string; href: string }[]
  articles: LocalArticle[]
}

/**
 * Recupera i dati della sezione notizie locali dal JSON fake.
 * In produzione questo endpoint verrà sostituito con l'API reale.
 */
export async function fetchLocalNews(): Promise<LocalNewsData> {
  const response = await fetch("/api/local-news.json")

  if (!response.ok) {
    throw new Error(`Errore nel caricamento notizie locali: ${response.status}`)
  }

  return response.json() as Promise<LocalNewsData>
}
