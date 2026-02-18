import re

with open('all_stock.py', 'r', encoding='utf-8') as f:
    content = f.read()

# エスケープされた引用符を修正
content = content.replace('\\"\\"\\"', '"""')
content = content.replace('\\"', '"')

with open('all_stock.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ 修正完了')
