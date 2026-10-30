"""Suivi client: liens temporaires, révocation, URLs de visionnement sûres."""
import datetime
import unittest

from flask import Flask, render_template_string

from live_print import _source_url, register_live_print


class MemoryConnection:
    def __init__(self, state):
        self.state=state
        self.statement=""
        self.params=()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=()):
        self.statement=statement
        self.params=params
        return self

    def fetchone(self):
        if "UPDATE private_quotes" in self.statement:
            if "SET live_enabled=FALSE" in self.statement:
                quote_id=self.params[0]
                if quote_id != 1:
                    return None
                self.state.update(token=None, url=None, enabled=False, expires=None)
                return {"id": quote_id}
            url,token,expires,quote_id=self.params
            if quote_id != 1:
                return None
            self.state.update(token=token,url=url,enabled=True,expires=expires)
            return {"id": quote_id}
        if "FROM private_quotes" in self.statement:
            token=self.params[0]
            if (self.state.get("enabled") and token==self.state.get("token")
                    and self.state["expires"]>datetime.datetime.now(datetime.timezone.utc)):
                return {"id": 1, "live_url":self.state["url"]}
        return None


class LivePrintTests(unittest.TestCase):
    def setUp(self):
        self.state={"token":None,"url":None,"enabled":False,"expires":None}
        self.app=Flask(__name__)
        self.app.secret_key="test-only"
        register_live_print(self.app, lambda:MemoryConnection(self.state),
                            lambda f:f,lambda:None,
                            lambda title,body,**kwargs:render_template_string(body,**kwargs))
        self.client=self.app.test_client()

    def test_approved_external_video_providers_only(self):
        url,embed=_source_url("https://www.youtube.com/live/Abc123_9-Zk")
        self.assertEqual(url, "https://www.youtube.com/live/Abc123_9-Zk")
        self.assertEqual(embed,"https://www.youtube-nocookie.com/embed/Abc123_9-Zk")
        self.assertEqual(_source_url("https://oe.ink/l/limited-view")[1],None)
        for url in ("http://oe.ink/l/limited-view",
                    "https://192.168.0.17:322/streaming/live/1",
                    "https://evil-octoeverywhere.com/live/test",
                    "https://oe.ink@evil.test/l/limited-view",
                    "https://www.youtube.com/redirect?u=https://evil.test",
                    "https://www.youtube.com/live/short",
                    "javascript:alert(1)"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _source_url(url)

    def test_live_access_revoke_and_new_token(self):
        invalid=self.client.post("/admin/soumissions-pro/1/diffusion",
                                 data={"live_action":"enable","live_url":"https://localhost/camera",
                                       "live_hours":"24"})
        self.assertEqual(invalid.status_code,400)
        response=self.client.post("/admin/soumissions-pro/1/diffusion",
                                  data={"live_action":"enable","live_url":"https://oe.ink/l/test-camera",
                                        "live_hours":"24"})
        self.assertEqual(response.status_code,302)
        first_token=self.state["token"]
        self.assertGreater(len(first_token),40)
        result=self.client.get("/suivi-impression/"+first_token)
        self.assertEqual(result.status_code,200)
        self.assertIn(b"oe.ink/l/test-camera",result.data)
        self.assertIn(b"FJ-00001",result.data)
        self.assertIn(b"no-store",result.headers["Cache-Control"].encode())
        self.assertEqual(result.headers["Referrer-Policy"],"no-referrer")
        self.assertEqual(result.headers["X-Robots-Tag"],"noindex, nofollow, noarchive")
        self.assertNotIn(b"Client test",result.data)
        self.assertEqual(self.client.get("/suivi-impression/short").status_code,404)
        self.assertEqual(self.client.get("/suivi-impression/"+"x"*43).status_code,404)
        renew=self.client.post("/admin/soumissions-pro/1/diffusion",
                               data={"live_action":"enable",
                                     "live_url":"https://www.youtube.com/watch?v=Abc123_9-Zk",
                                     "live_hours":"48"})
        self.assertEqual(renew.status_code,302)
        self.assertNotEqual(first_token,self.state["token"])
        self.assertEqual(self.client.get("/suivi-impression/"+first_token).status_code,404)
        video=self.client.get("/suivi-impression/"+self.state["token"])
        self.assertIn(b"youtube-nocookie.com/embed/Abc123_9-Zk",video.data)
        self.state["expires"]=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=1)
        self.assertEqual(self.client.get("/suivi-impression/"+self.state["token"]).status_code,404)
        disabled=self.client.post("/admin/soumissions-pro/1/diffusion",
                                  data={"live_action":"disable"})
        self.assertEqual(disabled.status_code,302)
        self.assertFalse(self.state["enabled"])
        self.assertIsNone(self.state["token"])

    def test_invalid_hours_and_missing_quote_are_rejected(self):
        response=self.client.post("/admin/soumissions-pro/1/diffusion",
                                  data={"live_action":"enable","live_url":"https://oe.ink/l/test-camera",
                                        "live_hours":"9999"})
        self.assertEqual(response.status_code,400)
        self.assertFalse(self.state["enabled"])
        self.assertEqual(self.client.post("/admin/soumissions-pro/99/diffusion",
                                          data={"live_action":"disable"}).status_code,404)
        self.assertEqual(self.client.post("/admin/soumissions-pro/1/diffusion",
                                          data={"live_action":"something"}).status_code,400)


if __name__=="__main__":
    unittest.main()
