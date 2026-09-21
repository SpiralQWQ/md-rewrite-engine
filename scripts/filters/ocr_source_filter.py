"""scripts/filters/ocr_source_filter.py — PDF/MinerU 源 OCR 噪音过滤器（通用引擎 + 章节规则）。

背景：机械对账（gate_check）要求"数字关键点覆盖率 ≥90%"，但 PDF 解析源
（MinerU/Gamma OCR）混入大量非教学噪音——ObjectId/UPC 哈希、scrapy 时间戳日志、
数据库客户端回显、截图 OCR 残片、json dump 等。这些数字既不是教学内容、
也不该逼着笔记去覆盖。本模块在源进入流程1之前做一次前置过滤。

结构（规则数据化，非逐章复制脚本）：
- 共用引擎 filter_lines()：判定顺序统一（整段跳过 → GLM 段 → noise_pre →
  标题/中文/shell/代码 → noise_post → 短行保留）；噪音分 pre/post 两段是
  4 章手工实战版的真实语义（pre 拦中文噪音行，post 拦纯 ascii dump）
- 章节规则 CHAPTER_RULES：每章一份 {"noise_pre", "noise_post", "short_line",
  "anchored_tokens", "bare_tokens", "skip_sections", ...}，新章节只需加规则，
  不改引擎。

用法：
    python -m scripts.filters.ocr_source_filter --chapter 12 \
        --src temp/第12章_clean.md --out temp/第12章_clean_only.md

零业务依赖：只依赖标准库（目录契约：scripts 层不 import md_rewrite_engine.core/services 业务逻辑，
本文件为独立工具，与 gate_check 同级使用）。
"""
from __future__ import annotations

import argparse
import re
import sys

# ── 通用噪音模式（所有 OCR 源通吃，与章节无关）──

# GLM 画面理解段：解析器对截图的补充描述，非正文，整段跳过（到下一个标题恢复）
GLM_SECTION_MARK = "GLM 画面理解"

# 通用保留判断（优先级从高到低，命中即保留）
HEADING_RE = re.compile(r"^#{1,3} ")                      # md 标题
CJK_RE = re.compile(r"[一-鿿]")                            # 含中文 = 正文
SHELL_RE = re.compile(r"^\$ |^>>> |^\.\.\. ")             # shell/python 提示符

# 短行兜底阈值说明：各章实战口径不同（ch9=20 / ch12=30 / ch13=45 / ch14=40），
# 由 CHAPTER_RULES[ch]["short_line"] 指定——阈值即语义，勿统一成一个常量。

# 各章特有代码保留令牌（章节规则里引用的公共池，行首锚定 + 独特 API）
# 注意：不含 print——第9章实战证明 print(len(...)) 会被 OCR 截行误利用；需要时章节自加
_CODE_TOKENS = (
    r"^\s*(import |from |class |def |return |yield |if |elif |else:|for |while "
    r"|try|except|with )"
    # 注意：不含 self\. 也不含 print——4 章手工实战版均无此二令牌
    #（self\. 会让 OCR 断行的 "self.db_cur = ..." 碎片混入；需要时章节自加）
)


def _skip_glm(line: str, skip: bool) -> bool:
    """GLM 画面理解段状态机：段内行全部丢弃，遇下个标题恢复。"""
    if GLM_SECTION_MARK in line:
        return True
    if skip:
        # 段结束条件：下一个 md 标题（## 开头）
        return not line.startswith("##")
    return False


def filter_lines(lines: list, noise_pre: list, noise_post: list, keep_code: re.Pattern,
                 skip_sections: list | None = None, short_line: int = 20,
                 short_line_requires: str = "", drop_cjk_frag: bool = False,
                 url_keep: bool = False) -> list:
    """共用过滤引擎：一行行判定保留/丢弃。

    判定顺序（与手工实战版逐章对齐——4 章顺序不同，用 pre/post 两段表达）：
        整段跳过 → GLM 段 → noise_pre → 孤立中文碎片 →
        标题/中文/shell/代码 → noise_post → 短行保留

    为什么分两段：章节噪音行的中英构成不同——
        noise_pre：命中即丢，先于中文保留（截图 OCR 行既含中文又是噪音，如 ch13
          电影行"大话西游 8.9 刘镇伟"）；ch9 的 hex30 同理须在最前。
        noise_post：保留判断之后才丢（纯 ascii dump，如 ch12 mysql 回显、ch14
          时间戳日志）；若放 pre 会误杀 ch12 里命中 scrapy_db 代码令牌的行。

    Args:
        lines: 源 md 行列表。
        noise_pre: 编译后的前段噪音正则（先于一切保留判断）。
        noise_post: 编译后的后段噪音正则（保留判断之后、短行之前）。
        keep_code: 代码保留正则（章节特有令牌 + 通用 _CODE_TOKENS）。
        skip_sections: 章节整段跳过规则列表，每项 {"start": 前缀, "end": 前缀}。
        short_line: 短行兜底阈值（strip 后 < 该值保留）。各章实战口径不同
            （ch9=20 / ch12=30 / ch13=45 / ch14=40），由章节规则指定，勿统一。
        short_line_requires: 短行保留附加条件正则（空=无条件；ch13 实战口径
            r"[\\d.:]" = 短行还须含数字/点，纯字母碎片与空行丢弃）。
        drop_cjk_frag: True 时丢弃孤立 1-3 字中文碎片（ch13 实战：海报 OCR
            残字「鲜枪」「接】」这类既非正文也非完整词的行）。
        url_keep: True 时含 http 的行未被前段噪音拦截则保留（ch9 实战：
            教学示例 URL 行如 start_urls = [...matplotlib...] 须保留）。

    Returns:
        保留的行列表（含空行，保持原文档结构）。
    """
    out: list = []
    skip = False              # GLM 段状态
    section_skip: dict | None = None  # 当前命中的整段跳过规则
    frag_re = re.compile(r"[一-鿿]{1,3}") if drop_cjk_frag else None
    req_re = re.compile(short_line_requires) if short_line_requires else None
    for ln in lines:
        # 0) 整段跳过状态机（章节特有，如第9章 9.2.2 截图密集节）
        if section_skip is not None:
            if ln.startswith(section_skip["end"]):
                section_skip = None
            else:
                continue
        else:
            for rule in (skip_sections or []):
                if ln.lstrip().startswith(rule["start"]):
                    section_skip = rule
                    break
        if section_skip is not None:
            continue

        # 1) GLM 画面理解段
        if _skip_glm(ln, skip):
            skip = True
            continue
        skip = False

        # 2) 前段噪音（先于一切保留——中文噪音行在此被拦）
        if any(r.search(ln) for r in noise_pre):
            continue

        # 3) 孤立中文碎片丢弃（章节开关，防海报 OCR 残字混入正文）
        st = ln.strip()
        if frag_re is not None and st and frag_re.fullmatch(st):
            continue

        # 4) 优先保留：标题 / 中文 / shell 命令 / 代码 / URL（章节开关）
        if HEADING_RE.match(ln) or CJK_RE.search(ln) or SHELL_RE.match(ln):
            out.append(ln)
            continue
        if keep_code.search(ln):
            out.append(ln)
            continue
        if url_keep and "http" in ln:
            out.append(ln)
            continue

        # 5) 后段噪音（保留判断之后、短行之前——纯 ascii dump 残片）
        if any(r.search(ln) for r in noise_post):
            continue

        # 6) 短行兜底保留（可附加条件）；其余默认丢弃（dump 残片）
        if len(st) < short_line and (req_re is None or req_re.search(st)):
            out.append(ln)
            continue
    return out


def _compile_rules(rule_strings: list) -> list:
    """把规则字符串列表编译为正则对象（集中在此，坏规则启动即报错不静默）。"""
    compiled = []
    for s in rule_strings:
        try:
            compiled.append(re.compile(s))
        except re.error as e:
            raise ValueError(f"噪音规则编译失败: {s!r}: {e}") from e
    return compiled


def _build_keep_code(rule: dict) -> re.Pattern:
    """拼章节代码保留正则，保持手工版锚定语义。

    三段结构：_CODE_TOKENS（^\\s* 锚定组） + anchored_tokens（章节行首令牌，
    拼进锚定组内） + bare_tokens（无锚定令牌：类名/中间件名等任意位置匹配）。
    锚定语义即语义：ch13 实战教训——"port = " 若落到无锚定区会误匹配
    "hostport = _parse_proxy" 这类 OCR 断行。
    """
    parts = [_CODE_TOKENS]
    anchored = rule.get("anchored_tokens")
    if anchored:
        # _CODE_TOKENS 形如 r"^\s*(...)"，把章节令牌插进锚定组内再闭合
        assert parts[0].endswith(")"), "_CODE_TOKENS 结构变化，需同步改 _build_keep_code"
        parts[0] = parts[0][:-1] + "|" + anchored + ")"
    bare = rule.get("bare_tokens")
    if bare:
        parts.append(bare)
    try:
        return re.compile("|".join(parts))
    except re.error as e:
        raise ValueError(f"章节令牌编译失败: {e}") from e


def filter_file(src: str, out: str, chapter: int) -> dict:
    """过滤单个文件（文件级入口，防呆在此层）。

    Returns:
        {"ok", "in_lines", "out_lines", "error"?}
    """
    import io
    if not src or not out:
        return {"ok": False, "error": "缺少 --src 或 --out 路径", "in_lines": 0, "out_lines": 0}
    rule = CHAPTER_RULES.get(chapter)
    if rule is None:
        known = ", ".join(str(k) for k in sorted(CHAPTER_RULES))
        return {"ok": False, "error": f"第{chapter}章无过滤规则（已有: {known}）",
                "in_lines": 0, "out_lines": 0}
    try:
        with io.open(src, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        return {"ok": False, "error": f"源文件读取失败: {e}", "in_lines": 0, "out_lines": 0}
    except UnicodeDecodeError as e:
        # 非 UTF-8（GBK 源/二进制文件）：明确报错不裸抛（终点一致性：失败统一 error dict）
        return {"ok": False, "error": f"源文件不是有效 UTF-8（请先转码）: {e}", "in_lines": 0, "out_lines": 0}
    if not lines:
        return {"ok": False, "error": f"源文件为空: {src}", "in_lines": 0, "out_lines": 0}
    keep = _build_keep_code(rule)
    out_lines = filter_lines(lines, _compile_rules(rule.get("noise_pre", [])),
                             _compile_rules(rule.get("noise_post", [])),
                             keep,
                             rule.get("skip_sections"),
                             short_line=rule.get("short_line", 20),
                             short_line_requires=rule.get("short_line_requires", ""),
                             drop_cjk_frag=rule.get("drop_cjk_frag", False),
                             url_keep=rule.get("url_keep", False))
    try:
        import os
        parent = os.path.dirname(os.path.abspath(out))
        os.makedirs(parent, exist_ok=True)
        with io.open(out, "w", encoding="utf-8") as f:
            f.writelines(out_lines)
    except OSError as e:
        return {"ok": False, "error": f"输出写入失败: {e}",
                "in_lines": len(lines), "out_lines": 0}
    return {"ok": True, "in_lines": len(lines), "out_lines": len(out_lines)}


# ── 章节规则表（迁移自 filter_ch9/12/13/14.py 实战版，新增章节在此登记）──
# code_tokens: 该章代码行保留令牌（追加在通用 _CODE_TOKENS 之后）
# noise_rules: 该章特有噪音正则（通用引擎已含 GLM 段/hex 哈希/标题/中文/shell 判定）
# skip_sections: 整段跳过（截图密集节），start 到 end 前缀之间全部丢弃

CHAPTER_RULES: dict = {
    1: {
        "short_line": 20,
        "anchored_tokens": (
            r"ITEM_PIPELINES|scrapy\.|response\."
        ),
        "bare_tokens": "",
        "noise_pre": [
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",  # scrapy 运行日志时间戳行
            r"col-x[s5]-6|col-md-3|col-lg-3",            # 页面截图 OCR（Bootstrap 栅格 class）
            r"Elements\|Network|EventListeners|DOM Break|Preservelog",
            r"element\.st|::before|::after",             # 开发者工具面板伪 CSS
        ],
        "noise_post": [],
    },
    # 噪音分两段（与手工实战版逐章对齐，勿合并）：
    #   noise_pre  — 先于一切保留判断（中文噪音行/哈希行在此被拦）
    #   noise_post — 保留判断之后、短行之前（纯 ascii dump 残片）
    9: {
        "short_line": 20,
        "url_keep": True,                        # 教学示例 URL 行保留（手工版独立 URL 分支）
        "bare_tokens": (                         # 手工版此章令牌无行首锚定（scrapy.Field() 等任意位置）
            r"ITEM_PIPELINES|FILES_STORE|IMAGES_STORE|IMAGES_MIN|MAX_DOWNLOAD"
            r"|scrapy\.|response\.|item\[|\.Field\(\)"
        ),
        "noise_pre": [
            r"[a-f0-9]{30,}",                       # hex30 哈希文件名行（手工版首条）
            r"/full|/thumbs",                        # 哈希路径（IMAGES_STORE/full/...）
            r"qhimg_url|qhimg_thumb",               # 图片 CDN 参数行
        ],
        "noise_post": [],
        "skip_sections": [
            {"start": "## 9.2.2", "end": "## 9.2.3"},   # 页面分析：截图 OCR 密集
            {"start": "## 9.3", "end": "## 9.4"},        # 360 图片实战：json/图片噪音密集
        ],
    },
    12: {
        "short_line": 30,
        "anchored_tokens": (
            r"cur\.|conn\.|dbpool\.|reactor|tx\.|r\.hmset|client\.|collection\.|doc ="
        ),
        "bare_tokens": (
            r"ITEM_PIPELINES|sqlite3|MySQLdb|pymongo|redis\.|StrictRedis|MongoClient"
            r"|insert_one|hmset|adbapi|ConnectionPool|runInteraction|ENGINE=InnoDB"
            r"|CHARSET=utf8|CHARACTER SET|CREATE TABLE|CREATE DATABASE|INSERT INTO"
            r"|select count|USE scrapy_db|MONGODB_|REDIS_|MYSQL_|SQLITE_|scrapy\.db|scrapy_db"
            r"|\.pipelines\.|'scrapy"
        ),
        "noise_pre": [],
        "noise_post": [                              # 保留判断之后（scrapy_db 令牌行已留）
            r"[a-f0-9]{12,}",                        # hex12+ UPC/ObjectId（手工版口径）
            r"\d{20,}",                              # 破碎大数（OCR 断行）
            r"\\x[0-9a-fA-F]{2}",                    # redis 十六进制转义
            r"^127\.\d",                             # redis 会话提示符
            r"^\d+\)\s+\"",                         # KEYS/HGETALL 字段枚举
            r"^\|",                                  # mysql 表格 dump
            r"SQLite version|Enter \\.|MongoDB shell version|Type \"it\"",
            r"row\(s\)? affected|Query OK",          # mysql 客户端回显
        ],
    },
    13: {
        "short_line": 45,
        "short_line_requires": r"[\d.:]",   # 短行还须含数字/点（纯字母碎片与空行丢弃）
        "drop_cjk_frag": True,               # 丢孤立 1-3 字海报 OCR 残字
        "anchored_tokens": (
            r"request\d? =|req =|url = |proxy = |meta = |creds|scheme = |ip = |port = "
            r"|fields|values = |info = |movie_item|infos|collection|client\.|client =|r = |conn"
            r"|BASE_URL|MOVIE_TAG|PAGE_LIMIT|page_start|name = |start_urls"
            r"|proxy_list|dbpool|self\."
        ),
        "bare_tokens": (
            r"USER_AGENT|DOWNLOAD_DELAY|ROBOTSTXT|DOWNLOADER_MIDDLEWARES|HTTPPROXY_"
            r"|auth_encoding|json\.|re\.|random\."
            r"|ITEM_PIPELINES|scrapy_|HttpProxyMiddleware|RandomHttpProxyMiddleware"
            r"|XiciSpider|MoviesSpider|TestRandomProxySpider|Proxy-Authorization"
            r"|request\.meta|response\.meta|check_available|dont_filter|dont_retry|download_timeout"
        ),
        "noise_pre": [                               # 中文噪音/dump 行（先于保留）
            r'"proxy":\s*"http',                     # proxy_list.json dump 行
            r"^\d+\.\d+\.\d+\.\d+",               # 西刺表格行（IP 开头）
            r"验证时间|存活时间|连接时间|服务器地址|高匿",
            r"\{'origin': '(?!116\.29\.35\.201|197\.10\.171\.143)",  # origin 输出（主角代理 IP 白名单外）
            r"'(cover_x|cover_y|rate|title|cover|playable|is_new|id|url)':",  # json dump
            r"[一-鿿]{2,}\s+\d\.\d\s+[一-鿿]",       # 电影输出行（片名 评分 导演）
            r"[一-鿿]\d\.\d",                        # 片名与评分粘连 OCR
            r"\d+推[荐排]",                          # 豆列推荐数
            r"★|剧情简介|本片原声|影人|马哈维亚|吉塔|白先勇|互评分|影讯|预告片",
            r"Dangal|3idiots|SPIRITEDAWAY|INCEPTION|CONCUBINA|SHAWSHANK",
            r"General Headers|ResponseCookies|vGeneral|<span|</span|<div|</div|cbr"
            r"|htmlbody|#wrapper|#content|spanclass|divid|ueds",
            r"电影、人、影院|可在线播放|按热度排序|按时间排序|按评价排序|冷门佳片",
            r"^/",                                   # httpbin 端点表行
            r"(GET|POST)\s+\d",                      # 开发者工具面板行
            r"★|☆|tutorabc|豆列|排荐|下载豆|豆排|好于|人评价|元起|影讯&购票|年度榜单",
            r"Elements|Network Sources|jquery\.js|RemoteAddress|RequestURL|StatusCode",
            r"Content-Encoding|Content-Type|Cache-Control|Connection:|Transfer-Encoding",
            r"view source|Vary:|Accept[-:]|fromcac|Preservelog|Breakpoints|EventListeners",
            r"DOM Break|Styles|Console|doubanio|影志",
            r"\d+月\d+日",                           # 海报日期行（含截行变体"6月23日一被辑发"）
            r"\s\d\.\d\s.*\s\d\.\d\s",             # 一行 ≥2 个评分的输出行
            r"日本 动作|欧美 韩国|华语 欧美",           # 分类导航截图行
            r"page_limit=%s&page_start",             # 模板串 OCR 截行
        ],
        "noise_post": [],
    },
    14: {
        "short_line": 40,
        "anchored_tokens": (
            r"r\.|data =|obj =|key =|params|optional|server|spider|serializer|self\."
        ),
        "bare_tokens": (
            r"ITEM_PIPELINES|REDIS_URL|REDIS_ITEMS|SCHEDULER|DUPEFILTER|ITEM_KEY"
            r"|redis\.|StrictRedis|process_item|_process_item|item_key|deferToThread"
            r"|serialize|load_object|enqueue_request|next_request|request_seen"
            r"|request_fingerprint|request_to_dict|request_from_dict|ScrapyJSONEncoder"
            r"|default_serialize|picklecompat|BaseDupeFilter|RedisSpider|Scheduler"
            r"|FifoQueue|LifoQueue|PriorityQueue|RFPDupeFilter|RedisPipeline"
            r"|_encode_request|_decode_request|block_pop_timeout|idle_before_close"
            r"|6379>|\b(SET|GET|DEL|LPUSH|RPUSH|LPOP|RPOP|LINDEX|LRANGE|LLEN|HSET|HDEL"
            r"|HGET|HGETALL|SADD|SREM|SMEMBERS|SCARD|SISMEMBER|ZADD|ZREM|ZRANGE"
            r"|ZRANGEBYSCORE|PING|PONG|keys|lpush|llen)\b|\(integer\)|\(nil\)"
        ),
        "noise_pre": [                               # dump 类（手工版在最前）
            r"['\"](price|name|review_num|review_rating|ststock|stock)['\"]:",  # item dump
            r"\\u00",                                # json 转义
            r"catalogue/|books\.toscrape",           # URL dump 行
        ],
        "noise_post": [                              # 保留之后（REDIS 演示行由令牌保留）
            r"[a-f0-9]{16}",                         # UPC hex
            r", encoding: utf",                      # 时间戳日志行尾碎片
            r"^\d{4}-\d{2}-\d{2}",                   # scrapy 时间戳日志
            r"^Proto\s+Recv-Q",                      # netstat 表头
            r"^\.+[└├]",                            # tree 缩进行
        ],
    },
}


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(description="PDF/MinerU 源 OCR 噪音前置过滤（流程1 第0步）")
    p.add_argument("--chapter", type=int, required=True, help="章节号（决定使用哪份规则）")
    p.add_argument("--src", required=True, help="源 md 路径（清洗后含 OCR 噪音）")
    p.add_argument("--out", required=True, help="输出路径（过滤后 clean_only.md）")
    args = p.parse_args(argv)
    r = filter_file(args.src, args.out, args.chapter)
    if r["ok"]:
        print(f"✅ 第{args.chapter}章过滤完成: {r['in_lines']} 行 → {r['out_lines']} 行 → {args.out}")
        return 0
    print(f"❌ {r['error']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
