# 衍生字卡生成（B 功能）

这一套东西负责把「原始字卡」改写成新句、或把两张卡拼成一句，写进根目录的
`generated.json`。前端只读这个文件，不会改原始字卡，也不会写回仓库。

```
tools/seed_cards.json        原始短句（生成用的种子，可自己增删）
tools/gen_cards.py           生成脚本（只用 Python 标准库）
generated.json               生成结果，前端读取
.github/workflows/generate-cards.yml   GitHub Actions 定时任务
```

> 云端任务读不到你浏览器里的字卡（那些只存在本机）。它用的是 `tools/seed_cards.json`；
> 想让它按你的常用卡生成，把那些句子加进这个文件再跑一次即可。你个人的卡仍由前端本地规则补足。

## 本地跑

只跑规则（不需要网络、不需要 token）：

```bash
python tools/gen_cards.py --engine rule --count 60
```

有 GitHub token 时，先试 GitHub Models，失败自动回退规则：

```bash
set GITHUB_TOKEN=你的token
python tools/gen_cards.py --engine auto --count 80 --merge
```

PowerShell 里设置环境变量用：

```powershell
$env:GITHUB_TOKEN = "你的token"
python tools/gen_cards.py --engine auto --count 80 --merge
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--engine rule/auto/models` | `rule` 只跑规则；`auto` 有 token 试模型、失败回退；`models` 只跑模型，失败报错 |
| `--count N` | 目标条数，默认 60 |
| `--merge` | 与旧 `generated.json` 合并去重，不覆盖旧句；最多保留 400 条 |
| `--seed 路径` | 换一份种子短句 |
| `--out 路径` | 换输出文件 |
| `--model 名称` | 默认 `openai/gpt-4o-mini`，也可用环境变量 `GEN_MODEL` |

## 云端跑（GitHub Actions）

`.github/workflows/generate-cards.yml` 会在两种时候跑：

- 在 GitHub 仓库页面 Actions → 「生成衍生字卡」→ Run workflow 手动触发；
- 每周一 03:00 UTC（北京时间 11:00）自动跑一次。

跑完会把 `generated.json` 提交回仓库。如果这次内容没变化，就跳过提交。

需要在仓库里确认两件事：

1. Actions 处于启用状态；
2. 工作流已声明 `permissions: models: read`（文件里已经写好，不用手动加 secret）。
   `GITHUB_TOKEN` 由 Actions 自动提供，不需要自己建。

> 这个工作流只在 GitHub 上执行。本地不会自动提交、不会推送，也不会部署。

## generated.json 长什么样

```json
{
  "ver": "v20261031",
  "updatedAt": "2026-10-31T11:12:30Z",
  "engine": "rule",
  "model": "",
  "seedCount": 49,
  "count": 60,
  "cards": [
    {
      "id": "gen-707626fbbd",
      "text": "有空一块儿去走走",
      "source": "generated",
      "method": "rewrite",
      "from": ["有空一起去走走"],
      "at": "2026-10-31T11:12:30Z"
    }
  ]
}
```

- `source` 固定是 `generated`，用来和原始字卡区分；
- `method` 是 `rewrite`（改写）或 `concat`（拼接）；
- `from` 记录用到的原始句，方便在「衍生字卡」页里看来源；
- 前端加载失败（离线、还没跑过 Action）时会自动回退到本地规则，不会白屏。

## 前端怎么用

- 每次打开页面会 `fetch('./generated.json')`，Service Worker 对 `.json` 走 network-first，
  所以新生成的内容下一次打开就能看到；离线时用缓存里的上一份。
- 「自由造句概率」命中时：一半从 `generated.json` 抽一句，一半用本地规则改写/拼接（保证会用到你自己的卡）；
  文件没加载到（离线 / 还没跑过 Action）时全部走本地规则。
- 设置 → 通知 →「新回复概率（全局）」里有两枚开关：
  - **回复时混入「造句 / 改写」衍生卡**：打开后，云端句子和本机新造的句子会进入主字卡抽取池；
  - **回复时混入「自动拾取」的字卡**：打开后，TA 从你消息里拾取的长句也会进入抽取池。
  - 两枚默认都关，关着时主字卡抽取仍然只取原始卡，和旧版行为一致。
- 字卡库页右上角的「衍生」、或更多 →「衍生字卡」，可以看拾取 / 造句两份列表，
  本机条目能删；云端条目只读，删了刷新会回来。

## 常见问题

- **Actions 里没有生成提交**：到仓库 Settings → Actions → General → Workflow permissions，
  确认选的是「Read and write permissions」；本工作流已声明 `contents: write`，但仓库总开关关着时仍然推不上去。
- **模型那一步失败**：脚本会自动回退到规则生成，工作流不会红；想查原因看日志里的
  「模型生成失败，回退规则：…」。确认工作流的 `permissions` 里有 `models: read`。
- **页面里看不到新句子**：Service Worker 对 `generated.json` 走 network-first，正常刷新一次就会更新；
  如果页面本身还是旧版，再刷新一次（旧版页面会先在后台把新版代码下载完）。
- **不想让 TA 说云端句子**：设置 → 通知 →「自由造句概率」填 0；或者不把 `generated.json` 部署上去，
  前端会自动回退到本地规则。

## 许可

- `tools/gen_cards.py` 只使用 Python 标准库，没有第三方依赖。
- GitHub Models 是 GitHub 提供的在线推理服务，按 GitHub 的条款使用；本项目不打包它的代码。
- 生成出来的句子由种子和模型产生，使用时请自行确认没有冒犯或不合适的内容。
