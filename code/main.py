import requests
import json

response =  requests.get("https://api.github.com/users/Eletroman179/repos")

with open("output.json", "w") as file:
    json.dump(response.json(), file, indent=4)