from pathlib import Path

url = "./output/example/images/example.jpg"
path = Path(url)
print(path.stem)
