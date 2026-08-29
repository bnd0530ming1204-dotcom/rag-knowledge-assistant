"""Create the isolated Parent Heading OFF collection; production code is untouched."""
from __future__ import annotations
import argparse, hashlib, json, re, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; EVAL=ROOT/'evaluation_v2'; sys.path.insert(0,str(ROOT))
from processor.import_processor.nodes.d_node_document_split import NodeDocumentSplit
from processor.import_processor.parent_context import assign_parent_titles
from processor.import_processor.nodes.g_node_import_milvus import NodeImportMilvus
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import get_milvus_client
COLL='rag_eval_v2_parent_off_chunks'
def split(p):
 n=NodeDocumentSplit(); text=p.read_text(encoding='utf-8'); x,c,_=n._step_2_split_by_title(text,p.stem); x=n._step_3_handle_no_title(text,x,c,p.stem); return assign_parent_titles(n._step_4_refine_chunks(x))
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--collection',default=COLL); ap.add_argument('--output',type=Path,default=EVAL/'artifacts/ingestion_parent_off.json'); a=ap.parse_args()
 if a.collection!=COLL: raise SystemExit('fixed evaluation-only collection name required')
 mf=json.loads((EVAL/'artifacts/manifest_frozen.json').read_text(encoding='utf-8')); client=get_milvus_client()
 if client.has_collection(a.collection):
  rows=int(client.get_collection_stats(a.collection).get('row_count',0))
  if rows: raise SystemExit('refusing to overwrite non-empty existing collection')
  client.drop_collection(a.collection)  # recover only this tool's failed empty create
 start=time.perf_counter(); allc=[]; docs=[]
 for d in mf['documents']:
  p=EVAL/d['file']; assert hashlib.sha256(p.read_bytes()).hexdigest()==d['sha256']; chunks=split(p)
  texts=[(str(x.get('item_name') or '')+'\n' if x.get('item_name') else '')+str(x['content']) for x in chunks]
  emb=generate_embeddings(texts)
  for i,x in enumerate(chunks):
   x=x.copy(); x.setdefault('item_name',''); x.setdefault('title',''); x.setdefault('file_title',p.stem); x.setdefault('parent_title',''); x['dense_vector']=emb['dense'][i]; x['sparse_vector']=emb['sparse'][i]; x['document_id']=d['document_id']; x['source_locator']=re.findall(r'<!-- locator: ([A-Z0-9-]+) -->',x['content']); x.setdefault('part',0); allc.append(x)
  docs.append({'document_id':d['document_id'],'chunk_count':len(chunks)})
 NodeImportMilvus().create_chunks_collection(client,a.collection,len(allc[0]['dense_vector'])); ins=client.insert(collection_name=a.collection,data=allc); client.load_collection(a.collection); rows=int(client.get_collection_stats(a.collection).get('row_count',0))
 out={'status':'COMPLETED','collection':a.collection,'document_count':len(docs),'chunk_count':len(allc),'row_count':rows,'insert_count':ins.get('insert_count'),'parent_heading_in_embedding':False,'chunk_boundaries_and_locators':'identical to Parent ON; Milvus auto-generated physical chunk_id differs by schema design','total_latency_ms':round((time.perf_counter()-start)*1000,3),'documents':docs}
 a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
