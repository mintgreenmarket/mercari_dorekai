"""
CSVファイルを比較して、ベースファイルに無い商品をソースファイルから追加するスクリプト
"""
import pandas as pd
import numpy as np
import os
import glob
import re
import shutil
import zipfile
from datetime import datetime

# ファイルパターン
BASE_FILE_PATTERN = r"C:\Users\progr\Desktop\Python\mercari_dorekai\downloads\dorekai-base-shop-*.csv"
SOURCE_FILE_PATTERN = r"C:\Users\progr\Desktop\Python\mercari_dorekai\downloads\product_data_*.csv"
IMAGE_BASE_PATH = r"\\LS210DNBD82\share\平良\Python\mercari_dorekai\mercari_images"

def extract_number_from_text(text):
    """テキストから最初の数字を抽出（先頭の0を除く）"""
    if pd.isna(text):
        return ""
    text = str(text)
    # 最初の数字パターンを検索
    match = re.search(r'\d+', text)
    if match:
        # 先頭の0を除去
        return str(int(match.group()))
    return ""

def to_int_or_nan(value):
    """数値に変換できればint、空や変換不可はNaNにする"""
    if value == "" or pd.isna(value):
        return np.nan
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return np.nan

def find_product_images(product_code, max_images=20):
    """商品コードに基づいて画像ファイルを検索"""
    images = []
    if not product_code or product_code == "":
        return images
    
    for i in range(1, max_images + 1):
        image_path = os.path.join(IMAGE_BASE_PATH, f"{product_code}-{i}.jpg")
        if os.path.exists(image_path):
            images.append(image_path)
        else:
            # 連続していない可能性もあるが、効率のため最初の欠番で終了
            break
    return images

def get_latest_file(pattern):
    """指定されたパターンに一致する最新のファイルを取得"""
    files = glob.glob(pattern)
    if not files:
        return None
    # 最新のファイルを取得（変更日時でソート）
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def main():
    print("=" * 80)
    print("商品追加スクリプト開始")
    print("=" * 80)
    
    # 最新のファイルを取得
    print("\n[*] 最新のファイルを検索中...")
    BASE_FILE = get_latest_file(BASE_FILE_PATTERN)
    SOURCE_FILE = get_latest_file(SOURCE_FILE_PATTERN)
    
    # ファイルの存在確認
    if not BASE_FILE:
        print(f"[X] ベースファイルが見つかりません: {BASE_FILE_PATTERN}")
        return
    
    if not SOURCE_FILE:
        print(f"[X] ソースファイルが見つかりません: {SOURCE_FILE_PATTERN}")
        return
    
    print(f"\n[+] ベースファイル: {os.path.basename(BASE_FILE)}")
    print(f"    パス: {BASE_FILE}")
    print(f"[+] ソースファイル: {os.path.basename(SOURCE_FILE)}")
    print(f"    パス: {SOURCE_FILE}")
    
    try:
        # CSVファイルを読み込み (Shift-JIS エンコーディング)
        print("\n[*] ベースファイルを読み込み中...")
        base_df = pd.read_csv(BASE_FILE, encoding='shift-jis', low_memory=False)
        print(f"    [OK] {len(base_df)} 件の商品を読み込みました")
        
        print("\n[*] ソースファイルを読み込み中...")
        source_df = pd.read_csv(SOURCE_FILE, encoding='shift-jis', low_memory=False)
        print(f"    [OK] {len(source_df)} 件の商品を読み込みました")
        
        # カラム名を表示
        print(f"\n[*] ベースファイルのカラム: {list(base_df.columns[:5])}...")
        print(f"[*] ソースファイルのカラム: {list(source_df.columns[:10])}...")
        
        # 商品IDカラムを特定
        base_id_col = base_df.columns[0]  # 最初のカラムを商品IDとして使用
        source_id_col = source_df.columns[0]
        
        print(f"\n[*] 比較キー:")
        print(f"    ベース: {base_id_col}")
        print(f"    ソース: {source_id_col}")
        
        # ベースファイルの商品IDセット
        base_ids = set(base_df[base_id_col].dropna().astype(str))
        print(f"\n[*] ベースファイルのユニーク商品ID数: {len(base_ids)}")
        
        # ソースファイルの商品IDセット
        source_ids = set(source_df[source_id_col].dropna().astype(str))
        print(f"[*] ソースファイルのユニーク商品ID数: {len(source_ids)}")
        
        # ベースに無い商品IDを特定（参考用）
        missing_ids = source_ids - base_ids
        print(f"\n[*] ベースファイルに無い商品: {len(missing_ids)} 件")
        print(f"[*] ベースファイルにある商品: {len(source_ids & base_ids)} 件（更新対象）")
        
        # すべてのソースファイルの商品を処理対象にする（既存商品の更新対応）
        processing_products = source_df.copy()
        
        print(f"\n[*] 処理対象: {len(processing_products)} 件（既存商品の更新も含む）")
        
        print(f"\n[*] {len(processing_products)} 件の商品を処理します...")
        print("[*] 商品データを変換中...")
        
        # ベースファイルのフォーマットに合わせて変換
        converted_products = []
        skipped_products = []
        new_image_files = set()
        
        for idx, row in processing_products.iterrows():
            new_row = {}
            
            # 先に商品コードを計算
            product_name = str(row.get('商品名', ''))
            product_desc = str(row.get('商品説明', ''))
            name_number = extract_number_from_text(product_name)
            desc_number = extract_number_from_text(product_desc)
            
            # 商品名の先頭が3～6桁の数字で始まっているかチェック
            product_code = ""
            if name_number and len(name_number) >= 3 and len(name_number) <= 6:
                # 商品名の先頭から3～6桁の数字で始まっている場合
                if name_number and name_number == desc_number:
                    product_code = name_number
                elif name_number:
                    product_code = name_number
                else:
                    product_code = ""
            else:
                # 商品名が3～6桁の数字で始まっていない場合はスキップ対象
                product_code = ""
                skipped_products.append({
                    'name': product_name[:50],
                    'reason': '商品名が3～6桁の数字で始まっていない' if name_number else '商品名に数字がない'
                })
            
            # 公開状態と在庫数のロジックを決定
            product_status = row.get('商品ステータス', '')
            current_stock = row.get('SKU1_現在の在庫数', '')

            status_value = to_int_or_nan(product_status)
            stock_value_raw = to_int_or_nan(current_stock)
            
            # 公開状態の決定（商品ステータス=1 を最優先で0）
            if status_value == 1:
                publish_state = 0
            elif stock_value_raw == 1:
                publish_state = 1
            elif stock_value_raw == 0:
                publish_state = 0
            elif status_value == 2:
                publish_state = 1
            else:
                publish_state = 1  # デフォルト
            
            # 在庫数の決定
            if current_stock == 1:
                stock_value = 1
            elif current_stock == 0:
                stock_value = 0
            else:
                stock_value = current_stock

            kind_id_value = to_int_or_nan(row.get('種類ID', ''))
            
            # ベースファイルの各カラムに対応
            for col in base_df.columns:
                if col == base_id_col or col == '商品ID':
                    # 新規追加商品の商品IDは空白
                    new_row[col] = ""
                elif col == '商品名':
                    # 商品名はそのまま
                    new_row[col] = row.get('商品名', '')
                elif col in ['商品説明', '説明']:
                    # 説明は「商品説明」カラムから取得
                    new_row[col] = row.get('商品説明', '')
                elif col in ['価格', '販売価格']:
                    # 価格は「販売価格」カラムから取得
                    new_row[col] = row.get('販売価格', '')
                elif col == '税率':
                    new_row[col] = 1
                elif col == '公開状態':
                    new_row[col] = publish_state
                elif col == '表示順':
                    new_row[col] = 1
                elif col in ['在庫数', '在庫']:
                    # 在庫数はロジックに基づいて設定
                    new_row[col] = stock_value
                elif col == '種類ID':
                    # 種類IDは数値として保持
                    new_row[col] = kind_id_value
                elif col == '種類在庫数':
                    # 種類在庫数は種類IDがある場合のみ在庫数と同等に設定
                    if pd.notna(kind_id_value):
                        new_row[col] = to_int_or_nan(stock_value)
                    else:
                        new_row[col] = np.nan
                elif col in ['商品コード', '品番ID']:
                    # 事前に計算した商品コードを使用
                    new_row[col] = product_code
                elif col.startswith('画像'):
                    # 画像ファイルのパスを設定
                    # カラム名から番号を抽出（例: 画像1 -> 1）
                    img_match = re.search(r'画像(\d+)', col)
                    if img_match:
                        img_num = int(img_match.group(1))
                        
                        # ベースファイルの対応する行を検索（商品コードで）
                        existing_image = ""
                        if product_code and product_code != "":
                            # 商品コード列を特定
                            code_col = None
                            for c in ['商品コード', '品番ID']:
                                if c in base_df.columns:
                                    code_col = c
                                    break
                            
                            # ベースファイルで同じ商品コードの行を検索
                            if code_col:
                                matching_rows = base_df[base_df[code_col].astype(str) == product_code]
                                if not matching_rows.empty and col in matching_rows.columns:
                                    existing_val = matching_rows.iloc[0][col]
                                    if pd.notna(existing_val) and str(existing_val).strip() != '':
                                        existing_image = str(existing_val).strip()
                        
                        # 既存の画像がある場合はそれを保持、なければ新しく取得
                        if existing_image:
                            # 既存の画像がある場合はそのまま使用
                            new_row[col] = existing_image
                        else:
                            # 既存画像がない場合（空白またはベースにない場合）は新しい画像を設定
                            if product_code and product_code != "":
                                # ファイル名を構築
                                image_filename = f"{product_code}-{img_num}.jpg"
                                # フルパスで存在確認
                                image_path = os.path.join(IMAGE_BASE_PATH, image_filename)
                                if os.path.exists(image_path):
                                    # ファイル名のみを保存
                                    new_row[col] = image_filename
                                    new_image_files.add(image_filename)
                                else:
                                    new_row[col] = ""
                            else:
                                new_row[col] = ""
                    else:
                        new_row[col] = ""
                else:
                    # その他のカラムは空白または元のデータを保持
                    if col in source_df.columns:
                        new_row[col] = row.get(col, '')
                    else:
                        new_row[col] = ""
            
            # 商品コードが空白の場合はスキップ（既に記録済み）
            if not product_code or product_code == "":
                continue
            
            converted_products.append(new_row)
        
        # スキップされた商品を表示
        if skipped_products:
            print(f"\n[*] スキップされた商品: {len(skipped_products)} 件")
            for prod in skipped_products[:5]:  # 最初の5件のみ表示
                print(f"    - {prod['name']}: {prod['reason']}")
            if len(skipped_products) > 5:
                print(f"    ... 他 {len(skipped_products) - 5} 件")
        # DataFrameに変換
        converted_df = pd.DataFrame(converted_products)
        
        print(f"    [OK] {len(converted_df)} 件の商品を変換しました")
        
        # 商品コード列を特定
        product_code_col = None
        for col in ['商品コード', '品番ID']:
            if col in converted_df.columns:
                product_code_col = col
                break
        
        # ベースファイルと統合（既存商品の更新と新規商品の追加）
        print(f"\n[*] ベースファイルと統合するかった...")
        combined_df = base_df.copy()
        updated_count = 0
        added_count = 0
        
        if product_code_col and product_code_col in base_df.columns:
            # 既存商品の更新と新規商品の追加
            for new_idx, new_row in converted_df.iterrows():
                new_code = new_row[product_code_col]
                
                # 同じ商品コードをベースファイルで検索
                matching_indices = combined_df[combined_df[product_code_col].astype(str) == str(new_code)].index.tolist()
                
                if matching_indices:
                    # 既存商品を更新
                    base_idx = matching_indices[0]
                    preserve_cols = {'種類ID', '種類コード', 'JAN/GTIN'}
                    stock_col = None
                    for c in ['在庫数', '在庫']:
                        if c in combined_df.columns:
                            stock_col = c
                            break
                    for col in combined_df.columns:
                        # 商品IDは更新しない（既存の値を保持）
                        if col == base_id_col or col == '商品ID':
                            continue
                        # 既存商品の保持対象カラムは更新しない
                        if col in preserve_cols:
                            continue
                        # 画像カラムで既存に値がある場合はスキップ（後で処理）
                        if col.startswith('画像'):
                            continue
                        # その他のカラムは新しい値で更新（型チェック）
                        new_val = new_row.get(col, '')
                        
                        # 列の型をチェック
                        col_dtype = combined_df[col].dtype
                        if pd.api.types.is_numeric_dtype(col_dtype):
                            # 数値型の場合：空文字列はNaN、その他は変換
                            if new_val == '' or pd.isna(new_val):
                                combined_df.at[base_idx, col] = np.nan
                            else:
                                try:
                                    combined_df.at[base_idx, col] = pd.to_numeric(new_val, errors='coerce')
                                except:
                                    combined_df.at[base_idx, col] = np.nan
                        else:
                            # 文字列型等その他の場合：そのまま設定
                            combined_df.at[base_idx, col] = new_val
                    # 種類在庫数は種類IDがある場合のみ在庫数と同等に設定（数値化）
                    if '種類在庫数' in combined_df.columns and stock_col:
                        if '種類ID' in combined_df.columns and pd.notna(combined_df.at[base_idx, '種類ID']):
                            combined_df.at[base_idx, '種類在庫数'] = to_int_or_nan(combined_df.at[base_idx, stock_col])
                        else:
                            combined_df.at[base_idx, '種類在庫数'] = np.nan
                    updated_count += 1
                else:
                    # 新規商品を追加
                    combined_df = pd.concat([combined_df, new_row.to_frame().T], ignore_index=True)
                    added_count += 1
        else:
            # 商品コード列がない場合は単純結合
            combined_df = pd.concat([base_df, converted_df], ignore_index=True)
        
        print(f"    [OK] 既存商品を更新: {updated_count} 件")
        print(f"    [OK] 新規商品を追加: {added_count} 件")
        print(f"    [OK] 合計: {len(combined_df)} 件")
        
        # 結合後に画像欄が空白の場合は新しく取得
        product_code_col = None
        for col in ['商品コード', '品番ID']:
            if col in combined_df.columns:
                product_code_col = col
                break
        
        if product_code_col:
            print(f"\n[*] 画像欄の補充処理を開始...")
            image_cols = [col for col in combined_df.columns if col.startswith('画像')]
            
            if image_cols:
                filled_count = 0
                # 画像1列のみで空白判定
                image1_col = None
                for col in image_cols:
                    if col == '画像1' or col.endswith('_1'):
                        image1_col = col
                        break
                
                if image1_col:
                    # 画像1列が空白の行を特定
                    blank_mask = combined_df[image1_col].isna() | (combined_df[image1_col].astype(str).str.strip() == '')
                    blank_indices = blank_mask[blank_mask].index
                    
                    if len(blank_indices) > 0:
                        # 各空白行について、全ての画像列を補充
                        for idx in blank_indices:
                            product_code = combined_df.at[idx, product_code_col]
                            
                            if pd.isna(product_code) or str(product_code).strip() == '':
                                continue
                            
                            # 全ての画像列をチェック
                            for img_col in image_cols:
                                img_match = re.search(r'画像(\d+)', img_col)
                                if not img_match:
                                    continue
                                
                                img_num = int(img_match.group(1))
                                image_filename = f"{str(product_code)}-{img_num}.jpg"
                                image_path = os.path.join(IMAGE_BASE_PATH, image_filename)
                                
                                if os.path.exists(image_path):
                                    combined_df.at[idx, img_col] = image_filename
                                    new_image_files.add(image_filename)
                                    filled_count += 1
                    
                    if filled_count > 0:
                        print(f"    [OK] {filled_count} 件の画像欄を補充（{len(blank_indices)}商品）")
        
        removed_blank = 0
        removed_dup = 0
        
        # 商品コード列を改めて特定（既に特定済みの場合）
        if not product_code_col:
            for col in ['商品コード', '品番ID']:
                if col in combined_df.columns:
                    product_code_col = col
                    break
        
        if product_code_col:
            print(f"\n[*] 重複排除処理を開始...")
            
            # 1. 商品コードが空白の行を除去
            before_count = len(combined_df)
            combined_df = combined_df[
                combined_df[product_code_col].notna() & 
                (combined_df[product_code_col].astype(str).str.strip() != '')
            ]
            removed_blank = before_count - len(combined_df)
            if removed_blank > 0:
                print(f"    [*] 商品コード空白の商品を除去: {removed_blank} 件")
            
            # 2. 商品コードの重複をチェック
            duplicate_codes = combined_df[combined_df.duplicated(subset=[product_code_col], keep=False)]
            if not duplicate_codes.empty:
                unique_dup_codes = duplicate_codes[product_code_col].unique()
                print(f"    [*] 重複している商品コード数: {len(unique_dup_codes)} 件")
                
                # 重複している商品コードごとに処理
                rows_to_keep = []
                processed_codes = set()
                
                for idx, row in combined_df.iterrows():
                    code = row[product_code_col]
                    
                    # 既に処理済みのコードはスキップ
                    if code in processed_codes:
                        continue
                    
                    # 同じ商品コードの全ての行を取得
                    same_code_rows = combined_df[combined_df[product_code_col] == code]
                    
                    if len(same_code_rows) == 1:
                        # 重複なし
                        rows_to_keep.append(idx)
                    else:
                        # 重複あり：優先順位に基づいて1件を選択
                        # 優先順位: 1) 商品IDが存在する（既存商品）, 2) 商品IDが小さい
                        
                        # 商品IDがある行とない行を分類
                        rows_with_id = same_code_rows[
                            same_code_rows[base_id_col].notna() & 
                            (same_code_rows[base_id_col].astype(str).str.strip() != '')
                        ]
                        rows_without_id = same_code_rows[
                            same_code_rows[base_id_col].isna() | 
                            (same_code_rows[base_id_col].astype(str).str.strip() == '')
                        ]
                        
                        if not rows_with_id.empty:
                            # 商品IDがある行（既存商品）から、IDが最小のものを選択
                            rows_with_id_copy = rows_with_id.copy()
                            rows_with_id_copy['_id_numeric'] = pd.to_numeric(
                                rows_with_id_copy[base_id_col], errors='coerce'
                            )
                            selected_row = rows_with_id_copy.sort_values('_id_numeric').iloc[0]
                            rows_to_keep.append(selected_row.name)
                        else:
                            # 全て商品IDがない場合（新規追加のみ）は最初の1件を保持
                            rows_to_keep.append(same_code_rows.iloc[0].name)
                    
                    processed_codes.add(code)
                
                # 選択された行のみを残す
                before_count = len(combined_df)
                combined_df = combined_df.loc[rows_to_keep]
                removed_dup = before_count - len(combined_df)
                if removed_dup > 0:
                    print(f"    [*] 商品コード重複の商品を除去: {removed_dup} 件")
            
            print(f"    [OK] 重複排除後: {len(combined_df)} 件")
        
        # 新しいファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.dirname(BASE_FILE)
        output_file = os.path.join(output_dir, f"dorekai-base-updated_{timestamp}.csv")

        # 種類ID/種類在庫数を数値に正規化
        if '種類ID' in combined_df.columns:
            combined_df['種類ID'] = pd.to_numeric(combined_df['種類ID'], errors='coerce').astype('Int64')
        if '種類在庫数' in combined_df.columns:
            combined_df['種類在庫数'] = pd.to_numeric(combined_df['種類在庫数'], errors='coerce').astype('Int64')
            if '種類ID' in combined_df.columns:
                combined_df.loc[combined_df['種類ID'].isna(), '種類在庫数'] = np.nan

        # 公開状態は0/1に正規化（空白は0）
        if '公開状態' in combined_df.columns:
            combined_df['公開状態'] = pd.to_numeric(combined_df['公開状態'], errors='coerce').fillna(0).astype('Int64')
        
        # ファイルに保存
        print(f"\n[*] ファイルを保存中: {os.path.basename(output_file)}")
        combined_df.to_csv(output_file, index=False, encoding='shift-jis')

        # dorekai-base-updated_*.csv は最新5件のみ保持
        updated_files = glob.glob(os.path.join(output_dir, "dorekai-base-updated_*.csv"))
        if len(updated_files) > 5:
            updated_files.sort(key=os.path.getmtime, reverse=True)
            old_files = updated_files[5:]
            for old_file in old_files:
                try:
                    os.remove(old_file)
                except OSError:
                    pass
            print(f"[*] 古い更新ファイルを削除: {len(old_files)} 件")

        # dorekai-base-shop-*.csv は最新5件のみ保持
        shop_files = glob.glob(os.path.join(output_dir, "dorekai-base-shop-*.csv"))
        if len(shop_files) > 5:
            shop_files.sort(key=os.path.getmtime, reverse=True)
            old_shop_files = shop_files[5:]
            for old_file in old_shop_files:
                try:
                    os.remove(old_file)
                except OSError:
                    pass
            print(f"[*] 古いベースファイルを削除: {len(old_shop_files)} 件")

        # 新しく追加された画像をコピーしてZIP化
        if new_image_files:
            zip_path = os.path.join(output_dir, "dorekai-base-image.zip")
            temp_image_dir = os.path.join(output_dir, "dorekai-base-image")
            os.makedirs(temp_image_dir, exist_ok=True)

            copied_count = 0
            for image_filename in sorted(new_image_files):
                src_path = os.path.join(IMAGE_BASE_PATH, image_filename)
                if os.path.exists(src_path):
                    dst_path = os.path.join(temp_image_dir, image_filename)
                    shutil.copy2(src_path, dst_path)
                    copied_count += 1

            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
                for image_filename in os.listdir(temp_image_dir):
                    file_path = os.path.join(temp_image_dir, image_filename)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, arcname=image_filename)

            shutil.rmtree(temp_image_dir, ignore_errors=True)

            print(f"\n[*] 画像コピー: {copied_count} 件")
            print(f"[*] 画像ZIP作成: {zip_path}")
        
        print("\n" + "=" * 80)
        print("[OK] 処理完了!")
        print("=" * 80)
        print(f"[*] 統計:")
        print(f"    元のベースファイル: {len(base_df)} 件")
        print(f"    ソースファイル: {len(source_df)} 件")
        print(f"    既存商品更新: {updated_count} 件")
        print(f"    新規商品追加: {added_count} 件")
        if removed_blank > 0:
            print(f"    商品コード空白除去: -{removed_blank} 件")
        if removed_dup > 0:
            print(f"    商品コード重複除去: -{removed_dup} 件")
        print(f"    最終出力: {len(combined_df)} 件")
        print(f"\n[*] 保存先: {output_file}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR] エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
