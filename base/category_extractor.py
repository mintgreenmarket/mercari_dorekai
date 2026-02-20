"""
カテゴリ抽出スクリプト
base-product-filter.phpのロジックをPythonで実装
商品CSVからブランド、サイズ、カラー、スカート丈を抽出する
"""

import pandas as pd
import re
import os
from pathlib import Path

# 設定
INPUT_CSV = Path(__file__).parent / 'カテゴリ抽出.csv'
OUTPUT_CSV = Path(__file__).parent / 'category_extracted.csv'

# フィルター定義（PHPと同じ）
FILTER_DEFINITIONS = {
    "brand": {
        "Ambient": ["Ambient"],
        "an Andy": ["an", "アン"],
        "Andy": ["Andy"],
        "Angel R": ["Angel R", "エンジェルアール"],
        "BayBClub": ["BayBClub"],
        "Ck Calvinklein": ["Calvin Klein"],
        "COCO&YUKA": ["COCO&YUKA"],
        "dazzy": ["dazzy"],
        "EmiriaWiz": ["EmiriaWiz"],
        "ERUKEI": ["ERUKEI", "エルケイ"],
        "GRL": ["GRL"],
        "H&M": ["H&M"],
        "IRMA": ["IRMA"],
        "JEAN MACLEAN": ["JEAN MACLEAN"],
        "JEWELS": ["JEWELS", "ジュエルズ"],
        "LIPSY": ["LIPSY"],
        "ROBE de FLEURS": ["ROBE de FLEURS"],
        "Ryuyu": ["Ryuyu"],
        "Tika": ["Tika"],
        "ZARA": ["ZARA"],
        "その他": ["その他"]
    },
    "color": {
        "ブラック": ["ブラック", "黒"],
        "ホワイト": ["ホワイト", "白"],
        "レッド": ["レッド", "赤"],
        "ブルー": ["ブルー", "青"],
        "ピンク": ["ピンク"],
        "ゴールド": ["ゴールド", "金"],
        "ネイビー": ["ネイビー", "紺"],
        "グレー": ["グレー", "灰"],
        "ベージュ": ["ベージュ"]
    },
    "size": {
        "XS": ["XS"],
        "S": ["S"],
        "M": ["M"],
        "L": ["L"],
        "XL": ["XL"],
        "FREE": ["FREE", "F"]
    },
    "length": ["ロング", "ミディ", "ミニ"]
}

def extract_number(text):
    """テキストから最初の数字を抽出"""
    if pd.isna(text):
        return None
    text = str(text).strip()
    match = re.search(r'\d+', text)
    return match.group(0) if match else None

def is_english_or_number(text):
    """英数字を含むかチェック"""
    return bool(re.search(r'[a-zA-Z0-9]', text))

def word_boundary_match(pattern, text, is_english=False):
    """単語境界でマッチさせる"""
    if is_english:
        # 英数字の場合は単語境界で完全一致
        return bool(re.search(r'\b' + re.escape(pattern) + r'\b', text, re.IGNORECASE))
    else:
        # 日本語の場合は前後の空白で判定
        return bool(re.search(r'(^|[\s\(\[\{])' + re.escape(pattern) + r'([\s\)\]\}]|$)', ' ' + text + ' '))

def extract_brand(title, description):
    """PHPのブランド判定ロジックをPythonで実装"""
    full_text = title + "\n" + description
    brand = None
    max_len = 0

    # タイトルから検索
    for category, keywords in FILTER_DEFINITIONS['brand'].items():
        if category == 'その他':
            continue
        for keyword in keywords:
            matched = False

            # ★特別処理: "an" は完全一致（単語境界）のみ
            if keyword == 'an':
                if word_boundary_match('an', title, is_english=True):
                    matched = True
            # "アン" は完全一致のみ（スペース区切り）
            elif keyword == 'アン':
                if len(title) >= 2:
                    if word_boundary_match('アン', title, is_english=False):
                        matched = True
            # その他のブランド
            elif is_english_or_number(keyword):
                if word_boundary_match(keyword, title, is_english=True):
                    matched = True
            else:
                if keyword in title:
                    matched = True

            if matched and len(keyword) > max_len:
                brand = category
                max_len = len(keyword)

    # タイトルになく、品番っぽくなければ説明文検索
    if not brand:
        if not re.match(r'^\s*\d+\s', title) and not re.search(r'\b([A-Z][a-zA-Z]{2,})\b', title):
            for category, keywords in FILTER_DEFINITIONS['brand'].items():
                if category == 'その他':
                    continue
                for keyword in keywords:
                    if keyword.lower() in description.lower():
                        brand = category
                        break
                if brand:
                    break

    return brand if brand else 'その他'

def extract_colors(description):
    """カラー判定（説明文のみから取得）"""
    colors = []
    for category, keywords in FILTER_DEFINITIONS['color'].items():
        for keyword in keywords:
            if keyword in description:
                colors.append(category)
                break
    return list(set(colors))  # 重複を除去

def extract_size(title, description):
    """サイズ判定"""
    full_text = title + "\n" + description
    for category, keywords in FILTER_DEFINITIONS['size'].items():
        for keyword in keywords:
            # サイズはスペースまたは括弧で囲まれた状態で検索
            if re.search(r'[\s\(\[\{]' + re.escape(keyword) + r'[\s\)\]\}]', ' ' + full_text + ' ', re.IGNORECASE):
                return category
            if re.search(r'サイズ[:：\s]*' + re.escape(keyword), full_text, re.IGNORECASE):
                return category
    return None

def extract_length(title):
    """丈判定（商品名のみから）"""
    for length in FILTER_DEFINITIONS['length']:
        if length.lower() in title.lower():
            return length
    return None

def process_csv(input_path, output_path):
    """CSVを読み込んでカテゴリを抽出"""
    print(f"📖 ファイルを読み込み中: {input_path}")
    
    try:
        # エンコーディングを試す
        try:
            df = pd.read_csv(input_path, encoding='utf-8')
        except:
            try:
                df = pd.read_csv(input_path, encoding='cp932')
            except:
                df = pd.read_csv(input_path, encoding='shift_jis')
        
        print(f"✅ {len(df)}行を読み込みました")
        print(f"📊 カラム: {list(df.columns)}")
        
        # 商品名と説明文のカラム名を特定
        title_col = None
        desc_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if any(x in col_lower for x in ['商品名', 'title', 'product']):
                title_col = col
            if any(x in col_lower for x in ['説明', 'description', 'detail', '詳細']):
                desc_col = col
        
        if not title_col:
            # デフォルト（1列目がタイトルと仮定）
            title_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        if not desc_col:
            # デフォルト（3列目が説明と仮定）
            desc_col = df.columns[2] if len(df.columns) > 2 else df.columns[0]
        
        print(f"📌 商品名カラム: {title_col}")
        print(f"📌 説明文カラム: {desc_col}")
        
        # カテゴリを抽出
        print("\n🔄 カテゴリを抽出中...")
        df['ブランド'] = df.apply(
            lambda row: extract_brand(
                str(row.get(title_col, '')),
                str(row.get(desc_col, ''))
            ), axis=1
        )
        
        df['サイズ'] = df.apply(
            lambda row: extract_size(
                str(row.get(title_col, '')),
                str(row.get(desc_col, ''))
            ), axis=1
        )
        
        df['カラー'] = df.apply(
            lambda row: ','.join(extract_colors(str(row.get(desc_col, '')))), axis=1
        )
        
        df['スカート丈'] = df.apply(
            lambda row: extract_length(str(row.get(title_col, ''))), axis=1
        )
        
        # ブランド整理（4件以上のブランドのみフィルタリング）
        brand_counts = df['ブランド'].value_counts()
        df['ブランド'] = df['ブランド'].apply(
            lambda x: x if x == 'その他' or brand_counts.get(x, 0) >= 4 else 'その他'
        )
        
        # 出力CSV（元の列 + 抽出された4カラム）
        output_df = df[[title_col, desc_col, 'ブランド', 'サイズ', 'カラー', 'スカート丈']]
        
        # ファイルに保存
        output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ 抽出完了！")
        print(f"📁 出力ファイル: {output_path}")
        print(f"📊 処理行数: {len(output_df)}行")
        print(f"\n統計:")
        print(f"  ブランド種別: {df['ブランド'].nunique()}種")
        print(f"  サイズ種別: {df['サイズ'].nunique()}種")
        print(f"  カラー種別: {len(set(','.join(df['カラー'].dropna()).split(',')))}種")
        print(f"  丈種別: {df['スカート丈'].nunique()}種")
        
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if INPUT_CSV.exists():
        process_csv(INPUT_CSV, OUTPUT_CSV)
    else:
        print(f"❌ ファイルが見つかりません: {INPUT_CSV}")
