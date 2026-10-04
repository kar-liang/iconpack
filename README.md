# 自建图标包（Loon / SenPlayer 通用）

一套图标，两个 App 都能导。同一份 JSON 同时喂给 Loon、SenPlayer、Quantumult X、Fileball、Yamby、Hills。

---

## iOS App 图标（官方原图，最推荐）

**不用抓包、不用截图、不用代理** —— 苹果官方有公开 API，直连 `itunes.apple.com` 就能拿  
**1024×1024 无损 PNG 原图**。

```bash
python fetch_ios_icon.py 微信 支付宝 网易云音乐 闪灵
python fetch_ios_icon.py --dry-run 微信 支付宝     # 先看有没有认错
python fetch_ios_icon.py --list apps.txt           # 批量，一行一个
python fetch_ios_icon.py --id 414478124            # 用 App Store ID（最准）
```

双击入口：`fetch-ios-icon.bat 微信 支付宝`，或先填 `apps.txt` 再直接双击 `fetch-ios-icon.bat`。

### ⚠️ 同名 App 一定要钉死 ID

苹果的搜索排序**不保证**你填的名字排在第一。实测四例：

| 你填的   | `[0]` 实际是什么                                    | 正确的在     |
| ------- | ------------------------------------------------ | ------------ |
| 元气壁纸  | **元气桌面壁纸**-超高清壁纸主题小组件（另一个 App） | `[1]`，id=6448843762 |
| Filmix  | **Filmix相机**（一个相机 App）                    | `[1]`，id=6476475132 |
| 人人视频  | **人人追剧**（这 App 已改名，id=6774511125）        | 就是它，钉死更稳 |
| 卡通农场  | **腾讯代理的国服版**（2024 年停更）                  | 国际版 Hay Day，id=506627515@us |

所以 `apps.txt` 支持写死 ID：

```
元气壁纸 = 6448843762
Filmix = 6476475132
卡通农场 = 506627515@us
微博
```

**拿 ID 的方法**：App Store 里点分享 → 复制链接 → 里面 `id` 后面那串数字。

### ⚠️ 国际版要写区号

App Store 的**区号决定上架范围**。搜「卡通农场」cn 区只出腾讯代理的国服版
（`com.tencent.hayday`，2024 年就停更了），国际版 Hay Day（Supercell 出品，
`id=506627515`）在 cn 区**根本查不到** —— 得搜 us / sg / hk / jp 区。

`@us` 可以省略，脚本会在查不到时自动扫一圈常见区并提示：

```
ℹ️  卡通农场 (id=506627515) 在 cn 区查不到，已自动改用 us 区
```

**找国际版 App 的 ID 时用 `lookup_by_id(id, 'us')` 试**，别用 cn 区 ——
查不到不代表不存在。

### dry-run 一定要跑

输出分两档：

- `❌ 硬告警` —— 选中的 App 跟查询词不是一回事，**真会下错**
- `ℹ️ 参考` —— 精确命中，但同系列还有别的 App（知乎/知乎盐选版、QQ/QQ音乐）

> 告警的价值在信噪比。早期版本对 29 个 App 报了 11 条（因为 App 全名普遍带副标题，
> 「部落冲突（Clash of Clans）」「夸克-AI旗舰应用」都误报），真告警被淹没。
> **宁可只报那 1 条真的错的。** 加新告警时务必先想清楚会不会引入噪音。


### 原理（想自己改就看着）

查 `https://itunes.apple.com/search?term=微信&country=cn&entity=software`，  
返回 JSON 里有 `artworkUrl512`，把它末尾的 `/512x512bb.jpg`  
换成 `/1024x1024w.png` 就是无损原图。

mzstatic 的后缀含义：

| 后缀               | 效果                    | 用不用           |
| ---------------- | --------------------- | ------------- |
| `1024x1024w.png` | 1024 无损 PNG 原图        | ✅ 用这个         |
| `512x512bb.jpg`  | 512 JPEG，**bb = 加边框** | ❌ bb 是 border |
| `0x0bb.jpg`      | 400 报错                | ❌             |

### 三个实测确认的细节

1. **搜索结果不能重排！** iTunes Search API 返回的 `results` 本身已按相关度降序。  
   我一开始自作聪明加了「名字最短优先」评分，结果  
   「支付宝」→抖音、「网易云音乐」→QQ音乐、「腾讯视频」→优酷，全错。**别动这个顺序。**
2. **图标名用你填的查询词，不是 App 全名。** App 全名常带副标题  
   （「网易云音乐-数亿音乐畅听」「腾讯视频-沈腾携《现在就出发4》爆笑回归」），太长。  
   更重要的是：查「元气壁纸」而全名是「元气桌面壁纸-超高清壁纸主题小组件」时，  
   取前缀段会得到比查询词更长的名字。查询词才是你的意图。
3. **App 改名后按新名搜。** 「人人视频」现在叫「人人追剧」，bundleId 仍是  
   `com.quantix9.data.pillar44`（千思网络），所以钉 ID 最保险。


### 关于透明通道

下下来的图是 **RGB 无透明**的 —— iOS 图标本来就是「圆角内图案 + 圆角外填充色」的方形图，  
不是抠好的透明 PNG。这对 Loon / SenPlayer 正好（它们自己会再套一层圆角），  
**不要**去抠成透明，反而容易把边缘弄脏。

### 版权提醒

App 图标版权归各开发者所有。自己用没问题，别打包公开分发。

---

## 零、从现成社区库挑图标（新增，最省事）

不想自己找图？直接拉现成库下来挑。

```bash
python fetch_source.py
python picker.py
```

三步：

1. **下载** —— `fetch_source.py` 把整个库拉到 `待挑选/`。  
   默认源是「恩秀 Emby 图标库」718 个（作者 sooyaaabo，标注说明部分图标源自 TFEL-Emby 图标库）。  
   换个源：`python fetch_source.py https://…/别的.json`
2. **挑选** —— `picker.py` 生成 `挑选.html`，浏览器打开。  
   支持按名字筛选、全选可见、反选。勾完点「导出选中」得到 `已选.txt`。
3. **收编** —— `python collect.py`

`collect.py` 做两件事：

- 把选中的 PNG 复制到 `icons/emby/`
- **按社区显示名重命名**（文件名 `DIYEmby-01.png` 显示名是「Emby」→ 存成 `Emby.png`）  
  因为 App 是按图标名精确匹配的，同名多图自动加 `-02/-03`

`-02/-03` **不用你管**：`build.py` 扫描时会发现 `X.png` 存在，自动把 `X-02/X-03` 
折叠成 `X` 的别名。这些带后缀的名字在 App 侧永远匹配不到任何 App，留在包里是纯垃圾。
所以别往 `aliases.txt` 里手写它们 —— 写了反而报「别名指向不存在的图标」。

### 这个库的坑（已处理）

- **718 个图标里有 180 个重名**。社区展示名不是唯一标识，同名不同图靠 `-01/-02` 后缀区分。  
  所以 `fetch_source.py` 按 **URL 里的文件名**保存，不按 name，否则会互相覆盖。
- 文件名和显示名大面积不一致（661 处），比如 `105-01.png` 的显示名是「105° Ciallo」。  
  `collect.py` 会按显示名落地，并在终端打印对照表。
- 社区图普遍只有 256×256，iOS 官方原图是 1024×1024。**同一个 App 两边都有时**
  留官方那份 —— 直接把 `icons/emby/` 里那张删掉就行，build 会自动去重。

- 尺寸实测：714 个 256×256，2 个 333×333，2 个 1024×1024，无损坏。

### 代理：不用手填了

`fetch_source.py` 现在**自动探测**：先试直连，不通就试 `192.168.2.100:7890`（NAS 旁路由）  
和 `127.0.0.1:7890`。单个图片下载失败时还会在这三条链上继续降级重试。

```bash
python fetch_source.py                      # 自动探测，什么都不用填
python fetch_source.py --proxy http://192.168.2.100:7890   # 手动指定
```

> ⚠️ 如果你在别的环境遇到「所有下载都 502」，先查环境变量：
>
> ```bash
> env | grep -i proxy
> ```
>
> 本机上 WorkBuddy 沙箱会注入 `http_proxy=http://127.0.0.1:64851`（由 `sandbox-cli.exe`  
> 动态设置，**不是系统配置，删不掉也不该删**），它对普通 HTTPS 请求一律回 502。  
> 所以脚本里用了 `ProxyHandler({})` 显式屏蔽环境变量 —— 注意**空参 `ProxyHandler()`  
> 会继承环境变量，空字典 `{}` 才是屏蔽**，这是 urllib 的隐蔽坑。

---

## 一、整个流程就三步

```
① 图标丢进 icons/     →   ② 跑 build.py 生成 JSON   →   ③ 把 icons/ + icons.json 传上网
                                                          ↓
                                        Loon / SenPlayer 各点一次导入，完事
```

**关键前提：图标必须放在公网上，手机 App 才拉得到。** 放本地的话 App 导入时会拉到空。

---

## 二、把图标丢进 `icons/`

- 支持子目录分类，比如 `icons/apps/`、`icons/emby/`、`icons/plane/` —— 目录只是给你自己看的，**不会**进图标名。
- **文件名 = 图标名**（不含扩展名）。`Emby.png` → 图标名 `Emby`。
- 格式：png / jpg / webp / gif 都行。
- 尺寸：**256×256 起步**。低于 108 会被我告警（TV 端卡片会糊）。
- 建议正方形，带不带透明通道都行。

> 名字重名（`apps/Emby.png` 和 `emby/Emby.png`）会被检出来并只保留第一个。  
> 实在要同名，用 `--prefix-folder`，会变成 `apps-Emby` / `emby-Emby`。

---

## 三、跑生成

```bash
python build.py --base "https://你的地址" --name "我的图标包"
```

| 参数                | 说明                                          |
| ----------------- | ------------------------------------------- |
| `--base`          | **必填**（不给会交互式问你）。图标包的公网前缀，后面拼 `子目录/文件名.png` |
| `--name`          | 图标包显示名，默认「我的图标包」                            |
| `--description`   | 图标包描述                                       |
| `--prefix-folder` | 图标名带目录前缀，防重名                                |
| `--strict`        | 有重名就退出不生成（用于 CI 拦错）                         |

跑完 `dist/` 里会有：

| 文件                      | 干嘛的                             |
| ----------------------- | ------------------------------- |
| `icons.json`            | **本体**，App 导入的就是它               |
| `loon-import.html`      | 浏览器打开，点一下跳 Loon 导入              |
| `senplayer-import.html` | 浏览器打开，点一下跳 SenPlayer 导入         |
| `preview.html`          | 图标墙，浏览核对（每张都直接拉线上 URL，一眼看出哪张挂了） |
| `manifest.txt`          | 名字 / 相对路径 / 实际尺寸，方便 grep 找图     |

---

## 四、传到哪儿（选一个）

### 方案 A：GitHub（最省事，推荐先用这个）

```bash
cd C:\Users\YuanL\WorkBuddy\2026-10-03-15-26-29\iconpack
git init && git add icons dist && git commit -m "icon pack"
gh repo create my-icons --public --source=. --push
```

`--base` 就填仓库地址，末尾带分支：

```
https://raw.githubusercontent.com/kar-liang/my-icons/main
```

坑：国内移动网络访问 `raw.githubusercontent.com` 时快时慢。**仓库必须 Public**，私有库 raw 直链要 token，手机端配不了。

### 方案 B：自己的 NAS

NAS 上开个静态服务目录指向 `icons/` 和 `dist/icons.json`，然后 `--base` 填 `http://192.168.2.144:<端口>`。

内网用这个足够了。**要在外网用**，把端口挂到 Lucky 上（`https://你的域名/icons/`），并保证 `dist/icons.json` 在同一前缀下。

坑：`--base` 末尾**不要带文件名**，脚本会自己拼 `子目录/图��.png` 和 `icons.json`。

### 方案 C：Cloudflare R2

适合不想开 GitHub 仓库的。`--base` 填 `https://<桶>.r2.dev`。R2 自定义域名走 Cloudflare CDN，图片扛造。

---

## 五、导入（改完图标记得重传 + 重导入）

**Loon**

- 浏览器打开 `dist/loon-import.html` → 点「一键导入到 Loon」，会跳 Loon 完成导入。
- 手动：Loon → 策略 → 长按某个策略组/订阅 → 图标 → 右上角 `+` → 粘贴 `https://你的地址/icons.json`

**SenPlayer**

- 浏览器打开 `dist/senplayer-import.html` → 弹窗选「打开」。
- 需要 **SenPlayer ≥ 6.0.6**（6.0.6 才加的 URLScheme 图标包功能）。
- 手动：`senplayer://importicon?iconset=<编码后的地址>`

> ⚠️ 改完图标包，App 里**删掉旧的再重新导入**，否则列表不会刷新。

---

## 六、大小写对不上？用别名

App 是按图标名**精确匹配**的。你节点叫 `Emby`、图标叫 `emby` 就选不到。改 `aliases.txt`：

```
# 格式：正式名 = 别名1, 别名2
Emby = emby, EMBY, 百度网盘
plex = Plex, PLEX
```

生成时会自动给这些名字各挂一条同 URL 的记录。

---

## 七、图标从哪来

1. **现成库抄**：社区库（24690 个那种）都是纯 PNG 仓库，直接 `git clone` 或只下你要的几个。
2. **截自己设备上的**：iOS/macOS 上把图标存到「文件」App，再挪到 `icons/`。
3. **从网站 favicon**：Chrome DevTools 那个小图标，右键「复制图片地址」，下下来转 256。
4. **自己画**：Procreate / Figma 导出 256 PNG，透明底。

---

## 八、换图标名 / 加别名后重新生成

```bash
python build.py --base "https://你的地址" --name "我的图标包"
```

把 `icons/` 和 `dist/icons.json` 一起重新传上去。`preview.html` 也要跟着看一遍确认。
