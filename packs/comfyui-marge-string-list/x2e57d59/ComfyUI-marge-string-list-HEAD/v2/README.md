# ComfyUI-marge-string-list

ComfyUIのカスタムノードで、複数のテキストまたはタグリストをマージするためのツールです。WD14 Taggerなどのタグ生成ノードの出力を統合するのに最適です。

## 機能

- **複数リストのマージ**: ComfyUIのリスト出力（WD14 Taggerなど）を単一の文字列にマージ
- **重複排除**: マージ時に重複するタグを自動的に削除
- **カスタム区切り文字**: タグ間の区切り文字を自由に指定可能（デフォルト: `,`）
- **ソート機能**: 必要に応じてアルファベット順にタグをソート
- **大文字小文字対応**: 大文字小文字を区別した重複判定に対応
- **ホワイトスペース正規化**: タグ内の複数のスペースを自動的に1つに統一

## インストール

ComfyUI の custom_nodes ディレクトリに本リポジトリをクローンしてください：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/palealloy2999-prog/ComfyUI-marge-string-list.git
```

## ノード: Merge String List

### 入力

| 入力 | 型 | 説明 | デフォルト |
|------|-----|------|----------|
| `text` | STRING | マージするテキストまたはタグリスト（複数行対応） | - |
| `separator` | STRING | タグ間の区切り文字 | `, ` |
| `sort_tags` | BOOLEAN | タグをアルファベット順にソートするかどうか | False |
| `case_sensitive` | BOOLEAN | 重複判定の際に大文字小文字を区別するかどうか | False |

### 出力

| 出力 | 型 | 説明 |
|-----|-----|------|
| `text` | STRING | マージされたテキスト |

## 使用例

### 基本的な使い方

WD14 Taggerなどから出力されたタグリストをマージします：

```
入力テキスト:
  "tag_a, tag_b"
  "tag_b, tag_c"

出力結果:
  "tag_a, tag_b, tag_c"
```

### ソート付きのマージ

タグを整理されたアルファベット順にマージします：

```
入力テキスト:
  "zebra, apple"
  "banana"

sort_tags: True
出力結果:
  "apple, banana, zebra"
```

### カスタム区切り文字

タグの区切り文字を変更できます：

```
separator: " | "

出力結果:
  "tag_a | tag_b | tag_c"
```

## 仕様

- **INPUT_IS_LIST**: ComfyUIのリスト出力を直接受け取ります（リスト展開なし）
- **重複処理**: デフォルトでは大文字小文字を区別せずに重複を判定
- **タグ正規化**: カンマで区切られたテキストを自動的にタグに分割し、ホワイトスペースを正規化

## ライセンス

詳細はLICENSEファイルを参照してください。

## 開発者

palealloy2999-prog
