import sys
import types

# Stub pymongo if missing
try:
    import pymongo  # noqa: F401
except ImportError:
    pymongo_stub = types.ModuleType("pymongo")
    class FakeCollectionForMongo(dict):
        def create_index(self, *args, **kwargs):
            pass
        def find_one(self, query):
            key = query.get('link') or query.get('comment_id')
            return self.get(key)
        def insert_one(self, item):
            key = item.get('link') or item.get('comment_id')
            self[key] = item
            return None
        def update_one(self, query, update, upsert=False):
            pass

    class FakeDatabaseForMongo:
        def __getitem__(self, name):
            # return a new collection for each requested table
            return FakeCollectionForMongo()

    class MongoClient:
        def __init__(self, *args, **kwargs):
            pass
        def __getitem__(self, name):
            # return a fake database
            return FakeDatabaseForMongo()
        def __getattr__(self, name):
            raise AttributeError(name)
    pymongo_stub.MongoClient = MongoClient
    sys.modules['pymongo'] = pymongo_stub

# Stub cfscrape if missing
try:
    import cfscrape  # noqa: F401
except ImportError:
    import requests
    cfscrape_stub = types.ModuleType('cfscrape')
    def create_scraper():
        # return an object with get/post attributes mapping to requests
        return requests
    cfscrape_stub.create_scraper = create_scraper
    sys.modules['cfscrape'] = cfscrape_stub

# Stub dotenv if missing
try:
    import dotenv  # noqa: F401
except ImportError:
    dotenv_stub = types.ModuleType('dotenv')
    def load_dotenv(path=None):
        return None
    dotenv_stub.load_dotenv = load_dotenv
    sys.modules['dotenv'] = dotenv_stub

# Now import the monitor class
from core import ForumMonitor

# Fake in-memory collection with required methods
class FakeCollection(dict):
    def create_index(self, *args, **kwargs):
        pass
    def find_one(self, query):
        key = query.get('link') or query.get('comment_id')
        return self.get(key)
    def insert_one(self, item):
        key = item.get('link') or item.get('comment_id')
        self[key] = item
        return None
    def update_one(self, query, update, upsert=False):
        pass

# Instantiate monitor with our config. Use absolute path to avoid relative path issues.
monitor = ForumMonitor(config_path=str('let-monitor-main/data/config.json'))
# Override database collections to avoid Mongo dependency
monitor.threads = FakeCollection()
monitor.comments = FakeCollection()
# Disable comments fetching for non-LET/LES sites to speed up test
monitor.fetch_comments = lambda thread: None

# Run check_lets once on configured URLs
monitor.check_lets(monitor.config.get('urls'))
print("check_lets executed on configured URLs.")
