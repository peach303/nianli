# 依赖库与许可

本站主体为纯静态 HTML/CSS/JS，没有后端。新增功能用到以下第三方库：

## pinyin-pro

- 版本：3.26.0
- 用途：把中文句子转成拼音，用于「拼音回复」彩蛋（例如 `wo hen xi huan ni`）。
- 许可证：MIT License
- 项目主页：https://github.com/zh-lx/pinyin-pro
- 本项目内的文件：`dist/pinyin-pro.min.js`（UMD 构建，浏览器全局名 `pinyinPro`）
- 引入位置：`index.html` 中 `dist/app.v22.4.4.js` 之前

MIT 许可允许免费使用、修改与再分发，但需保留原作者的版权与许可声明。若之后升级或替换该库，请同步更新本文件。

## 其它

- 系统字体、图标（`icon*.png` / `icon*.svg`）与站内图片素材为站内自带，未额外引入第三方库。
- `tools/gen_cards.py`（衍生字卡生成脚本）只使用 Python 标准库，没有第三方依赖。
- `generated.json` 可以由 GitHub Actions 调用 GitHub Models 生成；GitHub Models 是在线服务，
  本项目不打包它的代码，使用时遵循 GitHub 的服务条款。
- 若后续引入了新的第三方库，请在这里补充：库名、版本、用途、许可证、项目地址、放入本项目的文件路径。
