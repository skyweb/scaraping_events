/* ── Tipi API CMS ── */

export interface CmsArticolo {
  titolo: string
  immagine: string
  categoria: string
  colore_categoria: string
  url: string
}

export interface CmsSezione {
  titolo: string
  colore: string
  link_vedi_tutti: string
  articoli: CmsArticolo[]
}

export interface CmsCitta {
  nome: string
  slug: string
  navigazione: { label: string; url: string }[]
  sezioni: CmsSezione[]
}

export interface CmsCittaListItem {
  nome: string
  slug: string
}
