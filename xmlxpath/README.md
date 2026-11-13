# xmlxpath — 科研目录 XML 抽取后端

输入 UTF-8 JSON（仅含 `xml` 字符串与 `queries` 字符串数组），对 XML 按
XPath 1.0 子集求值，原序输出结果数组。表达式解析与求值全部自写
（不使用任何 XPath 引擎）；XML 解析基于标准库 expat。

## 用法

```bash
python3 main.py INPUT_JSON OUTPUT_JSON
```

* `INPUT_JSON`：`{"xml": "<xml 字符串>", "queries": ["<xpath>", ...]}`
* 成功：结果数组以 UTF-8 JSON **原子替换**写入 `OUTPUT_JSON`，退出码 0；
* 失败（JSON 语法错、非法输入、XML 非法、查询越子集、求值类型错误）：
  **整次拒绝**，旧 `OUTPUT_JSON` 原样保留，stderr 打印带字段路径的错误，
  退出码 1：

  ```json
  {"error": {"path": "$.queries[0]", "message": "..."}}
  ```

输出形如 `[[{"path": [1], "value": ""}], [], ...]`——每个查询一项：
结果节点集仅含元素、去重、按文档序；`path` 为元素子节点零基路径
（文档元素为 `[]`），`value` 为后代文本按文档序的连接。空集与空
`queries` 均为 `[]`。

```bash
$ echo '{"xml":"<r><a/><b/><c/></r>","queries":["/r/c/preceding::*[1]"]}' > in.json
$ python3 main.py in.json out.json && cat out.json
[[{"path": [1], "value": ""}]]
```

## 支持范围

**XML**（1.0 第五版子集）：允许 UTF-8 声明、CDATA、字符引用与预定义
实体；保留空白并合并相邻文本；同元素属性按名称 Unicode 码点序（亦
为其文档序）。拒绝：命名空间声明、冒号名称、DOCTYPE、注释、处理指令。

**XPath**（[REC-xpath-19991116](https://www.w3.org/TR/1999/REC-xpath-19991116/)
第 2～5 节）：除变量、前缀名、namespace 轴外全部语法；函数仅
`position last count string number boolean not`；初始上下文为文档
节点，位置及大小均 1。先验全式语法及子集（含静态类型检查：并集、
过滤/路径基、`count()` 实参须为节点集，整式结果须为节点集），再按
标准短路求值（反向轴按反向文档序定位，`and`/`or` 短路，`div`/`mod`
遵循 IEEE 754）。

## 代码结构

| 文件 | 职责 |
| --- | --- |
| `main.py` | 入口：读入、错误报告、成功原子替换输出 |
| `xpx/jsonstrict.py` | 严格 JSON：重复成员、孤立代理项、语法错（报 `$`） |
| `xpx/xmlmodel.py` | 受限 XML 解析（expat）与节点模型、轴、string-value |
| `xpx/lexer.py` | XPath 词法（含 `*`/运算符名消歧） |
| `xpx/parser.py` | XPath 语法（文法第 2～5 节，递归下降） |
| `xpx/checker.py` | 子集与静态类型检查 |
| `xpx/convert.py` | string/number/boolean 转换（第 4 节） |
| `xpx/evaluator.py` | 求值（第 2～5 节语义） |
| `xpx/service.py` | 输入校验、逐查询求值、结果成形 |

## 测试（`tests/`）

```bash
python3 tests/compare_lxml.py           # 合法交集对照 lxml（4980 例）
python3 tests/random_diff.py [seed [n]] # 随机差分对照 lxml
python3 tests/test_attr_order.py        # 属性码点序（独立验收）
python3 tests/test_reject.py            # 各类拒绝与字段路径（163 例）
python3 tests/test_spec_conformance.py  # 规范优先于 libxml2 的点位
python3 tests/test_cli.py               # 成功替换 / 失败保留旧文件
```

已知 libxml2 偏离规范、本实现遵循规范的两处（见
`test_spec_conformance.py`）：`number()` 不接受指数与 `+` 号；
从属性节点出发的 `following` 轴包含属主的子节点（规范第 5 节规定
属性节点排在元素的子节点之前）。
