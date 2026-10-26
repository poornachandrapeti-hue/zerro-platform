import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest

module_path = Path(__file__).resolve().parents[1] / 'command_center' / 'stores_approval_feed.py'
spec = importlib.util.spec_from_file_location('stores_feed', module_path)
import sys
stores_feed = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stores_feed
spec.loader.exec_module(stores_feed)

NOW = datetime(2026, 10, 23, 6, 0, tzinfo=timezone.utc)
def sample(**updates):
    data = dict(organization_id=1, project_id=2, source='zerrobuild.stores.material_requests',
                read_only=True, as_of=NOW.isoformat(), pending_approval_count=5,
                past_required_date_count=2, partner_origin_pending_count=3,
                pending_without_active_task_count=1, overdue_active_task_count=1,
                physical_stock_readiness='Unverified')
    data.update(updates)
    return data

class FeedTest(unittest.TestCase):
    def parse(self, payload, **kwargs):
        return stores_feed.validate_payload(payload, organization_id=1, project_id=2, now=NOW, **kwargs)
    def test_valid(self):
        self.assertEqual(self.parse(sample()).pending_approval_count, 5)
    def test_scope_isolated(self):
        with self.assertRaises(stores_feed.StoresFeedError): self.parse(sample(organization_id=6))
    def test_stale_flag(self):
        result = self.parse(sample(as_of=(NOW - timedelta(minutes=10)).isoformat()))
        self.assertTrue(result.stale)
    def test_future_timestamp_rejected(self):
        with self.assertRaises(stores_feed.StoresFeedError): self.parse(sample(as_of=(NOW + timedelta(minutes=5)).isoformat()))
    def test_no_false_stock_readiness(self):
        with self.assertRaises(stores_feed.StoresFeedError): self.parse(sample(physical_stock_readiness='Ready'))
    def test_no_bad_counts(self):
        for invalid in [-1, '3', True]:
            with self.assertRaises(stores_feed.StoresFeedError): self.parse(sample(pending_approval_count=invalid))
    def test_missing_viewer_grant_rejected_before_network(self):
        with self.assertRaises(stores_feed.StoresFeedError):
            stores_feed.fetch_stores_workload(base_url='https://example.test', service_key='secret', organization_id=1,
                project_id=2, viewer_authorized=False, opener=lambda *_a, **_k: self.fail('network attempted'))
    def test_no_plain_http(self):
        with self.assertRaises(stores_feed.StoresFeedError):
            stores_feed.fetch_stores_workload(base_url='http://example.test', service_key='secret', organization_id=1,
                project_id=2, viewer_authorized=True)

if __name__ == '__main__': unittest.main()
