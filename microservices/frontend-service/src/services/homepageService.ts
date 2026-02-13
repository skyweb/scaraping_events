import { get } from "@/lib/api"
import type { CmsCitta, CmsCittaListItem } from "@/lib/cms"

/**
 * Service per i dati homepage (pagine città, sezioni, articoli).
 * Centralizza tutte le chiamate API CMS per la homepage.
 */
export const homepageService = {
  /** Lista delle città attive. */
  getCittaList(): Promise<CmsCittaListItem[]> {
    return get<CmsCittaListItem[]>("/cms/citta/")
  },

  /** Configurazione completa di una città (navigazione + sezioni + articoli). */
  getCitta(slug: string): Promise<CmsCitta> {
    return get<CmsCitta>(`/cms/citta/${slug}/`)
  },
}
