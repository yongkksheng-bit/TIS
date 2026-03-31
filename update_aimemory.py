# -*- coding: utf-8 -*-
content = open('D:/tis_project/AI_MEMORY.md', 'r', encoding='utf-8', errors='replace').read()
idx = content.find('短期路线图')
print('Found at:', idx)
if idx >= 0:
    print(repr(content[idx:idx+500]))
else:
    print('NOT FOUND')
