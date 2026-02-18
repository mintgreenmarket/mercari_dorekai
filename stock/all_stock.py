"""
全プラットフォーム在庫取得スクリプト（高速版）
メルカリ、ラクマ、ヤフオク、BASEの在庫数を最速で取得します
"""

import os
import sys
import time
import pandas as pd
import re
import glob
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# ===== 設定 =====
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
DOWNLOAD_DIR = ROOT_DIR / 'downloads'

# CSVファイルパス
def get_latest_file(directory, pattern):
    """指定されたディレクトリからパターンに マッチする最新ファイルを取得"""
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        return None
    return max(files, key=os.path.getctime)

# メルカリ: product_data_*最新.csv
MERCARI_CSV = get_latest_file(DOWNLOAD_DIR, 'product_data_*.csv')

# BASE: base_products_*最新.csv
BASE_CSV_PATH = get_latest_file(DOWNLOAD_DIR, 'base_products_*.csv')
# フォールバック: stock ディレクトリの products_base.csv
if not BASE_CSV_PATH:
    BASE_CSV_PATH = ROOT_DIR / 'stock' / 'products_base.csv'
BASE_CSV = BASE_CSV_PATH

# ラクマ
RAKUMA_CSV = ROOT_DIR / 'products_rakuma.csv'

# ヤフオク
YAHOOKU_CSV = ROOT_DIR / 'products_yahooku.csv'

# ===== ユーティリティ関数 =====

def extract_hinban(text: str) -> Optional[str]:
    """商品名から品番（先頭の3-6桁の数字）を抽出"""
    if not isinstance(text, str):
        return None
    match = re.match(r'^\s*(\d{3,6})', text)
    return match.group(1) if match else None

def cleanup_old_files(directory, pattern: str, keep: int = 10):
    """
    指定されたディレクトリから特定パターンのファイルを保持数まで削除
    
    Args:
        directory: 対象ディレクトリ
        pattern: ファイル名パターン（glob）
        keep: 保持するファイル数
    """
    import glob
    files = glob.glob(os.path.join(directory, pattern))
    if len(files) <= keep:
        return
    
    # ファイルを更新日時でソート（新しい順）
    files.sort(key=os.path.getctime, reverse=True)
    
    # 古いファイルを削除
    for old_file in files[keep:]:
        try:
            os.remove(old_file)
            print(f"  🗑️ 削除: {os.path.basename(old_file)}")
        except Exception as e:
            print(f"  ⚠️ 削除失敗: {os.path.basename(old_file)} - {e}")

def print_header(text: str):
    """ヘッダー表示"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def print_result(platform: str, total: int, by_hinban: int, duration: float):
    """結果表示"""
    print(f" {platform:12} | 総在庫: {total:>6}個 | 品番数: {by_hinban:>4} | {duration:.2f}秒")

# ===== メルカリ在庫取得 =====

def get_mercari_stock() -> Tuple[int, int, float]:
    """
    メルカリの在庫を取得（CSVから読み込み）
    戻り値: (総在庫数, 品番数, 処理時間)
    """
    start = time.time()
    
    if not MERCARI_CSV or not os.path.exists(MERCARI_CSV):
        print(f" メルカリCSVが見つかりません: {DOWNLOAD_DIR / 'product_data_*.csv'}")
        return 0, 0, time.time() - start
    
    try:
        # メルカリCSVはcp932エンコーディング
        df = pd.read_csv(MERCARI_CSV, encoding='cp932')
        
        # 在庫列を探す（複数の可能性を考慮）
        stock_col = None
        for col in ['在庫数', 'SKU1_現在の在庫数', '在庫', 'stock']:
            if col in df.columns:
                stock_col = col
                break
        
        if stock_col is None:
            print(f" メルカリCSVに在庫列が見つかりません")
            return 0, 0, time.time() - start
        
        # 商品ステータスが2（公開中）かつSKU1_現在の在庫数が1以上のみをカウント
        if '商品ステータス' in df.columns:
            df = df[df['商品ステータス'] == 2]
        if 'SKU1_現在の在庫数' in df.columns:
            df = df[df['SKU1_現在の在庫数'] >= 1]
        
        # 在庫数を集計
        total_stock = int(df[stock_col].fillna(0).sum())
        
        # 品番数をカウント
        if '商品名' in df.columns:
            hinban_list = df['商品名'].apply(extract_hinban)
            hinban_count = hinban_list.nunique()
        else:
            hinban_count = 0
        
        return total_stock, hinban_count, time.time() - start
    
    except Exception as e:
        print(f" メルカリ在庫取得エラー: {e}")
        return 0, 0, time.time() - start

# ===== ラクマ在庫取得 =====

def get_rakuma_stock() -> Tuple[int, int, float]:
    """
    ラクマの在庫を取得（CSVから読み込み）
    戻り値: (総在庫数, 品番数, 処理時間)
    """
    start = time.time()
    
    if not RAKUMA_CSV.exists():
        print(f" ラクマCSVが見つかりません: {RAKUMA_CSV}")
        return 0, 0, time.time() - start
    
    try:
        df = pd.read_csv(RAKUMA_CSV, encoding='utf-8-sig')
        
        # ラクマは出品されている商品=在庫1としてカウント
        # 削除対象は除外
        if '削除' in df.columns:
            df = df[df['削除'] != '削除']
        
        total_stock = len(df)
        
        # 品番数をカウント
        if '品番' not in df.columns and '商品名' in df.columns:
            df['品番'] = df['商品名'].apply(extract_hinban)
        
        hinban_count = df['品番'].nunique() if '品番' in df.columns else 0
        
        return total_stock, hinban_count, time.time() - start
    
    except Exception as e:
        print(f" ラクマ在庫取得エラー: {e}")
        return 0, 0, time.time() - start

# ===== ヤフオク在庫取得 =====

def get_yahooku_stock() -> Tuple[int, int, float]:
    """
    ヤフオクの在庫を取得（CSVから読み込み）
    戻り値: (総在庫数, 品番数, 処理時間)
    """
    start = time.time()
    
    if not YAHOOKU_CSV.exists():
        print(f" ヤフオクCSVが見つかりません: {YAHOOKU_CSV}")
        return 0, 0, time.time() - start
    
    try:
        df = pd.read_csv(YAHOOKU_CSV, encoding='utf-8-sig')
        
        # 出品中の商品のみカウント（ステータス列がある場合）
        if 'ステータス' in df.columns:
            df = df[df['ステータス'] == '出品中']
        
        total_stock = len(df)
        
        # 品番数をカウント
        if '品番' not in df.columns and '商品名' in df.columns:
            df['品番'] = df['商品名'].apply(extract_hinban)
        
        hinban_count = df['品番'].nunique() if '品番' in df.columns else 0
        
        return total_stock, hinban_count, time.time() - start
    
    except Exception as e:
        print(f" ヤフオク在庫取得エラー: {e}")
        return 0, 0, time.time() - start

# ===== BASE在庫取得 =====

def get_base_stock() -> Tuple[int, int, float]:
    """
    BASEの在庫をCSVから取得
    戻り値: (総在庫数, 品番数, 処理時間)
    """
    start = time.time()
    
    if not BASE_CSV or not os.path.exists(BASE_CSV):
        print(f" BASECSVが見つかりません: {DOWNLOAD_DIR / 'base_products_*.csv'}")
        print(f" 💡 base_csv_downloader.py を実行してCSVをダウンロードしてください")
        return 0, 0, time.time() - start
    
    try:
        df = pd.read_csv(BASE_CSV, encoding='shift-jis')
        
        # 公開状态が1かつ在庫数が1以上のみ
        if '公開状态' in df.columns:
            df = df[df['公開状态'] == 1]
        if '在庫数' in df.columns:
            df = df[df['在庫数'] >= 1]
        
        # 在庫列を探す
        stock_col = None
        for col in ['在庫数', '在庫', 'stock', '現在の在庫数']:
            if col in df.columns:
                stock_col = col
                break
        
        if stock_col:
            total_stock = int(df[stock_col].fillna(0).sum())
        else:
            print(f" ⚠️ BASECSVに在庫列が見つかりません")
            total_stock = 0
        
        # 品番数をカウント
        if '品番' not in df.columns and '商品名' in df.columns:
            df['品番'] = df['商品名'].apply(extract_hinban)
        
        hinban_count = df['品番'].nunique() if '品番' in df.columns else 0
        
        return total_stock, hinban_count, time.time() - start
    
    except Exception as e:
        print(f" BASE在庫取得エラー: {e}")
        return 0, 0, time.time() - start

# ===== 品番別在庫取得 =====

def get_platform_stock_by_hinban(csv_path, platform_name: str, 
                                  stock_col_names: list = None,
                                  filter_conditions: dict = None,
                                  encoding: str = 'utf-8-sig') -> pd.DataFrame:
    """
    指定プラットフォームの品番別在庫を取得
    
    Args:
        csv_path: CSVファイルパス
        platform_name: プラットフォーム名（列名に使用）
        stock_col_names: 在庫列の候補名リスト
        filter_conditions: フィルター条件の辞書
        encoding: ファイルエンコーディング
    
    Returns:
        品番と在庫数のDataFrame
    """
    if not csv_path or not os.path.exists(csv_path):
        return pd.DataFrame(columns=['品番', platform_name])
    
    try:
        df = pd.read_csv(csv_path, encoding=encoding)
        
        # フィルター条件を適用
        if filter_conditions:
            for col, value in filter_conditions.items():
                if col in df.columns:
                    if callable(value):
                        df = df[value(df[col])]
                    else:
                        df = df[df[col] == value]
        
        # 品番を抽出（まだない場合）
        if '品番' not in df.columns:
            if '商品名' in df.columns:
                df = df.copy()
                df['品番'] = df['商品名'].apply(extract_hinban)
            else:
                return pd.DataFrame(columns=['品番', platform_name])
        
        # 品番がない行を除外
        if '品番' in df.columns:
            df = df[df['品番'].notna()]
        else:
            # 品番列がない場合は商品名から抽出
            if '商品名' in df.columns:
                df = df.copy()
                df['品番'] = df['商品名'].apply(extract_hinban)
                df = df[df['品番'].notna()]
            else:
                return pd.DataFrame(columns=['品番', platform_name])
        
        # 在庫列を探す
        stock_col = None
        if stock_col_names:
            for col in stock_col_names:
                if col in df.columns:
                    stock_col = col
                    break
        
        if stock_col:
            # 在庫数を集計（品番ごとに合計）
            result = df.groupby('品番')[stock_col].sum().reset_index()
            result.columns = ['品番', platform_name]
            result[platform_name] = result[platform_name].fillna(0).astype(int)
        else:
            # 在庫列がない場合は出品数をカウント
            result = df.groupby('品番').size().reset_index()
            result.columns = ['品番', platform_name]
        
        # 品番を文字列型に統一（マージ時のエラー防止）
        result['品番'] = result['品番'].astype(str)
        
        return result
    
    except Exception as e:
        print(f" ⚠️ {platform_name}データ読込エラー: {e}")
        return pd.DataFrame(columns=['品番', platform_name])

def create_stock_by_hinban_csv() -> pd.DataFrame:
    """
    全プラットフォームの品番別在庫を統合したDataFrameを作成
    
    Returns:
        統合されたDataFrame（品番、メルカリ、ラクマ、ヤフオク、BASE列）
    """
    print("\n 品番別在庫データを作成中...")
    
    # メルカリ
    mercari_df = get_platform_stock_by_hinban(
        MERCARI_CSV, 
        'メルカリ',
        stock_col_names=['在庫数', 'SKU1_現在の在庫数', '在庫', 'stock'],
        filter_conditions={'商品ステータス': 2, 'SKU1_現在の在庫数': lambda x: x >= 1},
        encoding='cp932'
    )
    
    # ラクマ
    rakuma_df = get_platform_stock_by_hinban(
        RAKUMA_CSV,
        'ラクマ',
        filter_conditions={'削除': lambda x: x != '削除'},
        encoding='utf-8-sig'
    )
    
    # ヤフオク
    yahooku_df = get_platform_stock_by_hinban(
        YAHOOKU_CSV,
        'ヤフオク',
        filter_conditions={'ステータス': '出品中'},
        encoding='utf-8-sig'
    )
    
    # BASE
    base_df = get_platform_stock_by_hinban(
        BASE_CSV,
        'BASE',
        stock_col_names=['在庫数', '現在の在庫数', '在庫', 'stock'],
        filter_conditions={'公開状态': 1, '在庫数': lambda x: x >= 1},
        encoding='shift-jis'
    )
    
    # 全データフレームを統合
    all_dfs = [mercari_df, rakuma_df, yahooku_df, base_df]
    
    # 全データフレームの品番をstr型に統一
    for i, df in enumerate(all_dfs):
        df['品番'] = df['品番'].astype(str)
        all_dfs[i] = df
    
    # 品番をキーに外部結合
    result = all_dfs[0]
    for df in all_dfs[1:]:
        result = pd.merge(result, df, on='品番', how='outer')
    
    # NaNを0に置き換え
    result = result.fillna(0)
    
    # 品番を数値に変換（ソート用）
    result['品番'] = result['品番'].astype(float).astype(int)
    
    # 各プラットフォームの列を整数型に変換
    for col in ['メルカリ', 'ラクマ', 'ヤフオク', 'BASE']:
        if col in result.columns:
            result[col] = result[col].astype(int)
    
    # 合計列を追加
    result['合計'] = result[['メルカリ', 'ラクマ', 'ヤフオク', 'BASE']].sum(axis=1)
    result['合計'] = result['合計'].astype(int)
    
    # ソート優先順位: 合計(降順) → メルカリ(降順) → BASE(降順) → 品番(昇順)
    result = result.sort_values(
        by=['合計', 'メルカリ', 'BASE', '品番'],
        ascending=[False, False, False, True]
    )
    
    # 品番を文字列に変換（CSV出力用）
    result['品番'] = result['品番'].astype(str)
    
    # 列の順序を変更（品番, 合計, メルカリ, ラクマ, ヤフオク, BASE）
    result = result[['品番', '合計', 'メルカリ', 'ラクマ', 'ヤフオク', 'BASE']]
    
    print(f" ✅ {len(result)}件の品番データを作成")
    
    return result

# ===== メイン処理 =====

def main():
    """メイン処理"""
    print_header("全プラットフォーム在庫取得（高速版）")
    
    start_time = time.time()
    
    # 各プラットフォームの在庫を並行して取得
    print("\n 在庫取得中...\n")
    
    # メルカリ
    mercari_stock, mercari_hinban, mercari_time = get_mercari_stock()
    print_result("メルカリ", mercari_stock, mercari_hinban, mercari_time)
    
    # ラクマ
    rakuma_stock, rakuma_hinban, rakuma_time = get_rakuma_stock()
    print_result("ラクマ", rakuma_stock, rakuma_hinban, rakuma_time)
    
    # ヤフオク
    yahooku_stock, yahooku_hinban, yahooku_time = get_yahooku_stock()
    print_result("ヤフオク", yahooku_stock, yahooku_hinban, yahooku_time)
    
    # BASE（CSVから取得）
    base_stock, base_hinban, base_time = get_base_stock()
    print_result("BASE", base_stock, base_hinban, base_time)
    
    # 合計
    total_stock = mercari_stock + rakuma_stock + yahooku_stock + base_stock
    total_time = time.time() - start_time
    
    print("\n" + "="*60)
    print(f" 総在庫数: {total_stock:,}個")
    print(f"  処理時間: {total_time:.2f}秒")
    print("="*60)
    
    # 詳細サマリー
    print("\n プラットフォーム別内訳:")
    print(f"  メルカリ:  {mercari_stock:>6}個 ({mercari_stock/total_stock*100 if total_stock > 0 else 0:>5.1f}%)")
    print(f"  ラクマ:    {rakuma_stock:>6}個 ({rakuma_stock/total_stock*100 if total_stock > 0 else 0:>5.1f}%)")
    print(f"  ヤフオク:  {yahooku_stock:>6}個 ({yahooku_stock/total_stock*100 if total_stock > 0 else 0:>5.1f}%)")
    print(f"  BASE:      {base_stock:>6}個 ({base_stock/total_stock*100 if total_stock > 0 else 0:>5.1f}%)")
    
    # CSV出力オプション
    if '--csv' in sys.argv:
        output_file = SCRIPT_DIR / f"stock_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        summary_df = pd.DataFrame([
            {'プラットフォーム': 'メルカリ', '在庫数': mercari_stock, '品番数': mercari_hinban},
            {'プラットフォーム': 'ラクマ', '在庫数': rakuma_stock, '品番数': rakuma_hinban},
            {'プラットフォーム': 'ヤフオク', '在庫数': yahooku_stock, '品番数': yahooku_hinban},
            {'プラットフォーム': 'BASE', '在庫数': base_stock, '品番数': base_hinban},
            {'プラットフォーム': '合計', '在庫数': total_stock, '品番数': '-'},
        ])
        summary_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n サマリーCSV保存: {output_file}")
    
    # 品番別CSV出力（デフォルトで実行）
    if '--no-hinban' not in sys.argv:
        try:
            hinban_df = create_stock_by_hinban_csv()
            if not hinban_df.empty:
                output_file = SCRIPT_DIR / f"stock_by_hinban_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                hinban_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"\n 品番別CSV保存: {output_file}")
                print(f" 📋 総品番数: {len(hinban_df)}件")
                
                # 簡易統計を表示
                has_stock = hinban_df[hinban_df['合計'] > 0]
                print(f" 📦 在庫あり: {len(has_stock)}件")
                print(f" 📭 在庫なし: {len(hinban_df) - len(has_stock)}件")
                
                # 古いファイルをクリーンアップ（最新10件を保持）
                print(f"\n 📂 古いファイルをクリーンアップ中...")
                cleanup_old_files(SCRIPT_DIR, "stock_by_hinban_*.csv", keep=10)
        except Exception as e:
            print(f"\n ⚠️ 品番別CSV作成エラー: {e}")
    
    print("\n 処理完了\n")
    
    # オプションヘルプ
    if '--help' in sys.argv or '-h' in sys.argv:
        print("使用方法:")
        print("  python all_stock.py             # 全プラットフォームの在庫を取得し品番別CSVを出力")
        print("  python all_stock.py --csv       # サマリーCSVも出力")
        print("  python all_stock.py --no-hinban # 品番別CSVを出力しない")
        print("  python all_stock.py -h          # ヘルプ表示")
        print("\nBASE在庫の更新:")
        print("  python base_csv_downloader.py   # BASE管理画面からCSVをダウンロード")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n 処理を中断しました")
    except Exception as e:
        print(f"\n エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
