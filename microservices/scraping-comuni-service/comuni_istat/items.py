import scrapy


class RegioneItem(scrapy.Item):
    nome = scrapy.Field()
    codice_istat = scrapy.Field()
    popolazione = scrapy.Field()
    popolazione_maschi = scrapy.Field()
    popolazione_femmine = scrapy.Field()
    superficie_kmq = scrapy.Field()
    densita = scrapy.Field()
    num_province = scrapy.Field()
    num_comuni = scrapy.Field()
    capoluogo = scrapy.Field()
    iso_3166_2 = scrapy.Field()
    nuts = scrapy.Field()


class ProvinciaItem(scrapy.Item):
    nome = scrapy.Field()
    regione = scrapy.Field()
    zona = scrapy.Field()
    sigla = scrapy.Field()
    codice_istat = scrapy.Field()
    popolazione = scrapy.Field()
    popolazione_maschi = scrapy.Field()
    popolazione_femmine = scrapy.Field()
    superficie_kmq = scrapy.Field()
    densita = scrapy.Field()
    num_comuni = scrapy.Field()
    capoluogo = scrapy.Field()
    iso_3166_2 = scrapy.Field()
    nuts = scrapy.Field()


class ComuneItem(scrapy.Item):
    # Dati base
    nome = scrapy.Field()
    provincia = scrapy.Field()
    regione = scrapy.Field()
    zona = scrapy.Field()
    codice_istat = scrapy.Field()
    codice_catastale = scrapy.Field()
    popolazione = scrapy.Field()
    superficie_kmq = scrapy.Field()
    densita = scrapy.Field()
    cap = scrapy.Field()
    prefisso_telefonico = scrapy.Field()
    patrono = scrapy.Field()
    festa_patronale = scrapy.Field()
    demonimo = scrapy.Field()

    # Sezioni extra (liste di stringhe)
    etimologia = scrapy.Field()
    il_comune_e = scrapy.Field()              # "Il Comune di X è:" (es. capoluogo)
    fa_parte_di = scrapy.Field()              # "Il Comune di X fa parte di:"
    localita_frazioni = scrapy.Field()        # lista frazioni
    comuni_confinanti = scrapy.Field()        # lista comuni confinanti
    musei = scrapy.Field()
    ville_palazzi = scrapy.Field()
    chiese = scrapy.Field()                   # chiese e altri edifici religiosi
    castelli_fortificazioni = scrapy.Field()
    fontane = scrapy.Field()
    giardini_orti_botanici = scrapy.Field()
    luoghi_interesse = scrapy.Field()
    teatri = scrapy.Field()
    stadi = scrapy.Field()
    eventi_feste_sagre = scrapy.Field()
    gemellaggi = scrapy.Field()               # "Il comune è gemellato con"
    stazioni_ferroviarie = scrapy.Field()
    cittadini_illustri = scrapy.Field()
