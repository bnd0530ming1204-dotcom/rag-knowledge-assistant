from modelscope.hub.snapshot_download import snapshot_download

model_dir = snapshot_download('BAAI/bge-m3', cache_dir='./data/models/modelscope_cache')
print(f"模型已下载到: {model_dir}")
