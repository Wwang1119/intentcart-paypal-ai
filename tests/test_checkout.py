"""Offline contract tests. These mocks are NOT evidence of a sandbox payment."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

import app


def intent():
    return {"items": [{"product_id": "notebook", "quantity": 2}, {"product_id": "desk-mat", "quantity": 1}],
            "budget": "45.00", "clarification": None}


class IntentTests(unittest.TestCase):
    def test_server_calculates_total_and_budget(self):
        result = app.validate_intent(intent())
        self.assertEqual(result["total"], "42.00")
        self.assertEqual(result["items"][0]["unit_price"], "12.00")

    def test_budget_overrun_is_clarification_not_checkout(self):
        data = intent(); data["budget"] = "30.00"
        result = app.validate_intent(data)
        self.assertIn("above", result["clarification"])
        self.assertNotIn("items", result)

    def test_model_cannot_override_price(self):
        data = intent(); data["items"][0]["price"] = "0.01"
        with self.assertRaises(app.AppError): app.validate_intent(data)

    def test_unknown_duplicate_and_invalid_quantities(self):
        cases = [{"product_id": "unknown", "quantity": 1}, {"product_id": "notebook", "quantity": True},
                 {"product_id": "notebook", "quantity": 0}, {"product_id": "notebook", "quantity": 11},
                 {"product_id": [], "quantity": 1}]
        for item in cases:
            with self.subTest(item=item):
                data = intent(); data["items"][0] = item
                with self.assertRaises(app.AppError): app.validate_intent(data)
        data = intent(); data["items"].append(data["items"][0])
        with self.assertRaises(app.AppError): app.validate_intent(data)

    def test_invalid_budgets(self):
        for value in ["NaN", "Infinity", "-1", "0", "0.001", "1001"]:
            with self.subTest(value=value):
                with self.assertRaises(app.AppError): app.amount(value)

    def test_no_fake_ai_fallback(self):
        with patch.dict(app.os.environ, {"LLM_API_KEY": ""}):
            with self.assertRaises(app.AppError) as cm: app.interpret("two notebooks")
        self.assertEqual(cm.exception.code, "SETUP_REQUIRED")

    def test_truncated_ai_response_rejected(self):
        with patch.dict(app.os.environ, {"LLM_API_KEY": "test-only"}), patch("app.request_json",return_value={"choices":[{"finish_reason":"length","message":{"content":json.dumps(intent())}}]}):
            with self.assertRaises(app.AppError): app.interpret("two notebooks")


class FakePayPal:
    def __init__(self, draft_id):
        self.calls = []
        self.order = {"id": "TESTORDER12345", "status": "CREATED", "links": [{"rel":"payer-action","href":"https://www.sandbox.paypal.com/checkoutnow?token=TESTORDER12345"}],
                      "purchase_units": [{"reference_id": draft_id, "payments": {"captures": [{"id":"TESTCAPTURE123", "status":"COMPLETED", "amount":{"currency_code":"USD","value":"42.00"}, "create_time":"2026-11-09T15:00:00Z"}]}}]}
        self.approved = False

    def call(self, path, payload=None, request_id=None):
        self.calls.append((path,payload,request_id))
        result = copy.deepcopy(self.order)
        if path.endswith("/capture"):
            result["status"] = "COMPLETED"; self.order = result
        elif path.endswith("TESTORDER12345") and self.approved:
            result["status"] = "APPROVED" if self.order["status"] != "COMPLETED" else "COMPLETED"
        return result


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = app.Store(Path(self.tmp.name)/"test.sqlite3")
        self.sid = self.store.session("")[0]["id"]
        self.draft = self.store.draft(self.sid,app.validate_intent(intent()))
        self.paypal = FakePayPal(self.draft["draft_id"])

    def tearDown(self): self.tmp.cleanup()

    def create(self):
        return self.store.create(self.sid,self.draft["draft_id"],self.paypal,"http://127.0.0.1:8000")

    def test_create_uses_catalog_amounts_and_sandbox_callback(self):
        self.create(); _,payload,rid = self.paypal.calls[0]
        self.assertEqual(payload["purchase_units"][0]["amount"]["value"],"42.00")
        self.assertEqual(payload["purchase_units"][0]["items"][0]["unit_amount"]["value"],"12.00")
        self.assertEqual(payload["payment_source"]["paypal"]["experience_context"]["shipping_preference"],"NO_SHIPPING")
        self.assertTrue(rid.startswith("create-"))

    def test_double_create_reuses_order(self):
        a=self.create(); b=self.create()
        self.assertEqual(a,b); self.assertEqual(len(self.paypal.calls),1)

    def test_capture_requires_approval(self):
        self.create()
        with self.assertRaises(app.AppError): self.store.capture(self.sid,"TESTORDER12345",self.paypal)
        self.assertFalse(any(path.endswith("/capture") for path,_,_ in self.paypal.calls))

    def test_full_mock_flow_and_double_capture(self):
        self.create(); self.paypal.approved=True
        first=self.store.capture(self.sid,"TESTORDER12345",self.paypal)
        count=len(self.paypal.calls)
        second=self.store.capture(self.sid,"TESTORDER12345",self.paypal)
        self.assertEqual(first,second); self.assertEqual(first["status"],"COMPLETED")
        self.assertEqual(len(self.paypal.calls),count)

    def test_session_cannot_capture_someone_elses_order(self):
        self.create(); self.paypal.approved=True
        other=self.store.session("")[0]["id"]
        with self.assertRaises(app.AppError): self.store.capture(other,"TESTORDER12345",self.paypal)

    def test_only_sandbox_approval_links(self):
        self.paypal.order["links"][0]["href"]="https://www.paypal.com/checkoutnow?token=TEST"
        with self.assertRaises(app.AppError): self.create()

    def test_amount_currency_reference_and_capture_status_must_match(self):
        self.create(); self.paypal.approved=True
        row=self.store.get_draft(self.sid,oid="TESTORDER12345")
        data=copy.deepcopy(self.paypal.order); data["status"]="COMPLETED"
        for key,value in [("value","0.01"),("currency_code","EUR")]:
            bad=copy.deepcopy(data);bad["purchase_units"][0]["payments"]["captures"][0]["amount"][key]=value
            with self.assertRaises(app.AppError):app.verify_receipt(bad,row)
        bad=copy.deepcopy(data);bad["purchase_units"][0]["reference_id"]="another-draft"
        with self.assertRaises(app.AppError):app.verify_receipt(bad,row)
        bad=copy.deepcopy(data);bad["purchase_units"][0]["payments"]["captures"][0]["status"]="PENDING"
        with self.assertRaises(app.AppError):app.verify_receipt(bad,row)

    def test_recover_completed_capture_after_network_interruption(self):
        self.create(); self.paypal.order["status"]="COMPLETED"
        receipt=self.store.capture(self.sid,"TESTORDER12345",self.paypal)
        self.assertEqual(receipt["status"],"COMPLETED")
        self.assertFalse(any(path.endswith("/capture") for path,_,_ in self.paypal.calls))


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.server=app.make_server(0,Path(cls.tmp.name)/"test.sqlite3")
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()

    def setUp(self):
        self.opener=build_opener(HTTPCookieProcessor(CookieJar()))
        self.origin=self.server.origin
        with self.opener.open(self.origin+"/api/config") as res:self.config=json.load(res)

    def post(self,headers=None):
        hdr={"Content-Type":"application/json","Origin":self.origin,"X-CSRF-Token":self.config["csrf"]}
        hdr.update(headers or {})
        return self.opener.open(Request(self.origin+"/api/interpret",data=b'{"prompt":"two notebooks"}',headers=hdr))

    def test_cross_origin_and_missing_csrf_rejected(self):
        for hdr in [{"Origin":"https://evil.example"},{"X-CSRF-Token":""}]:
            with self.assertRaises(HTTPError) as cm:self.post(hdr)
            self.assertEqual(cm.exception.code,403)

    def test_dotenv_not_served_and_no_credentials_in_config(self):
        self.assertFalse(any("secret" in key.lower() or "api_key" in key.lower() for key in self.config))
        with self.assertRaises(HTTPError) as cm:self.opener.open(self.origin+"/.env")
        self.assertEqual(cm.exception.code,404)

    def test_http_interpret_contract(self):
        with patch("app.interpret",return_value=app.validate_intent(intent())):
            with self.post() as response:data=json.load(response)
        self.assertEqual(data["total"],"42.00");self.assertIn("draft_id",data)


if __name__ == "__main__": unittest.main()
