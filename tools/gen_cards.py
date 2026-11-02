#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
言字卡 · 衍生字卡生成器（B 功能）

做什么
------
从 `tools/seed_cards.json` 里的原始短句出发，生成一批「衍生字卡」，写进根目录的
`generated.json`。前端只读这个文件，不会写它。

两种生成方式
------------
1. rule   纯规则：删程度词 / 换近义词（改写），或把两张卡用连接词拼起来（造句）。
          不需要网络，任何时候都能跑，用来保底。
2. models GitHub Models（需要 GITHUB_TOKEN）：让模型按同样的两种手法生成更自然的新句。
          失败、没 token、超时都会自动回退到 rule，不会让工作流红掉。

常用命令
--------
    python tools/gen_cards.py                     # 有 token 就试模型，没有就用规则
    python tools/gen_cards.py --engine rule       # 只跑规则（本地调试）
    python tools/gen_cards.py --engine models     # 只跑模型，失败则报错退出
    python tools/gen_cards.py --count 80 --merge  # 生成 80 条，并与旧文件合并去重

环境变量
--------
    GITHUB_TOKEN         GitHub Actions 自动提供；本地跑模型时需要自己有 models:read 权限
    GEN_MODEL            默认 openai/gpt-4o-mini
    GITHUB_MODELS_URL    默认 https://models.github.ai/inference/chat/completions

依赖
----
只使用 Python 标准库，不需要 pip install。
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SEED = os.path.join(ROOT, "tools", "seed_cards.json")
DEFAULT_OUT = os.path.join(ROOT, "generated.json")
DEFAULT_MODEL = os.environ.get("GEN_MODEL", "openai/gpt-4o-mini")
DEFAULT_URL = os.environ.get(
    "GITHUB_MODELS_URL", "https://models.github.ai/inference/chat/completions"
)

# 改写时优先删掉的程度词。保留「好」不动，避免把「好看」「好像」删坏。
DEGREE_RE = re.compile(r"(很|非常|特别|十分|极了|真的)")

# 删完程度词句子没变时，再换一两个近义词。只做低风险替换。
SYNONYMS = [
    ("喜欢你", "中意你"),
    ("喜欢你", "对你上心"),
    ("想你", "惦记你"),
    ("开心", "高兴"),
    ("好看", "顺眼"),
    ("一起", "一块儿"),
    ("现在", "这会儿"),
    ("今天", "今儿"),
    ("明天", "明儿"),
    ("有点", "有些"),
    ("马上", "这就"),
    ("刚才", "刚刚"),
    ("忽然", "突然"),
]

# 拼接用的连接词。可按喜好增删，前端规则版也有一份同样的列表。
CONNECTORS = ["，而且", "，还有", "，加上", "，顺便", "，然后", "，其实", "；", "，"]

# 改写没变化时，加一个很轻的口气，保证「改写」确实和原句不同。
SOFT_PREFIX = ["其实，", "说起来，", "忽然想到，"]
SOFT_SUFFIX = ["，说真的", "，就这样", "，你懂吧"]

CN_RE = re.compile(r"[\u4e00-\u9fff]")

# Windows 控制台默认 GBK，打印中文会乱码；有就切 UTF-8，没有也不影响运行。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def card_id(text):
    return "gen-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def valid(text, seed_set):
    """长度、汉字、去重、别和原句一模一样。"""
    if not text or text in seed_set:
        return False
    if not (4 <= len(text) <= 60):
        return False
    if not CN_RE.search(text):
        return False
    # 至少 4 个汉字，挡掉「，」「……」这类
    if len(CN_RE.findall(text)) < 4:
        return False
    return True


def rewrite(card, rng):
    t = DEGREE_RE.sub("", card).strip()
    if t != card and valid(t, set()):
        return t

    t2 = card
    hits = [(a, b) for a, b in SYNONYMS if a in t2]
    if hits:
        a, b = rng.choice(hits)
        t2 = t2.replace(a, b, 1)
        if valid(t2, set()):
            return t2

    if rng.random() < 0.5:
        t3 = rng.choice(SOFT_PREFIX) + card
    else:
        t3 = card + rng.choice(SOFT_SUFFIX)
    return t3


def concat(a, b, rng):
    conn = rng.choice(CONNECTORS)
    return a + conn + b


def make_card(text, method, sources, at):
    return {
        "id": card_id(text),
        "text": text,
        "source": "generated",
        "method": method,
        "from": sources,
        "at": at,
    }


def rule_cards(seed, count, rng):
    seed_set = set(seed)
    out = []
    seen = set()
    attempts = 0
    max_attempts = max(200, count * 30)
    at = now_iso()

    while len(out) < count and attempts < max_attempts:
        attempts += 1
        if rng.random() < 0.5 or len(seed) < 2:
            base = rng.choice(seed)
            text = rewrite(base, rng)
            method = "rewrite"
            sources = [base]
        else:
            a, b = rng.sample(seed, 2)
            text = concat(a, b, rng)
            method = "concat"
            sources = [a, b]

        text = clean(text)
        if text in seen or not valid(text, seed_set):
            continue
        seen.add(text)
        out.append(make_card(text, method, sources, at))

    return out


def parse_json_array(raw):
    """模型有时会包 ```json 代码块或前后带解释，这里只抠出第一段数组。"""
    if not raw:
        return []
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    start = s.find("[")
    end = s.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        arr = json.loads(s[start : end + 1])
    except Exception:
        return []
    return arr if isinstance(arr, list) else []


def models_cards(seed, count, model):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("没有 GITHUB_TOKEN，无法调用 GitHub Models")

    seed_text = "\n".join("- " + x for x in seed)
    prompt = f"""下面是一批中文第一人称短句（言字卡）：

{seed_text}

请生成 {count} 条新的中文短句，混用两种手法：
1. rewrite：从上面挑一句，删掉程度词或换近义词，让语气更平一点；
2. concat：从上面挑两句，用「，而且」「，还有」「，加上」「，顺便」「，然后」这类连接词拼成一句。

要求：
- 每条 6~40 个汉字，第一人称，像日常聊天会说的话；
- 不要出现「作为AI」「以下是」之类的说明；
- 不要和原句完全一样，也不要两条重复；
- 只输出 JSON 数组，不要代码块、不要解释。

数组每一项的格式：
{{"text":"新句子","method":"rewrite 或 concat","from":["用到的原句"]}}
"""

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是中文短句生成器，只输出 JSON 数组。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.9,
        "max_tokens": 8000,
    }
    req = urllib.request.Request(
        DEFAULT_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    content = ""
    try:
        content = payload["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError("模型返回格式不认识：" + json.dumps(payload, ensure_ascii=False)[:500])

    arr = parse_json_array(content)
    if not arr:
        raise RuntimeError("模型没有按要求返回 JSON 数组：" + content[:500])

    at = now_iso()
    seed_set = set(seed)
    out = []
    seen = set()
    for item in arr:
        if not isinstance(item, dict):
            continue
        text = clean(item.get("text"))
        if text in seen or not valid(text, seed_set):
            continue
        method = item.get("method")
        if method not in ("rewrite", "concat"):
            method = "rewrite"
        src = item.get("from")
        if not isinstance(src, list):
            src = []
        src = [clean(x) for x in src if clean(x)][:2]
        seen.add(text)
        out.append(make_card(text, method, src, at))
        if len(out) >= count:
            break

    if not out:
        raise RuntimeError("模型返回的句子全部不合格（长度/重复/非中文）")
    return out


def merge_cards(old, new, limit=None):
    out = []
    seen = set()
    for c in list(old) + list(new):
        if not isinstance(c, dict):
            continue
        text = clean(c.get("text"))
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(c)
    if limit:
        out = out[-limit:]
    return out


def main():
    ap = argparse.ArgumentParser(description="生成言字卡衍生字卡")
    ap.add_argument("--engine", choices=["auto", "rule", "models"], default="auto")
    ap.add_argument("--count", type=int, default=60)
    ap.add_argument("--seed", default=DEFAULT_SEED)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--merge", action="store_true", help="与已有 generated.json 合并去重")
    ap.add_argument("--random-seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.random_seed)

    seed = load_json(args.seed)
    seed = [clean(x) for x in seed if clean(x)]
    if not seed:
        print("原始短句为空：" + args.seed, file=sys.stderr)
        return 2

    engine = args.engine
    cards = []
    used_model = ""

    if engine in ("auto", "models"):
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            try:
                print("尝试 GitHub Models：%s" % args.model)
                cards = models_cards(seed, args.count, args.model)
                engine = "github-models"
                used_model = args.model
                print("模型生成了 %d 条" % len(cards))
            except Exception as e:
                if args.engine == "models":
                    print("模型生成失败：%s" % e, file=sys.stderr)
                    return 3
                print("模型生成失败，回退规则：%s" % e, file=sys.stderr)
                engine = "rule"
        else:
            if args.engine == "models":
                print("没有 GITHUB_TOKEN，无法调用 GitHub Models", file=sys.stderr)
                return 3
            print("没有 GITHUB_TOKEN，使用规则生成")
            engine = "rule"

    if engine == "rule":
        cards = rule_cards(seed, args.count, rng)
        used_model = ""
        print("规则生成了 %d 条" % len(cards))

    if not cards:
        print("没有生成任何合格句子", file=sys.stderr)
        return 4

    if args.merge and os.path.exists(args.out):
        try:
            old = (load_json(args.out) or {}).get("cards", [])
        except Exception:
            old = []
        # 合并时保留旧句；上限 400 条只是防止文件无限长，正常一周跑一次远到不了。
        cards = merge_cards(old, cards, limit=400)

    out = {
        "ver": "v" + datetime.now(timezone.utc).strftime("%Y%m%d"),
        "updatedAt": now_iso(),
        "engine": engine,
        "model": used_model,
        "seedCount": len(seed),
        "count": len(cards),
        "cards": cards,
    }
    save_json(args.out, out)
    print("已写入 %s（%s，%d 条）" % (args.out, engine, len(cards)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
