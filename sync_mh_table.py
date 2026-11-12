"""
修复版数据同步脚本
解决 pandas 比较中的假阳性问题
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import hashlib
import json

# === 数据库连接配置 主库 注意注意注意 敏感操作 别搞错数据库 ===
SOURCE_DB = {
    "host": "193.218.200.71",
    "port": 3306,
    "user": "yymh_com",
    "password": "SWyx4DpEWsB5KHa4",
    "database": "yymh_com"
}

# === 数据库连接配置 从库 注意注意注意 敏感操作 别搞错数据库 ===
TARGET_DB = {
    "host": "193.218.200.71",
    "port": 3306,
    "user": "xxmh_com",
    "password": "zpXnXKRTWHFRERb7",
    "database": "xxmh_com"
}

# 同步表及主键字段
TABLES = {
    "qiswl_manhua": "id",
    "qiswl_capter": "id"
}


def get_engine(cfg):
    return create_engine(
        f"mysql+pymysql://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['database']}?charset=utf8mb4"
    )


def normalize_value(value):
    """标准化值，处理各种数据类型的比较问题"""
    if pd.isna(value):
        return None

    # 处理字符串
    if isinstance(value, str):
        return value.strip()

    # 处理浮点数，保留合理精度
    if isinstance(value, float):
        # 对于看起来像整数的浮点数，转为整数
        if value.is_integer():
            return int(value)
        # 否则保留6位小数精度
        return round(value, 6)

    # 处理日期时间，统一到秒级精度
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime('%Y-%m-%d %H:%M:%S')

    return value


def calculate_row_hash(row_data):
    """计算行数据的哈希值，用于快速比较"""
    # 将行数据转换为标准化的字典
    normalized = {}
    for key, value in row_data.items():
        normalized[key] = normalize_value(value)

    # 生成 JSON 字符串并计算哈希
    json_str = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()


def are_rows_different(src_row, dst_row, ignore_fields=None):
    """准确比较两行数据是否不同"""
    if ignore_fields is None:
        ignore_fields = set()

    # 获取所有字段
    all_fields = set(src_row.index) | set(dst_row.index)

    for field in all_fields:
        if field in ignore_fields:
            continue

        src_val = normalize_value(src_row.get(field))
        dst_val = normalize_value(dst_row.get(field))

        # 处理 None 值的比较
        if src_val is None and dst_val is None:
            continue
        elif src_val is None or dst_val is None:
            return True
        elif src_val != dst_val:
            return True

    return False


def sync_table_improved(table_name, key_field, src_engine, dst_engine):
    """改进的表同步函数"""
    print(f"正在同步表：{table_name}")

    # 获取源和目标数据
    df_src = pd.read_sql(f"SELECT * FROM {table_name}", src_engine)
    df_dst = pd.read_sql(f"SELECT * FROM {table_name}", dst_engine)

    if df_src.empty and df_dst.empty:
        print("两表都为空，无需同步")
        return

    df_src.set_index(key_field, inplace=True)
    df_dst.set_index(key_field, inplace=True)

    # 统计信息
    stats = {
        'inserted': 0,
        'updated': 0,
        'deleted': 0,
        'unchanged': 0
    }

    # === 1. 查找需要插入的记录 ===
    insert_ids = df_src.index.difference(df_dst.index)
    insert_df = df_src.loc[insert_ids] if not insert_ids.empty else pd.DataFrame()

    # === 2. 查找需要更新的记录 ===
    common_ids = df_src.index.intersection(df_dst.index)
    update_ids = []

    print(f"检查 {len(common_ids)} 条共同记录...")

    # 使用改进的比较方法
    for idx in common_ids:
        src_row = df_src.loc[idx]
        dst_row = df_dst.loc[idx]

        if are_rows_different(src_row, dst_row, ignore_fields={key_field}):
            update_ids.append(idx)

    update_df = df_src.loc[update_ids] if update_ids else pd.DataFrame()

    # === 3. 查找需要删除的记录 ===
    delete_ids = df_dst.index.difference(df_src.index)

    # === 执行插入 ===
    if not insert_df.empty:
        stats['inserted'] = len(insert_df)
        print(f"插入 {stats['inserted']} 条")
        insert_df.reset_index().to_sql(table_name, dst_engine, if_exists='append', index=False)

    # === 执行更新 ===
    if not update_df.empty:
        stats['updated'] = len(update_df)
        print(f"更新 {stats['updated']} 条")

        # 显示前几条更新记录的详细信息
        if stats['updated'] <= 5:
            print(f"   更新记录详情：")
            for idx in update_ids[:5]:
                src_row = df_src.loc[idx]
                dst_row = df_dst.loc[idx]
                print(f"   ID {idx}:")
                for field in src_row.index:
                    if field == key_field:
                        continue
                    src_val = normalize_value(src_row[field])
                    dst_val = normalize_value(dst_row[field])
                    if src_val != dst_val:
                        print(f"     {field}: '{dst_val}' -> '{src_val}'")

        # 执行批量更新
        cols = update_df.columns.tolist()
        set_clause = ', '.join([f"`{col}` = :{col}" for col in cols])
        sql = text(f"UPDATE {table_name} SET {set_clause} WHERE `{key_field}` = :{key_field}")

        with dst_engine.begin() as conn:
            for idx, row in update_df.iterrows():
                # 处理 NaN 值
                row = row.where(pd.notna(row), None)
                params = row.to_dict()
                params[key_field] = idx
                conn.execute(sql, params)

    # === 执行删除 ===
    if not delete_ids.empty:
        stats['deleted'] = len(delete_ids)
        print(f"删除 {stats['deleted']} 条")
        id_list = delete_ids.tolist()
        chunks = [id_list[i:i + 1000] for i in range(0, len(id_list), 1000)]
        with dst_engine.begin() as conn:
            for chunk in chunks:
                placeholders = ','.join([str(int(i)) for i in chunk])
                delete_sql = text(f"DELETE FROM {table_name} WHERE {key_field} IN ({placeholders})")
                conn.execute(delete_sql)

    # 计算未变更记录数
    stats['unchanged'] = len(common_ids) - stats['updated']

    print(f"同步完成：{table_name}")
    print(f"插入:{stats['inserted']}, 更新:{stats['updated']}, 删除:{stats['deleted']}, 未变:{stats['unchanged']}")

    return stats


def sync_table_hash_based(table_name, key_field, src_engine, dst_engine):
    """基于哈希值的高效同步方法"""
    print(f"正在同步表（哈希模式）：{table_name}")

    # 获取源和目标数据
    df_src = pd.read_sql(f"SELECT * FROM {table_name}", src_engine)
    df_dst = pd.read_sql(f"SELECT * FROM {table_name}", dst_engine)

    if df_src.empty and df_dst.empty:
        print("两表都为空，无需同步")
        return

    # 计算每行的哈希值
    print("计算数据哈希值...")

    src_hashes = {}
    for _, row in df_src.iterrows():
        row_id = row[key_field]
        row_hash = calculate_row_hash(row.drop(key_field))
        src_hashes[row_id] = row_hash

    dst_hashes = {}
    for _, row in df_dst.iterrows():
        row_id = row[key_field]
        row_hash = calculate_row_hash(row.drop(key_field))
        dst_hashes[row_id] = row_hash

    # 比较哈希值找出差异
    src_ids = set(src_hashes.keys())
    dst_ids = set(dst_hashes.keys())

    # 需要插入的记录
    insert_ids = src_ids - dst_ids

    # 需要更新的记录（ID存在但哈希不同）
    common_ids = src_ids & dst_ids
    update_ids = [
        row_id for row_id in common_ids
        if src_hashes[row_id] != dst_hashes[row_id]
    ]

    # 需要删除的记录
    delete_ids = dst_ids - src_ids

    print(f"哈希比较结果: 插入{len(insert_ids)}, 更新{len(update_ids)}, 删除{len(delete_ids)}")

    # 如果没有变化就直接返回
    if not insert_ids and not update_ids and not delete_ids:
        print("数据完全一致，无需同步")
        return {'inserted': 0, 'updated': 0, 'deleted': 0, 'unchanged': len(common_ids)}

    # 执行实际的数据库操作
    df_src.set_index(key_field, inplace=True)
    df_dst.set_index(key_field, inplace=True)

    stats = {'inserted': 0, 'updated': 0, 'deleted': 0, 'unchanged': 0}

    # 插入
    if insert_ids:
        insert_df = df_src.loc[list(insert_ids)]
        stats['inserted'] = len(insert_df)
        print(f"插入 {stats['inserted']} 条")
        insert_df.reset_index().to_sql(table_name, dst_engine, if_exists='append', index=False)

    # 更新
    if update_ids:
        update_df = df_src.loc[update_ids]
        stats['updated'] = len(update_df)
        print(f"更新 {stats['updated']} 条")

        cols = update_df.columns.tolist()
        set_clause = ', '.join([f"`{col}` = :{col}" for col in cols])
        sql = text(f"UPDATE {table_name} SET {set_clause} WHERE `{key_field}` = :{key_field}")

        with dst_engine.begin() as conn:
            for idx, row in update_df.iterrows():
                row = row.where(pd.notna(row), None)
                params = row.to_dict()
                params[key_field] = idx
                conn.execute(sql, params)

    # 删除
    if delete_ids:
        stats['deleted'] = len(delete_ids)
        print(f"删除 {stats['deleted']} 条")
        id_list = list(delete_ids)
        chunks = [id_list[i:i + 1000] for i in range(0, len(id_list), 1000)]
        with dst_engine.begin() as conn:
            for chunk in chunks:
                placeholders = ','.join([str(int(i)) for i in chunk])
                delete_sql = text(f"DELETE FROM {table_name} WHERE {key_field} IN ({placeholders})")
                conn.execute(delete_sql)

    stats['unchanged'] = len(common_ids) - stats['updated']

    print(f"同步完成：{table_name}")
    print(f"插入:{stats['inserted']}, 更新:{stats['updated']}, 删除:{stats['deleted']}, 未变:{stats['unchanged']}")

    return stats


def main():
    print(f"同步开始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    src_engine = get_engine(SOURCE_DB)
    dst_engine = get_engine(TARGET_DB)

    total_stats = {'inserted': 0, 'updated': 0, 'deleted': 0, 'unchanged': 0}

    for table, key in TABLES.items():
        # 使用哈希模式进行高效同步
        stats = sync_table_hash_based(table, key, src_engine, dst_engine)

        # 累加统计信息
        for k, v in stats.items():
            total_stats[k] += v

    print(f"全部同步完成！")
    print(
        f"总计: 插入{total_stats['inserted']}, 更新{total_stats['updated']}, 删除{total_stats['deleted']}, 未变{total_stats['unchanged']}")


if __name__ == '__main__':
    main()