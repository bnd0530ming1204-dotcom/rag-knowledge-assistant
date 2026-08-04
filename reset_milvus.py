"""清空 Milvus kb_chunks collection 中的数据，但保留 collection 本身。"""

import os
import time

from dotenv import load_dotenv
from pymilvus import MilvusClient


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
EXPECTED_COLLECTION = "kb_chunks"


def get_row_count(client: MilvusClient, collection_name: str) -> int:
    stats = client.get_collection_stats(collection_name=collection_name)
    return int(stats.get("row_count", 0))


def get_primary_key_field(client: MilvusClient, collection_name: str) -> str:
    """从当前 collection schema 中读取真实主键字段名。"""
    description = client.describe_collection(collection_name=collection_name)
    for field in description.get("fields", []):
        if field.get("is_primary"):
            return str(field["name"])
    raise RuntimeError(f"无法从 {collection_name} schema 中找到主键字段")


def get_all_primary_keys(
    client: MilvusClient,
    collection_name: str,
    primary_key_field: str,
    expected_count: int,
) -> list[int]:
    """复用 inspect_milvus.py 的查询方式，分页读取全部实体主键。"""
    primary_keys: list[int] = []
    batch_size = 1000
    offset = 0

    while offset < expected_count:
        # 与 inspect_milvus.py 已成功读取数据的查询参数保持一致。
        # Milvus query 会在结果中自动包含 collection 的主键字段。
        rows = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["file_title"],
            limit=min(batch_size, expected_count - offset),
            offset=offset,
        )
        if not rows:
            break

        for row in rows:
            if primary_key_field not in row:
                raise RuntimeError(
                    f"查询结果未包含主键字段 {primary_key_field!r}：{row}"
                )
            primary_keys.append(int(row[primary_key_field]))

        offset += len(rows)

    return primary_keys


def compact_and_wait(client: MilvusClient, collection_name: str) -> None:
    """执行 compaction，等待逻辑删除数据被物理整理。"""
    job_id = client.compact(collection_name=collection_name)
    print(f"Compaction job ID: {job_id}")

    for _ in range(120):
        state = client.get_compaction_state(job_id=job_id)
        if state == "Completed":
            return
        if state not in {"Executing", "UndefiedState"}:
            raise RuntimeError(f"Compaction 状态异常：{state}")
        time.sleep(1)

    raise TimeoutError("等待 Milvus compaction 完成超时（120 秒）")


def main() -> None:
    load_dotenv(ENV_PATH)

    milvus_url = os.getenv("MILVUS_URL")
    collection_name = os.getenv("CHUNKS_COLLECTION")

    if not milvus_url:
        raise RuntimeError(f"{ENV_PATH} 中未配置 MILVUS_URL")
    if not collection_name:
        raise RuntimeError(f"{ENV_PATH} 中未配置 CHUNKS_COLLECTION")
    if collection_name != EXPECTED_COLLECTION:
        raise RuntimeError(
            f"安全检查失败：CHUNKS_COLLECTION={collection_name!r}，"
            f"脚本只允许清空 {EXPECTED_COLLECTION!r}"
        )

    client = MilvusClient(uri=milvus_url)
    try:
        if not client.has_collection(collection_name=collection_name):
            raise RuntimeError(f"Milvus collection 不存在：{collection_name}")

        before_count = get_row_count(client, collection_name)

        print(f"当前 Milvus 地址: {milvus_url}")
        print(f"当前 collection 名称: {collection_name}")
        print(f"清理前数据量: {before_count}")

        primary_key_field = get_primary_key_field(client, collection_name)
        print(f"Schema 主键字段: {primary_key_field}")
        if primary_key_field != "chunk_id":
            raise RuntimeError(
                f"安全检查失败：kb_chunks 的主键应为 'chunk_id'，"
                f"实际为 {primary_key_field!r}"
            )

        primary_keys = get_all_primary_keys(
            client,
            collection_name,
            primary_key_field,
            before_count,
        )
        print(f"查询到 {primary_key_field} 数量: {len(primary_keys)}")

        if primary_keys:
            # 使用明确的主键列表分批删除，只删除实体，不删除 collection 或索引。
            delete_batch_size = 1000
            for start in range(0, len(primary_keys), delete_batch_size):
                ids_to_delete = primary_keys[start : start + delete_batch_size]
                client.delete(
                    collection_name=collection_name,
                    ids=ids_to_delete,
                )

        # 即使 query 已经查不到数据，也执行 flush + compaction，以处理之前
        # 已逻辑删除、但 row_count 尚未更新的实体。
        client.flush(collection_name=collection_name)
        compact_and_wait(client, collection_name)

        # Compaction 完成后，继续轮询等待 collection 统计信息同步。
        after_count = get_row_count(client, collection_name)
        for _ in range(30):
            if after_count == 0:
                break
            time.sleep(1)
            after_count = get_row_count(client, collection_name)

        print(f"清理后数据量: {after_count}")

        if after_count != 0:
            raise RuntimeError(
                f"清理结果校验失败：{collection_name} 仍有 {after_count} 条数据"
            )

        print("清理完成：collection 已保留，数据量已确认变为 0。")
    finally:
        client.close()


if __name__ == "__main__":
    main()
