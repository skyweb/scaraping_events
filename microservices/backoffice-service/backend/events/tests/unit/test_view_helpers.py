from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from events.views import (
    CACHE_VERSION_KEY,
    PlanFieldFilterMixin,
    _get_cache_version,
    _invalidate_external_cache,
)


class _ParentLifecycleView:
    def perform_create(self, serializer):
        serializer.parent_create_called = True

    def perform_update(self, serializer):
        serializer.parent_update_called = True

    def perform_destroy(self, instance):
        instance.parent_destroy_called = True


class DummyPlanLifecycleView(PlanFieldFilterMixin, _ParentLifecycleView):
    pass


class ExternalViewHelpersTest(TestCase):
    def setUp(self):
        cache.delete(CACHE_VERSION_KEY)

    def test_get_cache_version_initializes_counter(self):
        version = _get_cache_version()

        self.assertEqual(version, 1)
        self.assertEqual(cache.get(CACHE_VERSION_KEY), 1)

    def test_invalidate_external_cache_increments_counter(self):
        cache.set(CACHE_VERSION_KEY, 1, timeout=None)

        _invalidate_external_cache()

        self.assertEqual(cache.get(CACHE_VERSION_KEY), 2)

    def test_invalidate_external_cache_resets_counter_when_missing(self):
        with patch("django.core.cache.cache.incr", side_effect=ValueError):
            _invalidate_external_cache()

        self.assertEqual(cache.get(CACHE_VERSION_KEY), 1)

    def test_plan_field_filter_mixin_invalidates_cache_after_create_update_destroy(self):
        view = DummyPlanLifecycleView()
        serializer = MagicMock()
        instance = MagicMock()

        with patch("events.views._invalidate_external_cache") as mocked_invalidate:
            view.perform_create(serializer)
            view.perform_update(serializer)
            view.perform_destroy(instance)

        self.assertTrue(serializer.parent_create_called)
        self.assertTrue(serializer.parent_update_called)
        self.assertTrue(instance.parent_destroy_called)
        self.assertEqual(mocked_invalidate.call_count, 3)
