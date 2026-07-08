from fonttools.ttLib import TTFont

tt = TTFont('assets/fonts/DancingScript-VF.ttf')
cmap = tt.getBestCmap()
tests = [
    (225,  'a-acute (a)'),
    (7883, 'i-dot-below (i)'),
    (7909, 'u-hook (u)'),
    (7907, 'o-hook-dot (o)'),
    (259,  'a-breve'),
    (7855, 'a-breve-acute'),
]
for cp, name in tests:
    has = "YES" if cp in cmap else "NO"
    print(f"U+{cp:04X} {name}: {has}")
