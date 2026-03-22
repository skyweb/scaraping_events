from rest_framework.routers import DefaultRouter

from .views import ScrapingWebsiteViewSet, CategoryViewSet, LocationViewSet

router = DefaultRouter()
router.register('websites', ScrapingWebsiteViewSet, basename='scraping-website')
router.register('categories', CategoryViewSet, basename='scraping-category')
router.register('locations', LocationViewSet, basename='scraping-location')

urlpatterns = router.urls
