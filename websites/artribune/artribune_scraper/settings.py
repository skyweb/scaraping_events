# Scrapy settings for artribune_scraper project

BOT_NAME = "artribune_scraper"

SPIDER_MODULES = ["artribune_scraper.spiders"]
NEWSPIDER_MODULE = "artribune_scraper.spiders"

# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Concurrency and throttling settings
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 1.5

# Configure item pipelines
ITEM_PIPELINES = {
   "artribune_scraper.pipelines.ArtribunePipeline": 300,
}

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"
