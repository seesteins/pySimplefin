# Pysimplefin

A library to simplify the interaction with a simplefin server in python. It is built to allow for the syncing of a local database with a remote simplefin server. This project has no affiliation with the SimpleFin project.

## Usage

You'll need to create a simplefin account. The cost is currently $1.50 per month. This can be done here <https://beta-bridge.simplefin.org/>.

### Access simplefin with a claim token

Go to your simplefin user page and generate a new claim token

```python
from simplefin import DefaultAuth

auth = DefaultAuth.claim_token("your_token") # This returns a auth object that can be used to generate a client
print(auth.url) # make sure to save this url. A claim token can only be used once.
# Get a client to access data.
client = auth.get_client()
# Get your transaction data. Will return a list of accounts.
client.get_data()
```

### Example Usage with a URL

Prior to doing this you'll need to setup connections to a bank or credit card.

```python
from simplefin import DefaultAuth

# pass the url generated from your claim token to the DefaultAuth
auth = DefaultAuth.from_url("https://user:pass@example_simpfin.tld/path")

# get client and data same as above
client = auth.get_client()
client.get_data()

# Sync data with a database
database = DatabaseManager() # Initialize a Database Manager
database.sync(data) # Sync the data with the database.
```
