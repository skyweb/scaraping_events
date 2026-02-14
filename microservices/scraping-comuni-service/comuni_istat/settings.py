BOT_NAME = "comuni_istat"

SPIDER_MODULES = ["comuni_istat.spiders"]
NEWSPIDER_MODULE = "comuni_istat.spiders"

# Rispetto del server
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 1.5

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10

ROBOTSTXT_OBEY = True

ITEM_PIPELINES = {
    "comuni_istat.pipelines.JsonExportPipeline": 300,
}

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

LOG_LEVEL = "INFO"
