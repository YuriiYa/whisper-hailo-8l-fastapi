import requests

url = "http://localhost:54322/transcribe"
## ffmpeg -i /home/pi5-dos/Downloads/kittenstrike1-quothello-therequot-158832.mp3 -ar 16000 -ac 1 hello.wav
files = {'file': open('hello.wav', 'rb')}
resp = requests.post(url, files=files)
print(resp.json())