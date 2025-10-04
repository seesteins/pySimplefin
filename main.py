from pysimplefin import DefaultAuth, SimpleFinClient
import os
from datetime import datetime

url = os.environ["SIMPLEFIN_URL"]
auth = DefaultAuth.from_url(url=url)
client = SimpleFinClient(auth=auth)
print(auth.url)
#data = client.get_data(start_date=datetime(2025,9,1), end_date=datetime.now())
#for d in data:
#    print(d)