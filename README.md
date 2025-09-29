# Pysimplefin

A library to simplify the usage of the simplefin protocol in python.

## Usage

You'll need to create a simplefin account. The cost is currently $1.50 per year. This can be done here <https://beta-bridge.simplefin.org/>.

### Access simplefin with a claim token

Go to your simplefin user page and generate a new claim token

```python
from simplefin import DefaultAuth

auth = DefaultAuth.claim_token("your_token")
print(auth.url) # make sure to save this url. A claim token can only be used once.
# Get a client to access data.
client = auth.client
# Get your transaction data. Will return a list of accounts.
client.get_data()
```

### Access simplefin with a url

Prior to doing this you'll need to setup connections to a bank or credit card.

```python
from simplefin import DefaultAuth

# pass the url generated from your claim token to the DefualtAuth
auth = DefaultAuth.from_url("https://user:pass@example_simpfin.tld/path")

# get client and data same as above
client = auth.get_client()
client.get_date()
```
