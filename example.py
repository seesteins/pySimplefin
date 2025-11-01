from pysimplefin import DefaultAuth, SimpleFinClient, DatabaseManager
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
url = os.environ["SIMPLEFIN_URL"]
auth = DefaultAuth.from_url(url)
client = SimpleFinClient(auth)
data = client.get_data(start_date=datetime.now()-timedelta(days=90), end_date=datetime.now(), pending=True)
database = DatabaseManager()
database.sync(data)