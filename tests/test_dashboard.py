import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app


class TestDashboard(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_dashboard_root_serves_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("PRAMAAN RAKSHAK", response.text)
        self.assertIn("Upload Evidence", response.text)

    def test_static_files_served(self):
        css_res = self.client.get("/static/css/style.css")
        self.assertEqual(css_res.status_code, 200)
        self.assertIn("PRAMAAN RAKSHAK", css_res.text)

        js_res = self.client.get("/static/js/app.js")
        self.assertEqual(js_res.status_code, 200)
        self.assertIn("DOMContentLoaded", js_res.text)


if __name__ == "__main__":
    unittest.main()
