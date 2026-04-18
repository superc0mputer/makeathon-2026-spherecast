import requests
import urllib.parse
import time
from typing import Dict, Any, Optional

REQUEST_TIMEOUT = 10
RATE_LIMIT_DELAY = 0.3

class PubChemClient:
    """Client for NCBI PubChem REST API"""
    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
    VIEW_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"
    PROPERTIES = "MolecularFormula,MolecularWeight,IUPACName,InChIKey,XLogP,Charge"

    @staticmethod
    def _request_json(url: str, rate_limit: bool = True) -> tuple[Optional[dict[str, Any]], Optional[int], Optional[str]]:
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            return None, None, "PubChem request timed out."
        except requests.exceptions.ConnectionError as exc:
            return None, None, f"Network error: {exc}"
        except requests.exceptions.RequestException as exc:
            return None, None, f"Request error: {exc}"
        finally:
            if rate_limit:
                time.sleep(RATE_LIMIT_DELAY)

        try:
            data = response.json()
        except ValueError:
            data = None

        return data, response.status_code, None
        
    @classmethod
    def get_properties_by_name(cls, name: str, rate_limit: bool = True):
        encoded = urllib.parse.quote(name.strip())
        url = f"{cls.BASE_URL}/name/{encoded}/property/{cls.PROPERTIES}/JSON"
        return cls._request_json(url, rate_limit=rate_limit)

    @classmethod
    def get_description_by_cid(cls, cid: int, rate_limit: bool = True):
        url = f"{cls.BASE_URL}/cid/{cid}/description/JSON"
        return cls._request_json(url, rate_limit=rate_limit)

    @classmethod
    def get_synonyms_by_cid(cls, cid: int, rate_limit: bool = True):
        url = f"{cls.BASE_URL}/cid/{cid}/synonyms/JSON"
        return cls._request_json(url, rate_limit=rate_limit)

    @classmethod
    def get_safety_hazards_by_cid(cls, cid: int, rate_limit: bool = True):
        heading = urllib.parse.quote("Safety and Hazards")
        url = f"{cls.VIEW_BASE_URL}/{cid}/JSON?heading={heading}"
        return cls._request_json(url, rate_limit=rate_limit)
