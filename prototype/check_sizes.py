import urllib.request
import json
import os

episodes = [
    {"n": 1, "title": "The Real Daughter Comes to Collect", "url": "https://huangguodrama.ai/trailers/30841.mp4"},
    {"n": 2, "title": "Five Million, Interest by the Day", "url": "https://huangguo.chat/motion/drama-episodes/6c75e1b1992fa71dc6807d118a64a3aa7cc635ba7aff640643cbc030c8ddb15d.mp4"},
    {"n": 3, "title": "Caught in the Moment", "url": "https://huangguo.chat/motion/drama-episodes/daf40e96f15cfa3ea6609672cbc749883068992e5ca3090cdaae1c74215a7818.mp4"},
    {"n": 4, "title": "She Covers for Sheila", "url": "https://huangguo.chat/motion/drama-episodes/0b7f84021843bc6f1df50310eef567638604bd1dc3c5b0ce18514964f4f301f9.mp4"},
    {"n": 5, "title": "A Game of Three Silent Minutes", "url": "https://huangguo.chat/motion/drama-episodes/a4d301af65ba2d1620ec9b432e415248102ae061865f7d82380e83e63cb646ff.mp4"},
    {"n": 6, "title": "Only One Minute Left", "url": "https://huangguo.chat/motion/drama-episodes/8bf1dc74a9646cc5f5679d8dfb1ec5e4e13857c299d4ad17617226f0b67c0d0d.mp4"},
    {"n": 7, "title": "The Way She Looks at Me Is So Gentle", "url": "https://huangguo.chat/motion/drama-episodes/b292f1d39e34195fc882b35ff9d391f4482f8c6786b4b2e087acb69a24cd950f.mp4"},
    {"n": 8, "title": "So She's an Underground Godmother", "url": "https://huangguo.chat/motion/drama-episodes/df94bfff6dda8cc30ff1ba540afa09fbc3d6e824d3d3674d77ee4407d0cd3def.mp4"},
    {"n": 9, "title": "On the Auction Block After One Glass of Water", "url": "https://huangguo.chat/motion/drama-episodes/46c760779eaffd05138a2d49803b3ca6838bdeb76d8b9cde340d0a6b6783f76e.mp4"},
    {"n": 10, "title": "He Sold Her Himself", "url": "https://huangguo.chat/motion/drama-episodes/706b3fa7a2a9d471f5838c3f92009e5e3a40da50384f67cdc303a1ae25b7df64.mp4"}
]

total_size = 0
for ep in episodes:
    try:
        req = urllib.request.Request(ep["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            cl = int(r.headers.get("content-length", 0))
            total_size += cl
            print(f"EP {ep['n']:>2}: {cl / (1024*1024):.2f} MB | {ep['title']}")
    except Exception as e:
        print(f"EP {ep['n']:>2}: Failed ({e})")

print(f"\nTotal video size: {total_size / (1024*1024):.2f} MB ({len(episodes)} episodes)")
