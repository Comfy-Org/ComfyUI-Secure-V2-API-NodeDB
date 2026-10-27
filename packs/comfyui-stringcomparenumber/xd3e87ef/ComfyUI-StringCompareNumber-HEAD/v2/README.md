# ComfyUI-StringCompareNumber

一个用于 ComfyUI 的自定义节点：**将字符串按指定方式分割后，与指定数字进行比较，返回 0 或 1**。

## 功能说明

- **输入**：字符串（可以是单个数字，也可以是按分隔符分隔的多个数字，例如 `1,2,3`）。
- **分割方式**：支持常见分隔符（`,` `;` 空格 Tab `|` `/` `:` `-` `_` `.`）、**换行**（自动识别 `\n`、`\r\n`、`\r` 三种换行）、**任意空白**（空格/Tab/换行任意组合）、**整体不分割**，以及 **自定义分隔符**（自定义里可以直接写 `\n` `\r` `\t`，会被当作真正的换行/制表符）。
- **比较方式**：`==`、`!=`、`>`、`>=`、`<`、`<=`。
- **返回**：
  - `result` (INT)：所有分段都满足条件返回 `1`，否则返回 `0`。
  - `detail` (STRING)：逐段比较的详细过程，便于调试。
- **特别处理**：
  - 任意一段无法转换为数字（既不是 int 也不是 float）→ 返回 `0`。
  - 任意一段不满足比较条件 → 返回 `0`。
  - 输入为空或分割后没有有效分段 → 返回 `0`。
  - 所有分段均满足条件 → 返回 `1`。

## 安装方法

### 方式一：通过 ComfyUI Manager（推荐）

1. 打开 ComfyUI Manager。
2. 选择「Install via Git URL」，填入本仓库地址即可。

### 方式二：手动 Git Clone

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/1946242666/ComfyUI-StringCompareNumber.git
```

然后重启 ComfyUI 即可。

## 节点位置

加载完成后，可在右键菜单的 `utils/string` 分类下找到：

> **String Compare Number (字符串数字比较)**

## 节点参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `input_string` | STRING | 需要比较的字符串（多行） |
| `delimiter` | 下拉 | 分割方式，支持常见分隔符；选 `none (whole string)` 表示不分割；选 `custom` 表示启用 `custom_delimiter` |
| `custom_delimiter` | STRING | 仅当 `delimiter = custom` 时生效的自定义分隔符 |
| `operator` | 下拉 | 比较方式：`==` `!=` `>` `>=` `<` `<=` |
| `compare_value` | FLOAT | 用于比较的数字（整数/浮点均可） |
| `strip_whitespace` | BOOLEAN | 是否去除每段首尾空白（默认 True） |
| `ignore_empty` | BOOLEAN | 是否忽略空的分段（默认 True） |

## 使用示例

### 示例 1：所有数字都大于 0
- `input_string` = `1,2,3`
- `delimiter` = `comma (,)`
- `operator` = `>`
- `compare_value` = `0`
- **结果**：`1`

### 示例 2：有一个不满足
- `input_string` = `1,2,-3`
- `operator` = `>`
- `compare_value` = `0`
- **结果**：`0`（因为 `-3 > 0` 不成立）

### 示例 3：含非数字
- `input_string` = `1,abc,3`
- `operator` = `>`
- `compare_value` = `0`
- **结果**：`0`（`abc` 无法转换为数字）

### 示例 4：单个字符串整体比较
- `input_string` = `12.5`
- `delimiter` = `none (whole string)`
- `operator` = `<=`
- `compare_value` = `13`
- **结果**：`1`

## 许可证

MIT License
