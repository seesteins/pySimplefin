from pysimplefin import DefaultAuth, SimpleFinClient, DatabaseManager
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
url = os.environ["SIMPLEFIN_URL"]
auth = DefaultAuth.from_url(url)
client = SimpleFinClient(auth)
data = client.get_data(start_date=datetime.now()-timedelta(days=90), end_date=datetime.now())
database = DatabaseManager()
database.sync(data)

print(auth.url)
#auth = DefaultAuth.from_url(url=url)
#client = SimpleFinClient(auth=auth)
#print(auth.url)
#data = client.get_data(start_date=datetime(2025,9,1), end_date=datetime.now())
#for d in data:
#    print(d)