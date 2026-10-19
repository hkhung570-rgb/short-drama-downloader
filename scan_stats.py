import os, json

DOWNLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
platforms = {}
total_eps = 0
total_bytes = 0

for plat in sorted(os.listdir(DOWNLOADS)):
    plat_path = os.path.join(DOWNLOADS, plat)
    if not os.path.isdir(plat_path):
        continue
    dramas = []
    for d in sorted(os.listdir(plat_path)):
        d_path = os.path.join(plat_path, d)
        if not os.path.isdir(d_path) or d.startswith('_'):
            continue
        mp4s = [f for f in os.listdir(d_path) if f.endswith('.mp4') and '.compressed' not in f and '.temp' not in f]
        size = sum(os.path.getsize(os.path.join(d_path, f)) for f in os.listdir(d_path) if os.path.isfile(os.path.join(d_path, f)))
        total_bytes += size
        total_eps += len(mp4s)
        dramas.append(dict(name=d, eps=len(mp4s), size_mb=round(size/1024/1024, 1)))
    platforms[plat] = dramas

print('总计: %d 部剧, %d 集, %.2f GB' % (
    sum(len(v) for v in platforms.values()), total_eps, total_bytes/1024/1024/1024))

for plat, dramas in platforms.items():
    if not dramas:
        continue
    print('\n== %s (%d 部) ==' % (plat, len(dramas)))
    for d in dramas:
        print('  %s  %d集  %.1fMB' % (d['name'], d['eps'], d['size_mb']))
