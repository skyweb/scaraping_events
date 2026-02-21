from rest_framework.routers import DefaultRouter

from .views import ScrapingWebsiteViewSet, ScrapingCategoryViewSet, ScrapingLocationViewSet

router = DefaultRouter()
router.register('websites', ScrapingWebsiteViewSet, basename='scraping-website')
router.register('categories', ScrapingCategoryViewSet, basename='scraping-category')
router.register('locations', ScrapingLocationViewSet, basename='scraping-location')

urlpatterns = router.urls
