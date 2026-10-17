import unittest
from fastapi.testclient import TestClient

import docchase
from server import app


class TestGuardrails(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.expected_off_topic = (
            "I can only help with open mortgage and healthcare exception cases. "
            "Ask me what's missing, the context, or what to decide."
        )
        self.expected_unclear = "sorry, say that again?"

    # --- Tests for docchase.py answer path ---
    def test_docchase_tell_me_about_pasta(self):
        ans = docchase.answer("tell me about pasta")
        self.assertEqual(ans, self.expected_off_topic)

    def test_docchase_whats_the_weather(self):
        ans = docchase.answer("what's the weather")
        self.assertEqual(ans, self.expected_off_topic)

    def test_docchase_hello(self):
        ans = docchase.answer("hello")
        self.assertEqual(ans, self.expected_unclear)

    def test_docchase_empty_text(self):
        ans = docchase.answer("")
        self.assertEqual(ans, self.expected_unclear)

    def test_docchase_valid_in_scope(self):
        ans = docchase.answer("CASE-101", "missing")
        self.assertIn("borrower signature is missing", ans)

    # --- Tests for server.py /ask endpoint ---
    def test_server_ask_tell_me_about_pasta(self):
        resp = self.client.post("/ask", json={"text": "tell me about pasta"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["answer"], self.expected_off_topic)
        self.assertIsNone(data["question_type"])

    def test_server_ask_whats_the_weather(self):
        resp = self.client.post("/ask", json={"text": "what's the weather"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["answer"], self.expected_off_topic)
        self.assertIsNone(data["question_type"])

    def test_server_ask_hello(self):
        resp = self.client.post("/ask", json={"text": "hello"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["answer"], self.expected_unclear)
        self.assertIsNone(data["question_type"])

    def test_server_ask_empty_text(self):
        resp = self.client.post("/ask", json={"text": ""})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["answer"], self.expected_unclear)
        self.assertIsNone(data["question_type"])

    def test_server_ask_no_default_case_fallback(self):
        # Even with valid question type, if no case is named and no last_case_id, never fall back to default case
        resp = self.client.post("/ask", json={"text": "what is missing"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["answer"], self.expected_off_topic)

    def test_server_ask_valid_in_scope(self):
        resp = self.client.post("/ask", json={"text": "what is missing in case 101"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["case_id"], "CASE-101")
        self.assertEqual(data["question_type"], "missing")
        self.assertIn("borrower signature is missing", data["answer"])

    def test_server_ask_session_last_case_id(self):
        resp = self.client.post(
            "/ask",
            json={"text": "what about the decision", "last_case_id": "CASE-101"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["case_id"], "CASE-101")
        self.assertEqual(data["question_type"], "decision")
        self.assertIn("Past evidence confirmed the required signature", data["answer"])

    def test_server_ask_off_topic_with_session_case(self):
        # Even if session has last_case_id, off-topic questions must still return fixed reply
        resp = self.client.post(
            "/ask",
            json={"text": "tell me about pasta", "last_case_id": "CASE-101"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["answer"], self.expected_off_topic)

    # --- Tests for PDF, Document and Domain Questions (No false-positive guardrails) ---
    def test_server_ask_pdf_domain_query(self):
        resp = self.client.post(
            "/ask",
            json={"text": "please go through the pdf and tell me what domain does this belong to"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertNotEqual(data["answer"], self.expected_off_topic)
        self.assertIn("domain", data["answer"].lower())

    def test_server_ask_pdf_domain_healthcare(self):
        resp = self.client.post(
            "/ask",
            json={
                "text": "please go through the pdf and tell me what domain does this belong to",
                "domain": "healthcare",
                "active_sample_file": "INS-H101.pdf"
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertNotEqual(data["answer"], self.expected_off_topic)
        self.assertIn("healthcare", data["answer"].lower())

    def test_server_ask_pdf_specific_case(self):
        resp = self.client.post(
            "/ask",
            json={"text": "what domain is case 104"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertNotEqual(data["answer"], self.expected_off_topic)
        self.assertIn("mortgage", data["answer"].lower())
        self.assertIn("CASE-104", data["answer"])

    def test_docchase_pdf_domain_query(self):
        ans = docchase.answer("please go through the pdf and tell me what domain does this belong to")
        self.assertNotEqual(ans, self.expected_off_topic)
        self.assertIn("domain", ans.lower())


if __name__ == "__main__":
    unittest.main()
