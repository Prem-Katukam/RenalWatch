import copy
import json
from pathlib import Path
import unittest
from fastapi.testclient import TestClient
from renalwatch.api import app

class APITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = json.loads(Path('example_request.json').read_text())
    def test_demo_prediction(self):
        response = self.client.post('/predict-demo', json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'synthetic_demo_only')
        self.assertGreaterEqual(response.json()['demo_score'], 0)
        self.assertLessEqual(response.json()['demo_score'], 1)
    def test_missing_signal_abstains(self):
        self.payload['observations'] = self.payload['observations'][:2]
        response = self.client.post('/predict-demo', json=self.payload)
        self.assertEqual(response.json()['status'], 'abstained')
        self.assertIsNone(response.json()['demo_score'])
    def test_invalid_unit_rejected(self):
        self.payload['observations'][0]['unit'] = 'wrong'
        response = self.client.post('/predict-demo', json=self.payload)
        self.assertEqual(response.status_code, 422)
