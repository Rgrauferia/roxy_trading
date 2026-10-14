"""Offline auth/route/CSP checks; inert AI module, no credentials or network."""
import os,sys,types,importlib.util,unittest,re,ast
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
brain=types.ModuleType('roxy_trader.openai_brain')
class ForbiddenBrain:
 def __init__(self,*a,**kw): raise AssertionError('AI must not run in route tests')
brain.RoxyCryptoOpenAIBrain=brain.RoxyTradingOpenAIBrain=ForbiddenBrain
brain.crypto_openai_status=brain.trading_openai_status=lambda: {'enabled':False,'configured':False}
package=types.ModuleType('roxy_trader');package.__path__=[]
sys.modules['roxy_trader']=package;sys.modules['roxy_trader.openai_brain']=brain
KEY='SYNTHETIC-OFFLINE-TEST-ONLY'
def load(product):
 spec=importlib.util.spec_from_file_location('route_test_'+product,ROOT/'tools/roxy_market_service.py')
 mod=importlib.util.module_from_spec(spec)
 with patch.dict(os.environ,{'ROXY_MARKET_PRODUCT':product},clear=True): exec(compile((ROOT/'tools/roxy_market_service.py').read_text(),str(ROOT/'tools/roxy_market_service.py'),'exec'),mod.__dict__)
 return mod
class ReleaseTests(unittest.TestCase):
 def test_private_crypto_routes_and_product_separation(self):
  for product in ('crypto','trading'):
   mod=load(product)
   with patch.dict(os.environ,{'ROXY_'+product.upper()+'_ACCESS_KEY':KEY},clear=True),TestClient(mod.app,base_url='https://test.invalid') as c:
    for route in ('/pulso','/contratos/1h'):
     self.assertEqual(c.get(route).status_code,401 if product=='crypto' else 404)
     allowed=c.get(route,headers={'Authorization':'Bearer '+KEY})
     self.assertEqual(allowed.status_code,200 if product=='crypto' else 404)
     if product=='crypto':
      self.assertIn('https://api.crypto.com',allowed.headers['content-security-policy'])
      self.assertNotIn('unsafe-inline',allowed.headers['content-security-policy'])
      self.assertEqual(allowed.headers['cache-control'],'no-store')
    self.assertNotIn('https://api.crypto.com',c.get('/').headers['content-security-policy'])
    self.assertEqual(c.get('/assets/roxy_crypto_pulso.html').status_code,404)
    self.assertEqual(c.get('/templates/roxy_crypto_pulso.html').status_code,404)
 def test_existing_cookie_without_new_credentials(self):
  mod=load('crypto')
  with patch.dict(os.environ,{'ROXY_CRYPTO_ACCESS_KEY':KEY},clear=True),TestClient(mod.app,base_url='https://test.invalid') as c:
   c.cookies.set(mod.COOKIE_NAME,mod._session_value())
   self.assertEqual(c.get('/pulso').status_code,200)
   c.cookies.set(mod.COOKIE_NAME,'expired.invalid')
   self.assertEqual(c.get('/pulso').status_code,401)
 def test_template_resources_and_no_historical_bootstrap(self):
  html=(ROOT/'templates/roxy_crypto_pulso.html').read_text()
  ids=re.findall(r'\bid="([^"]+)"',html)
  self.assertEqual(len(ids),len(set(ids)))
  self.assertNotRegex(html,r'<script[^>]*>\s*[^<\s]')
  self.assertNotRegex(html,r'\son[a-z]+=')
  for attr in re.findall(r'(?:src|href)="(/assets/[^"]+)"',html): self.assertTrue((ROOT/attr.lstrip('/')).is_file(),attr)
  boot=(ROOT/'assets/crypto_pulso/bootstrap-data.js').read_text()
  self.assertNotIn('83531',boot);self.assertNotIn('20261011',boot)
  self.assertIn('PULSO_NETWORK_ENABLED = true',boot)
if __name__=='__main__': unittest.main()
