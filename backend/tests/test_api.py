import unittest
from fastapi.testclient import TestClient
from backend.main import app


class ExistingApiTests(unittest.TestCase):
    def test_existing_routes(self):
        with TestClient(app) as client:
            for path, body in (('/', {'message': 'Welcome to MarketLens!'}),
                               ('/health', {'status': 'ok'})):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), body)
