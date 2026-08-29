"""Evaluation-only table-normalized embeddings; stored source content is unchanged."""
from __future__ import annotations
import hashlib, json, re, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; E=ROOT/'evaluation_v2'; sys.path.insert(0,str(ROOT))
from processor.import_processor.nodes.d_node_document_split import NodeDocumentSplit
from processor.import_processor.nodes.g_node_import_milvus import NodeImportMilvus
from processor.import_processor.parent_context import assign_parent_titles, build_embedding_text
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import get_milvus_client
COLL='rag_eval_v2_table_normalized_chunks'
ROW=re.compile(r'^\s*\|(.+)\|\s*$'); SEP=re.compile(r'^\s*:?-{3,}:?\s*$')
def normalize_tables(text):
 lines=text.splitlines(); out=[]; i=0
 while i<len(lines):
  m=ROW.match(lines[i])
  if not m or i+1>=len(lines) or not ROW.match(lines[i+1]): i+=1; continue
  head=[x.strip() for x in m.group(1).split('|')]; sep=[x.strip() for x in ROW.match(lines[i+1]).group(1).split('|')]
  if len(head)!=len(sep) or not all(SEP.match(x) for x in sep): i+=1; continue
  i+=2
  while i<len(lines) and ROW.match(lines[i]):
   vals=[x.strip() for x in ROW.match(lines[i]).group(1).split('|')]
   if len(vals)==len(head): out.append('Table row: '+'; '.join(f'{h}: {v}' for h,v in zip(head,vals)))
   i+=1
 return '\n'.join(out)
def split(p):
 n=NodeDocumentSplit(); text=p.read_text(encoding='utf-8'); x,c,_=n._step_2_split_by_title(text,p.stem); x=n._step_3_handle_no_title(text,x,c,p.stem); return assign_parent_titles(n._step_4_refine_chunks(x))
def main():
 mf=json.loads((E/'artifacts/manifest_frozen.json').read_text(encoding='utf-8')); client=get_milvus_client()
 if client.has_collection(COLL): raise SystemExit('refusing to overwrite existing collection')
 start=time.perf_counter(); allc=[]; table_chunks=0
 for d in mf['documents']:
  p=E/d['file']; assert hashlib.sha256(p.read_bytes()).hexdigest()==d['sha256']; chunks=split(p); texts=[]
  for x in chunks:
   norm=normalize_tables(x['content']); table_chunks+=bool(norm); texts.append(build_embedding_text(x)+(('\n\n'+norm) if norm else ''))
  emb=generate_embeddings(texts)
  for i,x in enumerate(chunks):
   x=x.copy(); x.setdefault('item_name',''); x.setdefault('title',''); x.setdefault('file_title',p.stem); x.setdefault('parent_title',''); x.setdefault('part',0); x['dense_vector']=emb['dense'][i]; x['sparse_vector']=emb['sparse'][i]; allc.append(x)
 NodeImportMilvus().create_chunks_collection(client,COLL,len(allc[0]['dense_vector'])); ins=client.insert(collection_name=COLL,data=allc); client.load_collection(COLL); time.sleep(1); rows=int(client.get_collection_stats(COLL).get('row_count',0))
 out={'status':'COMPLETED','collection':COLL,'documents':len(mf['documents']),'chunks':len(allc),'table_chunks_normalized':table_chunks,'rows':rows,'stored_content_changed':False,'embedding_representation_change':'generic Markdown header:value row serialization','latency_ms':round((time.perf_counter()-start)*1000,3)}
 (E/'artifacts/ingestion_table_normalized.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
