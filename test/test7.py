from utils.embedding_utils import generate_embeddings, get_bge_m3_ef

model = get_bge_m3_ef()

texts = ["测试","hello"]

documents = model.encode_documents(texts)
print(documents)
