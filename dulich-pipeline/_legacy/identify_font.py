from fontTools.ttLib import TTFont
import sys

path = sys.argv[1]
font = TTFont(path)
name_table = font['name']
for record in name_table.names:
    if record.nameID in (1, 2, 4):
        try:
            print(f'ID{record.nameID}: {record.toUnicode()}')
        except:
            pass
