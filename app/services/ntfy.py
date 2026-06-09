import requests

# EXAMPLE

# requests.post("https://ntfy.sh/mytopic",
#   data="Backup successful 😀".encode(encoding='utf-8'))

class NtfyService:
    def __init__(self,url,topic):
        self.url = url
        self.topic= topic

    async def test_connection(self):...
    
    def post(self,msg:str,priority:int=3):
        raise NotImplementedError(f"SEND NOTIFICATION TO {self.url}")
