import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
if os.path.isfile('.env'):
    load_dotenv()

from .helpers.cypher import MeganzClient
CypherClient = MeganzClient()
