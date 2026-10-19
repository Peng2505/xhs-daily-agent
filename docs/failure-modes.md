# 失败模式清单（20 条）

按发现顺序记录。每条都是**实际跑出来**的，不是预判。格式：现象 → 怎么确认 → 怎么绕。

## A. 浏览器与登录态

**1. 草稿只存在当前浏览器本地**
页面明说"草稿存储于当前使用的浏览器本地"。所以草稿只在这个专用 profile 里，换浏览器就看不到。→ 别删 `edge-profile/`；要发草稿必须用同一个实例。

**2. 登录态失效的表现是重定向**
URL 变成 `/login?redirectReason=401`。→ 立即停手报错，让人工在那个可见窗口登录（该页没有二维码入口，只有手机号+验证码或邮箱+密码）。**验证码/密码永不经过 Agent**。别反复重试，会触发风控。

## B. 渲染与截图

**3. 不固定 device metrics 会截成视口大小**
默认视口约 1699×982，直接截 1080×1440 的卡片会被裁。→ 截图前 `Emulation.setDeviceMetricsOverride(width=1080, height=1440, deviceScaleFactor=1, mobile=False)`。

**4. device metrics override 会跨导航保留**
渲染完卡片直接跳创作页，页面仍按 1080×1440 渲染，此时 DOM rect 是一套、真实窗口是另一套：`fill_input` **静默失败**（回读 `input.value` 为空）、`click_at_xy` 点偏。→ 渲染完必须 `Emulation.clearDeviceMetricsOverride()` 再干别的。

**5. DPR 不固定，坐标空间会打架**
本机实测 `window.devicePixelRatio` 见过 **1.5 和 1.125** 两个值（取决于窗口/缩放）。截图 PNG 宽度 = CSS 宽度 × DPR，即截图是设备像素、DOM/box model 是 CSS 像素。→ **不要硬编码 DPR**，每次开工先读 `devicePixelRatio` + `innerWidth`；最稳是坐标读取与点击在同一 CDP 调用内完成（`DOM.getBoxModel` + `Input.dispatchMouseEvent` 同属 CSS 像素空间）。

**6. `capture_screenshot` 会 IPC 超时**
偶发 `TimeoutError: timed out`。→ 重试即可，但重试前先确认仍停在目标页，别重复执行点击类动作。连续超时时改用 `Page.captureScreenshot(format="jpeg", quality=55)` 拿 base64 自己落盘（裁剪小区域更不容易超时）。

## C. 编辑器与表单

**7. 标题输入框不能用 `fill_input` 稳定填**
`fill_input('input[placeholder*="填写标题"]')` 在创作页不可靠（占位符实为「填写标题会有更多赞哦」）。→ 稳妥路径：JS `el.focus(); el.click()` → `Input.insertText` → 回读 `input.value` 确认。

**8. `press_key("Enter")` 在 tiptap 上不可靠**
414 字全挤进同一个 `<p>`，`children.length=1`，innerHTML 无 `<br>`。`Input.dispatchKeyEvent`、`Escape`、`Shift+Enter`、`execCommand('insertParagraph')` **全部无效**。→ 拿实例一次性写入真实段落：
```js
const ed = document.querySelector('div[contenteditable=true].ProseMirror').editor;
ed.commands.setContent('<p>第一段</p><p>第二段</p>', true);  // true = 发出更新事件
```
写完必须回读 `innerText.length` 和 `children.length` 双确认。没有 `.editor` 实例时退而用逐段 `type_text`。

**9. 正文区的 `contenteditable` 必须先聚焦**
不能直接赋 `innerText`（tiptap 不认）。→ JS 聚焦后再输入，或直接用坑 8 的 `setContent`。

## D. 按钮定位与点击

**10. 发布控件在 closed shadow DOM 里**
`document.querySelectorAll('*')` 和手写 shadow-root 遍历**都找不到**。注意假象：`innerHTML.indexOf('暂存')` 有值——那只是内联脚本里的字符串。→ 走 Accessibility 树：
```python
nodes = cdp("Accessibility.getFullAXTree")["nodes"]
btn = [n for n in nodes if n.get("name",{}).get("value")=="暂存离开"
       and n.get("role",{}).get("value")=="button"][0]
m = cdp("DOM.getBoxModel", backendNodeId=btn["backendDOMNodeId"])["model"]["content"]
```

**11. 坐标点击会完全失效，且不报错**
表现为：无成功页、无弹窗、无 toast、URL 不变，**且确认真的没发出请求**。同一坐标 `document.elementFromPoint` 明明就是那个按钮。→ 降级链：AX 树 + box model + `Input.dispatchMouseEvent` → 仍无效则 `DOM.resolveNode(backendNodeId)` → `Runtime.callFunctionOn("function(){this.click()}")`。重试前必须先确认没有重复提交。

**12. 别用坐标乱点导航区**
一次误点把页面跳到了「笔记管理」。→ 宁可 JS 精确 `click()` 或走 AX 树取坐标。

**13. 标签页有隐藏副本，坐标点击会点歪**
发布页 `.creator-tab` 有一份 rect 为负的隐藏副本。→ 用 JS 按 `getBoundingClientRect()` 过滤 `width>0 && x>-100` 后 `.click()` 那个可见的。

**14. 文件输入是 0×0 隐藏元素**
`input[type=file]` 存在但尺寸 0×0，点不到。→ `DOM.setFileInputFiles(nodeId, files=[cover, points])`，顺序即笔记里的图片顺序。

## E. 验收与幂等

**15. 不要用 `body.innerText` 的文本顺序判验收**
文本顺序有歧义。→ 点 `.tab-item` 按状态逐项筛选：「审核中」里没有、「已发布」里有，才算发布成功。

**16. 可见性要看 `permission_msg` 的归属，不是有没有**
`permission_msg`（文案「仅自己可见」）是**跟在所属卡片下方一行**的元素，不是跟在标题后面。→ 用 y 坐标判归属（实测卡片间距约 198px，标签相对自己卡片的标题偏移约 +106px 或 +304px）；新卡片对应 y 处**没有**该元素才是公开可见。

**17. 长调用会 IPC 超时**
单次调用动作太多会 `TimeoutError`。→ 拆成 2–3 段做，一次不超过约 6 个动作。超时后先重连确认页面状态（URL 已是目标页说明动作其实成功了），再决定是否重发。

**18. 原始 `Input.dispatchMouseEvent` 首调也会超时**
事件**未必**没发出去。→ 先重连，回读标题/正文/是否出现「保存成功」，再决定是否重发，避免重复提交。

## F. 内容与限额

**19. 标题 20 字 / 正文 1000 字是硬上限**
超出会被截断或拦截。→ `build_publish.py` 在生成期就告警截断；正文总量在生成后打印实际字数。

**20. 来源只记名称等于永久丢失链接**
检索轮每条候选都打开原文核实过，那一刻 URL 就在手上——**当场写进 spec**。只记来源名（「联合早报」「XX 合集」）事后无法回溯。→ `sources` 必须是 `{name, url}`，缺 `url` 的条目在生成阶段就打 `WARN` 并丢弃。

## 遗留缺陷

- **话题标签退化成纯文本**：输入 `#话题#` 后 `a[href*="topic"]` 数量为 0，标签不可点。根因是键事件通路不可靠（坑 8），没能从下拉里选中真话题。需要把「输入 `#词` → 点下拉第一项」这条路打通（下拉在 DOM 里，用 box model + 鼠标事件有希望）。
- **依赖页面结构**：`.creator-tab`、`.note-card`、`permission_msg`、tabs 文案等选择器一变，上传与验收逻辑都要跟着改。目前没有针对它们的存在性断言，属于已知的实施风险。
