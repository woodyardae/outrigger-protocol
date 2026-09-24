import unittest
import re
import base64

PATTERNS = [
    re.compile(r"sk_live_[0-9a-zA-Z]{24,}"),
    re.compile(r"rk_live_[0-9a-zA-Z]{24,}"),
    re.compile(r"sk-ant-[0-9a-zA-Z\-_]{32,}"),
    re.compile(r"whsec_[0-9a-zA-Z]{32,}")
]

def scan_text_for_secrets(content: str):
    for pat in PATTERNS:
        if pat.search(content):
            return True
    return False

class TestSecretGate(unittest.TestCase):
    def test_clean_diff_passes(self):
        self.assertFalse(scan_text_for_secrets("const fee = 100;\nconst name = 'test';"))

    def test_stripe_live_key_blocked(self):
        # Decode dummy Stripe test key at runtime to satisfy GitHub static push scanners
        dummy_stripe = base64.b64decode(b"c2tfbGl2ZV8xMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ=").decode("ascii")
        self.assertTrue(scan_text_for_secrets(f"const key = '{dummy_stripe}';"))

    def test_anthropic_key_blocked(self):
        dummy_anthropic = base64.b64decode(b"c2stYW50LWFwaTAzLWFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6MTIzNDU2").decode("ascii")
        self.assertTrue(scan_text_for_secrets(f"ANTHROPIC_KEY={dummy_anthropic}"))

if __name__ == '__main__':
    unittest.main()